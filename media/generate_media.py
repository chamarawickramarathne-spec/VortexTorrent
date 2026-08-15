import math
import os

from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
SIZE = 512
RENDER = SIZE * 4
CX, CY = SIZE // 2, SIZE // 2 - 6

R_INNER, R_OUTER = 46.0, 232.0
SWEEP = math.radians(820)
START_ANGLE = math.radians(-90)

PITCH = math.radians(16)
FOCAL = 300.0
FIT_R = 226
DOT_STEP = 1.8
TAIL_FADE_FROM = 0.72
ARM_TAPER = (33.0, 5.0)

HL_X, HL_Y = -0.47, -0.88
FOG_COLOR = (92, 120, 175)
FOG_AMOUNT = 0.55
LIGHT_AMOUNT = 0.34
HIGHLIGHT_ALPHA = 125
FAINT_ALPHA = 0.22

COLOR_STOPS = [
    (0.00, (34, 211, 238)),
    (0.28, (37, 99, 235)),
    (0.55, (124, 92, 255)),
    (0.78, (168, 85, 247)),
    (1.00, (217, 70, 239)),
]

SIN_P = math.sin(PITCH)
COS_P = math.cos(PITCH)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def color_at(t):
    t = max(0.0, min(1.0, t))
    for i in range(len(COLOR_STOPS) - 1):
        t0, c0 = COLOR_STOPS[i]
        t1, c1 = COLOR_STOPS[i + 1]
        if t0 <= t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return COLOR_STOPS[-1][1]


def spiral_points(phase=0.0):
    n_fine = 4000
    pts = []
    cum = []
    prev = None
    for i in range(n_fine + 1):
        t = i / n_fine
        a = START_ANGLE + phase - t * SWEEP
        r = R_INNER * (R_OUTER / R_INNER) ** t
        x = CX + r * math.cos(a)
        y = CY + r * math.sin(a)
        if prev is None:
            cum.append(0.0)
        else:
            cum.append(cum[-1] + math.hypot(x - prev[0], y - prev[1]))
        prev = (x, y)
        pts.append((t, x, y))
    total = cum[-1]
    n = max(1, int(total / DOT_STEP))
    out = []
    for k in range(n + 1):
        target = total * k / n
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        out.append(pts[lo])
    return out


def project_spiral(phase=0.0):
    pts = []
    for t, x, y in spiral_points(phase):
        xr = x - CX
        yr = y - CY
        z = yr * SIN_P
        yp = yr * COS_P
        s = FOCAL / (FOCAL + z)
        pts.append((t, xr * s, yp * s, z))
    return pts


def render_arms():
    dots = []
    for phase, alpha in ((0.0, 1.0), (math.pi, FAINT_ALPHA)):
        for t, x, y, z in project_spiral(phase):
            dots.append((t, x, y, z, alpha))
    max_r = max(math.hypot(x, y) for _, x, y, _, _ in dots)
    scale = FIT_R / max_r
    zs = [d[3] for d in dots]
    z_min, z_max = min(zs), max(zs)
    z_span = (z_max - z_min) or 1.0
    dots.sort(key=lambda d: d[3], reverse=True)

    layer = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for t, x, y, z, alpha in dots:
        s = FOCAL / (FOCAL + z)
        sx, sy = CX + x * scale, CY + y * scale
        rad = (ARM_TAPER[0] + (ARM_TAPER[1] - ARM_TAPER[0]) * t) * s * scale
        if rad < 0.6:
            continue
        brightness = 1.0 - FOG_AMOUNT * (z - z_min) / z_span
        brightness = max(0.15, min(1.0, brightness))
        color = color_at(t)
        r = int(color[0] + (FOG_COLOR[0] - color[0]) * (1 - brightness))
        g = int(color[1] + (FOG_COLOR[1] - color[1]) * (1 - brightness))
        b = int(color[2] + (FOG_COLOR[2] - color[2]) * (1 - brightness))
        light = 0.84 + LIGHT_AMOUNT * brightness
        r = min(255, int(r * light))
        g = min(255, int(g * light))
        b = min(255, int(b * light))
        a = alpha * (0.55 + 0.45 * brightness)
        if t > TAIL_FADE_FROM:
            a *= 1 - (t - TAIL_FADE_FROM) / (1 - TAIL_FADE_FROM)
        if a <= 0:
            continue
        px, py = sx * 4, sy * 4
        pr = rad * 4
        draw.ellipse((px - pr, py - pr, px + pr, py + pr), fill=(r, g, b, int(a * 255)))
        if alpha >= 1.0:
            hr = rad * 0.32
            hx, hy = sx + HL_X * rad, sy + HL_Y * rad
            ha = int(HIGHLIGHT_ALPHA * brightness)
            hxr, hyr = hx * 4, hy * 4
            hrr = hr * 4
            draw.ellipse((hxr - hrr, hyr - hrr, hxr + hrr, hyr + hrr), fill=(255, 255, 255, ha))
    return layer


def make_logo():
    canvas = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    cx, cy = CX * 4, CY * 4

    arms = render_arms()

    shadow = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    shadow.putalpha(arms.getchannel("A").point(lambda v: int(v * 0.38)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(50))
    canvas.paste(shadow, (44, 60), shadow)

    halo = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    dh = ImageDraw.Draw(halo)
    r = int(165 * 4)
    dh.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(124, 92, 255, 55))
    halo = halo.filter(ImageFilter.GaussianBlur(180))
    canvas = Image.alpha_composite(canvas, halo)

    halo = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    dh = ImageDraw.Draw(halo)
    r = int(95 * 4)
    dh.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(34, 211, 238, 80))
    halo = halo.filter(ImageFilter.GaussianBlur(130))
    canvas = Image.alpha_composite(canvas, halo)

    glow = arms.filter(ImageFilter.GaussianBlur(90))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.5)))
    canvas = Image.alpha_composite(canvas, glow)

    canvas = Image.alpha_composite(canvas, arms)

    core = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    dc = ImageDraw.Draw(core)
    r = int(27 * 4)
    dc.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(240, 252, 255, 255))
    core = core.filter(ImageFilter.GaussianBlur(26))
    canvas = Image.alpha_composite(canvas, core)

    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def make_icon(img, size):
    return img.resize((size, size), Image.LANCZOS)


def main():
    logo = make_logo()
    logo.save(os.path.join(BASE, "logo.png"))
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    icon.alpha_composite(make_icon(logo, 256))
    icon.save(os.path.join(BASE, "icon.ico"), sizes=ico_sizes)
    print("media assets created:", os.listdir(BASE))


if __name__ == "__main__":
    main()
