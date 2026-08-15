import math
import os

from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
SIZE = 512
RENDER = SIZE * 4
CX, CY = SIZE // 2, SIZE // 2 - 12
R_INNER, R_OUTER = 46.0, 232.0
SWEEP = math.radians(820)
START_ANGLE = math.radians(-90)
TAIL_FADE_FROM = 0.70
DOT_STEP = 1.8

COLOR_STOPS = [
    (0.00, (34, 211, 238)),
    (0.28, (37, 99, 235)),
    (0.55, (124, 92, 255)),
    (0.78, (168, 85, 247)),
    (1.00, (217, 70, 239)),
]


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


def draw_arm(alpha_scale=1.0, phase=0.0):
    img = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    thick_start, thick_end = 36.0, 4.5
    for t, x, y in spiral_points(phase):
        d = (thick_start + (thick_end - thick_start) * t) * 4
        r = d / 2.0
        a = 255
        if t > TAIL_FADE_FROM:
            a = int(255 * (1 - (t - TAIL_FADE_FROM) / (1 - TAIL_FADE_FROM)))
        a = int(a * alpha_scale)
        if a <= 0:
            continue
        px, py = x * 4, y * 4
        draw.ellipse((px - r, py - r, px + r, py + r), fill=color_at(t) + (a,))
    return img


def make_logo():
    canvas = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    cx, cy = CX * 4, CY * 4

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

    arm = draw_arm(alpha_scale=1.0)
    glow = arm.filter(ImageFilter.GaussianBlur(90))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.5)))
    canvas = Image.alpha_composite(canvas, glow)

    canvas = Image.alpha_composite(canvas, draw_arm(alpha_scale=0.28, phase=math.pi))

    canvas = Image.alpha_composite(canvas, arm)

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
