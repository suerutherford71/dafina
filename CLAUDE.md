# Dafina — design inspiration catalogue

A local web app that organises, describes and labels the user's design inspiration.

- Start: double-click `Start Catalogue.command` (or `python3 server.py --open`) → http://localhost:4610
- `sources/` — the user's own folder tree and the source of truth: top-level folders = categories, nested folders = sub-categories. The user changes it in Finder; the app re-reads it every ~2.5 s. Don't reorganise it unless asked. Folder names are lowercase on disk; the UI only *displays* them capitalised.
- `catalogue.json` — labels, matched to images by content `hash` so they survive moves/renames. Category comes from the folder, not the JSON.
- `server.py` — standard-library Python server: `/api/state`, `/api/version` (live polling), uploads (bulk, keeps dropped folder structure), edits (changing category/sub-folder moves the file), deletes (to `trash/`), Refero import (`/api/refero`: screenshot + link + description + DESIGN.md), thumbnails via `sips` cached in `~/Library/Caches/DesignInspirationThumbs`. CLI: `--pending`, `--save <file>`.
- `index.html` — the whole UI, styled after mishmash.pt (soft grey ground, Plus Jakarta Sans, rounded pastel cards, black rounded buttons).
- Ways in besides uploads: `/api/website` (Add → Websites tab; screenshots a URL with the Mac's own Chrome in the background, saves link + page title/description; Refero links are routed to the Refero importer), `/api/imageurl` (an image by URL), `/api/categories` (category and sub-folder names only).
- `chrome-extension/` — the **Save to Dafina** Chrome extension (MV3, loaded unpacked): toolbar popup saves the visible tab or a longer capture; right-click saves an image or the page. Talks to `http://localhost:4610`.
- `figma-plugin/` — the **Save to Dafina** Figma plugin (development plugin, Figma desktop app only): exports selected frames as PNG and uploads them with a "From Figma: file › page › frame" note. Figma doesn't give it the file link.
- Security: POSTs need JSON and an allowed Origin (this app, the Chrome extension, or no Origin). The Figma plugin's sandbox (Origin `null`) may only use `/api/categories` and `/api/upload`; it can never edit, move or delete.
- `/api/renamefolder` renames a category or sub-folder on disk (the ✎ Rename button on the folder row); refuses if the new name clashes, and keeps `categoryOrder` in step.
- `/api/openclaude` brings the Claude app forward (the "Label with Claude" button on the Awaiting labels page).

Public release (free, GitHub `suerutherford71/dafina`):
- This folder is the git repo. `.gitignore` ignores everything except the app files, so `sources/`, `catalogue.json`, `trash/`, `Share/` and `Exports/` (the user's own library) are never published. Add any new app file to the allow-list there.
- `install.sh` — the one-line installer (`curl … | bash`): installs to `~/Dafina`, checks for Python/Command Line Tools, keeps an existing library on update, makes the 17 starter category folders on a fresh install.
- `website/` — the marketing page (free + Ko-fi donations), published to GitHub Pages by `.github/workflows/pages.yml`. Links to fill in are in the `CONFIG` block at the bottom of `website/index.html`.
- `LICENCE.txt` — free to use (incl. client work), no reselling.

When the user asks to "label my dafina" (or the older "catalogue my inspiration" / "catalogue my inbox") / label new images, follow `.claude/skills/catalogue/SKILL.md`.

The user writes British English ("colour", "catalogue") — keep that in UI text and entries.
