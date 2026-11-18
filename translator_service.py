import os
import io
import re
import math
import asyncio
import threading
import tempfile
from PIL import Image, ImageDraw, ImageStat
from chrome_lens_py import LensAPI
import chrome_lens_py.constants as lens_const
import chrome_lens_py.core.image_processor as lens_img_proc
import chrome_lens_py.core.text_renderer as tr


def _sample_canvas_colors(canvas: Image.Image, x1: int, y1: int, x2: int, y2: int):
    """Samples true border background color and contrasting foreground color from canvas."""
    w, h = canvas.size
    bx1, by1 = max(0, x1 - 3), max(0, y1 - 3)
    bx2, by2 = min(w, x2 + 3), min(h, y2 + 3)

    ring_samples = []
    rgb = canvas.convert("RGB")
    if by1 < y1:
        ring_samples.append(rgb.crop((bx1, by1, bx2, y1)))
    if y2 < by2:
        ring_samples.append(rgb.crop((bx1, y2, bx2, by2)))
    if bx1 < x1:
        ring_samples.append(rgb.crop((bx1, max(0, y1), x1, min(h, y2))))
    if x2 < bx2:
        ring_samples.append(rgb.crop((x2, max(0, y1), bx2, min(h, y2))))

    bg_rgb = None
    max_std = 99.0
    if ring_samples:
        pixels = []
        for crop_im in ring_samples:
            pixels.extend(crop_im.getdata())
        if pixels:
            rs = sorted(p[0] for p in pixels)
            gs = sorted(p[1] for p in pixels)
            bs = sorted(p[2] for p in pixels)
            mid = len(pixels) // 2
            bg_rgb = (rs[mid], gs[mid], bs[mid])
            n = len(pixels)
            mean_r = sum(rs) / n
            mean_g = sum(gs) / n
            mean_b = sum(bs) / n
            var_r = sum((v - mean_r) ** 2 for v in rs) / n
            var_g = sum((v - mean_g) ** 2 for v in gs) / n
            var_b = sum((v - mean_b) ** 2 for v in bs) / n
            max_std = max(var_r, var_g, var_b) ** 0.5

    if bg_rgb is None:
        bg_rgb = (255, 255, 255)
    lum = 0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]
    fg_rgb = (15, 15, 15) if lum > 135 else (245, 245, 245)
    return bg_rgb + (255,), fg_rgb + (255,), max_std


