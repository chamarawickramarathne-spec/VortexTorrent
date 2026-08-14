BG = "#12141c"
PANEL = "#1c2030"
PANEL_HOVER = "#262b3f"
BORDER = "#2a2f45"
TEXT = "#e8eaf2"
TEXT_DIM = "#8b92ad"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#8f74ff"
CYAN = "#22d3ee"
CYAN_HOVER = "#3fe1f8"
SUCCESS = "#34d399"
DANGER = "#f43f5e"
WARNING = "#fbbf24"
ROW_ACTIVE = "#232844"
ROW_SELECTED = "#2d3350"

FONT_FAMILY = "Segoe UI"


def font(size=13, weight="normal"):
    return (FONT_FAMILY, size, weight)


def state_color(state):
    if state == "Downloading":
        return ACCENT
    if state == "Seeding":
        return CYAN
    if state == "Paused":
        return TEXT_DIM
    if state == "Error":
        return DANGER
    if state == "Finished":
        return SUCCESS
    return WARNING
