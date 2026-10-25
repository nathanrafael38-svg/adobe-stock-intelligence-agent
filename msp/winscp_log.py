"""Derive per-file SFTP outcomes from WinSCP's session log. The log is the
evidence for the sftp_uploaded status; a file merely being in the queue,
or the queue becoming empty, is not."""
from __future__ import annotations

import ntpath
import re

RUN = re.compile(r"^\. (\S+ \S+) Command-line:")
START = re.compile(r'^\. (\S+ \S+) Copying "(.+?)" to remote directory started\.')
DONE = re.compile(r"^\. (\S+ \S+) Transfer done: '(.+?)'")
OK_WARN = re.compile(r"^\. (\S+ \S+) \*\*Upload of file '(.+?)' was successful, but error occurred")
EXIT = re.compile(r"^\. (\S+ \S+) Script: Exit code: (\d+)")


def parse(text: str) -> list[dict]:
    """Return one dict per run: {started_at, exit_code, files: {name: outcome}}.
    outcome in {'uploaded', 'uploaded_with_warning', 'started_not_finished'}."""
    runs: list[dict] = []
    cur = None
    for line in text.splitlines():
        if "password" in line.lower():
            continue
        if m := RUN.match(line):
            cur = {"started_at": m.group(1), "exit_code": None, "files": {}}
            runs.append(cur)
            continue
        if cur is None:
            continue
        if m := START.match(line):
            cur["files"].setdefault(ntpath.basename(m.group(2)), "started_not_finished")
        elif m := DONE.match(line):
            cur["files"][ntpath.basename(m.group(2))] = "uploaded"
        elif m := OK_WARN.match(line):
            cur["files"][m.group(2)] = "uploaded_with_warning"
        elif m := EXIT.match(line):
            cur["exit_code"] = int(m.group(2))
    return runs


def upload_counts(runs: list[dict]) -> dict[str, int]:
    """How many times each file reached the server (any 'uploaded*' outcome)."""
    c: dict[str, int] = {}
    for r in runs:
        for f, o in r["files"].items():
            if o.startswith("uploaded"):
                c[f] = c.get(f, 0) + 1
    return c
