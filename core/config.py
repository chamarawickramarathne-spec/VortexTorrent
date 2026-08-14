import json
import os


def app_data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "VortexTorrent")
    os.makedirs(path, exist_ok=True)
    return path


DEFAULT_SETTINGS = {
    "download_dir": os.path.join(os.path.expanduser("~"), "Downloads", "VortexTorrent"),
    "download_rate": 0,
    "upload_rate": 0,
    "port": 6881,
}


def load_settings():
    path = os.path.join(app_data_dir(), "settings.json")
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                settings.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(settings):
    path = os.path.join(app_data_dir(), "settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
