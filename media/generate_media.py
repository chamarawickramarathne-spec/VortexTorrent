import math
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
SIZE = 512


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def blend(c1, c2, t):
    return lerp(c1, c2, max(0.0, min(1.0, t)))


def draw_vortex(img, cx, cy, r_inner, r_outer, arms=4, start_angle=-90, thickness=26):
    draw = ImageDraw.Draw(img)
    color_top = (20, 40, 120)
    color_mid = (60, 20, 160)
    color_bot = (220, 40, 120)
    steps = 240
    for i in range(steps):
        t = i / steps
        angle = math.radians(start_angle + t * 320 * arms / 2.0)
        r = r_inner + (r_outer - r_inner) * t
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        color = blend(color_bot, color_mid, t)
        if t > 0.5:
            color = blend(color_mid, color_top, (t - 0.5) * 2)
        draw.ellipse((x - thickness / 2, y - thickness / 2, x + thickness / 2, y + thickness / 2), fill=color)


def make_logo():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw_vortex(img, SIZE / 2, SIZE / 2, 60, 210, arms=4, thickness=30)
    draw = ImageDraw.Draw(img)
    draw.ellipse((SIZE / 2 - 150, SIZE / 2 - 150, SIZE / 2 + 150, SIZE / 2 + 150), outline=(255, 255, 255, 60), width=4)
    draw.ellipse((SIZE / 2 - 90, SIZE / 2 - 90, SIZE / 2 + 90, SIZE / 2 + 90), outline=(255, 255, 255, 90), width=4)
    return img


def make_icon(img, size):
    icon = img.resize((size, size), Image.LANCZOS)
    return icon


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
