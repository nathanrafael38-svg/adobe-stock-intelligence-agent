# Stage 2/3 — find tile, download 2K, match

Account: the microstock Google account (`…512@gmail.com`). Edge has several Google
accounts; Flow opens with the default (`…38`). Check the avatar menu; if it is not the
microstock account use *Switch account* and pick it (URL becomes `flow.google.com/u/1/`).
Never pick another account and never sign in with a password → `blocked: wrong account`.
Downloads land in `C:\Users\Nathan\Downloads\Buat Claude` (Edge setting, set by Nathan).

## Per batch
1. Open `https://labs.google/fx/tools/flow` (redirects to flow.google.com) → project named exactly `C-Day N`.
   Missing project → return `{error: "project not found"}` for all k.
2. Read every tile once (read_page/get_page_text) and build a list of tiles with
   their prompt text (open tile details if the grid does not show the prompt).

## Per k (in order)
1. Match: the tile prompt must equal the plan prompt after whitespace normalisation
   → `prompt_match: exact`. If only the first sentence matches → `differs` (still
   download, the orchestrator sends it to review). No tile → `{k, error: "not generated"}`.
   More than one tile for one prompt → take the newest, report `extra_tiles: n`.
2. Failed tile ("Failed", "unusual activity", policy notice) → `{k, error: <text>}`.
   Do not retry generation.
3. Download → choose **2K**. A confirmation dialog may appear: confirm it (standing
   auto-approval). Never choose 1K or 4K/upscaled.
4. Wait for the file: list the Downloads folder (device_list_dir) until a new
   `*_2K_*.jpg` newer than the click appears (max 60 s). Record its exact name.
5. Stage it with device_stage_files and return `staged_path`.

## Verified UI (2026-10-26)
- Tile `img[alt="Tile displaying a user's image"]` → click opens `/edit/<id>`; the page text
  contains the full prompt (longest line) and the tile title after `arrow_back`.
- `button[aria-label*="Download media"]` → menu `button[mat-menu-item]`: `1K Original size`,
  `2K Upscaled`, `4K` (paid). Click 2K; a toast "Upscaling your image, download will start
  automatically" appears, then the file saves as `<Title>_2K_<YYYYMMDDHHMMSS>.jpg`. There is
  no confirmation dialog in this flow.
- One tile takes ~20 s. Run the loop inside the page as a fire-and-forget async function
  storing results in `window.__dl` and poll it (a single JS call times out after 45 s).
- Match tiles to prompts by exact normalised prompt text (hash both sides), not by order.
- Required model: **Nano Banana Pro** (Nathan's decision, 2026-10-27). Flow's default is
  Nano Banana 2 Lite and it may also offer Nano Banana 2.1. Read the model label from the
  composer and, when shown, from each tile's details, and return `model_seen` per k
  (`"unknown"` if Flow does not show it). Do not change the model and do not regenerate.
  C-Day 183 and 184 were generated with "Nano Banana 2.1".

## Things that go wrong
- Aspect: Flow keeps the last ratio. If a 16:9 prompt's tile is square, still
  download and report `aspect_seen: 1:1` — tech QC rejects it; do not regenerate.
- Same download name twice → the newest mtime wins; report both names.
- A download dialog you do not recognise → screenshot, stop that k, report.
