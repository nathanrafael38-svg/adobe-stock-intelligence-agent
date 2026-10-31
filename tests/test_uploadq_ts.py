from msp.uploadq import _norm_ts


def test_norm_ts_variants():
    assert _norm_ts("2026-10-28T07:45:41") == "2026-10-28 07:45:41"
    assert _norm_ts("2026-10-29T08:12:00+07:00") == "2026-10-29 08:12:00"
    assert _norm_ts("2026-10-29 08:12:00") == "2026-10-29 08:12:00"
