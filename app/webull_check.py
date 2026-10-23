"""Show the accounts this API key can see, and what Webull sends back for the bot's account (balance and positions).

  Mac:     ./.venv/bin/python -m app.webull_check test        (or live)
  Server:  cd /opt/webull_bot1 && sudo -u thbot .venv/bin/python -m app.webull_check test

Uses the saved login (press Connect on the Webull page first). Prints no keys or secrets."""
import json
import sys

from . import brokers, db


def main():
    env = (sys.argv[1] if len(sys.argv) > 1 else "test").lower()
    if env not in ("test", "live"):
        print("usage: python -m app.webull_check test|live")
        return 1
    db.init()
    b = brokers.WebullBroker(env=env)
    try:
        accts = b.accounts()
        print(f"== Webull {env} · accounts this API key can see: {len(accts)}")
        for a in accts:
            print("   ", json.dumps({k: v for k, v in a.items() if "token" not in k.lower()}))
        if len(accts) > 1 and not b.account_id:
            print("Several accounts: enter the one the bot should use as Account ID on the Webull page, then run this again.")
            return 0
    except brokers.BrokerError as e:
        print("Webull:", e)
        return 1
    try:
        aid, bal, pos = b.raw_account()
        acct = b.account()
    except brokers.BrokerError as e:
        print("Webull:", e)
        return 1
    print(f"== Webull {env} · account {aid}")
    print("-- balance (raw):")
    print(json.dumps(bal, indent=1)[:4000])
    print("-- positions (raw, first 5):")
    rows = pos if isinstance(pos, list) else pos.get("data", pos.get("positions", pos))
    print(json.dumps(rows[:5] if isinstance(rows, list) else rows, indent=1)[:3000])
    print("-- what the bot reads:")
    print(json.dumps({k: acct[k] for k in ("total", "cash", "market_value", "buying_power")}, indent=1))
    print(f"   positions: {len(acct['positions'])} symbol(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
