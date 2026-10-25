---
name: adobe-portal-prep
description: In the Adobe Stock contributor portal, find the uploaded files of one batch, set file type, category and AI declarations, and either stop at review (prepare) or submit (only with recorded approval). Used by browser-operator at Stage 6b.
---

> NOT YET VERIFIED. The portal UI has not been inspected in this project.
> First run: `mode: "inspect"` only — read the page, map the controls,
> rewrite this file with the real steps, change nothing in the portal.

# Job input
```json
{"mode": "inspect|prepare|submit",
 "files": [{"filename": "C182_01.jpg", "type": "illustration", "category": 8,
            "has_people_or_property": false}],
 "submit_approved_by": null}
```

# Requirements from Adobe's generative-AI guide
- Tick "Created using generative AI tools" on every file.
- Tick "People and Property are fictional" when a person or property is
  depicted (even fictional); leave unticked when none appears.
- File type: Photos only if camera-realistic with accurate anatomy;
  otherwise Illustrations. Our `type` field maps directly.
- Category: the number from the batch state.
- Do not add "generative AI" to title or keywords (already enforced).

# Procedure (to be confirmed in inspect mode)
1. Open the contributor portal uploads page. Sign-in or CAPTCHA → `blocked`.
2. Select only files whose names are in `files`. A file of the batch not
   found → report it as `missing` (upload not yet processed); do not touch
   others.
3. Apply fields per file. Read every field back from the page.
4. `prepare`: stop before Submit. Return the per-file readback.
5. `submit`: only if `submit_approved_by == "nathan"`. Submit exactly the
   prepared files, then read the confirmation message.

# Output
```json
{"mode": "prepare", "found": ["C182_01.jpg"], "missing": [],
 "configured": [{"filename": "C182_01.jpg", "type": "Illustrations",
   "category": "Graphic Resources", "ai": true, "fictional": false}],
 "submitted": [], "portal_message": "...", "blocked": null}
```
Submitted ≠ accepted. Acceptance is read later from the portal's status tabs.
