---
name: flow-generate-download
description: Generate exactly one image per prompt in Google Flow and download it as 2K Upscaled, returning evidence per prompt. Used by browser-operator at Stages 2-3.
---

> STATUS 2026-10-26: AUTOMATED GENERATION BLOCKED. First test prompt in
> project C-Day 182 returned "Failed - We noticed some unusual activity. Note
> that browser extensions that modify the page may cause issues." (not
> charged). This is Google's automation detection. Do NOT retry, slow down,
> or otherwise work around it. If this message appears: stop, return
> `"blocked": "flow_unusual_activity"`. Stages 2-3 are manual until Nathan
> decides otherwise.
>
> Verified 2026-10-26 (UI, viewport 1024x768):
> - Home lists projects; "New project" creates one named by timestamp.
> - Project name = textbox "Editable text" top-left. Clicking + typing inserts
>   mid-string; set it with form_input, then Enter.
> - Prompt box = textbox "What do you want to create?"; submit = button
>   "Start generation". Settings = button "Settings trigger" next to the model
>   chip: Image/Video, aspect 16:9 4:3 1:1 3:4 9:16, model dropdown,
>   outputs x1 x2 x3 x4, and "Generating will use N credits".
> - DEFAULT OUTPUTS ARE x2. This is why Day 181 has two images per concept.
>   Always set x1 and confirm the chip reads "x1" before submitting.
> - Download path VERIFIED 2026-10-26 (C182 k=1): single click on the tile
>   opens `/project/<id>/edit/<asset>`; "Show asset info" reveals the full
>   prompt text (use it to map tile -> k, never the filename); "More options"
>   (top-right) -> "Download media" -> submenu 1K Original size / 2K Upscaled /
>   4K Upscaled (locked, "Upgrade"). Clicking 2K shows "Upscaling your image,
>   download will start automatically". File lands as
>   `<Flow title>_2K_<yyyymmddHHMMSS>.jpg` via a `<uuid>.tmp`, ~30 s total.
>   Automated download clicks were NOT blocked (generation was).
> - The Claude desktop app showed a download confirmation dialog that Nathan
>   approved. The agent cannot approve it. Until it is set to allow
>   automatically, a download waits for Nathan.
> - DOWNLOAD VIA CLAUDE IN CHROME (verified 2026-10-26 15:27): Nathan's
>   Chrome with "Ask where to save" OFF saves 2K straight to Downloads, no
>   dialog. In Chrome the microstock account is the 2nd signed-in account:
>   project URL is `https://flow.google.com/u/1/project/<id>`; if Flow shows
>   "Project not found", the wrong account is active -> use Google's account
>   chooser and pick nathanrafael512 (never type a password; if a password is
>   requested, stop and ask Nathan). Chrome's wider viewport shows a direct
>   "Download media" button in the editor toolbar -> 1K / 2K Upscaled / 4K.
>   Use the built-in browser only as fallback (it opens a Save As dialog per
>   file that only Nathan can click).
> - Model defaults differ per browser: Chrome showed "Nano Banana 2.1" while
>   the built-in browser showed "Nano Banana Pro". Record the model from asset
>   info when available; Nathan must check the chip when generating.
> - Generation stays manual (Nathan). This skill now covers DOWNLOAD ONLY.
> Steps marked [VERIFY] below are still unverified.

# Job input
```json
{"project": "C-Day 182", "model": "Nano Banana Pro", "download": "2K Upscaled",
 "downloads_dir": "C:\\Users\\Nathan\\Downloads",
 "prompts": [{"k": 1, "aspect": "1:1", "prompt": "..."}]}
```
Only prompts the orchestrator sends are processed; it skips ones already done.

# Per run
1. Open https://flow.google.com. Sign-in page → `blocked`.
2. If project `<project>` exists, open it (resume). Else create it with that
   exact name. [VERIFY]
3. Settings panel next to the prompt box: model = job model, outputs per
   prompt = 1, aspect = per prompt. Credit cost shown > 0 → `blocked`. [VERIFY]

# Per prompt k
1. Set aspect, paste prompt, submit. Wait until generation finishes.
2. Count the new tiles this prompt produced. Not exactly 1 → record
   `tiles_for_prompt` truthfully and do not download (orchestrator fails k).
3. Open the tile (double-click), top-right ⋮ → "Download media" →
   "2K Upscaled". Never 4K, never "Original". [VERIFY]
4. Stay on the page and poll `downloads_dir` with device_list_dir until a NEW
   `*_2K_*.jpg` (not present before step 3, size stable over two polls)
   appears. Usually 10-25 s; give up after 120 s → `download: "timeout"`.
   Navigating away early cancels the download.
5. A Claude permission prompt or browser download prompt may appear. In the
   scheduled run these are pre-approved by the task's approval setting; if one
   still blocks, return `blocked` rather than working around it.

# Output
```json
{"project": "C-Day 182", "results": [
  {"k": 1, "tiles_for_prompt": 1, "tile": "<tile id or position>",
   "download": "ok", "file": "<name>_2K_<...>.jpg", "bytes": 1234567}
], "blocked": null}
```
`download` ∈ ok | timeout | not_attempted. Never report ok without the file
name and size observed in `downloads_dir`.
