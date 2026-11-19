"""Download engine. Browser input is data, never a shell command or output path."""
from __future__ import annotations

import ipaddress
import math
import re
import json
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit


class Cancelled(Exception):
    pass


def safe_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 16384 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid video URL.")
    try:
        u = urlsplit(value)
        host = (u.hostname or "").lower().rstrip(".")
        if u.scheme not in ("http", "https") or not host or u.username or u.password:
            raise ValueError()
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and not address.is_global:
            raise ValueError()
        _ = u.port
    except (ValueError, TypeError):
        raise ValueError("Use a public HTTP or HTTPS video URL.") from None
    return value


def safe_error(error: object) -> str:
    # Do not relay signed URLs, tokens, browser paths, or verbose downloader logs.
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(error))
    message = re.sub(r"https?://\S+", "[video URL]", message)
    message = re.sub(r"(?:/Users/|/home/)[^\s:'\"]+", "[local path]", message)
    return message.replace("ERROR: ", "").strip()[:450] or "The site did not provide a downloadable video."


def quality_label(info: dict, fallback: bool = False) -> str:
    height = info.get("height")
    width = info.get("width")
    fps = info.get("fps")
    parts = [f"{width}×{height}" if width and height and width < height else f"{height}p" if height else "Best available"]
    if fps and fps > 30:
        parts.append(f"{fps:g} fps")
    if fallback:
        parts.append("player source; site quality unavailable")
    return " · ".join(parts)


def make_options(config: dict, target: dict, use_cookies: bool, profile: str,
                 progress, postprocessor, finished, logger) -> dict:
    folder = Path(config["folder"]).expanduser().resolve()
    if not folder.is_absolute():
        raise ValueError("Download folder must be absolute.")
    folder.mkdir(parents=True, exist_ok=True)
    index = target.get("itemIndex", 1)
    if type(index) is not int or not 1 <= index <= 1000:
        raise ValueError("Invalid video selection.")
    if profile and (not isinstance(profile, str) or not re.fullmatch(r"Default|Profile \d+", profile)):
        raise ValueError("Invalid Chrome profile. Use Default or Profile 1, etc.")
    options = {
        "format": "bestvideo*+bestaudio/best",
        "format_sort": ["res", "fps"],
        "noplaylist": True,
        "playlist_items": str(index),
        "paths": {"home": str(folder)},
        "outtmpl": {"default": "%(title).150B [%(id).70B].%(ext)s"},
        "windowsfilenames": True,
        "overwrites": False,
        "continuedl": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "logger": logger,
        "progress_hooks": [progress],
        "postprocessor_hooks": [postprocessor],
        "post_hooks": [finished],
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "cachedir": False,
        "enable_file_urls": False,
        "ffmpeg_location": config["ffmpeg"],
        "js_runtimes": {"node": {"path": config["node"]}},
        "remote_components": set(),
        "check_formats": "selected",
        "match_filter": lambda info, *, incomplete=False: "Live streams are not supported. Try again after the broadcast ends." if info.get("is_live") else None,
    }
    if use_cookies:
        options["cookiesfrombrowser"] = ("chrome", profile or None, None, None)
    return options


def download(config: dict, request: dict, cancel: threading.Event, emit) -> None:
    from yt_dlp import YoutubeDL
    target = request.get("target")
    if not isinstance(target, dict):
        raise ValueError("Missing video target.")
    url = safe_url(target.get("url"))
    media = target.get("mediaUrl")
    if media:
        try:
            media = safe_url(media)
        except ValueError:
            media = None
    last_progress = 0.0
    completed: list[Path] = []
    metadata: dict = {}
    warnings: list[str] = []

    def check_cancel():
        if cancel.is_set():
            raise Cancelled("Cancelled")

    class Logger:
        def debug(self, message):
            pass

        def warning(self, message):
            warnings.append(safe_error(message))

        def error(self, message):
            warnings.append(safe_error(message))

    def progress(data):
        nonlocal last_progress
        check_cancel()
        metadata.update({k: data.get("info_dict", {}).get(k) for k in ("width", "height", "fps", "title") if data.get("info_dict", {}).get(k) is not None})
        now = time.monotonic()
        if now - last_progress < .35 and data["status"] != "finished":
            return
        last_progress = now
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        percent = 100 * data.get("downloaded_bytes", 0) / total if total else None
        if percent is not None and not math.isfinite(percent):
            percent = None
        emit(status="downloading", percent=min(100, percent) if percent is not None else None)

    def postprocessor(data):
        check_cancel()
        if data["status"] in ("started", "processing"):
            emit(status="merging", percent=None)

    def finished(filename):
        check_cancel()
        path = Path(filename).resolve()
        # yt-dlp sanitizes the filename; only accept results inside the chosen folder.
        path.relative_to(Path(config["folder"]).expanduser().resolve())
        if path.is_file():
            completed.append(path)

    def extract(source, fallback=False):
        options = make_options(config, {**target, "itemIndex": 1} if fallback else target,
                               request.get("useCookies") is True,
                               request.get("chromeProfile") or "", progress, postprocessor, finished, Logger())
        if fallback:
            # A direct source may need its public webpage as Referer.
            options["http_headers"] = {"Referer": url}
        with YoutubeDL(options) as ydl:
            check_cancel()
            info = ydl.extract_info(source, download=True)
        check_cancel()
        if info and info.get("entries") is not None:
            info = next((entry for entry in info["entries"] if entry), None)
        if not info:
            raise RuntimeError("No matching video was returned. Open the individual video’s post page and try again.")
        metadata.update({k: info[k] for k in ("width", "height", "fps", "title") if info.get(k) is not None})
        return info

    emit(status="extracting", percent=None)
    fallback = False
    try:
        extract(url)
    except Exception:
        check_cancel()
        # Precise social permalinks must not silently fall back to a lower-quality
        # playback URL. Generic players can expose the only available source.
        if not media or media == url or target.get("precise") or completed:
            raise
        fallback = True
        emit(status="extracting", percent=None)
        extract(media, fallback=True)
    if not completed:
        raise RuntimeError("The site returned no saved video. It may be DRM protected or require a sign-in.")
    # Site format labels can disagree with the delivered file (especially portrait
    # video). Report the actual saved dimensions rather than promising its label.
    ffprobe = config.get("ffprobe") or str(Path(config["ffmpeg"]).resolve().with_name("ffprobe"))
    try:
        probe = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json",
                                str(completed[-1])], check=True, capture_output=True, text=True, timeout=15)
        stream = json.loads(probe.stdout)["streams"][0]
        metadata.update({"width": stream["width"], "height": stream["height"]})
        numerator, denominator = stream.get("avg_frame_rate", "0/1").split("/")
        if float(denominator):
            metadata["fps"] = float(numerator) / float(denominator)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
        pass  # The video is already saved; metadata probing must not lose it.
    check_cancel()
    emit(status="complete", percent=100, filename=completed[-1].name,
         quality=quality_label(metadata, fallback), title=metadata.get("title", target.get("title", "Video")))
