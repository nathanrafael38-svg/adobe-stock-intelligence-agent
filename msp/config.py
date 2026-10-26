"""Load pipeline config and derive device/workspace paths."""
from __future__ import annotations

import json
import os
from pathlib import Path, PureWindowsPath

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "config" / "pipeline.json"


def load(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def workspace() -> Path:
    """Local (cloud container) mirror of the device base folder.

    The device is the source of truth for files; the workspace holds copies
    staged in for processing. Override with MSP_WORKSPACE.
    """
    return Path(os.environ.get("MSP_WORKSPACE", "/home/claude/msp-work"))


def batch_id(cfg: dict, n: int) -> str:
    return cfg["naming"]["batch_id"].format(n=n)


def filename(cfg: dict, n: int, k: int) -> str:
    return cfg["naming"]["file"].format(n=n, k=k)


def device_path(cfg: dict, *parts: str) -> str:
    """Windows path on the user's PC (string, never touched locally)."""
    return str(PureWindowsPath(cfg["device"]["base"], *parts))


def day_dir(cfg: dict, n: int) -> str:
    return cfg["device"]["day_dir_pattern"].format(n=n)


def local_day(cfg: dict, n: int) -> Path:
    p = workspace() / day_dir(cfg, n)
    p.mkdir(parents=True, exist_ok=True)
    return p


def local_state_dir() -> Path:
    p = workspace() / "_state"
    p.mkdir(parents=True, exist_ok=True)
    return p
