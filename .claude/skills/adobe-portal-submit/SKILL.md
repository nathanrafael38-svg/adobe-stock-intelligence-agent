---
name: adobe-portal-submit
description: Prepare and (only after explicit batch approval) submit SFTP-uploaded files in the Adobe Stock contributor portal - category, generative-AI label, fictional people/property, title/keyword check. Used by browser-operator in prepare/submit modes.
---
# Stage 6b — Adobe portal

Portal: `https://contributor.stock.adobe.com/` → Uploads (files arrive here after SFTP;
processing can take minutes). Nathan logs in himself; if a login/2FA/CAPTCHA appears →
`blocked`.

## Verified requirements (Adobe "Generative AI content guidelines", Oct 2026)
- Tick **"Created using generative AI tools"** for every file of this pipeline.
- Tick **"People and Property are fictional"** when the image shows a person or
  property that only resembles real ones; leave it unticked when there are none.
- No artist names, real people, characters, third-party IP in title/keywords.
- Do not submit multiple near-identical versions of one prompt.

## prepare (no submit)
1. Filter/locate exactly the filenames given (C{N}_kk.jpg). Ignore all other files —
   Nathan's own unsubmitted files are not part of this batch.
2. For each file: check the title and keyword count the portal read from IPTC
   (`title_seen`, `keywords_seen_count`); set Category from input; set the AI label;
   set fictional per input. Save/close without submitting.
3. If a file is missing in Uploads → `{filename, error: "not in portal yet"}`.
4. Screenshot the list showing the files ready; report.

## submit (requires `APPROVAL: C{N} approved by Nathan` in the task)
Select exactly the prepared files → Submit → confirm Adobe's dialogs that belong to
submission (content agreement checkbox only if it is the standard submit attestation —
otherwise stop and report the text). Report the confirmation message verbatim.
Never submit files not listed. Never re-submit a file already in "In Review".
