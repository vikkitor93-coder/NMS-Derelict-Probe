# Public test site, sharing, top-by-modules maps (2026-10-24)

URL: https://vikkitor93-coder.github.io/nms-derelict-atlas/ (GitHub Pages, branch main, path /; password gate on). The password is NOT in any file: only a salt and its SHA-256 are in `tools/public_site_gate.json` and the published `config.js`.
Atlas commits pushed (plain fast-forward, under `atlas.repo_lock`): 6c6dc22, b3d5bca, fabb25c. Backups: `<file>.pre-public-site-20261024`.

## 1. Maps for the top 100 by frigate modules
- Index `map` column: 0 none, 1 top crates, 2 top modules only, 3 both (94 / 94 / 6 systems). Tie-break: modules desc, then total, crates, glyphs, galaxy (`build_atlas_index.top_modules / map_kinds / map_rows`; `top()` and `TOP_N` unchanged).
- `views/top100.json.gz` (name kept) holds 194 systems, each layout once, plus `k` (list marks). 168,496 B -> 293,094 B (+124 KB).
- `build_bundle(layouts, piece_index)` keeps its signature. It completes the modules-only layouts itself from the atlas that `build()` just indexed (`build_atlas_index.LAST`), so the scanner's next publish works with no scanner edit. Two builds are byte-identical (e1/e4).
- Viewer: chips "Top crates" / "Top modules" in the table and on the system page; a "List" filter (Any / Top crates / Top modules).
- Regression checks updated: e3, new e3b, e4, e6, new e7.

## 2. Sharing (local viewer and public site)
- Copy link (`<siteBase>#/d/<address>`), Share (`navigator.share`, copy fallback; for systems with a map it shares the preview-card link), Save image (canvas PNG: floor maps, 3D view or counts only; lookalike glyph SVGs; counts; link; share sheet on touch devices, download on desktop). Code: `viewer/static/share.js`; `view3d.js` got `snapshot()`.
- Cards: `tools/build_share_cards.py` (stdlib, deterministic, prunes stale ones): `s/<ADDR>.html` (Open Graph + Twitter tags, noindex, redirect to `../#/d/<ADDR>`) and `s/<ADDR>.png` (800x420). 388 files in `s/`, 888 KB in total for 194 systems, plus `preview.png` (2 KB) as the generic preview for systems without a map.
- Not yet in the scanner's `_derived_files` (REQUEST posted: `import build_share_cards; paths = build_share_cards.build(atlas)` after `tb.build_bundle`).
- "Open in..." menu: NMS Almanac (`/system/euclid/<GLYPHS12>`, hidden for non-Euclid galaxies) and NMS Hub map (`?arrival=1&addr=<GLYPHS12>&galaxy=<0-based>`). One config array `EXTERNAL` in share.js. Text links only, new tab, `rel="noopener noreferrer"`, `referrerpolicy="no-referrer"`, note "External sites, not affiliated." No API calls, no fetching. curl on 3 systems: all 6 URLs returned HTTP 200 (both look like single-page apps, so 200 alone does not prove the page shows the system).
- Credits: `#/about` page plus footer link ("Not affiliated with Hello Games" in the footer); `credits.js` lists NMS-Shipwright first, then three.js, with a marker comment for nms_namegen; a "Links to" group lists NMS Almanac and NMS Hub (elegra1965) as external, not affiliated. The atlas README has the same sections.

## 3. Public static site
- `tools/build_public_site.py ATLAS` copies a whitelist only (it refuses glyphs/, models/, compact/ and any image or mesh file), writes `config.js` (staticSite, siteBase, noindex, gate), `robots.txt` (Disallow: / while gated), `.nojekyll` and an index.html with OG tags. Gate off: `--gate off`, or set `gate.enabled` to false in the published `config.js`. The base URL lives in one place: `viewer/static/config.js` `siteBase`.
- Static mode: data comes from the same origin (`./index/systems.csv.gz`, `./views/top100.json.gz`, regions); the Done list falls back to localStorage; no `/api` calls. The local viewer is unchanged (`staticSite:false`).
- Published: 32 site files = 937 KB (vendor/three 692 KB of it); cards 388 files = 888 KB; bundle 286 KB; index 2.5 MB (already existed).
- Verified live with curl: `/` (200, OG tags), robots.txt, config.js, index (map counts 94/94/6) and bundle (194 systems, 194 marks), a card HTML (correct OG/Twitter tags, redirect) and card PNG, preview.png, a region file, `.nojekyll`; `/glyphs/0.png` and `/models/...` return 404. A headless Firefox screenshot of the live deep link `#/d/0000090004609CAD` shows the password gate.
- The unlocked site was tested only on a local copy with the gate off (About page, system page with maps and chips, Save image output). I did not enter the password on the live site.

## Excluded or uncertain (game-derived)
- Not published: `viewer/static/glyphs/*.png` (official icons), `viewer/static/models/containers-ultralow/*` (glb meshes + texture atlas), `viewer/static/compact/` (experiment data, not needed). The 3D view falls back to its built-in markers.
- Published but game-DERIVED DATA, not assets: `piece_props.json` (20 KB: scene names, prop positions, rotations) and the bundle's piece table (the same kind of data was already published). I could not classify these as clearly "not from the game", so I am flagging them. Say if you want them removed; maps need them.
- three.js (MIT) with its licence file.

## Tests actually run
- `python -I tools/regression_test_705.py`: 26 passed, 0 failed, 1 skipped (b, needs --full). Includes e1-e7 and h1-h3 (names, another agent's).
- `python -I tools/derelict_view.py --verify`: 1872 layouts, 0 different.
- `node tools/check_compact_view.js`: top100 100/100 identical, local 1672/1672 identical.
- Local viewer http://127.0.0.1:8765/ serves (/, config.js, share.js, credits.js 200; f1-f4 pass).
- NOT tested: the 3D-view image, Share on a phone (no WebGL or phone here), and the gate's success path in a browser (the hash was checked in Python only).

## What you must do
- Open the site, enter the password, try a deep link and Save image on a phone.
- Decide about `piece_props.json`.
- robots.txt Disallow also stops some link-preview bots, so previews may not show in some apps while the gate is on. The card PNGs and text are readable by URL even though the viewer is gated.
- Scanner: its first publish after this rebuilds the bundle (modules-only layouts are generated if missing, about 2 minutes). Optional: add the card call.