def _apply_clean_renderer_patches():
    """
    Patches Lens upload quality and text renderer:
    1. Prevents downscaling 1080p/1440p/4K screens and raises JPEG quality to 92 so small text is never missed.
    2. Samples true canvas border colors for uniform backgrounds to avoid off-white/gray smudge boxes.
    3. Fixes chrome_lens_py RTL clipping bug when grow=True widens text beyond the original box.
    4. Prevents dropping paragraphs when Lens returns mismatched line counts or missing translations.
    """
    # 1. Higher OCR upload fidelity for crisp small UI text
    try:
        lens_const.DEFAULT_IMAGE_MAX_WIDTH = 3840
        lens_const.DEFAULT_IMAGE_MAX_HEIGHT = 3840
        lens_const.DEFAULT_IMAGE_MAX_AREA = 8500000
        lens_const.DEFAULT_IMAGE_JPEG_QUALITY = 92

        lens_img_proc.DEFAULT_IMAGE_MAX_WIDTH = 3840
        lens_img_proc.DEFAULT_IMAGE_MAX_HEIGHT = 3840
        lens_img_proc.DEFAULT_IMAGE_MAX_AREA = 8500000
        lens_img_proc.DEFAULT_IMAGE_JPEG_QUALITY = 92

        lens_img_proc.encode_image_for_api.__defaults__ = (
            92,
            lens_const.DEFAULT_IMAGE_WEBP_QUALITY,
            lens_const.DEFAULT_ALPHA_MODE,
        )
        lens_img_proc._resize_and_serialize_pil_image.__defaults__ = (92,)
        lens_img_proc.prepare_image.__defaults__ = (
            None,
            True,
            92,
            lens_const.DEFAULT_IMAGE_WEBP_QUALITY,
            lens_const.DEFAULT_ALPHA_MODE,
        )
    except Exception:
        pass

    def clean_draw_background(canvas, tline, box_w, box_h, cx, cy, deg, aspect) -> bool:
        bg_rgba = (255, 255, 255, 255)
        if tline.HasField("style") and tline.style.background_primary_color:
            bg_rgba = tr._argb_to_rgba(tline.style.background_primary_color)
            if bg_rgba[3] == 0:
                bg_rgba = (bg_rgba[0], bg_rgba[1], bg_rgba[2], 255)

        # Sample true border color on horizontal UI lines to avoid off-white/gray patch mismatch
        sampled_bg, _, border_std = _sample_canvas_colors(
            canvas,
            int(round(cx - box_w / 2.0)),
            int(round(cy - box_h / 2.0)),
            int(round(cx + box_w / 2.0)),
            int(round(cy + box_h / 2.0)),
        )
        if abs(deg) < 1.5 and border_std < 12.0:
            bg_rgba = sampled_bg

        is_bright = (bg_rgba[0] > 195 and bg_rgba[1] > 195 and bg_rgba[2] > 195)

        if is_bright and border_std < 14.0:
            fill = Image.new(
                "RGBA",
                (max(1, round(box_w) + 6), max(1, round(box_h) + 4)),
                bg_rgba
            )
            tr._paste_rotated(canvas, fill, cx, cy, deg)
            return False

        if tline.HasField("background_image_data"):
            try:
                bgd = tline.background_image_data
                pad_w = bgd.horizontal_padding * box_h / aspect
                pad_h = bgd.vertical_padding * box_h
                patch_w = max(1, round(box_w + pad_w))
                patch_h = max(1, round(box_h + pad_h))
                patch = Image.open(io.BytesIO(bgd.background_image)).convert("RGBA")

                stat = ImageStat.Stat(patch.convert("RGB"))
                max_stddev = max(stat.stddev)
                if max_stddev < 14.0:
                    fill = Image.new(
                        "RGBA",
                        (max(1, round(box_w) + 6), max(1, round(box_h) + 4)),
                        bg_rgba
                    )
                    tr._paste_rotated(canvas, fill, cx, cy, deg)
                    return False

                patch = patch.resize((patch_w, patch_h), Image.Resampling.BILINEAR)
                tr._paste_rotated(canvas, patch, cx, cy, deg)
                return True
            except Exception:
                pass

        fill = Image.new("RGBA", (max(1, round(box_w) + 6), max(1, round(box_h) + 4)), bg_rgba)
        tr._paste_rotated(canvas, fill, cx, cy, deg)
        return False

    def layout_preserving_alignment(scene, data, is_rtl: bool) -> str:
        """
        Preserves the original page's visual alignment (left/center/right) instead of
        blindly flipping left-aligned English/LTR paragraphs to right-aligned when translating
        to Arabic — preventing giant gaps next to bullets and misaligned headings.
        """
        if scene.text_align != "auto":
            return scene.text_align
        align = tr._ALIGNMENT.get(data.alignment, "left")
        src_lang = (getattr(data, "source_language", "") or "").split("-")[0].lower()
        if src_lang in tr.RTL_LANGUAGES and align == "left":
            align = "right"
        return align

    def safe_render_text_block(
        lines,
        font,
        box_w: float,
        box_h: float,
        fill,
        outline: int,
        outline_color,
        align: str,
        grow: bool = False,
    ) -> Image.Image:
        """Fixes chrome_lens_py RTL negative-x clipping and keeps left/right edge anchored when grow=True."""
        ascent, descent = font.getmetrics()
        em = ascent + descent
        tile_w, tile_h = max(1, round(box_w)), max(1, round(box_h))
        ox = oy = 0.0
        edge = 2 * outline + 2
        if grow:
            widest = max((font.getlength(line) for line in lines), default=0.0)
            need_w, need_h = math.ceil(widest) + edge, len(lines) * em + edge
            if need_w > tile_w:
                if align in ("left", "right"):
                    # Grow symmetrically around cx so ox keeps left anchored at x1 and right anchored at x2
                    tile_w = max(need_w, math.ceil(2.0 * (widest + edge) - box_w))
                    ox = (tile_w - box_w) / 2.0
                else:
                    tile_w = need_w
                    ox = (tile_w - box_w) / 2.0
            if need_h > tile_h:
                tile_h = need_h
                oy = (tile_h - box_h) / 2.0

        tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)

        y = oy + (box_h - len(lines) * em) / 2
        for line in lines:
            advance = font.getlength(line)
            if grow and tile_w > round(box_w):
                if align == "center":
                    raw_x = (float(tile_w) - advance) / 2.0
                else:
                    raw_x = ox + tr._align_x(align, box_w, advance)
                draw_x = max(float(edge // 2), min(float(tile_w) - advance - edge // 2, raw_x))
            else:
                draw_x = ox + tr._align_x(align, box_w, advance)
            font.draw(
                draw,
                (draw_x, y),
                line,
                fill,
                stroke_width=outline if outline_color else 0,
                stroke_fill=outline_color,
            )
            y += em
        return tile

    def safe_paste_rotated(canvas: Image.Image, tile: Image.Image, cx: float, cy: float, deg: float):
        if deg:
            tile = tile.rotate(deg, expand=True, resample=Image.Resampling.BICUBIC)
        px = round(cx - tile.width / 2)
        py = round(cy - tile.height / 2)
        # Clamp only the non-transparent content bounding box so symmetric grow=True padding
        # near screen edges never shifts left/right-anchored text away from x1/x2.
        bbox = tile.getbbox()
        if bbox is not None:
            c_left, c_top, c_right, c_bot = bbox
            if c_right - c_left <= canvas.width - 4:
                if px + c_right > canvas.width - 2:
                    px = (canvas.width - 2) - c_right
                if px + c_left < 2:
                    px = 2 - c_left
            if c_bot - c_top <= canvas.height - 4:
                if py + c_bot > canvas.height - 2:
                    py = (canvas.height - 2) - c_bot
                if py + c_top < 2:
                    py = 2 - c_top
        tr.composite(canvas, tile, px, py)

    orig_render_paragraph = tr._render_paragraph

    def _should_skip_source_paragraph(paragraph, data) -> bool:
        src_text = " ".join(
            "".join(w.plain_text + w.text_separator for w in ln.words).strip()
            for ln in paragraph.lines
        ).strip()
        if not src_text:
            return False
        tgt_base = (getattr(data, "target_language", "") or "").split("-")[0].lower()
        src_base = (getattr(data, "source_language", "") or "").split("-")[0].lower()
        # Leave UI text that is already in Arabic untouched (prevents bogus fa/ps re-translation like بحث -> مناقشة)
        if tgt_base == "ar" and any('\u0600' <= c <= '\u06FF' for c in src_text) and not re.search(r'[A-Za-z]{2,}', src_text):
            return True
        # Leave tab filenames untouched
        if len(paragraph.lines) == 1 and re.search(r'\.(pdf|png|jpg|jpeg|py|dart|exe|zip|txt|json|html|css|js)\b', src_text, re.IGNORECASE):
            return True
        # Leave tiny toolbar icon artifacts (e.g. 'DA < >' -> 'نعم<>', 'مه' -> 'لا') untouched
        alpha_only = re.sub(r'[^A-Za-z\u0600-\u06FF]+', '', src_text)
        major_langs = {"en", "ar", "fr", "es", "de", "tr", "ru", "zh", "ja", "it", "pt"}
        if len(alpha_only) <= 2 and (
            any(ch in src_text for ch in ("<", ">", "^", "|", "×"))
            or (src_base and src_base not in major_langs and src_base != tgt_base)
        ):
            return True
        return False

    def resilient_render_paragraph(scene, index: int, paragraph, data) -> int:
        if _should_skip_source_paragraph(paragraph, data):
            return 0

        # Standard path when detected and translated line counts match
        if len(data.line) == len(paragraph.lines):
            vertical = data.writing_direction == tr._WRITING_DIRECTION_TOP_TO_BOTTOM
            use_hull = scene.draw_background and scene.erase_mode == "hull"
            if vertical or use_hull or len(data.line) <= 1 or not scene.draw_background:
                return orig_render_paragraph(scene, index, paragraph, data)

            # Two-pass erase-then-draw for multi-line horizontal paragraphs so line[i+1]'s
            # background box never paints over line[i]'s descending Arabic glyphs/dots.
            is_rtl = (
                data.writing_direction == tr._WRITING_DIRECTION_RTL
                or data.target_language.split("-")[0].lower() in tr.RTL_LANGUAGES
            )
            align = tr._paragraph_alignment(scene, data, is_rtl)

            # Collect translated lines first
            line_texts = []
            for li in range(len(data.line)):
                tline = data.line[li]
                next_line = data.line[li + 1] if li + 1 < len(data.line) else None
                lt = tr.build_line_text(data.translation, tline, next_line)
                line_texts.append(lt)

            inpainted = []
            for li in range(len(data.line)):
                tline = data.line[li]
                box = paragraph.lines[li].geometry.bounding_box
                box_w, box_h = box.width * scene.width, box.height * scene.height
                if box_w < 1 or box_h < 1:
                    inpainted.append(False)
                    continue
                deg = -math.degrees(box.rotation_z)
                cx, cy = box.center_x * scene.width, box.center_y * scene.height
                inpainted.append(
                    tr._draw_background(scene.canvas, tline, box_w, box_h, cx, cy, deg, scene.aspect)
                )

            non_empty_indices = [li for li, lt in enumerate(line_texts) if lt.strip()]
            use_para_block_rtl = (
                is_rtl
                and align == "left"
                and len(non_empty_indices) > 1
                and paragraph.HasField("geometry")
            )

            # Precompute uniform font size and block_right_x anchored at paragraph's left margin
            # so multi-line RTL bullets touch x1 (next to bullets) while trailing lines right-align under Line 1.
            block_right_x = None
            uniform_sizes = {}
            if use_para_block_rtl:
                pbox = paragraph.geometry.bounding_box
                p_right_x = (pbox.center_x + pbox.width / 2.0) * scene.width
                line_infos = []
                for li in non_empty_indices:
                    box = paragraph.lines[li].geometry.bounding_box
                    bw, bh = box.width * scene.width, box.height * scene.height
                    deg = -math.degrees(box.rotation_z)
                    if bw < 1 or bh < 1 or abs(deg) >= 1.5:
                        continue
                    lx1 = box.center_x * scene.width - bw / 2.0
                    full_w = max(bw, p_right_x - lx1)
                    shaped = tr.shape_for_display(line_texts[li], is_rtl)
                    plan = tr.FontPlan.resolve(shaped, scene.font_path)
                    _, fsz = tr.fit_font_size(shaped, plan, full_w, bh)
                    fsz = max(scene.floor, fsz)
                    line_infos.append((li, lx1, full_w, bh, shaped, plan, fsz))
                if line_infos:
                    common_fsz = max(scene.floor, min(info[6] for info in line_infos))
                    p_left_x = min(info[1] for info in line_infos)
                    widest_w = 0.0
                    for li, lx1, full_w, bh, shaped, plan, _ in line_infos:
                        sized = plan.at(common_fsz)
                        widest_w = max(widest_w, sized.getlength(shaped))
                        uniform_sizes[li] = (sized, common_fsz, shaped)
                    block_right_x = min(p_right_x, p_left_x + widest_w)

            drawn = 0
            for li in range(len(data.line)):
                tline = data.line[li]
                box = paragraph.lines[li].geometry.bounding_box
                box_w, box_h = box.width * scene.width, box.height * scene.height
                if box_w < 1 or box_h < 1:
                    continue
                text = line_texts[li]
                if not text.strip():
                    continue
                text = tr.shape_for_display(text, is_rtl)
                text_color = tr._argb_to_rgba(tline.style.text_color)
                outline_color = tr._argb_to_rgba(tline.style.background_primary_color) if inpainted[li] else None

                line_align = align
                cx = box.center_x * scene.width
                cy = box.center_y * scene.height
                deg = -math.degrees(box.rotation_z)

                if use_para_block_rtl and abs(deg) < 1.5 and block_right_x is not None and li in uniform_sizes:
                    sized, fsz, shaped_u = uniform_sizes[li]
                    line_left_x = cx - box_w / 2.0
                    avail_w = max(1.0, block_right_x - line_left_x)
                    cx = line_left_x + avail_w / 2.0
                    outline_w = tr.outline_px(fsz, scene.outline_scale) if outline_color else 0
                    tile = tr._render_line_tile(
                        shaped_u, sized, avail_w, box_h, text_color, outline_w, outline_color, "right", grow=(sized.getlength(shaped_u) > avail_w)
                    )
                else:
                    plan = tr.FontPlan.resolve(text, scene.font_path)
                    tile = tr._render_horizontal(scene, text, plan, box_w, box_h, text_color, outline_color, line_align)

                tr._paste_rotated(scene.canvas, tile, cx, cy, deg)
                drawn += 1
            return drawn

        if not data.translation or not data.translation.strip():
            return 0

        is_rtl = (
            data.writing_direction == tr._WRITING_DIRECTION_RTL
            or data.target_language.split("-")[0].lower() in tr.RTL_LANGUAGES
        )
        align = tr._paragraph_alignment(scene, data, is_rtl)

        # Erase each detected source line safely using true canvas color when style missing
        if scene.draw_background:
            if data.line:
                tr._erase_text_area(scene.canvas, paragraph, data, max(0.35, scene.hull_padding))
            else:
                for sline in paragraph.lines:
                    if not sline.HasField("geometry"):
                        continue
                    box = sline.geometry.bounding_box
                    bw, bh = box.width * scene.width, box.height * scene.height
                    if bw < 1 or bh < 1:
                        continue
                    sx1 = int(round(box.center_x * scene.width - bw / 2.0))
                    sy1 = int(round(box.center_y * scene.height - bh / 2.0))
                    sx2 = int(round(box.center_x * scene.width + bw / 2.0))
                    sy2 = int(round(box.center_y * scene.height + bh / 2.0))
                    bg_c, _, _ = _sample_canvas_colors(scene.canvas, sx1, sy1, sx2, sy2)
                    fill = Image.new("RGBA", (max(1, round(bw) + 4), max(1, round(bh) + 4)), bg_c)
                    tr._paste_rotated(
                        scene.canvas,
                        fill,
                        box.center_x * scene.width,
                        box.center_y * scene.height,
                        -math.degrees(box.rotation_z),
                    )

        if paragraph.HasField("geometry"):
            return tr._render_reflow_paragraph(scene, paragraph, data, align, is_rtl, use_hull=True)
        return 0

    orig_render_overlay = tr.render_translation_overlay

    def complete_render_overlay(image, objects_response, font_path=None, **kwargs):
        canvas = orig_render_overlay(image, objects_response, font_path=font_path, **kwargs)
        try:
            paragraphs = objects_response.text.text_layout.paragraphs
            gleams = objects_response.deep_gleams
            # Detect any paragraph skipped by Lens (missing gleam or failed translation)
            target_lang = None
            for g in gleams:
                if g.HasField("translation") and g.translation.target_language:
                    target_lang = g.translation.target_language
                    break
            if not target_lang:
                return canvas

            missed = []
            for idx, p in enumerate(paragraphs):
                has_trans = (
                    idx < len(gleams)
                    and gleams[idx].HasField("translation")
                    and gleams[idx].translation.status.code == tr._TRANSLATION_STATUS_SUCCESS
                    and bool(gleams[idx].translation.translation.strip())
                )
                if not has_trans and p.HasField("geometry"):
                    p_text = " ".join(
                        "".join(w.plain_text + w.text_separator for w in ln.words).strip()
                        for ln in p.lines
                    ).strip()
                    if (
                        p_text
                        and re.search(r'[A-Za-z]{2,}', p_text)
                        and not re.search(r'\.(pdf|png|jpg|jpeg|py|dart|exe|zip|txt|json|html|css|js)\b', p_text, re.IGNORECASE)
                    ):
                        missed.append((p, p_text))

            if missed:
                from offline_manager import OfflineManager, _has_rtl
                src_lang = objects_response.text.content_language or "en"
                if src_lang.split("-")[0].lower() in tr.RTL_LANGUAGES:
                    src_lang = "en"
                if OfflineManager.is_pair_available(src_lang, target_lang):
                    draw = ImageDraw.Draw(canvas)
                    w, h = canvas.size
                    is_rtl_tgt = target_lang.split("-")[0].lower() in tr.RTL_LANGUAGES
                    src_is_rtl = _has_rtl(" ".join(t for _, t in missed))
                    for p, p_text in missed:
                        trans = OfflineManager.translate_text(p_text, from_code=src_lang, to_code=target_lang)
                        if not trans or trans.strip().lower() == p_text.strip().lower():
                            continue
                        pbox = p.geometry.bounding_box
                        x1 = max(0, int(round((pbox.center_x - pbox.width / 2.0) * w)))
                        y1 = max(0, int(round((pbox.center_y - pbox.height / 2.0) * h)))
                        x2 = min(w, int(round((pbox.center_x + pbox.width / 2.0) * w)))
                        y2 = min(h, int(round((pbox.center_y + pbox.height / 2.0) * h)))
                        bw, bh = max(8, x2 - x1), max(8, y2 - y1)
                        bg_c, fg_c, _ = _sample_canvas_colors(canvas, x1, y1, x2, y2)
                        draw.rectangle([max(0, x1 - 2), max(0, y1 - 2), min(w, x2 + 2), min(h, y2 + 2)], fill=bg_c)
                        is_rtl = is_rtl_tgt or _has_rtl(trans)
                        fnt, fsz, shaped = OfflineManager._fit_single_line_font(
                            font_path or "", trans, is_rtl, bw, bh
                        )
                        tw = fnt.getlength(shaped)
                        anchor_x = (float(x2) - tw) if src_is_rtl else float(x1)
                        dx = max(2.0, min(float(w) - tw - 2.0, anchor_x))
                        dy = y1 + max(0.0, (bh - fsz) / 2.0)
                        draw.text((dx, dy), shaped, fill=fg_c, font=fnt)
        except Exception:
            pass
        return canvas

    try:
        import chrome_lens_py.api as lens_api
        tr._paragraph_alignment = layout_preserving_alignment
        tr._draw_background = clean_draw_background
        tr._render_text_block = safe_render_text_block
        tr._paste_rotated = safe_paste_rotated
        tr._render_paragraph = resilient_render_paragraph
        tr.render_translation_overlay = complete_render_overlay
        lens_api.render_translation_overlay = complete_render_overlay
    except Exception:
        pass


_apply_clean_renderer_patches()


class LensAsyncWorker:
    """
    Dedicated persistent background event loop thread that holds a warm LensAPI instance
    and HTTP connection pool. This enables blazing fast (sub-second) Google Lens responses
    without connection teardown lag.
    """
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="LensWorkerThread")
        self.thread.start()
        self._lens = None
        self._lock = threading.Lock()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def get_lens(self) -> LensAPI:
        with self._lock:
            if self._lens is None:
                windir = os.environ.get("WINDIR", "C:\\Windows")
                tahoma = os.path.join(windir, "Fonts", "tahoma.ttf")
                font_p = tahoma if os.path.exists(tahoma) else None
                self._lens = LensAPI(font_path=font_p)
            return self._lens

    def reset_lens(self):
        with self._lock:
            if self._lens is not None:
                try:
                    asyncio.run_coroutine_threadsafe(self._lens.aclose(), self.loop).result(timeout=2.0)
                except Exception:
                    pass
                self._lens = None

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def shutdown(self):
        self.reset_lens()
        self.loop.call_soon_threadsafe(self.loop.stop)


class TranslatorService:
    def __init__(self, target_lang="ar", mode="auto"):
        self.target_lang = target_lang
        self.mode = mode  # "auto", "offline", "online"
        self.temp_dir = os.path.join(tempfile.gettempdir(), "smart_screen_translator")
        os.makedirs(self.temp_dir, exist_ok=True)
        self._worker = LensAsyncWorker()

    def translate_offline_fallback(
        self,
        image: Image.Image,
        full_image: Image.Image = None,
        crop_box: tuple = None,
        target_lang: str = "ar",
        source_lang: str = "auto"
    ) -> dict:
        """
        Translates screen image completely offline using RapidOCR + Argos Translate.
        STRICT LAZY LOADING: offline_manager is loaded ONLY when offline translation is invoked!
        """
        from offline_manager import OfflineManager

        res = OfflineManager.render_offline_screen_translation(
            image,
            to_code=target_lang,
            from_code=source_lang
        )
        if not res.get("success", False):
            return res

        overlay_path = res.get("overlay_path")
        # If this was a cropped region, paste it back onto the full screen image
        if full_image is not None and crop_box is not None and overlay_path and os.path.exists(overlay_path):
            try:
                region_overlay = Image.open(overlay_path)
                composite = full_image.copy()
                composite.paste(region_overlay, (crop_box[0], crop_box[1]))
                composite.save(overlay_path, format="PNG")
            except Exception as paste_err:
                print("Error compositing offline region onto full image:", paste_err)

        res["is_offline"] = True
        return res

    def translate_image(
        self,
        image: Image.Image,
        full_image: Image.Image = None,
        crop_box: tuple = None,
        target_lang: str = None,
        source_lang: str = None
    ) -> dict:
        """
        Main translation entry point.
        Uses shared warm Google Lens session for 1-2s response, retries fresh session on transient errors,
        or falls back to offline engine.
        """
        if target_lang is None:
            target_lang = self.target_lang

        # If offline mode is explicitly requested, bypass online Google Lens completely
        if self.mode == "offline":
            return self.translate_offline_fallback(
                image, full_image, crop_box, target_lang, source_lang or "auto"
            )

        input_path = os.path.join(self.temp_dir, "capture_input.png")
        overlay_path = os.path.join(self.temp_dir, "capture_overlay.png")

        # Save input image
        image.save(input_path, format="PNG")

        src_arg = None if (not source_lang or source_lang == "auto") else source_lang

        async def _execute_lens(use_new_session=False):
            lens = self._worker.get_lens()
            return await lens.process_image(
                image_path=input_path,
                target_translation_language=target_lang,
                source_translation_language=src_arg,
                output_overlay_path=overlay_path,
                output_format="detailed",
                outline_scale=0.0,    # Eliminates black/gray outline shadows under text!
                text_align="auto",    # Respects RTL alignment for Arabic and LTR for English!
                min_readable_px=8.0,  # Preserves small labels cleanly without edge clipping
                erase_mode="patch",   # Uses our clean per-line background renderer
                new_session=use_new_session
            )

        last_err = None
        res = None
        for attempt in range(2):
            try:
                res = self._worker.run(_execute_lens(use_new_session=(attempt > 0)))
                break
            except Exception as e:
                last_err = e
                if attempt == 0:
                    self._worker.reset_lens()

        if res is not None:
            ocr_raw = res.get("ocr_text", "")
            if not ocr_raw and res.get("detailed_blocks"):
                ocr_raw = [b.get("text", "") for b in res["detailed_blocks"] if b.get("text")]
            if isinstance(ocr_raw, list):
                ocr_text = "\n".join(str(x) for x in ocr_raw).strip()
            else:
                ocr_text = str(ocr_raw).strip()

            trans_raw = res.get("translated_text", "")
            if isinstance(trans_raw, list):
                translated_text = "\n".join(str(x) for x in trans_raw).strip()
            else:
                translated_text = str(trans_raw).strip()

            detected_lang = res.get("detected_language") or "auto"

            # If this was a cropped region, paste it back onto the full screen image
            if full_image is not None and crop_box is not None and os.path.exists(overlay_path):
                try:
                    region_overlay = Image.open(overlay_path)
                    composite = full_image.copy()
                    composite.paste(region_overlay, (crop_box[0], crop_box[1]))
                    composite.save(overlay_path, format="PNG")
                except Exception as paste_err:
                    print("Error compositing region onto full image:", paste_err)

            has_overlay = os.path.exists(overlay_path)

            return {
                "success": True,
                "ocr_text": ocr_text,
                "translated_text": translated_text if translated_text else ocr_text,
                "detected_language": detected_lang,
                "target_language": target_lang,
                "overlay_path": overlay_path if has_overlay else None,
                "input_path": input_path,
                "is_offline": False,
                "raw": res
            }

        # If Google Lens fails and mode is auto, automatically fall back to offline translation!
        if self.mode in ("auto", "offline"):
            print(f"Google Lens online translation unavailable ({last_err}). Falling back to Offline Engine...")
            fallback_res = self.translate_offline_fallback(
                image, full_image, crop_box, target_lang, source_lang or "auto"
            )
            if fallback_res.get("success", False):
                return fallback_res

        return {
            "success": False,
            "error": str(last_err) if last_err else "تعذرت الترجمة عبر الإنترنت.",
            "ocr_text": "",
            "translated_text": "",
            "overlay_path": None,
            "input_path": input_path,
            "is_offline": False
        }

    async def translate_image_async(
        self,
        image: Image.Image,
        full_image: Image.Image = None,
        crop_box: tuple = None,
        target_lang: str = None,
        source_lang: str = None
    ) -> dict:
        """Async compatibility wrapper."""
        return await asyncio.to_thread(
            self.translate_image, image, full_image, crop_box, target_lang, source_lang
        )

    def close(self):
        """Clean shutdown of async worker."""
        if hasattr(self, "_worker"):
            self._worker.shutdown()
