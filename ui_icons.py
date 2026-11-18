"""
High-resolution vector-like anti-aliased icon generator for Smart Screen Translator PC.
Uses Pillow supersampling (4x) and Lanczos downscaling to produce crystal-clear icons
at any display scale and resolution.
"""

import math
from PIL import Image, ImageDraw, ImageTk

# In-memory cache for ImageTk.PhotoImage instances to prevent GC and redundant rendering
_ICON_CACHE = {}

def create_icon_image(name, size=20, color="#89b4fa"):
    """
    Renders a supersampled icon and returns a PIL Image in RGBA mode.
    """
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, int(s * 0.08))
    cx, cy = s / 2.0, s / 2.0

    if name == "moon":
        # Crescent moon (smooth curve)
        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        md.pieslice([s * 0.12, s * 0.12, s * 0.88, s * 0.88], 0, 360, fill=255)
        md.pieslice([s * 0.32, s * 0.04, s * 0.98, s * 0.78], 0, 360, fill=0)
        res = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        color_img = Image.new("RGBA", (s, s), color)
        res.paste(color_img, (0, 0), mask)
        return res.resize((size, size), Image.Resampling.LANCZOS)

    elif name == "sun":
        # Center circle
        cr = s * 0.22
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=color)
        # 8 rays with rounded ends
        ray_in = s * 0.32
        ray_out = s * 0.44
        ray_w = max(2, int(lw * 0.9))
        for i in range(8):
            ang = i * (math.pi / 4.0)
            x1 = cx + ray_in * math.cos(ang)
            y1 = cy + ray_in * math.sin(ang)
            x2 = cx + ray_out * math.cos(ang)
            y2 = cy + ray_out * math.sin(ang)
            d.line([x1, y1, x2, y2], fill=color, width=ray_w)
            cap_r = ray_w / 2.0
            d.ellipse([x2 - cap_r, y2 - cap_r, x2 + cap_r, y2 + cap_r], fill=color)

    elif name == "chevron_down":
        # Clean rounded chevron ⌄ as requested in user's Image 2
        ch_w = s * 0.48
        ch_h = s * 0.24
        y_top = cy - ch_h / 2.0
        y_bot = cy + ch_h / 2.0
        x_left = cx - ch_w / 2.0
        x_right = cx + ch_w / 2.0
        line_w = max(3, int(lw * 1.15))

        d.line([(x_left, y_top), (cx, y_bot)], fill=color, width=line_w)
        d.line([(cx, y_bot), (x_right, y_top)], fill=color, width=line_w)
        cr = line_w / 2.0
        d.ellipse([x_left - cr, y_top - cr, x_left + cr, y_top + cr], fill=color)
        d.ellipse([cx - cr, y_bot - cr, cx + cr, y_bot + cr], fill=color)
        d.ellipse([x_right - cr, y_top - cr, x_right + cr, y_top + cr], fill=color)

    elif name == "mic":
        # Modern podcast/studio mic capsule
        cap_w = s * 0.26
        cap_h = s * 0.44
        cap_cy = s * 0.34
        d.rounded_rectangle(
            [cx - cap_w / 2.0, cap_cy - cap_h / 2.0, cx + cap_w / 2.0, cap_cy + cap_h / 2.0],
            radius=int(cap_w / 2.0),
            fill=color
        )
        # U-bracket cradle
        u_w = s * 0.44
        u_top = s * 0.28
        u_bot = s * 0.64
        d.arc([cx - u_w / 2.0, u_top - u_w * 0.28, cx + u_w / 2.0, u_bot], start=0, end=180, fill=color, width=lw)
        # Vertical stem
        d.line([cx, u_bot, cx, s * 0.82], fill=color, width=lw)
        # Horizontal base
        base_w = s * 0.42
        d.line([cx - base_w / 2.0, s * 0.82, cx + base_w / 2.0, s * 0.82], fill=color, width=lw)
        br = lw / 2.0
        d.ellipse([cx - base_w / 2.0 - br, s * 0.82 - br, cx - base_w / 2.0 + br, s * 0.82 + br], fill=color)
        d.ellipse([cx + base_w / 2.0 - br, s * 0.82 - br, cx + base_w / 2.0 + br, s * 0.82 + br], fill=color)

    elif name == "reset":
        # Circular counter-clockwise reset arrow
        r = s * 0.32
        d.arc([cx - r, cy - r, cx + r, cy + r], start=40, end=330, fill=color, width=lw)
        ax = cx + r * math.cos(math.radians(40))
        ay = cy - r * math.sin(math.radians(40))
        ah = s * 0.13
        d.polygon([(ax, ay), (ax - ah * 0.2, ay - ah * 1.1), (ax + ah * 1.0, ay - ah * 0.4)], fill=color)

    elif name == "gear":
        # Modern settings gear / cogwheel
        teeth = 8
        r_out = s * 0.42
        r_mid = s * 0.34
        r_in = s * 0.16
        for i in range(teeth * 2):
            ang = i * (math.pi / teeth)
            r = r_out if i % 2 == 0 else r_mid
            x = cx + r * math.cos(ang)
            y = cy + r * math.sin(ang)
            d.line([cx, cy, x, y], fill=color, width=int(lw * 1.4))
        d.ellipse([cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid], fill=color)
        mask = Image.new("L", (s, s), 255)
        md = ImageDraw.Draw(mask)
        md.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=0)
        img.putalpha(mask)

    elif name == "guide":
        # Clean book / manual icon
        bw = s * 0.35
        bh = s * 0.50
        y1 = cy - bh / 2.0
        y2 = cy + bh / 2.0
        d.rounded_rectangle([cx - bw - s*0.02, y1, cx - s*0.02, y2], radius=int(s*0.04), fill=color)
        d.rounded_rectangle([cx + s*0.02, y1, cx + bw + s*0.02, y2], radius=int(s*0.04), fill=color)
        d.line([cx, y1, cx, y2], fill=color, width=int(lw*0.6))

    elif name == "offline":
        # Cloud with diagonal slash (Offline mode)
        d.ellipse([s * 0.18, s * 0.36, s * 0.48, s * 0.66], fill=color)
        d.ellipse([s * 0.38, s * 0.24, s * 0.74, s * 0.60], fill=color)
        d.ellipse([s * 0.54, s * 0.36, s * 0.84, s * 0.66], fill=color)
        d.rectangle([s * 0.28, s * 0.46, s * 0.74, s * 0.66], fill=color)
        slash_w = max(2, int(lw * 1.1))
        d.line([s * 0.16, s * 0.82, s * 0.84, s * 0.18], fill="#f38ba8", width=slash_w)

    elif name == "updates":
        # Circular refresh / update arrows
        r = s * 0.32
        d.arc([cx - r, cy - r, cx + r, cy + r], start=35, end=155, fill=color, width=lw)
        d.arc([cx - r, cy - r, cx + r, cy + r], start=215, end=335, fill=color, width=lw)
        x1 = cx + r * math.cos(math.radians(155))
        y1 = cy + r * math.sin(math.radians(155))
        d.polygon([(x1, y1), (x1 - s * 0.05, y1 - s * 0.11), (x1 + s * 0.10, y1 - s * 0.05)], fill=color)
        x2 = cx + r * math.cos(math.radians(335))
        y2 = cy + r * math.sin(math.radians(335))
        d.polygon([(x2, y2), (x2 + s * 0.05, y2 + s * 0.11), (x2 - s * 0.10, y2 + s * 0.05)], fill=color)

    elif name == "about":
        # Modern circled 'i' info icon
        r = s * 0.38
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
        dot_r = lw * 0.7
        d.ellipse([cx - dot_r, cy - r * 0.52 - dot_r, cx + dot_r, cy - r * 0.52 + dot_r], fill=color)
        d.line([cx, cy - r * 0.16, cx, cy + r * 0.48], fill=color, width=int(lw * 1.2))

    elif name == "check":
        # Crisp checkmark
        line_w = max(3, int(lw * 1.2))
        d.line([(s * 0.22, s * 0.52), (s * 0.44, s * 0.74)], fill=color, width=line_w)
        d.line([(s * 0.44, s * 0.74), (s * 0.80, s * 0.28)], fill=color, width=line_w)
        cr = line_w / 2.0
        d.ellipse([s * 0.22 - cr, s * 0.52 - cr, s * 0.22 + cr, s * 0.52 + cr], fill=color)
        d.ellipse([s * 0.44 - cr, s * 0.74 - cr, s * 0.44 + cr, s * 0.74 + cr], fill=color)
        d.ellipse([s * 0.80 - cr, s * 0.28 - cr, s * 0.80 + cr, s * 0.28 + cr], fill=color)

    elif name == "flask":
        # Chemistry test flask (for testing translation)
        fx_top = cx
        fy_neck = s * 0.28
        neck_w = s * 0.12
        d.line([cx - neck_w, s * 0.20, cx + neck_w, s * 0.20], fill=color, width=lw)
        d.line([cx - neck_w / 2.0, s * 0.20, cx - neck_w / 2.0, fy_neck], fill=color, width=lw)
        d.line([cx + neck_w / 2.0, s * 0.20, cx + neck_w / 2.0, fy_neck], fill=color, width=lw)
        # Flask body
        poly = [
            (cx - neck_w / 2.0, fy_neck),
            (s * 0.22, s * 0.76),
            (s * 0.26, s * 0.82),
            (s * 0.74, s * 0.82),
            (s * 0.78, s * 0.76),
            (cx + neck_w / 2.0, fy_neck)
        ]
        d.line(poly, fill=color, width=lw)
        # Liquid level inside
        d.line([s * 0.30, s * 0.64, s * 0.70, s * 0.64], fill=color, width=int(lw * 0.8))

    elif name == "download":
        # Download arrow into tray
        arrow_w = max(2, int(lw * 1.1))
        d.line([cx, s * 0.18, cx, s * 0.60], fill=color, width=arrow_w)
        d.line([cx - s * 0.16, s * 0.44, cx, s * 0.60], fill=color, width=arrow_w)
        d.line([cx + s * 0.16, s * 0.44, cx, s * 0.60], fill=color, width=arrow_w)
        # Tray base
        d.line([s * 0.22, s * 0.76, s * 0.78, s * 0.76], fill=color, width=arrow_w)
        d.line([s * 0.22, s * 0.64, s * 0.22, s * 0.76], fill=color, width=arrow_w)
        d.line([s * 0.78, s * 0.64, s * 0.78, s * 0.76], fill=color, width=arrow_w)

    elif name == "whatsapp":
        # WhatsApp style speech bubble + phone
        d.ellipse([cx - s * 0.36, cy - s * 0.36, cx + s * 0.36, cy + s * 0.36], fill=color)
        d.polygon([(cx - s * 0.28, cy + s * 0.16), (cx - s * 0.38, cy + s * 0.38), (cx - s * 0.12, cy + s * 0.30)], fill=color)
        # Inner white cut handset
        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([cx - s * 0.18, cy - s * 0.18, cx + s * 0.18, cy + s * 0.18], fill=255)
        # Cutout center hole
        md.ellipse([cx - s * 0.09, cy - s * 0.09, cx + s * 0.09, cy + s * 0.09], fill=0)
        img.paste(Image.new("RGBA", (s, s), "#ffffff"), (0, 0), mask)

    elif name == "cross":
        # Crisp 'X' close icon
        clw = max(2, int(lw * 1.1))
        d.line([s * 0.26, s * 0.26, s * 0.74, s * 0.74], fill=color, width=clw)
        d.line([s * 0.74, s * 0.26, s * 0.26, s * 0.74], fill=color, width=clw)

    elif name == "copy":
        # Clean double page copy icon with transparent layering
        pw = s * 0.38
        ph = s * 0.46
        d.rounded_rectangle([cx - pw/2.0 + s*0.06, cy - ph/2.0 - s*0.06, cx + pw/2.0 + s*0.06, cy + ph/2.0 - s*0.06], radius=int(s*0.04), outline=color, width=lw)
        d.rounded_rectangle([cx - pw/2.0 - s*0.06, cy - ph/2.0 + s*0.06, cx + pw/2.0 - s*0.06, cy + ph/2.0 + s*0.06], radius=int(s*0.04), outline=color, width=lw)

    elif name == "play":
        # Crisp play triangle (used for test translation)
        pr = s * 0.28
        p_points = [
            (cx - pr * 0.7, cy - pr),
            (cx + pr, cy),
            (cx - pr * 0.7, cy + pr)
        ]
        d.polygon(p_points, fill=color)

    elif name == "folder":
        # Clean folder icon with rounded tab
        d.rounded_rectangle([s * 0.15, s * 0.22, s * 0.50, s * 0.42], radius=int(s * 0.06), fill=color)
        d.rounded_rectangle([s * 0.15, s * 0.32, s * 0.85, s * 0.78], radius=int(s * 0.08), fill=color)
        # Inner contrast highlight
        mask = Image.new("L", (s, s), 255)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([s * 0.20, s * 0.40, s * 0.80, s * 0.72], radius=int(s * 0.05), fill=0)
        flap = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        fd = ImageDraw.Draw(flap)
        fd.rounded_rectangle([s * 0.15, s * 0.42, s * 0.85, s * 0.78], radius=int(s * 0.08), fill=color)

    elif name == "rocket":
        # Streamlined rocket icon
        rcx, rcy = cx, s * 0.44
        d.polygon([
            (rcx, s * 0.16),
            (s * 0.68, s * 0.56),
            (s * 0.60, s * 0.72),
            (s * 0.40, s * 0.72),
            (s * 0.32, s * 0.56)
        ], fill=color)
        d.polygon([(s * 0.32, s * 0.56), (s * 0.18, s * 0.72), (s * 0.35, s * 0.72)], fill=color)
        d.polygon([(s * 0.68, s * 0.56), (s * 0.82, s * 0.72), (s * 0.65, s * 0.72)], fill=color)
        d.ellipse([rcx - s * 0.07, rcy - s * 0.07, rcx + s * 0.07, rcy + s * 0.07], fill="#ffffff")

    elif name == "swap":
        # Clean bidirectional swap arrows ⇄
        arr_w = max(2, int(lw * 0.9))
        y1 = cy - s * 0.12
        y2 = cy + s * 0.12
        # Right arrow
        d.line([s * 0.24, y1, s * 0.76, y1], fill=color, width=arr_w)
        d.line([s * 0.62, y1 - s * 0.10, s * 0.76, y1], fill=color, width=arr_w)
        d.line([s * 0.62, y1 + s * 0.10, s * 0.76, y1], fill=color, width=arr_w)
        # Left arrow
        d.line([s * 0.24, y2, s * 0.76, y2], fill=color, width=arr_w)
        d.line([s * 0.38, y2 - s * 0.10, s * 0.24, y2], fill=color, width=arr_w)
        d.line([s * 0.38, y2 + s * 0.10, s * 0.24, y2], fill=color, width=arr_w)

    return img.resize((size, size), Image.Resampling.LANCZOS)


def get_icon_photo(name, size=20, color="#89b4fa"):
    """
    Returns a cached ImageTk.PhotoImage for Tkinter widgets.
    """
    key = (name, size, color)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    pil_img = create_icon_image(name, size, color)
    photo = ImageTk.PhotoImage(pil_img)
    _ICON_CACHE[key] = photo
    return photo
