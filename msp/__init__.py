"""Microstock pipeline: deterministic helpers used by the orchestrator and agents."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "pipeline.json")


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
