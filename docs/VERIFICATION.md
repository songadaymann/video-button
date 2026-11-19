# Verification — 2026-11-19

## MP4 + MP3 update (v0.2.0)

Every successful download now saves a matching MP4 with sound and a 320 kbps MP3. The installer's default is the main `~/Downloads` folder; the existing Mac helper was explicitly configured to that folder. No existing downloaded files were moved or deleted.

- Five Node tests and seven Python tests pass, including preserving existing downloads when publishing a numbered MP4/MP3 pair.
- Real native-host/yt-dlp/FFmpeg integration: selected the 720p track over a 360p alternative, saved an MP4 with AAC sound and a separate 320 kbps MP3. Both outputs were decoded and checked for a nonzero audio signal.
- VP9/Opus WebM: VP9 video preserved in MP4, Opus converted to AAC for that MP4, separate MP3 verified with audible signal.
- VP8/Opus WebM: unsupported MP4 video codec converted to H.264 at the original 320×180 resolution, plus AAC sound and MP3; both sound tracks verified.
- A repeated download preserved the first pair and produced a second matching numbered pair. Temporary sources were removed. A silent source returned an error without claiming audio exports or leaving partial files.
- The updated installed helper reports v0.2.0 and the main Downloads directory through its native handshake. Existing Chrome/helper connections require a Chrome restart or extension reload to activate the update.

The browser-installation limitation described below still applies; these tests verify the actual native pipeline and source-level extension checks, not a live installed-extension interaction.

## Initial v0.1.0 verification (historical)

Versions: macOS/Apple Silicon, Python 3.11.17, Node.js 22.23.4, yt-dlp 2026.10.26, yt-dlp-ejs 0.8.0, FFmpeg/ffprobe 9.0.2.

## Automated checks

- Five Node tests cover social-post matching, tracking-URL cleanup, unsafe URL rejection, background message boundaries, opt-in cookies, and native disconnect reporting.
- Six Python tests cover unsafe native URL rejection, bounded native framing, best-quality format selection, optional browser cookies, profile-path restrictions, redacted errors, and unsupported actions.
- The real adaptive-stream smoke test generated a 720p stream, a 360p alternative, and a separate AAC audio stream. The native host queue/framing and yt-dlp selected 720p plus AAC; FFmpeg combined them into exactly one file. ffprobe confirmed both original H.264 and AAC streams were preserved.
- The installed native host replied successfully through Chrome's length-prefixed JSON protocol. A different extension origin was rejected.

## Public-site checks (without cookies)

These are individual examples, not a site-wide compatibility guarantee. Metadata checks used actual extractor requests but did not save videos unless marked “downloaded.”

| Site | Example | Result |
| --- | --- | --- |
| YouTube | `YE7VzlLtp-4` (upstream test fixture) | Metadata: 49 formats; selected 1080p video with separate audio |
| TikTok | `@patroxofficial/video/6742501081818877190` (upstream fixture) | Downloaded: H.264 + AAC, 2,748,647 bytes; ffprobe confirmed 540×960. Upstream metadata labeled it differently, so completion now probes the saved file for accurate dimensions |
| Instagram | `reel/Chunk8-jurw/` (upstream fixture) | Metadata: 9 formats; selected portrait video with reported height 1280 |
| X/Twitter | `CTVJLaidlaw/status/1600649710662213632/video/2` (upstream fixture) | Metadata: 9 formats; selected HLS video plus separate audio; reported portrait height 1280 |
| Ordinary HTTP media | W3Schools HTML `mov_bbb.mp4` fixture | Downloaded: 788,493 bytes; ffprobe confirmed H.264 video and audio |

An older Star Wars Twitter fixture resolved to a dead Amplify domain and failed with a “Domain Not Found” response. Error handling reports that failure instead of claiming a download succeeded. No authentication, Chrome cookies, DRM content, or private posts were used in testing. Test downloads remain outside the repository.

## Browser UI checks and remaining verification

The actual popup, settings, and content-script files were served in a temporary local preview with a fake Chrome API. Chrome rendered the panel and settings, displayed the overlay on a `<video>` element, and a real user-input click moved the button into its queued state. Preview download data was simulated; no claim is made that this was an installed-extension test.

Automated navigation to `chrome://extensions` was rejected by the browser security policy, which allows only HTTP/HTTPS navigation. Therefore the extension has **not yet been loaded into the user's actual Chrome profile**. Loading `extension/` manually, refreshing a video tab, and checking that the popup says “Local helper ready” are the remaining installation checks. Actual website-feed overlay layouts, authenticated downloads, carousels, and browser restart behavior need live testing after that step.

No test demonstrates universal site support or DRM removal. yt-dlp extractor updates can change these results.
