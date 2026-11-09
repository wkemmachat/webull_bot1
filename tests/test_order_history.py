"""Order history (Orders page and strategy pages): every sent order with the ids needed to check it against Webull later."""
import csv
import io

from app import brokers, db, execution as X, orderhist
from app import strategies as S
from conftest import NOW
from test_api import client, sign_in  # noqa: F401  (fixture)
from test_execution import run_until_done


def _run(clock, sid="qld_regime"):
    s = S.get(sid)
    pid = X.reconcile("paper", s, s.evaluate(NOW), NOW, brokers.get("paper"), db.get_settings())
    run_until_done(clock, pid)
    return s, pid


def test_history_lists_sent_orders_with_ids_and_stats(clean, clock):
    s, pid = _run(clock)
    sent = db.rows("SELECT * FROM orders WHERE plan_id=? AND status NOT IN ('scheduled','skipped')", (pid,))
    d = orderhist.history("paper")
    assert d["total"] == len(sent) > 0
    r = d["rows"][0]
    assert r["client_order_id"] and r["name"] == s.name and r["result"] in ("filled", "part")
    assert r["value"] == round(r["filled_qty"] * r["avg_price"], 2)
    st = d["stats"]
    assert st["orders"] == len(sent) and st["filled"] == sum((o["filled_qty"] or 0) > 0 for o in sent)
    assert st["bought"] == round(sum((o["filled_qty"] or 0) * (o["avg_price"] or 0) for o in sent if o["side"] == "BUY"), 2)
    assert orderhist.history("paper", sid=s.id)["total"] == len(sent)
    assert orderhist.history("paper", sid="rom_tbd")["total"] == 0
    assert orderhist.history("paper", side="SELL")["total"] == sum(o["side"] == "SELL" for o in sent)
    assert orderhist.history("paper", result="none")["total"] == st["not_filled"]
    ts = [x["t"] for x in orderhist.history("paper", limit=500)["rows"]]
    assert ts == sorted(ts, reverse=True)                                   # newest first


def test_not_sent_lots_are_left_out_and_retries_are_marked(clean, clock):
    s, pid = _run(clock)
    o = db.one("SELECT * FROM orders WHERE plan_id=? AND status='filled' ORDER BY id LIMIT 1", (pid,))
    db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,plan_qty,status,updated_at,retry) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid, "paper", s.id, o["step"], o["lot"], o["lots"], o["symbol"], o["side"], 1, 1,
                                                "skipped", o["updated_at"], 0))
    n = orderhist.history("paper")["total"]
    db.run("UPDATE orders SET status='cancelled', filled_qty=0, avg_price=NULL WHERE id=?", (o["id"],))
    db.run("INSERT INTO orders(plan_id,mode,strategy,step,lot,lots,symbol,side,qty,plan_qty,status,updated_at,retry,client_order_id) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid, "paper", s.id, o["step"], o["lot"], o["lots"], o["symbol"], o["side"], o["qty"],
                                                  o["qty"], "submitted", o["updated_at"] + 60, 1, "x1"))
    d = orderhist.history("paper", limit=500)
    assert d["total"] == n + 1                                              # the skipped lot is not shown, the retry is
    first = next(r for r in d["rows"] if r["id"] == o["id"])
    assert first["retried"] and first["result"] == "cancelled"
    assert orderhist.history("paper", result="working")["total"] == 1


def test_check_against_the_broker(clean, clock):
    s, pid = _run(clock)
    o = db.one("SELECT * FROM orders WHERE plan_id=? AND status='filled' ORDER BY id LIMIT 1", (pid,))
    c = orderhist.check(o["id"])
    assert c["ok"] is True and c["diffs"] == [] and c["webull"]["filled_qty"] == o["filled_qty"]
    db.run("UPDATE orders SET filled_qty=filled_qty-1 WHERE id=?", (o["id"],))   # the books disagree with the broker
    c = orderhist.check(o["id"])
    assert c["ok"] is False and c["diffs"][0]["field"] == "filled shares"


def test_api_and_csv(client, clock):
    sign_in(client)
    s, pid = _run(clock)
    d = client.get("/api/orders/history?mode=paper&limit=5").json()
    assert len(d["rows"]) == 5 and d["total"] >= 5 and "stats" in d
    r = client.get(f"/api/orders/history.csv?mode=paper&strategy={s.id}")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == orderhist.CSV_COLS and len(rows) == d["total"] + 1
    assert rows[1][CSV := orderhist.CSV_COLS.index("client_order_id")]
    oid = d["rows"][0]["id"]
    assert client.get(f"/api/orders/{oid}/check").json()["ok"] is True
    assert client.get("/api/orders/999999/check").status_code == 404
