---
name: catalogue
description: Catalogue new design-inspiration images. Use when the user says "label my dafina", "catalogue my inspiration", "catalogue my inbox", "label my new screenshots", or adds images to sources/. Looks at every image that has no labels yet and writes a title, descriptors, labels, palette, design brief and an image-prompt recipe into catalogue.json.
---

# Catalogue new inspiration

How the library works:

- **`sources/` is the source of truth.** Top-level folders are categories, nested folders are sub-categories (any depth): `sources/cards/lucy/birthday/x.png`. The user reorganises these in Finder whenever they like — never rename, move or "tidy" their folders or files unless asked.
- **`catalogue.json`** holds labels as `{ "entries": [ … ] }`. Each entry is matched to its image by `hash` (a content fingerprint), so labels survive moves and renames. `path` is just the last known location. Category/sub-category are NOT stored — they come from the folder.
- **Item references.** The app's *Copy reference* button (and the copy icon on each card) produces a line like `“Sleeping Fox” — Clipart › Christmas Woodland Animals PNGs › PNG-06.png · id 1a2b3c4d5e6f7a8b`. The `id` is the entry's `hash` — find the entry by it in catalogue.json (or by hash in `/api/state`), even if the title, folder or file name in the line is out of date. To change labels on an existing item, write `{hash, <changed fields>}` and run `--save` as below; to move or rename it, use the app's Edit or ask before touching files.
- **Category pill order.** The user can drag the category pills into their own order; it's stored as `"categoryOrder": [folder names]` at the top level of catalogue.json (new categories go at the end). To reset it, POST `{"order": []}` to `/api/order` on the running app, or remove the `categoryOrder` key. Keep it when editing the file.
- An image is "awaiting labels" until its entry has a `title` and `tags`. Entries may already hold `source` (link), `notes` (user's note), and for Refero imports `designMd` (full DESIGN.md) + `refero`. Keep those.

## Steps

1. Run `python3 server.py --pending` from the Dafina folder. It prints JSON for every unlabelled image: `hash`, `path`, `category`, `sub`, `source`, `notes`, `refero`, `hasDesignMd`. If it's empty, say everything is already catalogued.
2. If there are many (more than ~25), tell the user the count and do them in batches, saving after each batch.
3. For each image **open it with the Read tool and look properly**. Describe only what is visible — never invent text, brand names or details. Use the folder (`category` › `sub`) and the user's `notes` as context. For Refero items with `hasDesignMd`, read the entry's `designMd` from catalogue.json and take the exact hex colours and font names from it.
4. Write the new labels to a scratch JSON file (a list of objects, each with `hash` plus the fields below — omit `source`/`notes`/`designMd` unless changing them), then run `python3 server.py --save <that file>`. It merges by hash and keeps existing fields. Don't hand-edit catalogue.json unless the helper fails.
5. Reply with a short table: title · where (category › sub) · style line. The open app updates by itself within a few seconds.

## Fields

```json
{
  "hash": "d116529017280707",
  "title": "Stillness",
  "style": "editorial x voxel 3D",
  "summary": "A meditation landing-page hero where the landscape is built from blocks — digital material, calm subject.",
  "tags": ["voxel-rendered landscape", "pixel mountains and river", "clean white ground", "muted blue-coral-green palette", "soft pill product buttons", "floating diorama illustration"],
  "palette": [{"hex": "#F6F5F0", "name": "white ground"}, {"hex": "#1F6F8B", "name": "slate teal"}, {"hex": "#E07A5F", "name": "coral"}],
  "typography": "…",
  "layout": "…",
  "mood": ["calm", "playful-precise", "airy"],
  "brief": "2–4 practical sentences a designer could use to recreate this look.",
  "recipe": "[SUBJECT: …] built entirely from …",
  "added": "YYYY-MM-DD"
}
```

### Writing guidance

- **title** — 1–3 words. The visible brand/product name if there is one; otherwise an evocative name for the style.
- **style** — lowercase line naming the blend, `x`-separated: "warm editorial x print DNA", "watercolour x storybook whimsy".
- **tags** — 5–8 concrete, visual, reusable labels (3–5 words, lowercase). Name the *technique* and *material*, not praise: "halftone CMYK dot texture", "loose wet-on-wet watercolour", "giant cropped footer wordmark". Most distinctive first (the first 3 show on the card). Reuse existing tag wording from catalogue.json where it fits so filters connect entries.
- **palette** — 3–6 colours sampled by eye (or from DESIGN.md), dominant first, each with a short name.
- **typography / layout** — only where there's type or a layout (skip for photos, textures, clipart).
- **mood** — 2–4 single words.
- **recipe** — one paragraph image-generation prompt reproducing the *visual language* with a swappable subject. Always start with `[SUBJECT: <what's in this image>]`. Then medium/technique, STRICT palette (and what to avoid), lighting, composition, background, space for typography where relevant. No brand names, logos or artist names. Tailor to the category:
  - **web design / emails / brochures / journals** — the hero or key illustration style, plus "generous empty space for typography".
  - **logos** — "flat vector logo mark of [SUBJECT] …, centred on plain background, no text, no mockup"; describe the construction.
  - **brand boards** — "brand identity board for [SUBJECT] … grid of logo, swatches, type specimen, photography, pattern tile".
  - **ui kits** — "UI component sheet for a [SUBJECT] app … buttons, inputs, cards, toggles, consistent radius/shadows".
  - **cards** — "greeting card front, 5×7 portrait, [SUBJECT] … with clear space for a short message"; note the occasion from the folder (birthday, christmas…).
  - **digital paper** — "seamless digital paper of [SUBJECT] …, square 12×12 in, 300 dpi, edge-to-edge, flat, no shadows, tileable".
  - **patterns** — "seamless repeating pattern of [SUBJECT] …, tileable, motif scale & spacing, background colour".
  - **textures** — "close-up seamless texture of [SUBJECT] … surface detail, even lighting, no perspective, tileable".
  - **colour palettes** — "[SUBJECT: a scene that embodies this palette] … colour story strictly limited to <colours>"; describe the palette relationships in tags.
  - **images (photos/illustrations)** — camera/lens or illustration medium, light, time of day, colour grade, framing.
  - **paintings / mixed media** — medium, brushwork/marks, layering, paper/canvas surface, edges.
  - **clipart** — "isolated [SUBJECT] clipart, <medium e.g. watercolour>, on pure white background, no shadow, clean edges for cut-out, PNG-ready".
  - **mockups** — "photorealistic mockup scene: [SUBJECT: the product/artwork placed in it] in a <room/device> …, lighting, props, camera angle, blank area for artwork".
