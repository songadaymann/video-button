# Assets

The code in this repository is covered by [LICENSE](LICENSE). This file covers everything that isn't code: where each asset came from, what you may do with it, and how to get the assets that aren't included.

## 1. Ours: included and open

Unless a row says otherwise, original art, music, sound, video, and 3D files made by Jonathan Mann for this project are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit "Jonathan Mann (Song A Day)". Media generated with an AI tool from our own prompts, with no one else's art, audio, likeness, or trademark as input, counts as ours: name the tool under "Made with".

No art, audio, video, fonts, or third-party media are bundled. The arrow mark is text styled in CSS. The integration test synthesizes temporary test media and deletes it afterward.

## 2. Free third-party: included under their own licenses

No third-party media is included. Separately installed program dependencies are described in [THIRD_PARTY.md](THIRD_PARTY.md).

<!-- assets.mjs:begin (generated from private-assets.json by `node scripts/assets.mjs docs`; edit the manifest, not this block) -->

## 3. Licensed (paid or restricted): not included

These files keep their normal paths, but their bytes are not in the public repository. A public checkout gets same-size placeholders from `node scripts/assets.mjs sync`, so it still builds and runs. To build the full version, get your own copy of each pack, then run `node scripts/assets.mjs import <download>` and `node scripts/assets.mjs sync`. Files Jonathan edited (recolours, crops, recompressions) stay placeholders unless you place your own copies by hand.

None.

## 4. Not ours and not licensed: never in the repo

Each one is listed so nobody wonders why it is missing. The public build gets a placeholder at the same path, so ids and saved data keep working.

None.

<!-- assets.mjs:end -->

## Runtime content that is not in this repository

User-selected video downloads remain in the configured download folder outside this repository. Their original copyright and licenses apply; the project's MIT license does not cover them. Browser cookies, Chrome profiles, helper configuration, download history, and logs are never included in the source.

## Never commit

Ripped songs or videos, press, stock, or Getty photos, photos or likenesses of real people, other NFT collections' art, screenshots of commercial software, the source files of paid asset packs, voice models with noncommercial terms, and personal data.
