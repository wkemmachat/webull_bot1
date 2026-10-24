(function () {
  const V = window.Views || (window.Views = {});

  function lotClass(o) {
    if (o.status === 'filled' && o.retry > 0) return 'l-retry';
    return 'l-' + o.status;
  }

  /* one plan as a card: header, numbers, lot grid, fills table (detail=true) */
  V.planCard = function (p, compact) {
    const sells = {}, buys = {};
    p.orders.forEach((o) => {
      const m = o.side === 'SELL' ? sells : buys;
      m[o.symbol] = m[o.symbol] || { plan: 0, filled: 0, value: 0 };
      if (o.retry === 0) m[o.symbol].plan += o.plan_qty || 0;
      m[o.symbol].filled += o.filled_qty || 0;
      m[o.symbol].value += (o.filled_qty || 0) * (o.avg_price || 0);
    });
    const rounds = {};
    p.orders.forEach((o) => { const k = o.lot; (rounds[k] = rounds[k] || []).push(o); });
    const lotsHtml = Object.keys(rounds).sort((a, b) => a - b).map((k) => {
      const os = rounds[k];
      const st = os.some((o) => o.status === 'failed') ? 'l-failed' : os.every((o) => o.status === 'scheduled') ? 'l-scheduled'
        : os.every((o) => ['filled', 'skipped', 'partial', 'cancelled'].includes(o.status)) ? (os.some((o) => o.retry > 0) ? 'l-retry' : os.every((o) => o.status === 'skipped') ? 'l-skipped' : 'l-filled') : 'l-submitted';
      const r = Math.max(0, ...os.map((o) => o.retry));
      return `<div class="lot ${st}" title="Round ${k}: ${os.map((o) => `${o.side} ${o.qty || o.plan_qty || ''} ${o.symbol} ${o.status}`).join(', ')}">${k}${r ? ' ↻' + r : ''}</div>`;
    }).join('');
    const stateCls = p.state === 'queued' ? 'warn' : p.state === 'running' ? 'info' : p.status === 'done' ? 'ok' : 'err';
    const stateTxt = p.state === 'queued' ? 'Queued · starts ' + U.dt(p.start_at) : p.state === 'running' ? 'Running' : p.status === 'done' ? 'Done · ' + U.dt(p.finished_at) : 'Cancelled';
    const fills = p.orders.filter((o) => o.status !== 'scheduled');
    return `<section class="card col" style="gap:14px;${compact ? 'padding:14px;margin-bottom:12px' : ''}" data-plan="${p.id}">
      <div class="row sb" style="align-items:flex-start"><div class="col" style="gap:5px">
        <div class="row" style="gap:10px">${U.dot(p.color || '#888', 12)}<b style="font-size:16px">${U.esc(p.name)} · ${U.esc(p.reason)}</b>${U.pill(stateCls, stateTxt)}<span class="muted small">#${p.id}</span></div>
        <span class="muted small">${U.esc(p.note || '')} Target: ${Object.entries(p.target || {}).map(([k, v]) => `${(v * 100).toFixed(0)}% ${k}`).join(' + ') || 'cash'} · created ${U.dt(p.created_at)}</span></div>
        ${p.status === 'active' && !compact ? `<div class="row" style="gap:8px">${p.state === 'queued' ? '<button class="btn s" data-act="start-now">Start now</button>' : ''}<button class="btn d s" data-act="cancel">Cancel plan</button></div>` : ''}</div>
      <div class="grid" style="--min:170px;gap:12px">
        ${Object.entries(sells).map(([s, x]) => `<div><div class="eyebrow">Sell</div><div class="num" style="font-size:18px;font-weight:600">${U.n(x.filled, 0)} / ${U.n(x.plan, 0)} ${U.esc(s)}</div><div class="muted num small">${x.filled ? 'avg ' + U.usd(x.value / x.filled) : 'not filled yet'}</div></div>`).join('')}
        ${Object.entries(buys).map(([s, x]) => `<div><div class="eyebrow">Buy</div><div class="num" style="font-size:18px;font-weight:600">${U.n(x.filled, 0)} ${U.esc(s)}</div><div class="muted num small">${x.filled ? U.usd(x.value, 0) + ' · avg ' + U.usd(x.value / x.filled) : 'sized when each lot is sent'}</div></div>`).join('')}
        <div><div class="eyebrow">Rounds</div><div class="num" style="font-size:18px;font-weight:600">${p.lots} × ${p.interval_min} min</div><div class="muted small">each round: sells, then buys</div></div>
        <div><div class="eyebrow">Window (BKK)</div><div class="num" style="font-size:18px;font-weight:600">${p.window ? U.time(p.window[0]) + ' → ' + U.time(p.window[1]) : '—'}</div><div class="muted small">US regular session</div></div>
      </div>
      <div class="lots" style="--n:${Math.min(Object.keys(rounds).length, 20)}">${lotsHtml}</div>
      ${!compact && fills.length ? `<details><summary class="small muted" style="cursor:pointer">Lots sent (${fills.length})</summary><div class="tw"><table class="t" style="margin-top:8px"><thead><tr><th>Round</th><th>Sent (BKK)</th><th>Side</th><th>Symbol</th><th class="r">Qty</th><th class="r">Limit</th><th class="r">Filled</th><th class="r">Avg</th><th>Status</th><th>Order id</th></tr></thead><tbody>
        ${fills.map((o) => `<tr><td class="num">${o.lot}${o.retry ? ' (retry ' + o.retry + ')' : ''}</td><td class="num">${U.dt(o.submitted_at)}</td><td class="${o.side === 'BUY' ? 'up' : 'dn'}">${o.side}</td><td class="num">${U.esc(o.symbol)}</td>
          <td class="r num">${U.n(o.qty, 0)}</td><td class="r num">${o.limit_price ? U.n(o.limit_price, 2) : '—'}</td><td class="r num">${U.n(o.filled_qty, 0)}</td><td class="r num">${o.avg_price ? U.n(o.avg_price, 2) : '—'}</td>
          <td>${U.pill(o.status === 'filled' ? 'ok' : ['failed', 'cancelled'].includes(o.status) ? 'err' : o.status === 'skipped' ? '' : 'warn', o.status)}${o.error ? `<div class="muted tiny" style="white-space:normal;max-width:260px">${U.esc(o.error)}</div>` : ''}</td>
          <td class="num muted small">${U.esc(o.client_order_id || '')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
    </section>`;
  };

  V.orders = async function (el) {
    const mode = U.mode();
    let status = 'all';
    async function load() {
      const d = await U.api(`/api/plans?mode=${mode}&status=${status}&limit=40`);
      setTimeout(() => { const u = el.querySelector('#unb'); if (u) u.onclick = (e) => U.busy(e.target, async () => { await U.api('/api/orders/unblock', { body: { mode } }); U.toast('The bot will try again at the next tick'); load(); }); }, 0);
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">Split execution · ${U.modeLabel[mode]}</div><h1 class="h1">Orders</h1>
        <div class="muted" style="margin-top:4px">Every signal becomes a plan: lots of limit orders sent a few minutes apart, from the start time you set.</div></div>
        <a class="btn" href="#/execution">Execution settings</a></div>
        ${Object.keys(d.blocked || {}).length ? `<div class="note err" style="flex-direction:column;align-items:flex-start;gap:6px"><b>Webull refuses ${Object.keys(d.blocked).join(', ')} — no orders for ${Object.keys(d.blocked).length > 1 ? 'them' : 'it'} until you press the button below</b>
          ${Object.entries(d.blocked).map(([s, b]) => `<span>${U.esc(s)}: ${U.esc(b.msg)}${b.hint ? ' → ' + U.esc(b.hint) : ''}</span>`).join('')}
          <button class="btn s" id="unb">I fixed it — try again now</button></div>` : ''}
        <div class="seg" style="align-self:flex-start" id="st">${[['all', 'All'], ['queued', 'Queued · ' + d.counts.queued], ['running', 'Running · ' + d.counts.running], ['done', 'Done']].map(([k, l]) => `<button data-s="${k}" class="${status === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        ${d.plans.map((p) => V.planCard(p)).join('') || '<div class="card empty">No plans here. Plans appear when a strategy\'s target changes or money is added.</div>'}
        <div class="row small muted" style="gap:16px"><span class="row" style="gap:6px"><span class="lot l-scheduled" style="width:20px;height:14px"></span>scheduled</span>
          <span class="row" style="gap:6px"><span class="lot l-submitted" style="width:20px;height:14px"></span>sent</span><span class="row" style="gap:6px"><span class="lot l-filled" style="width:20px;height:14px"></span>filled</span>
          <span class="row" style="gap:6px"><span class="lot l-retry" style="width:20px;height:14px"></span>filled after retry</span><span class="row" style="gap:6px"><span class="lot l-failed" style="width:20px;height:14px"></span>failed</span>
          <span>Unfilled lots are cancelled after the interval and re-sent at a fresh price, up to 3 times.</span></div>`;
      U.on(el, '#st button', 'click', (e, b) => { status = b.dataset.s; load(); });
      U.on(el, '[data-act]', 'click', async (e, b) => {
        const id = b.closest('[data-plan]').dataset.plan, act = b.dataset.act;
        if (act === 'cancel' && !(await U.confirm('Cancel this plan?', 'Unsent lots are dropped and working orders are cancelled. Fills that already happened stay. The strategy plans again at the next tick if its target still differs.', { danger: true, ok: 'Cancel plan' }))) return;
        await U.api(`/api/plans/${id}/${act}`, { body: {} });
        U.toast('Done'); load();
      });
    }
    await load();
    return { cleanup: () => {}, refresh: () => load().catch(() => {}), every: 20000 };
  };

  /* ---------------------------------------------------------------- execution settings */
  V.execution = async function (el) {
    const d = await U.api('/api/settings/execution');
    const x = d.defaults, tl = d.timeline;
    const pos = (t) => Math.max(0, Math.min(100, (t - tl.start) / (tl.end - tl.start) * 100));
    const hours = [0, 3, 6, 9, 12].map((h) => tl.start + h * 3600);
    el.innerHTML = `<div class="page-head"><div><div class="eyebrow">Configure</div><h1 class="h1">Execution</h1>
      <div class="muted" style="margin-top:4px">How targets turn into orders: split size, spacing and start time. Strategies can override the defaults.</div></div>
      <button class="btn p" id="save">Save changes</button></div>
    <section class="card col" style="gap:10px"><div class="row sb"><h2 class="h2">Tonight in Bangkok time</h2><span class="muted small">US daylight saving changes are handled automatically</span></div>
      <div style="position:relative;height:${74 + tl.items.length * 26}px;border-radius:10px;background:var(--panel2);border:1px solid var(--line);overflow:hidden">
        ${tl.session ? `<div style="position:absolute;left:${pos(tl.session[0])}%;width:${pos(tl.session[1]) - pos(tl.session[0])}%;top:0;bottom:0;background:var(--info-bg)"></div>
          <div style="position:absolute;left:calc(${pos(tl.session[0])}% + 6px);top:6px;font-size:11.5px;color:var(--info)">US regular session ${U.time(tl.session[0])} – ${U.time(tl.session[1])}</div>` : ''}
        ${tl.marks.map((m) => `<div style="position:absolute;left:${pos(m.t)}%;top:24px;bottom:0;border-left:1px dashed var(--accent)"></div><div style="position:absolute;left:calc(${pos(m.t)}% + 4px);bottom:4px;font-size:11px;color:var(--warn-fg)">${U.esc(m.label)}</div>`).join('')}
        ${tl.items.map((it, i) => `<div style="position:absolute;left:${pos(it.from)}%;width:max(${pos(it.to) - pos(it.from)}%, 6px);top:${30 + i * 26}px;height:20px;border-radius:5px;background:${it.color};color:#0B0E13;font-size:11px;font-weight:600;padding-left:6px;white-space:nowrap;overflow:visible">${U.esc(it.label)} · ${U.esc(U.modeLabel[it.mode])}</div>`).join('')}
      </div>
      <div class="row sb num muted tiny">${hours.map((h) => `<span>${U.time(h)}</span>`).join('')}</div></section>
    <div class="grid" style="--min:420px">
      <section class="card"><h2 class="h2" style="margin-bottom:8px">Defaults for every plan</h2>
        ${row('Number of lots', 'One order is split into this many smaller orders.', `<input class="in num" id="lots" value="${x.exec_lots}" style="width:110px">`)}
        ${row('Minutes between lots', 'Unfilled lots are cancelled and re-priced when the next one goes.', `<input class="in num" id="int" value="${x.exec_interval_min}" style="width:110px">`)}
        ${row('Start entries', '"Not before" this time. A later signal starts at once if the market is open.', `<div class="row"><div class="seg" id="sm"><button data-v="time" class="${x.exec_start_mode === 'time' ? 'on' : ''}">At a set time</button><button data-v="asap" class="${x.exec_start_mode !== 'time' ? 'on' : ''}">At market open</button></div><input class="in num" id="stime" value="${x.exec_start_time}" style="width:90px"></div>`)}
        ${row('Start exits', 'Selling is usually more urgent than buying.', `<div class="seg" id="em"><button data-v="asap" class="${x.exec_exit_mode !== 'same' ? 'on' : ''}">As soon as the market is open</button><button data-v="same" class="${x.exec_exit_mode === 'same' ? 'on' : ''}">Same as entries</button></div>`)}
        ${row('Limit price', 'Each lot is a limit order this far through the market (%).', `<input class="in num" id="off" value="${x.exec_limit_offset_pct}" style="width:110px">`)}
        ${row('Retries per lot', 'After this many re-sends a lot is marked failed and LINE tells you.', `<input class="in num" id="ret" value="${x.exec_retries}" style="width:110px">`)}
        ${row('Smallest lot (USD)', 'Small plans use fewer lots so each lot is at least this big.', `<input class="in num" id="minlot" value="${x.exec_min_lot_usd}" style="width:110px">`)}
        ${row('Largest single order (USD)', 'A safety cap per order.', `<input class="in num" id="maxo" value="${x.exec_max_order_usd}" style="width:110px">`)}
        ${row('When new money arrives', 'The default for Add money, Move and the paper start money. You can still choose each time you add money.', `<div class="seg" id="nm"><button data-v="now" class="${x.new_money_start !== 'buy' ? 'on' : ''}">Invest at today's signal</button><button data-v="buy" class="${x.new_money_start === 'buy' ? 'on' : ''}">Wait for the next buy signal</button></div>`)}
      </section>
      <div class="col" style="gap:20px">
        <section class="card"><h2 class="h2" style="margin-bottom:6px">Per strategy</h2><div class="tw"><table class="t"><thead><tr><th>Strategy</th><th>Now</th><th></th></tr></thead><tbody>
          ${d.strategies.map((s) => `<tr><td><span class="row" style="gap:8px">${U.dot(s.color)}${U.esc(s.name)}</span></td><td class="small">${U.esc(s.text)}${Object.keys(s.override).length ? ' ' + U.pill('info', 'own') : ''}</td>
            <td class="r"><a class="btn s" href="#/strategies/${s.id}">Edit</a></td></tr>`).join('')}</tbody></table></div>
          <div class="muted small" style="margin-top:8px">Regimes decide after the US close and start at the next market open (the research filled at the next open). Edit a strategy's own lots and start time on its Execution tab.</div></section>
        <section class="card"><h2 class="h2" style="margin-bottom:6px">US market calendar</h2>
          ${d.calendar.map((c) => `<div class="kv"><span>${U.esc(c.date)}</span>${U.pill(c.kind === 'closed' ? 'warn' : 'info', c.kind)}</div>`).join('') || '<div class="muted">No holidays in the next 4 months</div>'}
          <div class="muted small" style="margin-top:8px">Plans that land on a closed day wait for the next session. The holiday list lives in app/markethours.py; check it each January.</div></section>
      </div>
    </div>`;
    function row(t, h, input) { return `<div style="display:grid;grid-template-columns:minmax(200px,1fr) minmax(240px,1.3fr);gap:16px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line2)"><div><b style="font-weight:500">${t}</b><div class="muted small">${h}</div></div><div>${input}</div></div>`; }
    U.on(el, '#sm button, #em button, #nm button', 'click', (e, b) => b.parentElement.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)));
    el.querySelector('#save').onclick = (e) => U.busy(e.target, async () => {
      const v = (id) => el.querySelector(id).value.trim();
      await U.api('/api/settings/execution', { body: { defaults: { exec_lots: v('#lots'), exec_interval_min: v('#int'), exec_start_mode: el.querySelector('#sm .on').dataset.v,
        exec_start_time: v('#stime'), exec_exit_mode: el.querySelector('#em .on').dataset.v, exec_limit_offset_pct: v('#off'), exec_retries: v('#ret'),
        exec_min_lot_usd: v('#minlot'), exec_max_order_usd: v('#maxo'), new_money_start: el.querySelector('#nm .on').dataset.v } } });
      U.toast('Execution settings saved');
    });
  };

  /* ---------------------------------------------------------------- trades (fills) */
  V.trades = async function (el) {
    const mode = U.mode();
    const strats = (await U.api('/api/strategies?mode=' + mode)).strategies;
    const f = { strategy: '', side: '', days: 0, offset: 0 };
    async function load() {
      const q = new URLSearchParams({ mode, limit: 50, offset: f.offset });
      if (f.strategy) q.set('strategy', f.strategy);
      if (f.side) q.set('side', f.side);
      if (f.days) q.set('days', f.days);
      const d = await U.api('/api/fills?' + q);
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">${U.modeLabel[mode]} account · every filled lot</div><h1 class="h1">Trades</h1></div>
        <a class="btn" href="/api/fills.csv?mode=${mode}">Export CSV</a></div>
        <div class="row" style="gap:8px"><button class="btn s ${!f.strategy ? 'p' : ''}" data-st="">All strategies</button>
          ${strats.map((s) => `<button class="btn s ${f.strategy === s.id ? 'p' : ''}" data-st="${s.id}">${U.dot(s.color)} ${U.esc(s.name.split(' · ')[0])}</button>`).join('')}
          <span style="flex:1"></span><div class="seg" id="sd">${[['', 'All'], ['BUY', 'Buys'], ['SELL', 'Sells']].map(([k, l]) => `<button data-v="${k}" class="${f.side === k ? 'on' : ''}">${l}</button>`).join('')}</div>
          <div class="seg" id="dy">${[[0, 'All time'], [7, '7 days'], [30, '30 days']].map(([k, l]) => `<button data-v="${k}" class="${+f.days === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>
        <div class="grid" style="--min:200px"><div class="card"><div class="eyebrow">Filled lots</div><div class="num big" style="margin-top:6px">${d.stats.fills}</div></div>
          <div class="card"><div class="eyebrow">Value traded</div><div class="num big" style="margin-top:6px">${U.usd(d.stats.traded, 0)}</div></div>
          <div class="card"><div class="eyebrow">Plans completed</div><div class="num big" style="margin-top:6px">${d.stats.plans_done}</div></div></div>
        <section class="card flush"><div class="tw"><table class="t"><thead><tr><th>Time (BKK)</th><th>Strategy</th><th>Side</th><th>Symbol</th><th class="r">Qty</th><th class="r">Avg price</th><th class="r">Value</th><th>Lot</th><th>Plan · reason</th></tr></thead><tbody>
          ${d.rows.map((r) => `<tr><td class="num">${U.dt(r.updated_at)}</td><td><span class="row" style="gap:8px">${U.dot(r.color)}${U.esc(r.name)}</span></td>
            <td>${U.pill(r.side === 'BUY' ? 'ok' : 'err', r.side)}</td><td class="num">${U.esc(r.symbol)}</td><td class="r num">${U.n(r.filled_qty, 0)}</td><td class="r num">${U.usd(r.avg_price)}</td>
            <td class="r num">${U.usd(r.value)}</td><td class="num muted">${r.lot}/${r.lots}${r.retry ? ' ↻' + r.retry : ''}</td><td class="muted small">#${r.plan_id} · ${U.esc(r.reason)}</td></tr>`).join('') || '<tr><td colspan="9" class="empty">No fills yet</td></tr>'}
          </tbody></table></div>
          <div class="row sb" style="padding:12px 16px"><span class="muted small">Showing ${d.rows.length ? f.offset + 1 : 0}–${f.offset + d.rows.length} of ${d.total}</span>
            <div class="row" style="gap:6px"><button class="btn s" id="prev" ${f.offset ? '' : 'disabled'}>Previous</button><button class="btn s" id="nxt" ${f.offset + 50 < d.total ? '' : 'disabled'}>Next</button></div></div></section>`;
      U.on(el, '[data-st]', 'click', (e, b) => { f.strategy = b.dataset.st; f.offset = 0; load(); });
      U.on(el, '#sd button', 'click', (e, b) => { f.side = b.dataset.v; f.offset = 0; load(); });
      U.on(el, '#dy button', 'click', (e, b) => { f.days = +b.dataset.v; f.offset = 0; load(); });
      el.querySelector('#prev').onclick = () => { f.offset = Math.max(0, f.offset - 50); load(); };
      el.querySelector('#nxt').onclick = () => { f.offset += 50; load(); };
    }
    await load();
  };

  /* ---------------------------------------------------------------- positions */
  V.positions = async function (el) {
    const mode = U.mode();
    async function load() {
      const d = await U.api('/api/positions?mode=' + mode);
      const bad = d.rows.filter((r) => r.status === 'missing');
      const c = d.cash;
      const cashOk = c.outside == null || c.outside > -1;
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">Bot books vs ${U.modeLabel[mode]} account · checked ${d.checked_at ? U.time(d.checked_at) : '—'}</div><h1 class="h1">Positions</h1></div>
        <button class="btn p" id="rc">Reconcile now</button></div>
        ${d.account_error ? `<div class="note err">${U.esc(d.account_error)}</div>` : bad.length || !cashOk ? `<div class="note err"><b>${bad.length} symbol(s) differ from the account.</b> Buys in those symbols wait until you check. Did you sell something by hand in Webull?</div>`
          : `<div class="note ok"><b>All ${d.rows.length} symbols and cash match the account.</b><span>No action needed. A mismatch shows up in the nightly Health check and on LINE.</span></div>`}
        <section class="card flush"><div style="padding:14px 18px 4px"><h2 class="h2">Bot positions</h2></div><div class="tw"><table class="t"><thead><tr><th>Symbol</th><th class="r">Account shares</th><th class="r">Bot books</th><th>Owned by</th><th class="r">Price</th><th class="r">Value</th><th class="r">Difference</th><th>Status</th></tr></thead><tbody>
          ${d.rows.map((r) => `<tr><td><b class="num">${U.esc(r.symbol)}</b></td><td class="r num">${U.n(r.account, 0)}</td><td class="r num">${U.n(r.bot, 0)}</td>
            <td>${r.owners.map((o) => `<span class="pill" style="margin-right:4px">${U.dot(o.color)} ${U.esc(o.name.split(' · ')[0])} · ${U.n(o.qty, 0)}</span>`).join('')}</td>
            <td class="r num">${U.usd(r.price)}</td><td class="r num">${U.usd(r.value, 0)}</td><td class="r num">${r.diff == null ? '—' : U.n(r.diff, 0)}</td>
            <td>${U.pill(r.status === 'match' ? 'ok' : r.status === 'extra' ? 'info' : r.status === 'missing' ? 'err' : '', r.status === 'extra' ? 'extra = yours' : r.status)}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">The bot holds nothing in this mode yet</td></tr>'}</tbody></table></div></section>
        <div class="grid" style="--min:380px">
          <section class="card"><h2 class="h2" style="margin-bottom:8px">Cash</h2>
            <div class="kv"><span class="muted">Account cash balance</span><span class="num">${U.usd(c.account)}</span></div>
            <div class="kv"><span class="muted">Cash inside strategies</span><span class="num">${U.usd(c.strategies)}</span></div>
            <div class="kv"><span class="muted">Bot unassigned</span><span class="num">${U.usd(c.unassigned)}</span></div>
            <div class="kv"><span class="muted">Not for the bot (free cash)</span><span class="num">${U.usd(c.outside)}</span></div>
            <div class="kv"><b>Bot's cash covered by the account</b><span class="num ${cashOk ? 'up' : 'dn'}">${cashOk ? 'yes ✓' : 'no ✗'}</span></div></section>
          <section class="card"><div class="row sb" style="margin-bottom:8px"><h2 class="h2">Not bot — your own holdings</h2>${U.pill('', 'never traded by the bot')}</div>
            ${d.not_bot.map((p) => `<div class="kv"><span class="num">${U.esc(p.symbol)} · ${U.n(p.qty, 0)} sh</span><span class="num">${U.usd(p.value)}</span></div>`).join('') || '<div class="muted small">None</div>'}
            <div class="muted small" style="margin-top:10px">Shares in the account beyond the bot's books (e.g. you bought QLD yourself) are yours and are never sold by the bot.</div></section>
        </div>`;
      el.querySelector('#rc').onclick = (e) => U.busy(e.target, load);
    }
    await load();
    return { cleanup: () => {}, refresh: () => load().catch(() => {}), every: 60000 };
  };
})();
