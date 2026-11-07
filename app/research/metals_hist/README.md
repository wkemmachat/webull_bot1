Hourly spot gold (XAUUSD → GC) and silver (XAGUSD → SI), OANDA, March 2006 – October 2026, from the Hugging Face datasets
bunqi/OANDA_XAUUSD_Gold and bunqi/OANDA_XAGUSD_Silver (folder 60 = 1-hour bars; times are the bar's start, UTC).

Used only by backtests (metals.long_history): the years before the bot's own Yahoo COMEX futures bars start, scaled to the
futures price where they join. Live signals never read these files.
