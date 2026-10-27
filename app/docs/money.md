<!--{"title": "Money: Webull → bot → strategies", "group": "Using the app"}-->
# Money: Webull → bot → strategies

Your Webull account has three layers. The bot only ever uses the money you **allocate to it**.

```
Webull account               $100
├─ Allocated to the bot       $70
│   ├─ 6 strategies × $10     $60
│   └─ Bot unassigned         $10
└─ Not for the bot            $30   (the bot never touches it)
```

| Layer | What it is | Who can use it |
|---|---|---|
| **In Webull** | Everything in the account: cash and shares | — |
| **Allocated to the bot** | Strategies (their cash and shares) + bot unassigned | the bot |
| **Bot unassigned** | Given to the bot, not yet to a strategy | waits for you to give it to strategies |
| **Not for the bot** | Free cash you did not allocate + your own shares | only you; the bot never touches it |

## Step by step (the $100 example)

1. **Deposit** $100 into Webull in the Webull app. The Money page shows it under *Not for the bot*.
2. **Allocate to bot** → $70. It lands in **bot unassigned**. Nothing is bought yet.
3. **Give to strategies** → tick the six strategies, type $60 in *Total to split* and press **Split equally** ($10 each), or type your
   own amount per strategy. Press **Give to strategies**. $10 stays in bot unassigned.
4. Later, **Allocate to bot** another $20 → bot unassigned is now $30. Give it to strategies 1, 2, 3 … yourself, or split it equally.

## Every action

- **Allocate to bot**: free account cash → bot unassigned. You can never allocate more than the cash that is not already the bot's.
- **Give to strategies** (or **+ Add** on one row): bot unassigned → strategies. Two choices for how they invest it:
  - *Now, by today's signal*: buys toward the strategy's current target with a split plan (for example UGL if gold is long today).
  - *Wait for the next buy signal*: the money stays as cash inside the strategy until a **new** BUY comes. For the gold and silver
    strategies that is the next BUY (a 4H close that starts a long); for QLD / Semis it is a step up in state (off → 1x, 1x → 2x,
    0.5x → 2x …). Sell signals and step-downs do not start it. Money already in the strategy keeps trading as usual.
  - Waiting can be long. A strategy that is already in a position today (QLD regime at 2x, QLD + Trend + bear-dip in its
    trend) only gives a new BUY after it has stepped down first, which can take months. The backtests are always invested at the
    current signal, so for those **Invest now** (on the strategy's row, shown while cash waits) is closer to the tested result.
  - A strategy that is stopped, or set to Stop & sell, never buys. It is left out of *Give to strategies* and of *Move* targets;
    money added to it anyway (with + Add) gets a warning on screen and on LINE. Set it back to Active first.
- **Withdraw** (on a strategy): the strategy's free cash first; if that is not enough, the bot sells its holdings evenly with a
  split plan. The cash goes back to **bot unassigned**.
- **Move**: from one strategy straight to another (selling evenly first if needed).
- **Return to Webull**: bot unassigned → *not for the bot*. The bot stops using it. To take money out of Webull itself, withdraw in
  the Webull app (after any sale has settled).

**Default for new money**: *Execution → When new money arrives*. The Give / Add dialogs start from it.

## Currencies: USD only

A Webull Thailand account can hold several currencies (USD, THB, CNY …). The strategies buy US ETFs, which are paid
in USD, so the bot reads and uses **only the USD part**: "In Webull", cash, buying power, the money guard and the
protected floor are all USD. THB or CNY balances are shown on the Money page as "Also in Webull … not counted" and are
never used. To give the bot more money, exchange THB → USD in the Webull app first, then allocate the USD to the bot.
If Webull ever sends a balance where the USD cash cannot be told apart, the bot buys nothing rather than count THB.

## Safety: how money outside the bot is protected

Webull's API keys cannot be limited to an amount: a key with trading permission can trade the whole account. So the limit is
enforced by the bot, in three independent layers:

1. **Books.** Every buy is sized from the strategy's own cash in the bot's books, never from the account. Strategies only get
   money you allocate; broker fees are taken from the strategy that traded.
2. **Money guard, checked against Webull right before every buy.** The bot reads the account's cash and buying power, and refuses
   or shrinks the order if
   - the bot's cash in its books (strategies + bot unassigned) is more than the account's cash (money left the account?), or
   - the order would take the account's cash below your **protected cash floor**, or
   - the order is bigger than Webull's buying power.
   A blocked buy is never sent; LINE tells you at once (critical) and the Money page shows why.
3. **Sells** only sell shares the bot bought (its books) and never more than the account really holds, so your own shares are
   never sold.

**Protected cash floor** (Money → *Not for the bot* → 🛡 Set): the account cash the bot never spends below. Set it to your free cash
(the button suggests it) and update it when you deposit or withdraw in the Webull app or allocate more to the bot. The bot also
refuses to allocate money below the floor. Even if the books were wrong, money above the floor stays untouched.

**Extra protection outside the bot:** keep only the bot's money in the Webull account it trades (or ask Webull for a separate
account and enter its Account ID on the Webull page), use a cash account (no margin), and limit the API key to the server's IP.

Also:

- If Webull's cash drops below the bot's cash (for example you withdrew in the Webull app), buys stop at once and the nightly
  **Health check** reports a problem on LINE. Return money to Webull or withdraw from a strategy to fix it.
- Returns are measured on **net money in** (in − out), and *Today* on the Dashboard leaves out money added that day, so adding money
  never looks like profit.
- In **Paper** mode the account is $150,000 on a new install ($100,000 on older ones); each strategy starts with $10,000 and the rest is *not for the bot* until you
  allocate it.
