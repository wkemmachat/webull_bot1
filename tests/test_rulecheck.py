"""Check the rule (app/rulecheck.py): every view of every daily strategy type that has one builds, its charts and lanes point
at series that exist, and the rule worked out from the charted numbers agrees with the bot's decision on every day."""
import re

import pytest

from app import rulecheck
from app import strategies as S
from conftest import NOW
from test_api import client, sign_in  # noqa: F401  (fixture)

IDS = ["usd_trend_split", "qld_split_2c", "rom_split_2c", "sso_macd_calm", "rxl_ichi_calm", "rom_vol_ibs"]


def default(sid):
    d = S.DEFAULTS[[x[0] for x in S.DEFAULTS].index(sid)]
    return S.TYPES[d[1]]({"id": sid, "name": d[2], "params": d[4]})


@pytest.mark.parametrize("sid", IDS)
def test_views_build_and_agree_with_the_bot(sid):
    s = default(sid)
    out = rulecheck.build(s, NOW, "1Y")
    n = len(out["t"])
    assert n > 100 and out["views"]
    for v in out["views"]:
        keys = [l["key"] for c in v["charts"] for l in c["lines"]] + [ln["key"] for ln in v["lanes"]] + [c["ok"] for c in v["checks"] if c["ok"] is not None]
        keys += [c["shade"]["key"] for c in v["charts"] if c.get("shade") and c["shade"].get("key") not in (None, "cloud")]
        for c in v["checks"]:
            keys += re.findall(r"\{([^}]+)\}", c["t"])
        for k in keys:
            assert k in out["series"] and len(out["series"][k]["v"]) == n, (v["id"], k)
        if v["id"] != "mix":
            assert v["mismatch"] == 0, (sid, v["id"])
            assert [ln["kind"] for ln in v["lanes"]][-2:] == ["rule", "bot"] and v["checks"] and v["rule"]
    if s.type in ("split_mix", "trend_split"):
        assert out["views"][0]["id"] == "mix" and len(out["views"]) == len(s.legs() if s.type == "split_mix" else (1, 2, 3)) + 1


def test_types_without_a_check():
    assert rulecheck.build(S.TYPES["trend_dip"]({"id": "x", "name": "x", "params": {}}), NOW) is None


def test_api(client):
    sign_in(client)
    r = client.get("/api/strategies/rxl_ichi_calm/rulecheck?range=8M").json()
    assert r["views"][0]["mismatch"] == 0 and r["t"]
    assert client.get("/api/strategies/qld_tbdv/rulecheck").json().get("none") is True
