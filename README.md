# Adobe Stock Intelligence Agent

Daily microstock pipeline for contributor *xiangan*: prompts → Google Flow →
2K download → QC → metadata (IPTC/XMP + CSV) → WinSCP SFTP → Adobe portal.

## Architecture

| Component | Kind | Why |
|---|---|---|
| `orchestrator/ORCHESTRATOR.md` | Scheduled-task session | Owns state, ordering, lock, approvals. Sees JSON only. |
| `.claude/agents/browser-operator.md` | Agent | Screenshot-heavy UI work isolated from the orchestrator |
| `.claude/agents/qc-reviewer.md` | Agent | Independent visual judgement; did not create the images |
| `.claude/agents/metadata-writer.md` | Agent | Looks at images to describe them; separate from QC's reject mindset |
| `.claude/skills/prompt-generation` | Skill | Text procedure, orchestrator runs it |
| `.claude/skills/flow-generate-download` | Skill | UI procedure for browser-operator |
| `.claude/skills/adobe-portal-prep` | Skill | UI procedure for browser-operator |
| `msp/` | Python | Everything deterministic: state machine, plan validation, technical QC, IPTC/XMP embed + read-back, CSV export, WinSCP log parsing |
| WinSCP + Task Scheduler on the PC | Existing | SFTP upload; credentials stay in WinSCP |
| `config/pipeline.json` | Config | Every rule and limit, with its source |

Per-asset status order (`msp/state.py`): prompt_generated → image_generated →
downloaded → qc_passed → metadata_validated → metadata_embedded →
sftp_uploaded → portal_configured → submit_approved → submitted →
platform_accepted. Side exits: failed, qc_hold, qc_reject, platform_rejected.

## Naming
Batch folder `1. Dari Claude\Day N` (own counter, first new = 182), Flow
project `C-Day N`, files `C{N}_{kk}.jpg` (no spaces, unique vs manual Days).

## Tests
`python -m pytest -q tests` — unit tests plus a simulated batch. Tests marked
real need the Day 181 sample staged (path in `D181`).

## Status
- Verified: msp modules against real Day 181 files and WinSCP log.
- Not verified: Flow UI steps, Adobe portal steps, end-to-end scheduled run,
  agent tool restrictions when loaded from this repo.

## Data and privacy
- Never commit credentials, tokens, cookies, or private sales records.
- Never delete or modify published stock assets automatically.
- Nothing is submitted to Adobe without Nathan's explicit reply per batch.
