import os

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE, "logo.png")
ICON_PATH = os.path.join(BASE, "icon.ico")
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    logo = Image.open(LOGO_PATH).convert("RGBA")
    icon = logo.resize((256, 256), Image.LANCZOS)
    icon.save(ICON_PATH, sizes=ICO_SIZES)
    print("icon.ico regenerated from", LOGO_PATH)


if __name__ == "__main__":
    main()
