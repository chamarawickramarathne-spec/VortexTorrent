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
    "port": 6881,
    "max_active_downloads": 2,
}


MAX_PORT = 65535
MIN_PORT = 1024


def _coerce(settings):
    """Validate and clamp setting values to safe ranges in place."""
    try:
        settings["download_rate"] = max(0, int(settings.get("download_rate", 0)))
    except (TypeError, ValueError):
        settings["download_rate"] = DEFAULT_SETTINGS["download_rate"]
    try:
        port = int(settings.get("port", DEFAULT_SETTINGS["port"]))
        settings["port"] = min(MAX_PORT, max(MIN_PORT, port))
    except (TypeError, ValueError):
        settings["port"] = DEFAULT_SETTINGS["port"]
    try:
        settings["max_active_downloads"] = max(
            0, int(settings.get("max_active_downloads", 0))
        )
    except (TypeError, ValueError):
        settings["max_active_downloads"] = DEFAULT_SETTINGS["max_active_downloads"]
    download_dir = settings.get("download_dir")
    if not isinstance(download_dir, str) or not download_dir.strip():
        settings["download_dir"] = DEFAULT_SETTINGS["download_dir"]
    return settings


def load_settings():
    path = os.path.join(app_data_dir(), "settings.json")
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                settings.update(loaded)
        except (json.JSONDecodeError, OSError, ValueError):
            # Back up the corrupt file instead of silently discarding it.
            try:
                backup = path + ".bak"
                with open(path, "r", encoding="utf-8") as f:
                    data = f.read()
                if data.strip():
                    with open(backup, "w", encoding="utf-8") as f:
                        f.write(data)
            except OSError:
                pass
    return _coerce(settings)


def save_settings(settings):
    path = os.path.join(app_data_dir(), "settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
