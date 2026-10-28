# Runbook

## Daily rhythm (Asia/Jakarta)
| time | what | who |
|---|---|---|
| PC on, logon | Claude desktop + Edge open by themselves (`autostart.bat` in Startup) | Windows |
| 06:30 | "Microstock daily run" (once a day): `msp due` decides — weekly research and report (Mondays), process batches Nathan generated, reconcile uploads, prepare portal fields and tell Nathan the batch is ready (he submits manually), then prompts for the next C-Day. Silent when nothing to do. | Claude scheduled task |
| any time after the run | generate x1 per prompt in Flow project `C-Day N` (microstock account) | Nathan |
| every 15 min | `adobe_upload.bat` uploads the queue | Windows task (after `setup_tasks.bat`) |
| every 15 min | `upscale_watch.bat` (only does work when files are queued) | Windows task "Microstock Upscale Watch" |
| when convenient | submit the prepared batch in the Adobe portal yourself (Terms + CAPTCHA) | Nathan |

**One click:** open the scheduled task "Microstock daily run" in Claude → *Run now*, or just tell Claude in chat "sudah generate".
It resumes from state, so running it twice is safe.

Requirements for unattended runs: PC on and awake (sleep is off on AC), Windows logged in,
Claude desktop app open (file bridge), Edge open with the Claude extension connected and
signed in to Flow (microstock account) and Adobe Stock contributor; Edge downloads go to
`Downloads\Buat Claude`.

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
