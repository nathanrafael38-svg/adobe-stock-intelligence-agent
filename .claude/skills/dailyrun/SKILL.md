---
name: dailyrun
description: Orchestrator runbook for the C-Day N microstock pipeline - stage order, device file protocol, locking, approvals, upscaling, recovery. Load at the start of every prompts run or process run, scheduled or manual.
---
# Daily run (orchestrator)

Verified end-to-end on C183–C185. One state machine, run **once a day at 06:30 WIB** by the
scheduled task "Microstock daily run" (hourly and twice-daily runs were removed on 2026-10-28:
too many weekly tokens). Nathan can also start any stage in chat ("sudah generate").
One run does all pending work in this order: research (Mondays) → process what Nathan
generated since the last run → reconcile the previous 09:30 upload and prepare the portal →
prompts for the next C-Day. **Submission is manual by Nathan** (Terms + CAPTCHA): the run
only tells him the batch is ready. After processing a batch, re-run `msp due` once: the
batch no longer blocks `prompts`. Each run decides its own work:

## Scheduled mode (do this right after "0. Start")
1. `python -m msp due --now "<PC local time ISO, +07:00>"` on the staged states.
2. `silent: true` → release the lock (`state=done`) and **end without any message**.
3. `skip_stale` → `msp mark --n N --k ... --status skipped --evidence '{"reason":"not generated within 2 days"}'`.
4. Execute the actions in order:
   - `process` → "Process run" for that batch from the first step its assets need.
   - `check_flow` → open Flow project `C-Day N`; if tiles exist, "Process run" step A
     onward; if none yet, do nothing and stay silent (Nathan has not generated).
   - `ask_submit` → in a scheduled run do not ask for submission: tell Nathan the batch is ready and he submits manually, then `msp checkpoint --n N` (no re-notice for 12 h). In chat, on his request, step J applies.
   - `research` → spawn agent `market-researcher` (skill `weeklyreport`); store its brief
     with `msp research-save` and commit it to `<base>\_research\`; send Nathan the summary.
     Runs before `prompts`, so tonight's prompts already use it.
   - `prompts` → "Prompts run" (offered from 06:00, once per day, when the newest batch
     is no longer waiting for generation). 
   - On Mondays (or when `research` ran): after the brief is saved, also run the **weekly
     report** (skill `weeklyreport`, section 5) and send it to Nathan.
5. Message Nathan only when something changed or needs him (prompts ready, QC summary,
   "Submit this batch?", CAPTCHA, a failure). Never send "nothing to do" messages.

Entry points kept for manual use: **prompts run** (Stage 1) and **process run**
(Stages 3 → 6b-prepare, then the submit checkpoint). Re-running resumes where state says.

## Standing decisions from Nathan
- **QC is yours.** No REVIEW is sent to Nathan: you make the final call on every
  `qc_review` asset after looking at 100% crops yourself. In doubt about AI artifacts,
  duplicated objects, brand-like product design or anatomy → TOLAK. Watercolor paper
  texture or intentional spatter on a near-white (≥250) background → KIRIM.
- Only QC-passed images get metadata and are uploaded.
- Browser: Nathan's Edge via the Claude extension (`mcp__claude-in-chrome__*`); downloads
  land in `C:\Users\Nathan\Downloads\Buat Claude`.
- Adobe CAPTCHA: Nathan solves it. Stop, message him, then verify the In review tab.
- Submission and Adobe's Terms attestation: follow `upload` (ask Nathan).

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
   `browser-operator` are available as Agent types and the skill `dailyrun` is loaded,
   e.g. with `python -m msp doctor` plus the agent list in your system context.
   - Missing from the session but present in the repo → load them from files: Read
     `.claude/skills/<name>/SKILL.md` for skills; for an agent, spawn
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
skill `prompts` → commit outputs → message Nathan: project name, sheet path,
"generate x1 per prompt, check ratio per group". Release the lock (`state=done`). Done.

## Process run
For the open batch, only act on assets whose status needs the step:

| step | who | command / action | commit to device |
|---|---|---|---|
| A download | `browser-operator` mode=download (Edge, microstock account, in-page 2K loop, files in `Buat Claude`, match by exact prompt hash) | per success: `msp generated` then `msp ingest --src <staged>`; missing tiles stay `prompt_generated` and go in the summary; any `model_seen` other than Nano Banana Pro goes in the summary as a warning to Nathan (QC still decides) | `_original\C{N}_kk.jpg`, state |
| B tech QC | you | `msp qc --n N` | state |
| C upscale | you | for `upscale_pending`: commit the original to `_UPSCALE\in\`; the PC task `upscale_watch.bat` writes `_UPSCALE\out\C{N}_kk.jpg`; poll up to 20 min; stage it; `msp ingest` (re-ingest) then `msp qc` again (one upscale per asset max) | state |
| D visual QC | two `visual-qc` agents in parallel (10 images each) for downloaded+non-FAIL assets | `msp review` per result, then decide every `qc_review` yourself (standing decisions) | state |
| E metadata | you, skill `metadata` | `msp metadata`, `msp embed`, `msp csv` | finals `Day N\C{N}_kk.jpg`, `Day N\Metadata\*.csv` |
| F verify finals | you | stage `Day N\C{N}_kk.jpg` back from the PC → `msp verify-device --dir <staged Day N>` (the bridge rewrites the C2PA segment on write, so bytes change; pixels + IPTC/XMP must match; device size/sha become canonical) | state |
| G queue | you | `msp enqueue` → commit to `_UPLOAD_QUEUE\_incoming\` → list `_incoming` to JSON → `msp enqueue --confirm listing.json --local-ts "<PC local now>"` → commit READY.flag **last** | READY.flag, state |
| H upload | Windows task "Adobe Stock SFTP Upload" runs every 15 min (after `setup_tasks.bat`) | poll `_UPLOAD_QUEUE` until empty (≤30 min); stage `_logs\winscp.log`; `msp reconcile --log`; never run WinSCP yourself | state |
| I prepare | `browser-operator` mode=prepare for `sftp_uploaded`; pass `file_type` per file from the asset `type` (illustration→Illustrations, photo→Photos) | per file confirmed: `msp mark --status fields_configured --evidence '{"category":..,"ai_label":true,"fictional":..,"title_seen":..}'` | state |
| J checkpoint | you | SendUserMessage + push: table of files, titles, categories, labels, rejects → **"Submit this batch? (ya / tidak)"**, then `msp checkpoint --n N` | — |
| K submit | **you (orchestrator), never a subagent**, only after Nathan's explicit "ya" in chat | `msp approve --text "<his words>"` → follow `upload` submit section yourself: reload New tab, untick "Include in submission" on every non-batch file until the button shows exactly the batch count, verify each ticked name, Submit → ask Nathan before ticking the Terms attestation → Continue → CAPTCHA: stop and ask Nathan → verify the In review tab → `msp mark --status submitted --evidence '{"portal_evidence":"..."}'` | state |

Any answer other than an explicit yes → no submission; leave `fields_configured`.

## Device file protocol
- Write outputs to `/mnt/user-data/outputs/...`, then `device_commit_files`.
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
