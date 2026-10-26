# Runbook

## Daily rhythm (Asia/Jakarta)
| time | what | who |
|---|---|---|
| 20:13 | prompts run → `PROMPTS_C{N}.txt` + Flow project name | Claude scheduled task |
| evening / before 07:13 | generate x1 per prompt in Flow project `C-Day N` | Nathan |
| 07:43 | process run: download → QC → metadata → queue | Claude scheduled task |
| every 15 min | `adobe_upload.bat` uploads queue | Windows task |
| after upload | portal prepare → "Submit this batch?" push message | Claude |
| when convenient | reply **ya** in that conversation → submit | Nathan |

**One click:** open the scheduled task "Microstock process run" in Claude → *Run now*.
It resumes from state, so running it twice is safe.

Requirements for unattended runs: PC on and awake, logged in, Claude desktop app open
(the built-in browser and file bridge run through it), Adobe/Flow sessions signed in.

## Manual commands (in a Claude session with the repo)
```
python -m msp status --n 183
python -m msp qc --n 183
python -m msp reconcile --n 183 --log winscp.log
```

## Troubleshooting
| symptom | cause | fix |
|---|---|---|
| asset `failed` "unusual activity" | Flow blocked generation | regenerate manually in Flow, then rerun process run |
| `qc_reject aspect_mismatch` | Flow kept the previous ratio | set ratio, regenerate that prompt; rerun |
| stuck in `queued` | upload task not run / WinSCP error | check `_logs\upload_runs.log`, `winscp.log`; files still in `_UPLOAD_QUEUE` are retried next run |
| `BYTES_MISMATCH` in reconcile | queued file changed after verification | do not submit; re-enqueue from `Day N\` final |
| `upscale_pending` for long | `upscale_watch.bat` not scheduled / Upscayl path | check `_logs\upscale_runs.log` |
| browser `blocked` | login, 2FA or CAPTCHA | sign in yourself in the built-in browser, rerun |
| "another run is active" | `RUN.lock` active < 3 h | wait, or if the run crashed, rerun after 3 h |

## Logs
- Batch history: `_state\C{N}.json` → `assets[k].history`, `run_log`, `approvals`.
- QC per batch: `Day N\QC_C{N}.json`.
- SFTP: `_logs\winscp.log` (contains username/IP — keep out of git).
