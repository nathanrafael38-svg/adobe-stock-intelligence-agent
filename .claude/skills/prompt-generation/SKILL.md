---
name: prompt-generation
description: Write the daily 20-prompt plan (8 illustrations, 12 photos) for Adobe Stock in the plan.json format that msp/plan.py validates. Used by the orchestrator at Stage 1.
---

# Inputs
- `config/pipeline.json` → `composition`
- `history.txt`: one line per previous concept/title (orchestrator builds it
  from all `Metadata/adobe-metadata.csv` files under `1. Dari Claude`)

# Mix (Nathan's existing rule, unchanged)
- 8 illustrations, aspect `1:1`: line art, watercolor, kawaii/sticker, seasonal.
- 12 photos, aspect `16:9`: concrete subjects with a clear use context — work
  and money, food preparation with hands, gifts and seasonal, vintage objects
  macro, home life.
- No video, no generic landscapes, no generic portraits, beauty at most 2.
- One concept per prompt. Two prompts must not describe the same subject in
  different words (Day 181 failed this four times).

# Avoid subjects that make the model invent text
Forms, labels, signs, numbers, keyboards, typewriters, dials with digits,
book pages, newspapers, receipts, calendars, posters, menu boards.

# Prompt body
Specific subject, material, action, setting, light. Then the suffix,
verbatim, from `msp/plan.py` (`ILLU_SUFFIX` or `PHOTO_SUFFIX`).

# Output: plan.json
```json
[{"concept": "short noun phrase", "type": "illustration", "aspect": "1:1",
  "beauty": false, "prompt": "<body>. <suffix>"}]
```
Run `python -m msp.cli init ...`. If it exits 2, fix only the listed errors
and rerun. Warnings about earlier concepts: replace those prompts.
