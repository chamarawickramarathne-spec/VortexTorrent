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

# Publisher name expected on the signing certificate of a SIGNED installer.
# Policy (checksum is always verified separately in download_installer):
#   - Unsigned installers are permitted as long as the downloaded bytes match
#     the SHA-256 checksum published in the release (integrity guarantee).
#   - An installer that DOES carry a signature must pass WinVerifyTrust (chain
#     validates against the trusted root store) AND its signing-certificate
#     subject must contain EXPECTED_PUBLISHER.
#   - A signature that is present but invalid/tampered is always refused.
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


def _winverifytrust_valid(path):
    """Cryptographically validate the signed file against the trusted root
    store. Returns False for unsigned files (error TRUST_E_NOSIGNATURE)."""
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
    return result == 0


def _signature_status(path):
    """Return (status, signer_subject) for the file's Authenticode signature.
    status is Get-AuthenticodeSignature's Status value ("NotSigned" when the
    file carries no signature; "Valid", "HashMismatch", "NotTrusted", ...).
    subject is None when the file is unsigned."""
    escaped = str(path).replace("'", "''")
    command = (
        "$s = Get-AuthenticodeSignature -LiteralPath '%s'; "
        "Write-Output ('STATUS=' + [string]$s.Status); "
        "Write-Output ('SUBJECT=' + [string]$s.SignerCertificate.Subject)" % escaped
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return "Unknown", None
    status = "Unknown"
    subject = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("STATUS="):
            status = line[len("STATUS="):].strip() or "Unknown"
        elif line.startswith("SUBJECT="):
            subject = line[len("SUBJECT="):].strip() or None
    return status, subject


def _verify_signature(path):
    """Return True when the installer is acceptable to run.

    The SHA-256 checksum is verified separately by the caller. Here:
      - unsigned installers (NotSigned) are permitted - integrity is covered
        by the published checksum, so no silent security downgrade occurs;
      - a PRESENT signature must be cryptographically valid (WinVerifyTrust)
        and its certificate subject must match EXPECTED_PUBLISHER;
      - a present-but-invalid signature is always refused.
    """
    status, subject = _signature_status(path)
    if status == "NotSigned":
        return True
    if status != "Valid" or not subject:
        return False
    if not _winverifytrust_valid(path):
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
            if 0 <= age < CACHE_MAX_AGE:
                cached_ok = True
                if checksum_url:
                    try:
                        cached_ok = _sha256_file(target_path) == self._expected_sha256(
                            checksum_url, installer_name
                        )
                    except Exception:
                        cached_ok = False
                if cached_ok and _verify_signature(target_path):
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
                raise RuntimeError("Installer signature is invalid - update aborted for safety")
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
