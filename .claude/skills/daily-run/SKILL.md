---
name: daily-run
description: Orchestrator runbook for the C-Day N microstock pipeline - stage order, device file protocol, locking, approvals, upscaling, recovery. Load at the start of every prompts run or process run, scheduled or manual.
---
# Daily run (orchestrator)

Two entry points, same state machine:
- **prompts run** (evening): Stage 1 only.
- **process run** (morning, after Nathan generated in Flow): Stages 3 → 6b-prepare,
  then the submit checkpoint. Re-running it at any time resumes where state says.

Device base = `config.device.base`. Workspace = `$MSP_WORKSPACE`.

## 0. Start (both runs)
1. Setup per CLAUDE.md; `python -m pytest -q` must pass.
2. Stage `<base>\_state\RUN.lock` if it exists. If it says `state=active` and its mtime
   is < 3 h ago → stop: "another run is active". Else commit `RUN.lock` with
   `state=active`, run type and UTC time (files cannot be deleted from here, so the
   lock is released by overwriting it with `state=done`).
3. Stage every `C*.json` from the device into `$MSP_WORKSPACE/_state/` (device wins).
4. `msp status --n N` for the open batch (highest N whose state is not fully terminal).

## Prompts run
skill `microstock-prompts` → commit outputs → message Nathan: project name, sheet path,
"generate x1 per prompt, check ratio per group". Release the lock (`state=done`). Done.

## Process run
For the open batch, only act on assets whose status needs the step:

| step | who | command / action | commit to device |
|---|---|---|---|
| A download | `browser-operator` mode=download for `prompt_generated` assets | per success: `msp generated` then `msp ingest --src <staged>` | `_original\C{N}_kk.jpg`, state |
| B tech QC | you | `msp qc --n N` | state |
| C upscale | you | for `upscale_pending`: commit the original to `_UPSCALE\in\`; the PC task `upscale_watch.bat` writes `_UPSCALE\out\C{N}_kk.jpg`; poll up to 20 min; stage it; `msp ingest` (re-ingest) then `msp qc` again (one upscale per asset max) | state |
| D visual QC | `visual-qc` agent with downloaded+non-FAIL assets | `msp review` per result | state |
| E metadata | you, skill `stock-metadata` | `msp metadata`, `msp embed`, `msp csv` | finals `Day N\C{N}_kk.jpg`, `Day N\Metadata\*.csv` |
| F verify finals | you | device_list_dir `Day N`; sizes must equal `final_bytes` | — |
| G queue | you | `msp enqueue` → commit to `_UPLOAD_QUEUE\_incoming\` → list `_incoming` to JSON → `msp enqueue --confirm listing.json --local-ts "<PC local now>"` → commit READY.flag **last** | READY.flag, state |
| H upload | Windows task runs `adobe_upload.bat` (schedule in RUNBOOK) | wait/poll `_UPLOAD_QUEUE` empty; stage `_logs\winscp.log`; `msp reconcile --log` | state |
| I prepare | `browser-operator` mode=prepare for `sftp_uploaded` | per file confirmed: `msp mark --status fields_configured --evidence '{"category":..,"ai_label":true,"fictional":..,"title_seen":..}'` | state |
| J checkpoint | you | SendUserMessage + push: table of files, titles, categories, labels, rejects → **"Submit this batch? (ya / tidak)"** | — |
| K submit | only after Nathan's explicit "ya" in chat | `msp approve --text "<his words>"` → `browser-operator` mode=submit with `APPROVAL: C{N} approved by Nathan` → `msp mark --status submitted --evidence '{"portal_evidence":"<confirmation text>"}'` | state |

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
