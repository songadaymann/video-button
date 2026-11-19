# Separately installed tools

This repository contains our MIT-licensed extension/helper code and Jonathan Mann's vendored open-source asset checker. It does not redistribute third-party executable binaries or Python packages.

- [yt-dlp](https://github.com/yt-dlp/yt-dlp): Unlicense for its source, with component notices in its repository. Installed by pip with the `default` dependency set, which includes yt-dlp-ejs and its own notices. Python packages retain their licenses in the local environment.
- [FFmpeg](https://ffmpeg.org/legal.html): LGPL/GPL depending on the installed build. Invoked as a separate process by yt-dlp. Install your own build; none is bundled here.
- [Node.js](https://github.com/nodejs/node/blob/main/LICENSE): MIT and third-party component notices. Invoked by yt-dlp for JavaScript challenge support; no Node binary is bundled.
- [Python](https://docs.python.org/3/license.html): PSF and component notices. Used for the helper/runtime; no interpreter is bundled.

Downloading a video does not change its copyright or license. Saved videos and browser data are not covered by this repository's MIT license.
