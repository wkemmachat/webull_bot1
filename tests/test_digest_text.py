"""LINE digest: repeated messages are merged with a count; daily reports show fractional shares."""
from app import brokers, db, execution as X, notify


def test_repeated_digest_lines_are_merged(clean, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "_deliver", lambda text, kind: (sent.append(text) or True, None))
    for _ in range(3):
        notify.send("system", "Bot started.")
    notify.send("system", "Trading resumed.")
    assert notify.send_digest("08:00")
    txt = sent[-1]
    assert txt.count("Bot started.") == 1 and "(×3)" in txt and "Trading resumed." in txt


def test_daily_report_shows_fractions(clean, monkeypatch):
    from app import engine, ledger
    from conftest import NOW
    db.run("INSERT OR REPLACE INTO holdings(mode,strategy,symbol,qty,cost) VALUES('paper','semis_regime','USD',29.6561,2350)")
    engine.queue_reports(NOW)
    r = db.one("SELECT text FROM line_queue WHERE event='report' AND strategy='semis_regime' ORDER BY id DESC LIMIT 1")
    assert "Holds 29.6561 USD" in r["text"]
