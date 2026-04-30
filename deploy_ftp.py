"""
deploy_ftp.py — RoboTrack FTP Deployment
==========================================
Upload de volledige PHP-dashboard naar de webhosting via FTP.

Gebruik:
    python deploy_ftp.py

Vereisten:
    - .env bestand met FTP_HOST, FTP_USER, FTP_PASSWORD, FTP_WEBROOT
    - Python 3.8+  (alleen standaardbibliotheek)
"""

import ftplib
import os
import sys

# ── Laad .env ────────────────────────────────────────────────
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def load_env(path: str) -> dict:
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    except FileNotFoundError:
        print(f"[!] .env niet gevonden op {path}")
    return env


_env = load_env(_ENV_PATH)

FTP_HOST     = _env.get("FTP_HOST", "")
FTP_USER     = _env.get("FTP_USER", "")
FTP_PASSWORD = _env.get("FTP_PASSWORD", "")
FTP_WEBROOT  = _env.get("FTP_WEBROOT", "/")

# Bestanden die NIET geüpload worden (lokaal-only)
EXCLUDE_FILES = {
    ".env",
    ".gitignore",
    "robots_live.json",
    "robot_overrides.json",
}

# Extensies die geüpload worden
INCLUDE_EXTENSIONS = {
    ".php", ".js", ".css", ".jpg", ".jpeg", ".png",
    ".svg", ".ico", ".htaccess", ".json",
}


# ── FTP hulpfuncties ─────────────────────────────────────────

def ftp_mkdir_p(ftp: ftplib.FTP, remote_dir: str):
    """Maak de map en alle tussenliggende mappen aan als ze niet bestaan."""
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    current = "/"
    for part in parts:
        current = f"{current}/{part}".replace("//", "/")
        try:
            ftp.cwd(current)
        except ftplib.error_perm:
            try:
                ftp.mkd(current)
                print(f"  [mkdir] {current}")
            except ftplib.error_perm:
                pass  # bestaat al


def ftp_upload_file(ftp: ftplib.FTP, local_path: str, remote_path: str):
    """Upload één bestand naar de FTP-server."""
    remote_dir, remote_name = remote_path.rsplit("/", 1)
    ftp_mkdir_p(ftp, remote_dir)
    ftp.cwd(remote_dir)
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {remote_name}", f)
    print(f"  [upload] {remote_path}")


def collect_files(local_dir: str) -> list[tuple[str, str]]:
    """
    Verzamel alle te uploaden bestanden.
    Geeft lijst van (lokaal_pad, relatief_pad) terug.
    """
    result = []
    for root, dirs, files in os.walk(local_dir):
        # Sla verborgen mappen over (.git, .claude, __pycache__)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for filename in files:
            if filename in EXCLUDE_FILES:
                continue
            ext = os.path.splitext(filename)[1].lower()
            # .htaccess heeft geen extensie-match — apart afvangen
            if ext not in INCLUDE_EXTENSIONS and filename != ".htaccess":
                continue
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
            result.append((local_path, rel_path))
    return result


# ── Hoofd-deploy ─────────────────────────────────────────────

def main():
    if not (FTP_HOST and FTP_USER and FTP_PASSWORD):
        print("[!] FTP-credentials ontbreken in .env — stoppen.")
        sys.exit(1)

    public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
    if not os.path.isdir(public_dir):
        print(f"[!] 'public/' map niet gevonden op {public_dir}")
        sys.exit(1)

    files = collect_files(public_dir)
    print(f"\n[Deploy] {len(files)} bestanden gevonden in public/")
    print(f"[Deploy] Verbinden met {FTP_HOST} als {FTP_USER} ...")

    try:
        ftp = ftplib.FTP(FTP_HOST, timeout=30)
        ftp.login(FTP_USER, FTP_PASSWORD)
        ftp.set_pasv(True)
        print(f"[Deploy] Verbonden. Webroot: {FTP_WEBROOT}\n")
    except Exception as e:
        print(f"[!] FTP verbinding mislukt: {e}")
        sys.exit(1)

    errors = []
    for i, (local_path, rel_path) in enumerate(files, 1):
        remote_path = f"{FTP_WEBROOT.rstrip('/')}/{rel_path}"
        remote_path = remote_path.replace("//", "/")
        try:
            ftp_upload_file(ftp, local_path, remote_path)
        except Exception as e:
            print(f"  [!] FOUT bij {rel_path}: {e}")
            errors.append(rel_path)

    # Maak ook /data/ en /cams/ mappen aan op de server
    for remote_dir in [
        f"{FTP_WEBROOT.rstrip('/')}/data",
        _env.get("FTP_CAMS_DIR", "/cams"),
    ]:
        ftp_mkdir_p(ftp, remote_dir)

    ftp.quit()

    print(f"\n[Deploy] Klaar — {len(files) - len(errors)}/{len(files)} bestanden geüpload.")
    if errors:
        print("[!] Mislukte bestanden:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("[Deploy] Alle bestanden succesvol geüpload!")
        domain = FTP_HOST.replace("ftp.", "www.", 1) if FTP_HOST.startswith("ftp.") else FTP_HOST
        print(f"\n   Dashboard bereikbaar op: http://{domain}/")
        print(f"   Camera snapshot URL:      http://{domain}/cams/camera_snapshot.jpg")


if __name__ == "__main__":
    main()
