# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People who clone this repository and run it for themselves. They change the city, zodiac, and data sources, then use the result as their own desktop wallpaper.

## Product Purpose

one-wallpaper is a wallpaper composer. The person using it places blocks on a grid and points each block at their own API, then generates a desktop wallpaper from that layout.

Success is a wallpaper they configured: their blocks, their endpoints, on their machine.

## Positioning

The built-in blocks — portrait, date and lunar calendar, weather, AI news, a one-line quote, and horoscope — are a loadable example, not the product. A scenic wallpaper or a fixed daily dashboard could not truthfully claim that the layout and the endpoints are the user's to define.

## Operating Context

The composer is an Electron window (`src/composer`). Generating runs in the main process: fetch, capture the wallpaper page to a PNG, and optionally set the Windows desktop wallpaper with `set_wallpaper.ps1`. A scheduled task can launch the same program with no window. Config and the PNG live in the app data directory. The first launch seeds that config from the repository `config.json`.

The live surface is a Lively Wallpaper page (`lively/index.html`, titled 每日信息壁纸). It refreshes from the network and falls back to the last baked snapshot.

## Capabilities and Constraints

- Users arrange a grid of blocks, set each block's endpoint, choose resolution, and save to `config.json`.
- 「载入内置示例」loads the original six blocks: portrait (今日老婆), calendar, weather, news, quote (毒鸡汤), and zodiac. Loading does not write config until save.
- Generation produces a static PNG in the app data directory and can set it as the desktop wallpaper.
- The app is Electron, Vue 3, and Node. It does not run Python. `lively/index.html` remains a separate Lively page and is not baked by this app. Setting the wallpaper uses `set_wallpaper.ps1`.
- Not confirmed as requirements: the portrait must stay uncropped and unmasked; content must stay above the taskbar; a failed API must still produce an image; the interface must stay Chinese-first; the product must remain Windows-only.

## Brand Commitments

The repository name is one-wallpaper. The Lively wallpaper title is 每日信息壁纸. Author credit in the Lively manifest is Liwncy. License is MIT.

## Evidence on Hand

- `README.md` describes the original fixed dashboard and its data sources.
- `config.json` holds the current grid, the example areas, and defaults (city 潍坊, zodiac 处女) that a cloner is expected to replace.
- `src/composer` is the composer.
- `lively/` is the live wallpaper (`index.html`, `LivelyInfo.json`, baked `data.js`).
- `docs/preview.png` and `output/` are generated wallpaper images.

Do not invent testimonials, user counts, or third-party endorsements.

## Product Principles

1. The product is the composer: blocks, layout, and endpoints belong to the person who runs it.
2. The six original panels are an example that can be loaded, not the definition of the product.
3. Someone who clones the repo must be able to change city, zodiac, and data sources and run it themselves.
4. Generation delivers a static PNG and can set it as the desktop wallpaper.
