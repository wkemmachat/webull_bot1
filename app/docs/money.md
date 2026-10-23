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
- **Withdraw** (on a strategy): the strategy's free cash first; if that is not enough, the bot sells its holdings evenly with a
  split plan. The cash goes back to **bot unassigned**.
- **Move**: from one strategy straight to another (selling evenly first if needed).
- **Return to Webull**: bot unassigned → *not for the bot*. The bot stops using it. To take money out of Webull itself, withdraw in
  the Webull app (after any sale has settled).

**Default for new money**: *Execution → When new money arrives*. The Give / Add dialogs start from it.

## Safety

- The bot sizes every buy from the strategy's own cash, so it cannot spend money you did not allocate.
- If Webull's cash drops below the bot's cash (for example you withdrew in the Webull app), the nightly **Health check** reports a
  problem on LINE. Return money to Webull or withdraw from a strategy to fix it.
- Returns are measured on **net money in** (in − out), and *Today* on the Dashboard leaves out money added that day, so adding money
  never looks like profit.
- In **Paper** mode the account is $100,000; each strategy starts with $10,000 and the other $40,000 is *not for the bot* until you
  allocate it.
