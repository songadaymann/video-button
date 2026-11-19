#!/usr/bin/env python3
"""Install or update the per-user native helper, without admin rights."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "com.songaday.video_button"


def extension_id():
    public = base64.b64decode(json.loads((ROOT / "extension/manifest.json").read_text())["key"])
    return "".join(chr(97 + int(c, 16)) for c in hashlib.sha256(public).hexdigest()[:32])


def locations():
    if sys.platform == "darwin":
        return (Path.home() / "Library/Application Support/Video Button",
                Path.home() / "Library/Application Support/Google/Chrome/NativeMessagingHosts")
    if sys.platform.startswith("linux"):
        return (Path.home() / ".local/share/video-button", Path.home() / ".config/google-chrome/NativeMessagingHosts")
    raise SystemExit("This installer supports macOS and Linux. Windows setup is not included yet.")


def find_tool(name):
    tool = shutil.which(name)
    if tool:
        return str(Path(tool).resolve())
    for directory in (Path.home()/".local/bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        candidate = directory / name
        if candidate.is_file():
            return str(candidate.resolve())
    raise SystemExit(f"Missing {name}. Install Python 3.11+, FFmpeg, and Node.js 22+ first. See README.md.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--folder", type=Path)
    args = parser.parse_args()
    home, manifests = locations()
    manifest = manifests / f"{HOST}.json"
    if args.uninstall:
        manifest.unlink(missing_ok=True)
        # Remove only the helper's known directory; downloaded videos are untouched.
        if home.exists():
            shutil.rmtree(home)
        print("Local helper removed. Remove Video Button at chrome://extensions to finish.")
        return
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")
    ffmpeg, ffprobe, node = find_tool("ffmpeg"), find_tool("ffprobe"), find_tool("node")
    node_major = int(subprocess.check_output([node, "--version"], text=True).strip().lstrip("v").split(".")[0])
    if node_major < 22:
        raise SystemExit("Node.js 22 or newer is required for YouTube support.")
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    python = home / "runtime/bin/python3"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(home / "runtime")], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "-r", str(ROOT/"requirements.txt")], check=True)
    for name in ("host.py", "core.py"):
        shutil.copy2(ROOT/"native"/name, home/name)
    existing = json.loads((home/"config.json").read_text()) if (home/"config.json").exists() else {}
    folder = args.folder or Path(existing.get("folder", str(Path.home()/"Downloads")))
    folder = folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    config = {"extensionId": extension_id(), "folder": str(folder), "ffmpeg": ffmpeg, "ffprobe": ffprobe, "node": node}
    (home/"config.json").write_text(json.dumps(config, indent=2)+"\n")
    (home/"config.json").chmod(0o600)
    launcher = home/"launch-host"
    launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(python)) + " " + shlex.quote(str(home/"host.py")) + ' "$@"\n')
    launcher.chmod(0o700)
    manifests.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name":HOST,"description":"Video Button local video downloader","path":str(launcher),"type":"stdio","allowed_origins":[f"chrome-extension://{extension_id()}/"]},indent=2)+"\n")
    manifest.chmod(0o600)
    version = subprocess.check_output([str(python),"-m","yt_dlp","--version"],text=True).strip()
    print(f"\nVideo Button helper ready (yt-dlp {version}).\nDownloads: {folder}\n\nChrome: open chrome://extensions, turn on Developer mode, click Load unpacked, select:\n{ROOT/'extension'}\n\nExtension ID: {extension_id()}\nRefresh existing video tabs after loading the extension.")


if __name__ == "__main__":
    main()
