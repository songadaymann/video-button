# Video Button

A personal Chrome extension that adds **Download video** to visible video players. One click asks a local [yt-dlp](https://github.com/yt-dlp/yt-dlp) helper for the best available video and audio; [FFmpeg](https://ffmpeg.org/) combines separate tracks without re-encoding. Files stay on your computer. No account, paid API, cloud downloader, analytics, or public Chrome Web Store listing is required.

Source: <https://github.com/songadaymann/video-button>. This is a locally installed extension, not a hosted app.

## Install on a Mac

You need **Python 3.11+**, **Node.js 22+**, and **FFmpeg** (including ffprobe). With [Homebrew](https://brew.sh/):

```sh
brew install python node ffmpeg
```

1. Download or clone this repository and keep the folder somewhere convenient.
2. Double-click **Install.command**, or run `python3 scripts/install.py` from this folder in Terminal. The installer creates a per-user helper and its isolated Python environment. No administrator access is needed.
3. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and select this repository's **extension** folder.
4. Refresh existing video tabs. You can pin Video Button in Chrome's extensions menu.

Keep Developer mode enabled. Keep the extension folder in place; Chrome reads it directly. The helper is copied into your user application-support folder, so it does not need a server running in a Terminal window.

The default download folder is `~/Downloads/Video Button`. Set a different folder when installing:

```sh
python3 scripts/install.py --folder '/path/to/videos'
```

Linux Chrome is also supported by the command-line installer, provided Python, Node, FFmpeg and `xdg-open` are installed. Windows and other browsers have not been implemented or tested.

## Use

- Click **↓ Download video** at the top right of a visible player.
- The toolbar popup shows download progress, cancellation, recent results, and an **Open download folder** button.
- If a player does not show a button, right-click the video and choose **Download video — best quality**, or use **Download this page's video** in the toolbar.
- In scrolling feeds, the extension looks for the clicked video's individual post link. If that is unavailable or a carousel selects the wrong item, open the individual video/post page and try there. Feed layouts and closed shadow-root/custom players can prevent automatic matching.
- For private/login-only videos that you can already access, open Settings and enable **Use my Chrome sign-in for downloads**. This is off by default. macOS may ask for Chrome's Keychain item. You can optionally specify `Default` or `Profile 1`, etc.; find that folder name at the end of Chrome's Profile Path in `chrome://version`.

Two downloads can run at once, with up to four total running/queued. Keep Chrome open until they finish. Cancelled downloads may leave partial files for resuming on retry. Download history is kept only for this browser session; up to 30 finished entries are retained.

## What “best available” means

The helper uses yt-dlp's `bestvideo*+bestaudio/best` selector, prioritizing resolution and frame rate. It fetches separate video/audio tracks when available and uses FFmpeg to combine them. It does **not** cap quality to the playback setting, favor MP4 at the expense of resolution, or re-encode. Output can be MP4, WebM, or MKV depending on the original codecs. A site's available renditions can depend on sign-in, account, region, device, and current extractor support.

YouTube, X/Twitter, TikTok, Instagram, and many other sites have upstream yt-dlp extractors. That is a capability target, not a claim that every video on those sites was tested or will download. Site changes, anti-bot checks, inaccessible content, DRM, and some live players can prevent downloading. The extension does not remove DRM or grant access to videos you cannot access.

For ordinary HTML video players, it first tries webpage extraction. If that fails, it can try the player's direct HTTP media URL; completion explicitly says **player source; site quality unavailable** in that case. Precise social-post downloads do not silently fall back to lower-quality playback URLs. Blob URLs cannot be downloaded directly by a native process, so those need a supported page extractor. Generic multi-video pages and carousels can be ambiguous; the selected item index is best effort.

See [the verification record](docs/VERIFICATION.md) for what was actually tested.

## Update and remove

Run **Update.command** to copy the current helper source and update yt-dlp/site fixes, then close and reopen Chrome. If you changed extension code, click its reload icon in `chrome://extensions` and refresh video tabs.

Run **Uninstall.command** and remove the extension in `chrome://extensions` to uninstall. Downloaded files are preserved.

## Privacy and permissions

- Content scripts run on HTTP/HTTPS pages, including embedded frames, so the button can find ordinary `<video>` elements and their post links. Settings can hide the page buttons.
- `activeTab` reads the current page when you open the toolbar. `contextMenus` supplies the fallback menu. `storage` stores settings and session status. `nativeMessaging` talks to the helper.
- The native host accepts only this extension's fixed ID. There is no HTTP listener, exposed local server, external-message endpoint, `eval`, or shell evaluation of webpage input.
- Native messages are size-limited. Downloads accept public HTTP/HTTPS URLs, reject local file schemes, credentials, localhost and private IP literals, and write only under the configured output folder. These are input restrictions, not a comprehensive network sandbox for yt-dlp redirects or DNS.
- Optional Chrome-cookie access happens in the helper through yt-dlp, not a cloud service. Cookie values, full URLs, and downloader logs are not saved in the repository or extension history. Downloads necessarily contact the video site/CDN; cookies are used according to their domain rules.
- The manifest contains a **public** extension identity key; it is not a credential. A malicious local process with the same user privileges is outside the extension's security boundary.

Use for videos you have permission to save. Downloads and all account/browser data are excluded from this project's source and licenses.

## Development

No bundler or npm dependencies are required for the extension. Load `extension/` directly after edits.

```sh
npm test
npm run check:assets
```

For the real adaptive-stream integration test, run the following with a Python environment that has `requirements.txt` installed and FFmpeg/ffprobe on PATH:

```sh
python3 scripts/smoke_test.py
```

It synthesizes two video qualities and separate audio, serves them temporarily over loopback, downloads through the native host's framing/queue and real yt-dlp/FFmpeg, and verifies that the higher-quality video and audio are present in one file. Its test-only URL patch allows the loopback fixture; the production helper rejects loopback URLs. Temporary media is deleted afterwards.

## License

MIT, copyright Jonathan Mann. No downloaded videos, account data, or licensed media are bundled. yt-dlp, its dependencies, Node.js, and FFmpeg are separately installed tools with their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md) and [ASSETS.md](ASSETS.md).
