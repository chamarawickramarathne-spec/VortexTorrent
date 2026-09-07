import ctypes
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from ctypes import wintypes

GITHUB_OWNER = "chamarawickramarathne-spec"
GITHUB_REPO = "VortexTorrent"

# Publisher name expected on the signed installer's certificate. If the
# installer is not signed by an identity whose subject contains this string,
# the update is refused.
EXPECTED_PUBLISHER = "Vortex"

# Reuse a cached, already-verified installer if it is younger than this.
CACHE_MAX_AGE = 86400


class WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pcwszFilePath", wintypes.LPCWSTR),
        ("hFile", wintypes.HANDLE),
        ("pgKnownSubject", ctypes.c_void_p),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class WINTRUST_DATA(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pPolicyCallbackData", ctypes.c_void_p),
        ("pSIPClientData", ctypes.c_void_p),
        ("dwUIChoice", wintypes.DWORD),
        ("fdwRevocationChecks", wintypes.DWORD),
        ("dwUnionChoice", wintypes.DWORD),
        ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
        ("dwStateAction", wintypes.DWORD),
        ("hWVTStateData", ctypes.c_void_p),
        ("pwszURLReference", wintypes.LPCWSTR),
        ("dwProvFlags", wintypes.DWORD),
        ("dwUIContext", wintypes.DWORD),
    ]


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


def _http_get(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_signature(path):
    """Return True when the Authenticode signature is valid and its signing
    certificate subject matches EXPECTED_PUBLISHER."""
    # 1) Structural validation via WinVerifyTrust (cryptographically checks
    #    the signature chain against the trusted root store).
    guid = GUID()
    guid.Data1, guid.Data2, guid.Data3 = 0x00AAC56B, 0xCD44, 0x11D0
    guid.Data4 = (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE)

    file_info = WINTRUST_FILE_INFO()
    file_info.cbStruct = ctypes.sizeof(WINTRUST_FILE_INFO)
    file_info.pcwszFilePath = path

    trust = WINTRUST_DATA()
    trust.cbStruct = ctypes.sizeof(WINTRUST_DATA)
    trust.dwUIChoice = 2  # WTD_UI_NONE
    trust.fdwRevocationChecks = 0
    trust.dwUnionChoice = 1  # WTD_CHOICE_FILE
    trust.pFile = ctypes.pointer(file_info)
    trust.dwStateAction = 0  # WTD_STATEACTION_IGNORE
    trust.dwUIContext = 1  # WTD_UICONTEXT_EXECUTE

    result = ctypes.windll.wintrust.WinVerifyTrust(
        wintypes.HWND(0), ctypes.byref(guid), ctypes.byref(trust)
    )
    if result != 0:
        return False

    # 2) Publisher check via PowerShell's Authenticode APIs.
    return _publisher_matches(path)


def _publisher_matches(path):
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "(Get-AuthenticodeSignature -LiteralPath '%s').SignerCertificate.Subject" % path,
            ],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return False
    subject = (proc.stdout or "").strip()
    if not subject:
        return False
    return EXPECTED_PUBLISHER.lower() in subject.lower()


class UpdateChecker:
    def __init__(self, owner=GITHUB_OWNER, repo=GITHUB_REPO):
        self.owner = owner
        self.repo = repo

    def latest_release(self):
        url = "https://api.github.com/repos/%s/%s/releases/latest" % (self.owner, self.repo)
        return json.loads(_http_get(url, 15))

    def check(self, current):
        """Return the newest release tag if it is NEWER than `current`, else None."""
        data = self.latest_release()
        latest = (data.get("tag_name") or "").lstrip("v")
        if not latest:
            return None
        if version_key(latest) > version_key(current):
            return latest
        return None

    def _asset_info(self):
        data = self.latest_release()
        installer = None
        checksum = None
        for asset in data.get("assets", []):
            name = asset["name"]
            if name.startswith("VortexTorrent-Setup") and name.endswith(".exe"):
                installer = asset["browser_download_url"]
            elif name.lower().find("checksum") != -1 or name.lower().endswith(
                (".sha256", ".sha256sum", ".sha512")
            ):
                checksum = asset["browser_download_url"]
        if installer is None:
            raise FileNotFoundError("No installer asset found in release")
        return installer, checksum

    def installer_url(self):
        return self._asset_info()[0]

    def _expected_sha256(self, checksum_url, installer_name):
        text = _http_get(checksum_url, 30).decode("utf-8", "replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if installer_name not in line:
                continue
            parts = line.split()
            for part in parts:
                digest = part.lower()
                try:
                    if len(digest) == 64:
                        int(digest, 16)
                        return digest
                except ValueError:
                    continue
        raise FileNotFoundError("No sha256 entry matched the installer")

    def download_installer(self, target_path):
        url, checksum_url = self._asset_info()
        installer_name = os.path.basename(url)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if os.path.exists(target_path):
            age = time.time() - os.path.getmtime(target_path)
            if 0 <= age < CACHE_MAX_AGE and _verify_signature(target_path):
                return target_path

        temp = target_path + ".part"
        try:
            with urllib.request.urlopen(url, timeout=300) as resp, open(temp, "wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            if checksum_url and _sha256_file(temp) != self._expected_sha256(
                checksum_url, installer_name
            ):
                raise RuntimeError("Installer checksum mismatch - update aborted for safety")
            if not _verify_signature(temp):
                raise RuntimeError("Installer signature is missing/invalid - update aborted for safety")
            os.replace(temp, target_path)
        finally:
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except OSError:
                    pass
        return target_path

    def cleanup_stale(self, config_dir, keep_name):
        prefix = "VortexTorrent-Setup-"
        for name in os.listdir(config_dir):
            if name.startswith(prefix) and name.endswith(".exe") and name != keep_name:
                try:
                    os.remove(os.path.join(config_dir, name))
                except OSError:
                    pass
