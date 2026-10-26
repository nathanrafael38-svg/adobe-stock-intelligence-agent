---
name: flow-download
description: Procedure for downloading exactly one 2K image per prompt from a Google Flow project (C-Day N) in the built-in browser and matching each download to its prompt. Used by browser-operator in download mode.
---
# Stage 2/3 — find tile, download 2K, match

Account: the microstock Google account (Nathan's Flow account for microstock).
If the Flow page shows a different account, or asks to sign in → `blocked: wrong account`.

## Per batch
1. Open `https://labs.google/fx/tools/flow` → project named exactly `C-Day N`.
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

## Things that go wrong
- Aspect: Flow keeps the last ratio. If a 16:9 prompt's tile is square, still
  download and report `aspect_seen: 1:1` — tech QC rejects it; do not regenerate.
- Same download name twice → the newest mtime wins; report both names.
- A download dialog you do not recognise → screenshot, stop that k, report.
