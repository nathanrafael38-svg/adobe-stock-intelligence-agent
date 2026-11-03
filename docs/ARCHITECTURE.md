# Architecture

## Current state found (2026-10-26)
- PC folder `…\1. Gambar\1. Dari Claude\` already had: `_state\C182.json` (per-asset
  state with evidence), `_tools\adobe_upload.bat` (queue + READY.flag + WinSCP),
  `_logs\winscp.log`, `Day 181` (legacy names), `Day 182` (C182_kk naming, QC json, CSVs).
- The code that produced C182 state/QC/embeds was **not** on the PC or in this repo
  (it lived in an ephemeral cloud session). Rebuilt here as `msp/`, compatible with the
  existing state format (same dhash algorithm — verified on C182_01).
- Defects found and fixed by design:
  - Archive copies in `Day N` had no IPTC (only Google C2PA); the embedded copy existed
    only in the upload queue and was deleted by `put -delete`. Now the final file with
    metadata lives in `Day N\`, the raw download in `Day N\_original\`.
  - C182_01 state said 2,473,363 bytes embedded, WinSCP sent 2,465,744. Now an asset is
    only `sftp_uploaded` when the log shows the same filename **and byte count** after
    it was queued.
  - Adobe CSV schema drifted (4 vs 5 columns). Now one fixed header from config.

## Execution model
```
 Claude scheduled task (cloud, linked to PC)                  Windows Task Scheduler (PC)
 ┌───────────────────────────────────────────┐               ┌──────────────────────────┐
 │ Orchestrator  (CLAUDE.md + skill dailyrun)│  files via    │ adobe_upload.bat  (SFTP)  │
 │  ├─ msp CLI (python, exiftool) in cloud    │ device bridge │ upscale_watch.bat (Upscayl│
 │  ├─ agent browser-operator (built-in       │◄─────────────►│        GPU, on demand)    │
 │  │    browser on PC: Flow, Adobe portal)   │               └──────────────────────────┘
 │  └─ agent visual-qc (pixels only)          │      F:\…\1. Dari Claude  = source of truth
 └───────────────────────────────────────────┘
```
Why: this session has no shell on the PC, so deterministic processing runs in the cloud
workspace on staged copies; only SFTP (credentials) and Upscayl (GPU) run on the PC.
Credentials never leave the PC.

## Agents vs skills
| Component | Kind | Why |
|---|---|---|
| Orchestrator | main session | owns state, ordering, approvals; one per run |
| browser-operator | **agent** | distinct tools (signed-in browser) and risky actions (submit); screenshot-heavy context kept out of the orchestrator |
| visual-qc | **agent** | must be independent of the prompt/metadata writer (no self-grading); image-heavy context |
| prompts, metadata | skills | text generation with rules; no independent context needed |
| download, upload | skills | procedures loaded by browser-operator |
| qc | skill | checklist loaded by visual-qc |
| dailyrun | skill | orchestrator runbook |
| tech QC, embed, CSV, queue, reconcile | scripts (`msp`) | deterministic, testable |
| upload, upscale | existing/added .bat | must run on the PC |

Rejected: one agent per stage (prompt/metadata/upload agents) — they would only pass
data along; upload is already a .bat.

## State machine (per asset)
`prompt_generated → image_generated → downloaded → (upscale_pending → downloaded) →
qc_passed | qc_review | qc_reject → metadata_validated → metadata_embedded → queued →
sftp_uploaded → fields_configured → submit_approved → submitted → platform_accepted |
platform_rejected`; `failed`/`skipped` from anywhere. Each transition requires
evidence keys (see `msp/state.py`). Batch approvals are stored in `approvals[]`.

## Directory contract (PC)
```
1. Dari Claude\
  _state\C{N}.json, C{N}-plan.json, RUN.lock
  _tools\adobe_upload.bat, adobe_upload.txt (credentials, never read), upscale_watch.bat
  _logs\winscp.log, upload_runs.log, upscale_runs.log
  _UPLOAD_QUEUE\_incoming\ (+ READY.flag last)
  _UPSCALE\in | out | done
  Day N\C{N}_kk.jpg            final, IPTC+XMP embedded, approved by QC
  Day N\_original\C{N}_kk.jpg  raw 2K download (all, incl. rejects)
  Day N\Metadata\adobe-metadata.csv, vecteezy-metadata.csv
  Day N\QC_C{N}.json, PROMPTS_C{N}.xlsx
```
