<!--{"title": "Hong Kong ETFs and HKD", "group": "Using the app"}-->
# Hong Kong ETFs and Hong Kong dollars

The bot can now hold **Hong Kong dollars (HKD)** and run a **test trade** on three Hong Kong 2x ETFs:

| Code | ETF | Tracks | Board lot |
| --- | --- | --- | --- |
| 7234 | Bosera SZSE ChiNext Daily (2x) | ChiNext (Shenzhen growth board) | 100 shares |
| 7226 | CSOP Hang Seng TECH Index Daily (2x) | Hang Seng TECH | 100 shares |
| 7233 | CSOP CSI 300 Index Daily (2x) | CSI 300 | 100 shares |

**Why these three:** the research (Docs report "HK 2x ETFs vs QQQ") found robust rules for 7234, and yuan-filtered rules for 7226.
7233 is there so we learn whether Webull lets the bot trade the China A-share products too.

## Step 1 · Can the bot trade Hong Kong at all?

Webull Thailand's OpenAPI documentation covers **US stocks only**. So before building Hong Kong strategies we test it:

1. **Get HKD.** In the Webull app: Assets → Currency exchange → USD to HKD. About **HK$1,500** covers all three tests
   (one lot of 7234 ≈ HK$520, 7226 ≈ HK$220, 7233 ≈ HK$370).
2. **Give HKD to the bot.** Money → **Hong Kong dollars** → *Allocate HKD to bot*. It goes into **bot HKD**, separate
   from the USD the bot uses for US ETFs. HKD you do not allocate is never used.
3. **Run the test.** Go-live → Test trade → **Hong Kong** → *Test* (or *Test all 3*). The bot buys 1 board lot with
   Webull's Hong Kong order type and sells it straight back. Only while Hong Kong is open:
   **08:30–11:00 and 12:00–15:00 Bangkok** (09:30–12:00 and 13:00–16:00 Hong Kong), Mon–Fri except HK holidays.
4. **Read the answer** in the Go-live checklist, section *Hong Kong market (optional)*:
   * **Can buy**: Webull accepts Hong Kong orders through the API. Then Hong Kong strategies can be built.
   * **Refused by Webull**: Webull's own answer is shown. If it is about the market or a permission, ask Webull
     Thailand support whether OpenAPI Hong Kong trading can be switched on for your account. If it asks for a
     **BCAN** (Hong Kong investor ID), enter it on the Webull page (Live keys → *Hong Kong investor ID*) and test again.

The Hong Kong section is **not counted** in the readiness percentage: US go-live does not depend on it.

## How a Hong Kong order is sent

| | US ETFs | Hong Kong ETFs |
| --- | --- | --- |
| Symbol | QLD | 07234 (the bot shows 7234) |
| Money | USD (bot unassigned) | HKD (bot HKD) |
| Order | LIMIT | ENHANCED_LIMIT, priced on HKEX's tick table (HK$0.01 steps from HK$0.50 to HK$10) |
| Size | shares (fractions possible) | whole board lots only |
| Prices | Webull quote | Webull HK quote if allowed, else Yahoo (7234.HK, about 15 minutes late) |

A test is limited to 1–2 lots and HK$15,000. The USD money guard does not apply to HKD; instead the bot checks that bot
HKD and the account's HKD cash both cover the buy.

## Money in HKD

Money → **Hong Kong dollars** shows three numbers, like the USD block:

* **HKD in Webull**: the account's HKD cash (and roughly what it is in USD);
* **Bot HKD**: what you gave the bot. The Hong Kong tests are paid from it and the sale goes back into it;
* **Not for the bot**: the rest of your HKD, never touched.

*Return HKD to Webull* gives bot HKD back to the account; convert it back to USD in the Webull app if you like.
In **Paper** mode there is a *Convert USD → HKD* button that does the exchange with pretend money (paper starts with
HK$100,000 as well).

The Health check adds **Hong Kong dollars add up** (bot HKD must still be in the account) as soon as bot HKD is above zero.
The Portfolio page shows bot HKD in USD under *Bot HKD (Hong Kong)*.

## What comes next

When at least one test says **Can buy**, the next step is Hong Kong strategies: 7234 (half trend + half IBS dip) and
7226 (yuan filter). They need their own schedule (Hong Kong hours, signals at the Hong Kong close) and HKD books per
strategy. Until then no strategy trades Hong Kong.
