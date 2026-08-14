import json
import os
import urllib.request

GITHUB_OWNER = "chamarawickramarathne-spec"
GITHUB_REPO = "VortexTorrent"


def version_key(version):
    parts = []
    for piece in str(version).lstrip("v").split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


class UpdateChecker:
    def __init__(self, owner=GITHUB_OWNER, repo=GITHUB_REPO):
        self.owner = owner
        self.repo = repo

    def latest_release(self):
        url = "https://api.github.com/repos/%s/%s/releases/latest" % (self.owner, self.repo)
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.load(resp)

    def check(self):
        data = self.latest_release()
        return data.get("tag_name", "").lstrip("v")

    def installer_url(self, version):
        data = self.latest_release()
        for asset in data.get("assets", []):
            if asset["name"].startswith("VortexTorrent-Setup") and asset["name"].endswith(".exe"):
                return asset["browser_download_url"]
        raise FileNotFoundError("No installer asset found in release %s" % version)

    def download_installer(self, version, target_path):
        url = self.installer_url(version)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as resp, open(target_path, "wb") as f:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
        return target_path
