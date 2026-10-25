---
name: flow-generate-download
description: Generate exactly one image per prompt in Google Flow and download it as 2K Upscaled, returning evidence per prompt. Used by browser-operator at Stages 2-3.
---

> UI steps below come from the routine that produced Day 181 on 2026-10-24.
> They are NOT yet re-verified. Marked [VERIFY] = confirm on the first test
> run and update this file.

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
