---
name: dailyrun
description: Single entry point for the whole C-Day N microstock pipeline (prompts, Flow download, QC, metadata, upload queue, Adobe portal prepare, weekly report). Detects which parts of today are already done and continues from the first pending stage. Use for the scheduled 06:30 run and whenever Nathan types /dailyrun or says "lanjut".
---
# Daily run (orchestrator) — one skill for the whole pipeline

Verified end-to-end on C183–C189. One state machine, run **once a day at 06:30 WIB** by the
scheduled task "Microstock daily run"; Nathan can also start it in chat (`/dailyrun`, "sudah generate",
"lanjut"). **Every run starts by detecting what is already done today** and continues from there, so it
is safe to run at any hour and any number of times: nothing done is repeated.
**Submission is manual by Nathan** (Terms + CAPTCHA): the run only tells him the batch is ready.

Stage details live next to this file and are read **only when that stage runs** (keeps tokens low):

| stage | reference file | read by |
|---|---|---|
| prompt plan | `reference/prompts.md` | orchestrator |
| Flow 2K download | `reference/download.md` | `browser-operator` (mode=download) |
| visual QC rubric | `reference/qc.md` | `visual-qc` |
| metadata (Adobe + Vecteezy) | `reference/metadata.md` | orchestrator |
| Adobe portal prepare / submit | `reference/portal.md` | `browser-operator` (prepare), orchestrator (submit) |
| weekly research brief + report | `reference/weekly.md` | `market-researcher`, orchestrator |

Paths are relative to `.claude/skills/dailyrun/` in the repo clone.

## 1. Detect (right after "0. Start")
1. `python -m msp day-status --now "<PC local time ISO, +07:00>"` on the staged states. It returns:
   `research` (done/pending), `prompts_today` (done / pending / not_yet / blocked_by_open_batch),
   `open_batches[]` each with a per-stage checklist (`generate`, `download`, `qc`, `metadata`,
   `embed_queue`, `upload`, `prepare`, `submit` → done / pending / waiting + asset counts) and `next`,
   plus `actions` and `skip_stale` (same as `msp due`).
2. Write the checklist for yourself (and for Nathan in chat) as a table: stage → done / pending / waiting.
   Example, C-Day 190 at 11:00: prompts done, `generate` done (Nathan generated), `download` pending →
   run download, QC, metadata, queue; then prompts for C-Day 191 are not due yet.
3. `generate` = `waiting` does **not** prove Nathan has not generated: state only changes after a download.
   Look at the Flow project Nathan already has open (browser-operator, mode=download; never create a new project): tiles exist → continue at download;
   none yet → stay silent in a scheduled run, or say "belum ada tile di Flow" in chat.
4. `silent: true` → release the lock (`state=done`) and **end without any message**.
5. `skip_stale` → `msp mark --n N --k ... --status skipped --evidence '{"reason":"not generated within 2 days"}'`.

