(function () {
  const V = window.Views || (window.Views = {});

  const KIND = { to_bot: ['info', 'to bot'], to_webull: ['', 'to Webull'], add: ['ok', 'add'], withdraw: ['err', 'withdraw'], move: ['info', 'move'] };

  V.money = async function (el) {
    const mode = U.mode();
    async function load() {
      const d = await U.api('/api/money?mode=' + mode);
      const f = d.fund || {};
      const tin = d.rows.reduce((x, r) => x + r.cap_in, 0), tout = d.rows.reduce((x, r) => x + r.cap_out, 0);
      const tnet = d.rows.reduce((x, r) => x + r.net_in, 0);
      const T = Math.max(f.account_total || 0, f.allocated || 0, 1);
      const seg = (v, bg, title, extra) => v > 0 ? `<div title="${U.esc(title)}" style="flex:${v / T};background:${bg};min-width:3px;${extra || ''}"></div>` : '';
      el.innerHTML = `
      <div class="page-head"><div><div class="eyebrow">${U.modeLabel[mode]} account</div><h1 class="h1">Money</h1>
        <div class="muted" style="margin-top:4px;max-width:760px">Three layers: your ${mode === 'paper' ? 'paper' : 'Webull'} account → the part you <b>allocate to the bot</b> → each strategy. The bot only ever uses money you allocate to it; the rest stays yours.</div></div>
        <div class="row"><button class="btn" data-f="out">Return to ${mode === 'paper' ? 'account' : 'Webull'}</button><button class="btn" data-f="in">Allocate to bot</button><button class="btn p" data-split="1">Give to strategies</button></div></div>
      ${d.account_error ? `<div class="note warn">${U.esc(d.account_error)}</div>` : ''}
      ${f.guard_block ? `<div class="note err"><b>A buy was blocked by the money guard ${U.ago(f.guard_block.at)}:</b> ${U.esc(f.guard_block.why)}. No money outside the bot's allocation was used.</div>` : ''}
      <section class="card col" style="gap:16px">
        <div style="display:flex;align-items:stretch;height:14px;border-radius:7px;overflow:hidden;gap:2px;background:var(--line2)">
          ${d.rows.map((r) => seg(r.value, r.color, r.name)).join('')}
          ${seg(f.pool, 'repeating-linear-gradient(45deg,var(--accent) 0 5px,color-mix(in srgb,var(--accent) 55%,transparent) 5px 10px)', 'Bot unassigned')}
          ${seg(f.not_bot, 'var(--line)', 'Not for the bot')}</div>
        <div class="flow">
          <div class="fl"><div class="eyebrow">In ${mode === 'paper' ? 'the paper account' : 'Webull'}${mode === 'paper' ? '' : ' · USD'}</div><div class="num big" style="font-size:26px;margin-top:4px">${U.usd(f.account_total)}</div>
            <div class="muted small">cash ${U.usd(f.account_cash, 0)}${d.account && d.account._at ? ' · updated ' + U.time(d.account._at) : ''}</div>
            ${d.account && (d.account.other_cash || []).length ? `<div class="muted small" style="margin-top:4px">Also in Webull: ${d.account.other_cash.map((o) => `${U.esc(o.currency)} ${U.n(o.cash, 0)}`).join(' · ')} — not counted, the bot uses USD only</div>` : ''}</div>
          <div class="arrow" aria-hidden="true">=</div>
          <div class="fl" style="border-color:color-mix(in srgb,var(--accent) 45%,var(--line))"><div class="eyebrow">Allocated to the bot</div><div class="num big" style="font-size:26px;margin-top:4px">${U.usd(f.allocated)}</div>
            <div class="muted small">strategies ${U.usd(f.strategies, 0)} + bot unassigned ${U.usd(f.pool, 0)}</div></div>
          <div class="arrow" aria-hidden="true">+</div>
          <div class="fl"><div class="eyebrow">Not for the bot</div><div class="num big" style="font-size:26px;margin-top:4px;color:var(--muted)">${U.usd(f.not_bot)}</div>
            <div class="muted small">free cash ${U.usd(f.outside_cash, 0)}${f.own_shares > 1 ? ' + your own shares ' + U.usd(f.own_shares, 0) : ''} · the bot never touches it</div>
            <div class="row small" style="gap:8px;margin-top:8px">🛡 <span>Protected cash floor <b class="num">${U.usd(f.protect_floor, 0)}</b></span><button class="btn s" data-protect="1">Set</button></div></div>
        </div>
        <div class="pool">
          <div><div class="eyebrow" style="color:var(--warn-fg)">Bot unassigned</div><div class="num big" style="font-size:30px;margin-top:4px;color:var(--warn-fg)">${U.usd(f.pool)}</div>
            <div class="muted small">Given to the bot, not yet to a strategy. Withdrawals from strategies come back here.</div></div>
          <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn" data-f="in">+ Allocate more from ${mode === 'paper' ? 'the account' : 'Webull'}</button>
            <button class="btn" data-f="out" ${f.pool > 0 ? '' : 'disabled'}>Return to ${mode === 'paper' ? 'account' : 'Webull'}</button>
            <button class="btn p" data-split="1" ${f.pool > 0 ? '' : 'disabled'}>Give to strategies →</button></div>
        </div>
      </section>
      <section class="card flush"><div class="row sb" style="padding:16px 20px 4px"><h2 class="h2">Capital per strategy</h2><span class="muted small">Return is measured on net money in, so adding money never looks like profit.</span></div>
        <div class="tw"><table class="t"><thead><tr><th>Strategy</th><th class="r">Money in</th><th class="r">Taken out</th><th class="r">Net capital</th><th class="r">Value now</th><th class="r">P&amp;L</th><th class="r">Share</th><th class="r">Actions</th></tr></thead><tbody>
        ${d.rows.map((r) => `<tr><td><a href="#/strategies/${r.id}" class="row" style="gap:10px;color:var(--text)">${U.dot(r.color, 10)}<b style="font-weight:500">${U.esc(r.name)}</b>${r.waiting ? ' ' + U.pill('warn', U.usd(r.waiting, 0) + ' waits for a buy signal') : ''}</a></td>
          <td class="r num">${U.usd(r.cap_in, 0)}</td><td class="r num muted">${U.usd(r.cap_out, 0)}</td><td class="r num">${U.usd(r.net_in, 0)}</td><td class="r num" style="font-weight:600">${U.usd(r.value)}</td>
          <td class="r num ${U.cls(r.pnl)}">${U.sgnUsd(r.pnl, 0)} · ${U.pct(r.ret)}</td><td class="r num muted">${(r.share * 100).toFixed(1)}%</td>
          <td class="r"><span class="row" style="gap:6px;justify-content:flex-end;flex-wrap:nowrap"><button class="btn s" data-k="add" data-s="${r.id}">+ Add</button><button class="btn s" data-k="withdraw" data-s="${r.id}">− Withdraw</button></span></td></tr>`).join('')}</tbody>
        <tfoot><tr><td>Total</td><td class="r num">${U.usd(tin, 0)}</td><td class="r num">${U.usd(tout, 0)}</td><td class="r num">${U.usd(tnet, 0)}</td><td class="r num">${U.usd(d.total, 0)}</td><td class="r num ${U.cls(d.total - tnet)}">${U.sgnUsd(d.total - tnet, 0)}</td><td class="r num">100%</td><td></td></tr></tfoot></table></div>
        <div class="row" style="padding:10px 20px 14px;gap:8px"><button class="btn s" data-k="move">Move between strategies</button></div></section>
      <div class="grid" style="--min:380px">
        <section class="card span2"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Money movements</h2></div>
          <div class="tw"><table class="t"><thead><tr><th>When (BKK)</th><th>Type</th><th>From → to</th><th class="r">Amount</th><th>How</th><th>Status</th></tr></thead><tbody>
          ${d.moves.map((m) => { const k = KIND[m.kind] || ['', m.kind]; const W = mode === 'paper' ? 'Account' : 'Webull';
            const path = m.kind === 'to_bot' ? `${W} → Bot` : m.kind === 'to_webull' ? `Bot → ${W}` : m.kind === 'add' ? `Bot → ${U.esc(m.name)}` : m.kind === 'withdraw' ? `${U.esc(m.name)} → Bot` : `${U.esc(m.name)} → ${U.esc(m.other_name || '')}`;
            return `<tr><td class="num">${U.dt(m.t)}</td><td>${U.pill(k[0], k[1])}</td><td>${path}</td><td class="r num">${U.usd(m.done_amount || m.amount)}</td>
            <td class="muted small wrap">${U.esc(m.note || (m.invest === 'wait' ? 'waits in cash for the next buy signal' : m.plan_id ? 'sell plan #' + m.plan_id : ''))}</td>
            <td>${U.pill(m.status === 'done' ? 'ok' : m.status === 'pending' ? 'warn' : 'err', m.status === 'pending' ? 'selling…' : m.status)}</td></tr>`; }).join('') || '<tr><td colspan="6" class="muted">No money movements yet</td></tr>'}</tbody></table></div></section>
        <section class="card col" style="gap:12px;align-self:flex-start"><h2 class="h2">Rules that keep money safe</h2>
          <div><b>Only what you allocate.</b> <span class="muted">The bot trades only with money you allocated to it. Cash you did not allocate, and shares you bought yourself, are never touched.</span></div>
          <div><b>Never more than the account has.</b> <span class="muted">You can only allocate free cash, and only give strategies what is in bot unassigned.</span></div>
          <div><b>Withdraw takes cash first.</b> <span class="muted">If that is not enough, it sells the strategy's holdings evenly with a split plan; the cash goes back to bot unassigned.</span></div>
          <div><b>Every change is a record.</b> <span class="muted">Each line here is kept, shown on the strategy page and sent to LINE.</span></div></section>
      </div>`;
      U.on(el, '[data-k]', 'click', (e, b) => V.moneyDialog(b.dataset.k, b.dataset.s || null, load));
      U.on(el, '[data-f]', 'click', (e, b) => V.fundDialog(b.dataset.f, load));
      U.on(el, '[data-split]', 'click', () => V.splitDialog(load));
      U.on(el, '[data-protect]', 'click', () => V.protectDialog(f, load));
    }
    await load();
    return { cleanup: () => {}, refresh: () => load().catch(() => {}), every: 60000 };
  };

  /* Protected cash floor: the bot never lets the account's cash fall below this */
  V.protectDialog = function (f, onDone) {
    const mode = U.mode();
    const suggest = Math.max(0, Math.floor((f.outside_cash || 0) / 100) * 100);
    U.modal('Protected cash floor', `<div class="col" style="gap:14px">
      <div class="muted">Before <b>every</b> buy, the bot reads the cash in ${mode === 'paper' ? 'the account' : 'Webull'} and refuses any order that would take it below this amount. It is a second lock on top of the books: even if the books were wrong, money above the floor is never spent.</div>
      <div class="f"><label for="pf">Never let ${mode === 'paper' ? 'account' : 'Webull'} cash fall below (USD)</label><input class="in num" id="pf" inputmode="decimal" style="height:50px;font-size:20px" value="${(f.protect_floor || 0).toFixed(2)}">
        <div class="row" style="gap:6px"><button class="btn s" data-v="${suggest}">Your free cash now · ${U.usd(suggest, 0)}</button><button class="btn s" data-v="0">0 (off)</button></div>
        <span class="h">Update it when you deposit to or withdraw from ${mode === 'paper' ? 'the account' : 'Webull'} outside the bot, or when you allocate more to the bot.</span></div>
      <div class="row" style="justify-content:flex-end"><button class="btn" id="pc">Cancel</button><button class="btn p" id="pgo">Save</button></div></div>`, {
      width: 520,
      onOpen: (box, close) => {
        U.on(box, '[data-v]', 'click', (e, b) => { box.querySelector('#pf').value = (+b.dataset.v).toFixed(2); });
        box.querySelector('#pc').onclick = close;
        box.querySelector('#pgo').onclick = (e) => U.busy(e.target, async () => {
          const amount = parseFloat((box.querySelector('#pf').value || '0').replace(/[$,]/g, '')) || 0;
          await U.api('/api/money/protect', { body: { mode, amount } });
          U.toast('Protected cash floor saved'); close(); if (onDone) onDone();
        });
      },
    });
  };

  /* Allocate to bot / Return to Webull */
  V.fundDialog = async function (dir, onDone) {
    const mode = U.mode();
    const d = await U.api('/api/money?mode=' + mode);
    const f = d.fund || {};
    const W = mode === 'paper' ? 'the paper account' : 'Webull';
    const max = dir === 'in' ? Math.max(0, f.outside_cash || 0) : Math.max(0, f.pool || 0);
    U.modal(dir === 'in' ? 'Allocate to the bot' : `Return to ${mode === 'paper' ? 'the account' : 'Webull'}`, `
      <div class="col" style="gap:16px">
        <div class="note info">${dir === 'in' ? `Moves free cash in ${W} into <b>bot unassigned</b>. Nothing is bought yet: next, give it to strategies.`
          : `Moves money from <b>bot unassigned</b> back to ${W}. The bot will not use it any more.${mode !== 'paper' ? ' To take it out of Webull, withdraw in the Webull app.' : ''}`}</div>
        <div class="f"><label for="fa">Amount (USD)</label><input class="in num" id="fa" inputmode="decimal" style="height:54px;font-size:22px" placeholder="0.00">
          <div class="row" style="gap:6px">${[100, 1000, 5000].filter((v) => v <= max).map((v) => `<button class="btn s" data-q="${v}">${U.usd(v, 0)}</button>`).join('')}<button class="btn s" data-q="${max}">All ${U.usd(max)}</button></div>
          <span class="h">${dir === 'in' ? `Free cash in ${W} not given to the bot: ${U.usd(f.outside_cash)}` : `In bot unassigned: ${U.usd(f.pool)}. To return more, withdraw from a strategy first.`}</span></div>
        <div class="row" style="justify-content:flex-end"><button class="btn" id="fc">Cancel</button><button class="btn p" id="fgo">${dir === 'in' ? 'Allocate to bot' : 'Return'}</button></div></div>`, {
      width: 520,
      onOpen: (box, close) => {
        U.on(box, '[data-q]', 'click', (e, b) => { box.querySelector('#fa').value = (+b.dataset.q).toFixed(2); });
        box.querySelector('#fc').onclick = close;
        box.querySelector('#fgo').onclick = (e) => U.busy(e.target, async () => {
          const amount = parseFloat((box.querySelector('#fa').value || '').replace(/[$,]/g, ''));
          if (!(amount > 0)) throw new Error('Enter an amount');
          await U.api('/api/money/' + (dir === 'in' ? 'to-bot' : 'to-webull'), { body: { mode, amount } });
          U.toast(dir === 'in' ? `${U.usd(amount)} allocated to the bot` : `${U.usd(amount)} returned`);
          close(); if (onDone) onDone();
          if (dir === 'in') V.splitDialog(onDone);
        });
      },
    });
  };

  /* Give bot-unassigned money to several strategies: your own amounts or an equal split */
  V.splitDialog = async function (onDone, opts) {
    opts = opts || {};   // opts.prefill {strategy id: amount}, opts.note (html) — used by the ratio planner
    const mode = U.mode();
    const d = await U.api('/api/money?mode=' + mode);
    const pool = Math.max(0, (d.fund || {}).pool || 0);
    const rows = d.rows.filter((r) => r.control !== 'stopped');
    let invest = d.new_money_start === 'buy' ? 'wait' : 'now';
    U.modal('Give to strategies', `
      <div class="col" style="gap:14px">
        <div class="row sb"><div><div class="eyebrow" style="color:var(--warn-fg)">Bot unassigned</div><div class="num big" style="font-size:24px;color:var(--warn-fg)">${U.usd(pool)}</div></div>
          <div class="row" style="gap:8px;align-items:flex-end"><div class="f" style="margin:0"><label for="st">Total to split</label><input class="in num" id="st" inputmode="decimal" style="width:130px" value="${pool.toFixed(2)}"></div>
            <button class="btn" id="eq">Split equally</button><button class="btn s" id="clr">Clear</button></div></div>
        ${opts.note ? `<div class="note info small" style="margin:0;display:block">${opts.note}</div>` : ''}
        <div class="tw"><table class="t"><thead><tr><th style="width:34px"></th><th>Strategy</th><th class="r">Now</th><th class="r" style="width:150px">Give (USD)</th></tr></thead><tbody>
          ${rows.map((r) => `<tr><td><input type="checkbox" class="ck" data-s="${r.id}" checked style="width:18px;height:18px;accent-color:var(--accent)"></td>
            <td><span class="row" style="gap:8px">${U.dot(r.color)}${U.esc(r.name)}</span></td><td class="r num muted">${U.usd(r.value, 0)}</td>
            <td class="r"><input class="in num amt" data-s="${r.id}" inputmode="decimal" placeholder="0.00" style="width:130px;text-align:right"></td></tr>`).join('')}</tbody></table></div>
        <div class="row sb small"><span>Giving <b class="num" id="tg">$0.00</b></span><span>Left in bot unassigned <b class="num" id="tl">${U.usd(pool)}</b></span></div>
        <div class="col" style="gap:8px"><span class="lbl">Invest it</span>
          <label class="opt ${invest === 'now' ? 'on' : ''}"><input type="radio" name="inv" value="now" ${invest === 'now' ? 'checked' : ''}><span><b style="font-weight:500">Now, by today's signal</b><br><span class="muted small">Each strategy buys toward its current target with a split plan.</span></span></label>
          <label class="opt ${invest === 'wait' ? 'on' : ''}"><input type="radio" name="inv" value="wait" ${invest === 'wait' ? 'checked' : ''}><span><b style="font-weight:500">Wait for the next buy signal</b><br><span class="muted small">Stays as cash in each strategy until its next BUY.</span></span></label></div>
        <div class="row" style="justify-content:flex-end"><button class="btn" id="sc">Cancel</button><button class="btn p" id="sgo">Give to strategies</button></div></div>`, {
      width: 680,
      onOpen: (box, close) => {
        const amts = () => [...box.querySelectorAll('.amt')];
        const val = (i) => parseFloat((i.value || '').replace(/[$,]/g, '')) || 0;
        const sum = () => { const t = amts().reduce((x, i) => x + val(i), 0); box.querySelector('#tg').textContent = U.usd(t);
          const left = pool - t; const tl = box.querySelector('#tl'); tl.textContent = U.usd(left); tl.className = 'num ' + (left < -0.004 ? 'dn' : ''); return t; };
        box.querySelector('#eq').onclick = () => {
          const total = parseFloat((box.querySelector('#st').value || '').replace(/[$,]/g, '')) || 0;
          const on = [...box.querySelectorAll('.ck')].filter((c) => c.checked).map((c) => c.dataset.s);
          if (!on.length) { U.toast('Tick at least one strategy'); return; }
          const cents = Math.round(total * 100), base = Math.floor(cents / on.length), rem = cents - base * on.length;
          amts().forEach((i) => { const k = on.indexOf(i.dataset.s); i.value = k < 0 ? '' : ((base + (k < rem ? 1 : 0)) / 100).toFixed(2); });
          sum();
        };
        box.querySelector('#clr').onclick = () => { amts().forEach((i) => { i.value = ''; }); sum(); };
        if (opts.prefill) { amts().forEach((i) => { const v = opts.prefill[i.dataset.s]; i.value = v > 0 ? v.toFixed(2) : ''; }); sum(); }
        U.on(box, '.amt', 'input', sum);
        U.on(box, '.ck', 'change', (e, c) => { if (!c.checked) { box.querySelector(`.amt[data-s="${c.dataset.s}"]`).value = ''; sum(); } });
        U.on(box, 'input[name=inv]', 'change', (e, b) => { invest = b.value; box.querySelectorAll('.opt').forEach((o) => o.classList.toggle('on', o.querySelector('input').checked)); });
        box.querySelector('#sc').onclick = close;
        box.querySelector('#sgo').onclick = (e) => U.busy(e.target, async () => {
          const allocations = {};
          amts().forEach((i) => { if (val(i) > 0) allocations[i.dataset.s] = val(i); });
          if (!Object.keys(allocations).length) throw new Error('Enter an amount, or press Split equally');
          if (sum() > pool + 0.004) throw new Error('That is more than bot unassigned');
          const r = await U.api('/api/money/split', { body: { mode, allocations, invest } });
          U.toast(`Gave ${U.usd(r.total)} to ${r.count} strateg${r.count === 1 ? 'y' : 'ies'}`);
          close(); if (onDone) onDone();
        });
      },
    });
  };

  /* Add / Withdraw / Move dialog */
  V.moneyDialog = async function (kind, sid, onDone) {
    const mode = U.mode();
    const d = await U.api('/api/money?mode=' + mode);
    const rows = d.rows.filter((r) => r.control !== 'stopped' || kind !== 'add');
    let tab = kind || 'add', invest = d.new_money_start === 'buy' ? 'wait' : 'now';
    U.modal(`Money · ${U.modeLabel[mode]}`, '<div id="mb"></div>', {
      onOpen: (box, close) => {
        const opts = (sel) => rows.map((r) => `<option value="${r.id}" ${r.id === sel ? 'selected' : ''}>${U.esc(r.name)} — ${U.usd(r.value, 0)}</option>`).join('');
        function draw() {
          const s = box.querySelector('#ms') ? box.querySelector('#ms').value : (sid || (rows[0] && rows[0].id));
          const r = rows.find((x) => x.id === s) || rows[0] || {};
          box.querySelector('#mb').innerHTML = `
          <div class="seg" style="width:100%;display:grid;grid-template-columns:repeat(3,1fr)">${['add', 'withdraw', 'move'].map((k) => `<button data-t="${k}" class="${tab === k ? 'on' : ''}">${k[0].toUpperCase() + k.slice(1)}</button>`).join('')}</div>
          <div class="col" style="gap:16px;margin-top:16px">
          ${tab === 'move' ? `<div class="fs"><div class="f"><label for="ms">From</label><select class="in" id="ms">${opts(s)}</select></div>
            <div class="f"><label for="mt">To</label><select class="in" id="mt">${opts(rows.find((x) => x.id !== s) ? rows.find((x) => x.id !== s).id : '')}</select></div></div>`
            : `<div class="f"><label for="ms">Strategy</label><select class="in" id="ms">${opts(s)}</select></div>`}
          <div class="f"><label for="ma">${tab === 'add' ? 'Amount to add' : tab === 'withdraw' ? 'Amount to withdraw' : 'Amount to move'} (USD)</label>
            <input class="in num" id="ma" inputmode="decimal" style="height:54px;font-size:22px" placeholder="0.00">
            <div class="row" style="gap:6px">${(tab === 'add' ? [1000, 5000, 10000] : [1000, 5000]).map((v) => `<button class="btn s" data-q="${v}">${U.usd(v, 0)}</button>`).join('')}
              <button class="btn s" data-q="${tab === 'add' ? Math.max(0, d.unassigned || 0) : r.value}">${tab === 'add' ? 'All bot unassigned' : 'Everything'}</button></div>
            <span class="h">${tab === 'add' ? 'Bot unassigned: ' + U.usd(d.unassigned) + (d.unassigned > 0 ? '' : ' — allocate money to the bot first (Money → Allocate to bot)') : U.esc(r.name || '') + ' is worth ' + U.usd(r.value) + ' · cash in it ' + U.usd(r.cash)}</span></div>
          ${tab !== 'withdraw' ? `${tab === 'move' ? '<div class="note info">Frees the cash in the first strategy (selling evenly if needed), then gives it to the second.</div>' : ''}
            <div class="col" style="gap:8px"><span class="lbl">${tab === 'move' ? 'The receiving strategy invests it' : 'Invest it'}</span>
            <label class="opt ${invest === 'now' ? 'on' : ''}"><input type="radio" name="inv" value="now" ${invest === 'now' ? 'checked' : ''}><span><b style="font-weight:500">Now, by today's signal</b><br><span class="muted small">The bot buys toward the strategy's current target with a split plan (e.g. UGL if gold is long today).</span></span></label>
            <label class="opt ${invest === 'wait' ? 'on' : ''}"><input type="radio" name="inv" value="wait" ${invest === 'wait' ? 'checked' : ''}><span><b style="font-weight:500">Wait for the next buy signal</b><br><span class="muted small">This money stays as cash in the strategy until a new BUY comes (for QLD / Semis: a step up, like off → 1x or 0.5x → 2x). Sell signals do not start it. Money already in the strategy keeps trading as usual.</span></span></label></div>`
            : `<div class="note info">Uses the strategy's cash first, then sells its holdings evenly with a split plan. The money goes back to <b>bot unassigned</b>; use <b>Return to Webull</b> if the bot should stop using it.</div>`}
          <label class="row small" style="color:var(--text2)"><input type="checkbox" checked disabled style="width:18px;height:18px;accent-color:var(--accent)">A LINE message is sent when it is done (if Money alerts are on)</label>
          <div class="row" style="justify-content:flex-end"><button class="btn" id="mc">Cancel</button><button class="btn p" id="mgo">${tab === 'add' ? 'Add money' : tab === 'withdraw' ? 'Withdraw' : 'Move money'}</button></div></div>`;
          U.on(box, '[data-t]', 'click', (e, b) => { tab = b.dataset.t; draw(); });
          U.on(box, '[data-q]', 'click', (e, b) => { box.querySelector('#ma').value = (+b.dataset.q).toFixed(2); });
          U.on(box, 'input[name=inv]', 'change', (e, b) => { invest = b.value; box.querySelectorAll('.opt').forEach((o) => o.classList.toggle('on', o.querySelector('input').checked)); });
          box.querySelector('#ms').addEventListener('change', draw);
          box.querySelector('#mc').onclick = close;
          box.querySelector('#mgo').onclick = (e) => U.busy(e.target, async () => {
            const amount = parseFloat((box.querySelector('#ma').value || '').replace(/[$,]/g, ''));
            if (!(amount > 0)) throw new Error('Enter an amount');
            const b = { mode, strategy: box.querySelector('#ms').value, amount, invest };
            if (tab === 'move') b.other = box.querySelector('#mt').value;
            const r = await U.api('/api/money/' + tab, { body: b });
            U.toast(r.status === 'pending' ? 'Selling with a split plan; the money moves when it finishes' : 'Done');
            close(); if (onDone) onDone();
          });
        }
        draw();
      },
    });
  };
})();
