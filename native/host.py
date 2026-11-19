#!/usr/bin/env python3
"""Chrome native-messaging host. No listening port and no web-accessible API."""
from __future__ import annotations

import json
import struct
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core import Cancelled, download, safe_error

MAX_MESSAGE = 256 * 1024
MAX_PENDING = 4
HOST_VERSION = "0.2.0"


def read_exact(stream, count):
    chunks = bytearray()
    while len(chunks) < count:
        part = stream.read(count - len(chunks))
        if not part:
            if not chunks:
                return None
            raise ValueError("Truncated native message")
        chunks.extend(part)
    return bytes(chunks)


def read_message(stream):
    header = read_exact(stream, 4)
    if header is None:
        return None
    size, = struct.unpack("=I", header)
    if not 0 < size <= MAX_MESSAGE:
        raise ValueError("Native message too large")
    body = read_exact(stream, size)
    if body is None:
        raise ValueError("Missing native message")
    message = json.loads(body)
    if not isinstance(message, dict):
        raise ValueError("Native message must be an object")
    return message


class Host:
    def __init__(self, config, output=None):
        self.config = config
        self.output = output or sys.stdout.buffer
        self.write_lock = threading.Lock()
        self.job_lock = threading.Lock()
        self.cancelled = {}
        self.active_targets = {}
        self.pool = ThreadPoolExecutor(max_workers=2)

    def send(self, message):
        data = json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8")
        with self.write_lock:
            self.output.write(struct.pack("=I", len(data)))
            self.output.write(data)
            self.output.flush()

    def reply(self, request, **payload):
        self.send({"requestId": request.get("requestId"), **payload})

    def run_download(self, request, event):
        def emit(**state):
            self.send({"type": "job", "job": {"id": request["id"], **state}})
        try:
            if event.is_set():
                raise Cancelled()
            download(self.config, request, event, emit)
        except Exception as error:
            if event.is_set() or isinstance(error, Cancelled):
                emit(status="cancelled", percent=None)
            else:
                emit(status="error", error=safe_error(error), percent=None)
        finally:
            with self.job_lock:
                self.cancelled.pop(request["id"], None)
                self.active_targets.pop(request["id"], None)

    def handle(self, request):
        action = request.get("action")
        if action == "hello":
            from yt_dlp.version import __version__
            self.reply(request, ok=True, type="hello", version=HOST_VERSION,
                       downloaderVersion=__version__, folder=self.config["folder"])
        elif action == "download":
            job_id = request.get("id")
            if not isinstance(job_id, str) or not 1 <= len(job_id) <= 80:
                raise ValueError("Invalid job ID")
            target = request.get("target")
            if not isinstance(target, dict) or not isinstance(target.get("url"), str):
                raise ValueError("Missing video target")
            target_key = (target["url"], str(target.get("itemIndex", 1)))
            with self.job_lock:
                if job_id in self.cancelled:
                    raise ValueError("Duplicate job ID")
                if len(self.cancelled) >= MAX_PENDING:
                    raise ValueError("The queue is full. Let a download finish first.")
                if target_key in self.active_targets.values():
                    raise ValueError("This video is already downloading.")
                event = threading.Event()
                self.cancelled[job_id] = event
                self.active_targets[job_id] = target_key
            # Reply before worker events so the initiating button knows its job ID.
            self.reply(request, ok=True)
            self.pool.submit(self.run_download, request, event)
        elif action == "cancel":
            with self.job_lock:
                event = self.cancelled.get(request.get("id"))
            if event:
                event.set()
            self.reply(request, ok=True)
        elif action == "openFolder":
            folder = Path(self.config["folder"]).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            opener = ["/usr/bin/open", str(folder)] if sys.platform == "darwin" else ["xdg-open", str(folder)]
            subprocess.Popen(opener, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.reply(request, ok=True)
        else:
            raise ValueError("Unsupported helper action")

    def close(self):
        for event in list(self.cancelled.values()):
            event.set()
        self.pool.shutdown(wait=True, cancel_futures=True)


def main():
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    # Chrome supplies the extension origin as argv[1]. Other extensions are rejected.
    expected = f"chrome-extension://{config['extensionId']}/"
    if len(sys.argv) < 2 or sys.argv[1] != expected:
        print("Video Button: unexpected extension origin", file=sys.stderr)
        return 1
    host = Host(config)
    try:
        while True:
            request = read_message(sys.stdin.buffer)
            if request is None:
                break
            try:
                host.handle(request)
            except Exception as error:
                host.reply(request, ok=False, error=safe_error(error))
    except (ValueError, BrokenPipeError, OSError):
        return 1
    finally:
        host.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