## 2. Execute pending work in this fixed order
Skip anything detection marked done. Never redo a done stage; resume mid-batch from the first non-done stage.
1. `research` pending (Mondays, or newest brief older than 8 days) → `market-researcher` reading
   `reference/weekly.md`; `msp research-save`; commit to `<base>\_research\`; summary to Nathan.
   Runs before prompts so the new batch already uses it.
2. Each open batch, oldest first, from its `next` stage: **Process run** below (download → qc → metadata →
   queue → upload/reconcile → prepare). `upload` = waiting means the Windows task has not run yet: do not
   wait for it; report and let the next run reconcile.
3. `submit` waiting / `ask_submit` → a scheduled run only tells Nathan the batch is ready (he submits
   manually) and runs `msp checkpoint --n N` (no re-notice for 12 h). In chat, on his request, step J/K applies.
4. After processing, re-run `msp day-status`: `prompts_today = pending` → **Prompts run** (read
   `reference/prompts.md`). `done` / `blocked_by_open_batch` / `not_yet` → nothing to do.
5. Weekly report (Mondays, or when research ran): `reference/weekly.md` section 5, send to Nathan.
6. Message Nathan only when something changed or needs him (prompts ready, QC summary,
   "Submit this batch?", CAPTCHA, a failure, a login wall). Never send "nothing to do" messages.
   In chat, always answer the detection table first ("sudah: … / belum: …"), then work.

## Standing decisions from Nathan
- **QC is yours.** No REVIEW is sent to Nathan: you make the final call on every
  `qc_review` asset after looking at 100% crops yourself. In doubt about AI artifacts,
  duplicated objects, brand-like product design or anatomy → TOLAK. Watercolor paper
  texture or intentional spatter on a near-white (≥250) background → KIRIM.
- Only QC-passed images get metadata and are uploaded.
- Browser: Nathan's Edge via the Claude extension (`mcp__claude-in-chrome__*`); downloads
  land in `C:\Users\Nathan\Downloads\Buat Claude`.
- Adobe CAPTCHA: Nathan solves it. Stop, message him, then verify the In review tab.
- Submission and Adobe's Terms attestation: follow `reference/portal.md` (ask Nathan).

Device base = `config.device.base`. Workspace = `$MSP_WORKSPACE`.

## 0. Start (both runs)
1. Setup per CLAUDE.md; `python -m pytest -q` must pass.
2. Stage `<base>\_state\RUN.lock` if it exists. If it says `state=active` and its mtime
   is < 90 min ago → stop: "another run is active". Older than 90 min, or any mtime with
   no state change in `_state\C*.json` since → it is stale (a run died without releasing
   it): take over and say so in the summary. Else commit `RUN.lock` with
   `state=active`, run type and UTC time (files cannot be deleted from here, so the
   lock is released by overwriting it with `state=done`).
3. **Component check (before any work).** Confirm the repo agents `visual-qc` and
   `browser-operator` are available as Agent types and the skill `dailyrun` is loaded (it is the only skill; stage details are in `reference/`),
   e.g. with `python -m msp doctor` plus the agent list in your system context.
   - Missing from the session but present in the repo → load them from files: Read
     `.claude/skills/dailyrun/SKILL.md` for the skill; for an agent, spawn
     `subagent_type: general-purpose` whose prompt starts with the full body of
     `.claude/agents/<name>.md`, then the task. Log `components: loaded-from-files`.
   - Files missing or unreadable → stop the run, release the lock, and message Nathan.
   Never fall back to doing an agent's job yourself (QC independence is the point).
4. Stage every `C*.json` from the device into `$MSP_WORKSPACE/_state/` and every
   `<base>\_research\RESEARCH_*.json` into `$MSP_WORKSPACE/_research/` (device wins).
5. `msp status --n N` for every batch that is not terminal; finish older batches first (e.g. assets still `queued` or `fields_configured`).
6. **Every exit path releases the lock** (`state=done`), including "silent", "PC unreachable"
   and errors. A run that cannot release it must say so in its last message.

## Prompts run
`reference/prompts.md` → commit outputs → message Nathan: project name, sheet path,
"generate x1 per prompt, check ratio per group". Release the lock (`state=done`). Done.

## Process run
For the open batch, only act on assets whose status needs the step:

| step | who | command / action | commit to device |
|---|---|---|---|
| A download | `browser-operator` mode=download (Edge, microstock account, in-page 2K loop, files in `Buat Claude`, match by exact prompt hash) | per success: `msp generated` then `msp ingest --src <staged>`; missing tiles stay `prompt_generated` and go in the summary; any `model_seen` other than Nano Banana Pro goes in the summary as a warning to Nathan (QC still decides) | `_original\C{N}_kk.jpg`, state |
| B tech QC | you | `msp qc --n N` | state |
| C upscale | you | for `upscale_pending`: commit the original to `_UPSCALE\in\`; the PC task `upscale_watch.bat` writes `_UPSCALE\out\C{N}_kk.jpg`; poll up to 20 min; stage it; `msp ingest` (re-ingest) then `msp qc` again (one upscale per asset max) | state |
| D visual QC | two `visual-qc` agents in parallel (10 images each) for downloaded+non-FAIL assets | `msp review` per result, then decide every `qc_review` yourself (standing decisions) | state |
| E metadata | you, `reference/metadata.md` | `msp metadata`, `msp embed`, `msp csv` | finals `Day N\C{N}_kk.jpg`, `Day N\Metadata\*.csv` |
| F verify finals | you | stage `Day N\C{N}_kk.jpg` back from the PC → `msp verify-device --dir <staged Day N>` (the bridge rewrites the C2PA segment on write, so bytes change; pixels + IPTC/XMP must match; device size/sha become canonical) | state |
| G queue | you | `msp enqueue` → commit to `_UPLOAD_QUEUE\_incoming\` → list `_incoming` to JSON → `msp enqueue --confirm listing.json --local-ts "<PC local now>"` → commit READY.flag **last** | READY.flag, state |
| H upload | Windows task "Adobe Stock SFTP Upload" runs every 15 min (after `setup_tasks.bat`) | poll `_UPLOAD_QUEUE` until empty (≤30 min); stage `_logs\winscp.log`; `msp reconcile --log`; never run WinSCP yourself | state |
| I prepare | `browser-operator` mode=prepare for `sftp_uploaded`; pass `file_type` per file from the asset `type` (illustration→Illustrations, photo→Photos) | per file confirmed: `msp mark --status fields_configured --evidence '{"category":..,"ai_label":true,"fictional":..,"title_seen":..}'` | state |
| J checkpoint | you | SendUserMessage + push: table of files, titles, categories, labels, rejects → **"Submit this batch? (ya / tidak)"**, then `msp checkpoint --n N` | — |
| K submit | **you (orchestrator), never a subagent**, only after Nathan's explicit "ya" in chat | `msp approve --text "<his words>"` → follow `reference/portal.md` submit section yourself: reload New tab, untick "Include in submission" on every non-batch file until the button shows exactly the batch count, verify each ticked name, Submit → ask Nathan before ticking the Terms attestation → Continue → CAPTCHA: stop and ask Nathan → verify the In review tab → `msp mark --status submitted --evidence '{"portal_evidence":"..."}'` | state |

Any answer other than an explicit yes → no submission; leave `fields_configured`.

## Device file protocol
- Write outputs to `/mnt/user-data/outputs/...`, then `device_commit_files`.
- **Use a new, unique staged path for every commit** (e.g. `/mnt/user-data/outputs/<unix-ts>/RUN.lock`).
  The bridge can reuse an earlier upload of the same staged path, so re-committing a changed file from
  the same path silently writes the OLD content (seen 2026-11-08: RUN.lock stayed `active`, C193 state
  lost 10 marks). After committing state or RUN.lock, re-stage it and check its size/content.
- For any device file you overwrite (state JSON), pass `expectedMtimeMs` from your
  last listing; on mtime conflict, re-stage, re-apply your change, retry once.
- Never commit into `_UPLOAD_QUEUE\` root; only `_incoming\` + READY.flag.

## Failure isolation
- One asset failing never blocks others; record `failed` with the error and continue.
- Flow "unusual activity"/policy failures: record `failed`, tell Nathan in the summary.
- Browser blocked (login/CAPTCHA): skip the browser steps, finish the rest, report.
- Upload task did not run within 30 min: report; do not run WinSCP yourself.

## Finish (always, even after errors)
`msp qc-report --n N`, `msp status --n N`, commit state + QC report, overwrite `RUN.lock` with `state=done` + time,
then a short summary: done / pending Nathan / failed / next step.
