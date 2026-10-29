/* Orders waiting for the next US open (or trading now): V.renderNextOrders(el, {sid}).
   Sells are exact; buys are estimated from the last price (the bot sizes each lot when it sends it). */
(function () {
  const V = window.Views || (window.Views = {});
  const inTxt = (t) => {
    const s = t - Date.now() / 1000;
    if (s <= 0) return 'now';
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h ? `in ${h} h ${m} min` : `in ${m} min`;
  };
  const fullDt = (t) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).format(t * 1000);
  const REASON = { signal: 'signal', rebalance: 'rebalance', add: 'new money', withdraw: 'withdrawal', move: 'money move', stop: 'stop & sell' };

  V.renderNextOrders = async function (el, opts) {
    opts = opts || {};
    const mode = U.mode();
    let d;
    try { d = await U.api('/api/next-orders?mode=' + mode + (opts.sid ? '&sid=' + encodeURIComponent(opts.sid) : '')); } catch (e) { el.innerHTML = ''; return; }
    const rows = d.rows || [];
    if (!rows.length) {
      el.innerHTML = opts.sid
        ? `<div class="note info small" style="margin:0;display:block"><b>Next US open:</b> no order waiting — this strategy already holds its target. If the next close changes its signal, the orders appear here (and on LINE) soon after the close.</div>`
        : `<section class="card row sb" style="gap:10px;padding:14px 18px;flex-wrap:wrap"><div><b>Next US open</b> <span class="muted small">· ${U.modeLabel[mode]}</span>
            <div class="muted small">No orders waiting. Strategies decide after each US close (about 04:00–05:30 Bangkok); anything they will buy or sell at the next open shows here and on LINE.</div></div>
            <a class="small" href="#/orders">Orders →</a></section>`;
      return;
    }
    const running = rows.filter((r) => r.state === 'running'), queued = rows.filter((r) => r.state === 'queued');
    const title = queued.length && d.next_start ? `Next US open · ${fullDt(d.next_start)} Bangkok <span class="muted small" style="font-weight:400">(${inTxt(d.next_start)})</span>`
      : 'Trading now';
    const body = rows.map((r) => r.items.map((it, k) => `<tr>
        ${k === 0 ? `<td rowspan="${r.items.length}" style="vertical-align:top;white-space:normal;min-width:170px">
          <a href="#/strategies/${U.esc(r.strategy)}" class="row" style="gap:8px;flex-wrap:nowrap;color:var(--text)">${U.dot(r.color || '#888', 10)}<b>${U.esc(r.name)}</b></a>
          <div class="tiny muted" style="margin-top:3px">${r.state === 'running' ? U.pill('info', 'running · ' + r.rounds_left + ' round' + (r.rounds_left === 1 ? '' : 's') + ' left') : 'starts ' + U.time(r.start_at)} · ${r.lots} × ${r.interval} min · ${U.esc(REASON[r.reason] || r.reason)}</div></td>` : ''}
        <td>${it.side === 'BUY' ? U.pill('ok', 'BUY') : U.pill('err', 'SELL')}</td>
        <td class="mono"><b>${U.esc(it.symbol)}</b>${it.blocked ? ' ' + U.pill('warn', 'refused') : ''}</td>
        <td class="r num">${it.qty == null ? '—' : (it.exact ? '' : '≈') + U.qty(it.qty)}${it.filled ? `<div class="tiny muted">${U.qty(it.filled)} done</div>` : ''}</td>
        <td class="r num">${it.price ? U.usd(it.price) : '—'}</td>
        <td class="r num">${it.value == null ? '—' : '≈' + U.usd(it.value, 0)}</td>
        ${k === 0 ? `<td rowspan="${r.items.length}" class="small" style="vertical-align:top;white-space:normal;min-width:200px">
          ${r.why ? `<div>${U.esc(r.why)}</div>` : ''}<div class="muted tiny" style="margin-top:3px">After: ${Object.entries(r.after).map(([s, w]) => `${(w * 100).toFixed(0)}% ${U.esc(s)}`).join(' + ') || 'cash'}</div></td>` : ''}
      </tr>`).join('')).join('');
    const narrow = (el.clientWidth || window.innerWidth) < 640;          // phones: one block per strategy instead of a wide table
    const cards = rows.map((r) => `<div style="border:1px solid var(--line);border-radius:10px;padding:12px 14px" class="col">
        <a href="#/strategies/${U.esc(r.strategy)}" class="row" style="gap:8px;color:var(--text)">${U.dot(r.color || '#888', 10)}<b>${U.esc(r.name)}</b></a>
        <div class="tiny muted" style="margin:3px 0 8px">${r.state === 'running' ? 'running · ' + r.rounds_left + ' rounds left' : 'starts ' + U.time(r.start_at)} · ${r.lots} × ${r.interval} min</div>
        ${r.items.map((it) => `<div class="row sb" style="gap:8px;padding:4px 0"><span class="row" style="gap:8px">${it.side === 'BUY' ? U.pill('ok', 'BUY') : U.pill('err', 'SELL')}<b class="mono">${it.qty == null ? '' : (it.exact ? '' : '≈') + U.qty(it.qty)} ${U.esc(it.symbol)}</b></span>
          <span class="num small">${it.value == null ? '' : '≈' + U.usd(it.value, 0)}<span class="muted"> @ ${it.price ? U.usd(it.price) : '—'}</span></span></div>`).join('')}
        ${r.why ? `<div class="small" style="margin-top:6px">${U.esc(r.why)}</div>` : ''}<div class="tiny muted">After: ${Object.entries(r.after).map(([k, w]) => `${(w * 100).toFixed(0)}% ${U.esc(k)}`).join(' + ') || 'cash'}</div></div>`).join('');
    el.innerHTML = `<section class="card col" style="gap:12px;${opts.sid ? '' : 'border-color:color-mix(in srgb, var(--accent) 45%, var(--line))'}">
      <div class="row sb" style="gap:10px;flex-wrap:wrap;align-items:flex-start"><div style="min-width:0;flex:1 1 320px">
        <h2 class="h2">${title}</h2>
        <div class="muted small">${U.modeLabel[mode]} · decided after the US close${running.length && queued.length ? ' · some plans are already trading' : ''}. Sells are exact; buys are estimated from the last price and sized when each lot is sent.</div></div>
        <div class="row" style="gap:8px;flex-wrap:wrap">${U.pill('ok', 'Buys ≈' + U.usd(d.buys, 0))}${U.pill('err', 'Sells ≈' + U.usd(d.sells, 0))}${opts.sid ? '' : U.pill('', rows.length + ' strateg' + (rows.length === 1 ? 'y' : 'ies'))}</div></div>
      ${(d.warnings || []).map((w) => `<div class="note warn small" style="margin:0;display:block">${U.esc(w)}</div>`).join('')}
      ${narrow ? cards : `<div class="tw"><table class="t"><thead><tr><th>Strategy</th><th>Action</th><th>Symbol</th><th class="r">Shares</th><th class="r">Last price</th><th class="r">Value</th><th>Why</th></tr></thead>
        <tbody>${body}</tbody></table></div>`}
      ${Object.keys(d.inside || {}).length && !opts.sid ? `<div class="tiny muted">Settled inside the bot (one strategy sells what another buys, no Webull order, no fee): ${Object.entries(d.inside).map(([s, v]) => `${U.esc(s)} ≈${U.usd(v, 0)}`).join(', ')}. Webull gets only the net: ${Object.keys(d.inside).map((s) => `${U.esc(s)} ${d.by_symbol[s] >= 0 ? 'buy' : 'sell'} ≈${U.usd(Math.abs(d.by_symbol[s] || 0), 0)}`).join(', ')}.</div>` : ''}
      ${(d.shared || []).filter((s) => !(d.inside || {})[s]).length && !opts.sid ? `<div class="tiny muted">${d.shared.filter((s) => !(d.inside || {})[s]).map((s) => U.esc(s)).join(', ')}: traded by more than one strategy in the same direction; each sends its own orders.</div>` : ''}
      <div class="row sb tiny muted" style="gap:8px;flex-wrap:wrap"><span>Times are Bangkok time. Lots go out from the US open, spaced as set in Execution.</span>
        <a href="#/orders">Start now or cancel on the Orders page →</a></div>
    </section>`;
  };
})();
