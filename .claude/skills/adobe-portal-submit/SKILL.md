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

## Verified portal behaviour (2026-10-26)
- Uploads page = tab **New**; right panel per file: `select[name=contentType]`
  (Illustrations/Photos), `select[name=category]`, checkboxes "This is Illustrative
  Editorial content" (**never tick**), "Created using generative AI tools", then
  "People and Property are fictional"; radio Recognizable people Yes/No (hidden once
  fictional is ticked); "Save work" bottom-left. Title/keywords are read from IPTC/XMP.
- Coordinates shift when checkboxes expand — use DOM (label text) not pixels; the first
  pixel click on C183 hit the Editorial box by mistake.
- **"Include in submission" auto-ticks for every complete file, including Nathan's own
  files.** The "Submit N files" button submits all ticked files. Before submit, untick
  every non-batch file (record the list for Nathan) until the button shows exactly the
  batch count, then re-verify each ticked file's name.
- Submit opens **Terms and conditions** (two attestation checkboxes: guidelines incl.
  no IP / AI declared / no artist reference, and account-suspension acknowledgement).
  Ask Nathan before ticking them unless he has pre-approved for this batch.
- Continue may trigger an **Adobe CAPTCHA** ("Verify you are a human"). Stop; Nathan
  solves it; then verify in the **In review** tab before marking `submitted`.

## submit — orchestrator only (never in a subagent)
Requires Nathan's explicit "ya" to "Submit this batch?" recorded with `msp approve`.
A subagent cannot ask Nathan for the Terms consent or the CAPTCHA, so this section is
executed by the orchestrator in the main session.
Select exactly the prepared files → Submit → confirm Adobe's dialogs that belong to
submission (content agreement checkbox only if it is the standard submit attestation —
otherwise stop and report the text). Report the confirmation message verbatim.
Never submit files not listed. Never re-submit a file already in "In Review".
