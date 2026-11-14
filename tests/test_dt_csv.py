import json, subprocess, sys, os


def test_dt_csv_help():
    r = subprocess.run([sys.executable, "-m", "msp", "dt-csv", "-h"], capture_output=True, text=True)
    assert r.returncode == 0 and "--cats" in r.stdout


def test_dt_constants():
    from msp import cli
    assert cli.DT_AI_SUBCAT == 212
    assert cli.DT_COLUMNS[0] == "Filename" and cli.DT_COLUMNS[3] == "Category 1"


def test_stock_select_commands_registered():
    for cmd in ("stock-select", "vz-csv"):
        r = subprocess.run([sys.executable, "-m", "msp", cmd, "-h"], capture_output=True, text=True)
        assert r.returncode == 0 and "--ns" in r.stdout
