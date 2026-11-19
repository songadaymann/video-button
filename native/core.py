"""Download engine. Browser input is data, never a shell command or output path."""
from __future__ import annotations

import ipaddress
import os
import math
import re
import json
import subprocess
import threading
import tempfile
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
        "merge_output_format": "mkv",  # Lossless intermediate; final exports are MP4 + MP3.
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


def probe_media(config: dict, path: Path) -> dict:
    ffprobe = config.get("ffprobe") or str(Path(config["ffmpeg"]).resolve().with_name("ffprobe"))
    result = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
                            check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def run_ffmpeg(config: dict, arguments: list[str], cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled()
    # A file keeps stderr bounded in memory even during a long conversion.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([config["ffmpeg"], "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *arguments],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors)
        try:
            while process.poll() is None:
                if cancel.wait(.15):
                    raise Cancelled()
            if cancel.is_set():
                raise Cancelled()
            if process.returncode:
                errors.seek(0, 2)
                errors.seek(max(0, errors.tell() - 4000))
                raise RuntimeError("Could not save MP4 and MP3: " + safe_error(errors.read().decode("utf-8", "replace")))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def publish_pair(mp4: Path, mp3: Path, folder: Path, stem: str) -> tuple[Path, Path]:
    # Both staged files live on the same filesystem as Downloads. Hard links
    # publish complete files without replacing an existing file or symlink.
    for number in range(1, 10001):
        name = stem if number == 1 else f"{stem} ({number})"
        video, audio = folder / f"{name}.mp4", folder / f"{name}.mp3"
        linked_video = False
        try:
            os.link(mp4, video)
            linked_video = True
            os.link(mp3, audio)
            return video, audio
        except FileExistsError:
            if linked_video:
                video.unlink()
        except OSError:
            if linked_video:
                video.unlink()
            raise
    raise RuntimeError("Too many files already use this video's name.")


def export_pair(config: dict, source: Path, workspace: Path, cancel: threading.Event, emit) -> tuple[Path, Path, dict]:
    streams = probe_media(config, source).get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError("The site did not return a video track.")
    if not audio:
        raise RuntimeError("This video has no audio track, so an MP4 with sound and an MP3 cannot be created.")
    emit(status="exporting", percent=None)
    mp4, mp3 = workspace / "export.mp4", workspace / "export.mp3"
    arguments = ["-i", str(source), "-map", f"0:{video['index']}", "-map", f"0:{audio['index']}"]
    # Keep the highest-quality video packets when the codec fits MP4. Only
    # unsupported codecs are converted, at the original resolution/frame rate.
    codec = video.get("codec_name")
    if codec in {"h264", "hevc", "av1", "vp9", "mpeg4"}:
        arguments += ["-c:v", "copy"]
        if codec == "hevc":
            arguments += ["-tag:v", "hvc1"]
    else:
        arguments += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                      "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
    if audio.get("codec_name") == "aac":
        arguments += ["-c:a", "copy"]
    else:
        arguments += ["-c:a", "aac", "-b:a", "512k" if audio.get("channels", 2) > 2 else "320k"]
    arguments += ["-movflags", "+faststart", str(mp4),
                  "-map", f"0:{audio['index']}", "-vn", "-c:a", "libmp3lame", "-b:a", "320k", "-ar", "48000",
                  "-ac", "1" if audio.get("channels") == 1 else "2", "-id3v2_version", "3", str(mp3)]
    run_ffmpeg(config, arguments, cancel)
    saved_streams = probe_media(config, mp4).get("streams", [])
    saved_video = next((s for s in saved_streams if s.get("codec_type") == "video"), None)
    if not saved_video or not any(s.get("codec_type") == "audio" for s in saved_streams):
        raise RuntimeError("The MP4 export is missing its video or sound.")
    mp3_streams = probe_media(config, mp3).get("streams", [])
    if not any(s.get("codec_name") == "mp3" for s in mp3_streams):
        raise RuntimeError("The MP3 export could not be verified.")
    if cancel.is_set():
        raise Cancelled()
    video_path, audio_path = publish_pair(mp4, mp3, Path(config["folder"]).expanduser().resolve(), source.stem)
    return video_path, audio_path, saved_video


def _download(config: dict, request: dict, cancel: threading.Event, emit, workspace: Path) -> None:
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
    working_config = {**config, "folder": str(workspace)}

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
        path.relative_to(workspace)
        if path.is_file():
            completed.append(path)

    def extract(source, fallback=False):
        options = make_options(working_config, {**target, "itemIndex": 1} if fallback else target,
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
    video, audio, stream = export_pair(config, completed[-1], workspace, cancel, emit)
    metadata.update({"width": stream["width"], "height": stream["height"]})
    numerator, denominator = stream.get("avg_frame_rate", "0/1").split("/")
    if float(denominator):
        metadata["fps"] = float(numerator) / float(denominator)
    emit(status="complete", percent=100, filename=video.name, audioFilename=audio.name,
         quality=quality_label(metadata, fallback), title=metadata.get("title", target.get("title", "Video")))


def download(config: dict, request: dict, cancel: threading.Event, emit) -> None:
    folder = Path(config["folder"]).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    # Incomplete/source files are temporary. Only the finished MP4 + MP3 pair is
    # published into Downloads; cancellation/error removes the intermediates.
    with tempfile.TemporaryDirectory(prefix=".video-button-", dir=folder) as temporary:
        _download(config, request, cancel, emit, Path(temporary).resolve())
