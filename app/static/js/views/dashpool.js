/* Dashboard when the strategy pool is on (v2): does anything need me → how much and how is it doing → is it working as
   expected → what happens next; then members, where the money is, profit, month by month. Data: /api/dashboard → d.dash
   (app/dashpool.py). */
(function () {
  const V = window.Views || (window.Views = {});
  const pc = (x, d = 1) => (x == null ? '—' : (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x * 100).toFixed(d) + '%');
  const short = (n) => U.esc(String(n || '').split(' (')[0]);
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function attention(a) {
    if (a.items.length) {
      return `<div class="grid" style="--min:300px">${a.items.map((x) => `<div class="note fx ${x.level}" style="align-items:center" role="${x.level === 'err' ? 'alert' : 'status'}">
        <div style="flex:1;min-width:0"><b>${U.esc(x.title)}</b>${x.text ? `<div class="small">${U.esc(x.text)}</div>` : ''}</div>
        ${x.action ? `<a class="btn s ${x.level === 'err' ? 'p' : ''}" href="${x.action.href}" style="white-space:nowrap">${U.esc(x.action.label)}</a>` : ''}</div>`).join('')}</div>`;
    }
    return `<div class="row" style="gap:10px;flex-wrap:wrap;padding:12px 16px;border-radius:12px;background:var(--ok-bg);color:var(--ok-fg)">
      <b style="font-size:14.5px">✓ All good — nothing needs you</b>
      ${a.ok.map((t) => `<span class="row small" style="gap:6px;padding:4px 10px;border-radius:999px;background:var(--panel);color:var(--text);border:1px solid var(--line)">${U.dot('var(--ok-fg)', 8)}${U.esc(t)}</span>`).join('')}
      <a class="small" href="#/health" style="margin-left:auto;color:var(--ok-fg)">Health check →</a></div>`;
  }

  /* bullet: a bar for the real value over the backtest's normal band (green) with its middle (black mark) */
  function bullet(val, lo, hi, mid, mn, mx) {
    const X = (v) => Math.max(0, Math.min(100, (v - mn) / (mx - mn) * 100));
    const inside = val == null || lo == null || (val >= lo && val <= hi);
    const a = X(Math.min(0, val || 0)), b = X(Math.max(0, val || 0));
    const z = mn < 0 && mx > 0 ? `<span style="position:absolute;left:${X(0)}%;top:-2px;bottom:-2px;width:1px;background:var(--muted)"></span>` : '';
    return `<div style="position:relative;height:16px;border-radius:4px;background:var(--line2);margin:6px 0 4px">
      ${lo != null ? `<span style="position:absolute;top:0;bottom:0;left:${X(lo)}%;width:${Math.max(X(hi) - X(lo), 0.8)}%;background:color-mix(in srgb,var(--ok-fg) 22%,transparent);border-radius:4px"></span>` : ''}${z}
      ${val != null ? `<span style="position:absolute;top:5px;height:6px;border-radius:3px;left:${mn < 0 ? a : 0}%;width:${Math.max((mn < 0 ? b - a : X(val)), 0.8)}%;background:${inside ? 'var(--ok-fg)' : 'var(--err-fg)'}"></span>` : ''}
      ${mid != null ? `<span style="position:absolute;top:-3px;bottom:-3px;width:2px;left:${X(mid)}%;background:var(--text)"></span>` : ''}</div>`;
  }

  function checkCard(c, pv, since) {
    const bt = c.bt || {}, rg = bt.ranges || {}, b1 = (rg.bands || [])[0];
    const wait = !bt.ready ? `<div class="muted small"><span class="spin"></span> The backtest of today's members is running (${bt.done || 0} of ${bt.of || '…'})…</div>` : '';
    const month = c.month, fall = c.fall, work = c.work, avg = bt.idle != null ? 1 - bt.idle / 100 : null, worst = (bt.all || {}).maxdd;
    const monthOk = b1 && month != null ? (month * 100 >= b1[1] && month * 100 <= b1[3]) : null;
    return `<section class="card col" style="gap:6px">
      <div class="row sb"><div class="eyebrow">Is it working as expected?</div>${c.too_early ? `<span class="pill info">pool: ${c.since_days} day${c.since_days === 1 ? '' : 's'} · too early</span>` : ''}</div>${wait}
      <div class="small" style="margin-top:4px"><b>This month</b> <span class="num ${U.cls(month)}">${pc(month)}</span></div>
      ${bullet(month == null ? null : month * 100, b1 && b1[1], b1 && b1[3], b1 && b1[2], -20, 20)}
      <div class="row sb tiny muted"><span>${b1 ? `normal month ${b1[1]}% … +${b1[3]}% (8 of 10 backtest months)` : 'normal month: after the backtest'}</span><span>${monthOk == null ? '' : monthOk ? 'inside' : 'outside the usual range'}</span></div>
      <div class="small" style="margin-top:6px"><b>Fall from the top</b> <span class="num ${U.cls(fall)}">${pc(fall)}</span></div>
      ${bullet(fall == null ? null : fall * 100, worst, 0, null, Math.min(-35, (worst || -30) - 5), 0)}
      <div class="row sb tiny muted"><span>${worst != null ? `backtest's worst fall ${worst}% (since ${String((bt.all || {}).from || '').slice(0, 4)})` : ''}</span><span>${fall != null && worst != null ? (fall * 100 >= worst ? 'inside' : 'past it') : ''}</span></div>
      <div class="small" style="margin-top:6px"><b>Money at work</b> <span class="num">${work == null ? '—' : Math.round(work * 100) + '%'}</span></div>
      ${bullet(work == null ? null : work * 100, null, null, avg == null ? null : avg * 100, 0, 100)}
      <div class="row sb tiny muted"><span>${avg != null ? `backtest average ${Math.round(avg * 100)}% in trades (black mark)` : ''}</span><span>${pv.waiting.length ? pv.waiting.length + ' waiting for money' : ''}</span></div>
      <div class="muted tiny" style="margin-top:4px">Green band = where the pool's backtest of today's ${pv.members.length} members usually is · black mark = its middle.${c.too_early ? ` The pool started ${since ? U.day(since) : 'recently'}; it is judged against its backtest after 20 trading days.` : ''}</div></section>`;
  }

  function nextCard(d) {
    const ds = d.dash, plans = ds.plans || [];
    const dec = (d.next || []).find((n) => /Daily decision/.test(n.title));
    const rows = [];
    if (dec) rows.push([U.dt(dec.t).replace('Today ', ''), 'After the US close the bot decides each member\'s signal; LINE tells you any buy or sell.']);
    plans.forEach((p) => rows.push([p.start_at ? U.dt(p.start_at).replace('Today ', '') : 'Now',
      `<b>${p.buys.length ? 'Buy' : 'Sell'} ${U.esc((p.buys.length ? p.buys : p.sells).join(', '))}</b> · ${short(p.name)}${p.amount ? ' · ' + U.usd(p.amount, 0) : ''} · ${p.lots} lot${p.lots > 1 ? 's' : ''}${p.state === 'queued' ? '' : ' · running'}`]));
    if (!plans.length) rows.push(['', '<span class="muted">No orders planned for the next open.</span>']);
    const inT = ds.pool.members.filter((m) => m.value > 0.5).length;
    rows.push(['After', `Free cash ${U.usd(ds.pool.free, 0)} · next trade gets ${ds.pool.slot_pct}% = ${U.usd(ds.pool.slot_usd, 0)}${inT ? ` · ${inT} trade${inT > 1 ? 's' : ''} open` : ''}`]);
    return `<section class="card col" style="gap:10px"><div class="eyebrow">What happens next · Bangkok time</div>
      <div style="display:grid;grid-template-columns:92px 1fr;gap:6px 12px;font-size:13.5px">${rows.map((r) => `<span class="num" style="font-weight:600;color:var(--accent)">${r[0]}</span><span>${r[1]}</span>`).join('')}</div>
      <a class="small" href="#/orders" style="margin-top:auto">Orders and schedule →</a></section>`;
  }

  /* real return (time-weighted, %) since the start, with the backtest's usual range from the pool's start */
  function chartSvg(ds, mode) {
    const cv = ds.curve || [];
    if (cv.length < 2) return '<div class="empty small">The chart fills in as the bot records its value after each US close.</div>';
    const w = 1180, h = 230, n = cv.length;
    const bands = ((ds.check.bt || {}).ranges || {}).bands || [];
    const t0 = ds.since ? new Date(ds.since * 1000).toISOString().slice(0, 10) : null;
    const i0 = t0 ? Math.max(0, cv.findIndex((p) => p[0] >= t0)) : -1;
    const base = i0 > 0 ? cv[i0 - 1][1] : 0;
    const band = (k) => {                                     // k trading days after the pool started → [lo, mid, hi] in %
      const m = k / 21;
      if (!bands.length || m <= 0) return [0, 0, 0];
      const lo = Math.max(1, Math.min(12, Math.floor(m))), hi = Math.min(12, lo + 1);
      const a = bands[lo - 1], b = bands[hi - 1] || a, f = m < 1 ? m : Math.min(1, m - lo);
      if (m < 1) return [a[1] * Math.sqrt(m), a[2] * m, a[3] * Math.sqrt(m)];
      return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f];
    };
    const g = (x) => (1 + base / 100) * (1 + x / 100) * 100 - 100;
    const pts = cv.map((p) => p[1]);
    const ext = [];
    for (let i = i0; i0 >= 0 && i < n; i++) { const b = band(i - i0 + 1); ext.push(g(b[0]), g(b[2])); }
    const lo = Math.min(-5, ...pts, ...ext) - 2, hi = Math.max(5, ...pts, ...ext) + 2;
    const X = (i) => 46 + i * (w - 120) / (n - 1), Y = (v) => 12 + (h - 44) * (1 - (v - lo) / (hi - lo));
    const step = Math.max(5, Math.ceil((hi - lo) / 5 / 5) * 5);
    let grid = '';
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) grid += `<line x1="46" x2="${w - 74}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line2)"/><text x="${w - 68}" y="${Y(v) + 4}" font-size="10.5" fill="var(--muted)">${v > 0 ? '+' : ''}${v}%</text>`;
    const xs = cv.map((p, i) => [i, p[0]]).filter((x, i) => i % Math.max(1, Math.floor(n / 6)) === 0 || i === n - 1)
      .map(([i, dd]) => `<text x="${X(i)}" y="${h - 10}" font-size="10.5" fill="var(--muted)" text-anchor="middle">${U.day(Date.parse(dd) / 1000)}</text>`).join('');
    let extra = '';
    if (i0 >= 0 && bands.length) {
      const up = [], dn = [], md = [];
      for (let i = i0 - 1; i < n; i++) { const b = band(Math.max(0, i - i0 + 1)); up.push(`${X(Math.max(i, 0))},${Y(g(b[2]))}`); dn.unshift(`${X(Math.max(i, 0))},${Y(g(b[0]))}`); md.push(`${X(Math.max(i, 0))},${Y(g(b[1]))}`); }
      extra = `<polygon points="${up.concat(dn).join(' ')}" fill="var(--ok-fg)" opacity=".14"/><polyline points="${md.join(' ')}" fill="none" stroke="var(--ok-fg)" stroke-width="1.5" stroke-dasharray="5 4"/>`;
    }
    const line = pts.map((v, i) => `${X(i)},${Y(v)}`).join(' ');
    const pl = i0 > 0 ? `<line x1="${X(i0 - 1)}" x2="${X(i0 - 1)}" y1="12" y2="${h - 34}" stroke="var(--warn-fg)" stroke-dasharray="3 3"/><text x="${X(i0 - 1) - 6}" y="24" font-size="10.5" fill="var(--warn-fg)" text-anchor="end">pool on</text>` : '';
    return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px" role="img" aria-label="Real return since the start against the backtest range">${grid}${xs}${extra}
      <polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="2.6"/>${pl}</svg>`;
  }

  function board(pv) {
    const lane = (title, list, emptyText, total) => `<div style="background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:8px;min-height:110px">
      <div class="row sb tiny" style="text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:2px 4px"><span>${title} · ${list.length}</span>${total ? `<span class="num">${total}</span>` : ''}</div>
      ${list.length ? `<div class="grid" style="--min:190px;gap:8px">${list.map(card).join('')}</div>` : `<div class="muted small" style="padding:4px 6px">${emptyText}</div>`}</div>`;
    const card = (m) => `<a href="#/strategies/${m.id}" style="color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 11px;font-size:13px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 8px">
      <span class="row" style="gap:7px;flex-wrap:nowrap;font-weight:600;min-width:0">${U.dot(m.color, 9)}<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${short(m.name)}</span></span>
      <span class="num" style="font-weight:600">${m.value > 0.5 ? U.usd(m.value, 0) : ''}</span>
      <span class="muted tiny">${U.esc(m.etf || '')}${m.since ? ' · since ' + U.day(m.since) : ''}${/group cap/.test(m.status[1]) ? ' · group cap' : /partial/.test(m.status[1]) ? ' · partial' : ''}</span>
      <span class="num tiny ${U.cls(m.open_pnl)}">${m.open_pnl != null ? U.sgnUsd(m.open_pnl, 0) : ''}</span></a>`;
    const st = (m) => m.status[1];
    const inT = pv.members.filter((m) => /^In a trade/.test(st(m)));
    const buy = pv.members.filter((m) => /buys at the next/.test(st(m)));
    const wait = pv.members.filter((m) => /waits for money/.test(st(m)));
    const back = pv.members.filter((m) => /Trade ended|Selling/.test(st(m)));
    const none = pv.members.filter((m) => !inT.includes(m) && !buy.includes(m) && !wait.includes(m) && !back.includes(m));
    const inUsd = inT.reduce((a, m) => a + m.value, 0);
    return `<section class="card col" style="gap:12px">
      <div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">Members now</h2><div class="muted small">Where each of the ${pv.members.length} members is · money goes out to a trade and back to the pool</div></div><a class="small" href="#/money">Manage the pool →</a></div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
        ${lane('In a trade', inT, 'No member is in a trade.', inT.length ? `${U.usd(inUsd, 0)} · ${pv.total ? Math.round(inUsd / pv.total * 100) : 0}%` : '')}
        ${lane('Buys at the next open', buy, 'No buy planned.')}
        ${lane('Waiting for money', wait, 'None — free cash covers the next trades.')}
        ${lane('Money coming back', back, 'None. When a trade ends, its money goes back to the pool.')}
      </div>
      <div class="row small" style="gap:8px;flex-wrap:wrap"><span class="muted">No signal · ${none.length}:</span>${none.map((m) => `<a href="#/strategies/${m.id}" class="row" style="gap:6px;padding:4px 10px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);color:var(--text);font-size:12.5px">${U.dot(m.color, 8)}${short(m.name)}</a>`).join('')}
        ${pv.outside.length ? `<span class="muted" style="margin-left:8px">· Not in the pool (signals only): ${pv.outside.length}${pv.outside.some((r) => r.leaving) ? ', ' + pv.outside.filter((r) => r.leaving).length + ' finishing a trade' : ''}</span>` : ''}</div></section>`;
  }

  function moneyCard(pv) {
    const T = pv.total || 1, scale = Math.max(40, pv.cap_pct * 1.6);
    const g = pv.groups.filter((x) => x.value > 0.5).map((x) => `<div style="display:grid;grid-template-columns:170px minmax(0,1fr) 110px;gap:12px;align-items:center;padding:6px 0">
      <div class="small"><b style="font-weight:500">${U.esc(x.label)}</b><div class="muted tiny">${U.esc(x.who.join(', '))}</div></div>
      <div style="position:relative;height:10px;border-radius:5px;background:var(--line2)"><i style="position:absolute;left:0;top:0;bottom:0;border-radius:5px;width:${Math.min(100, x.pct * 100 / scale * 100)}%;background:${x.color}"></i><span style="position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--text);left:${pv.cap_pct / scale * 100}%"></span></div>
      <div class="num small" style="text-align:right">${(x.pct * 100).toFixed(1)}% <span class="muted">/ ${pv.cap_pct}%</span></div></div>`).join('');
    return `<section class="card"><div class="row sb" style="margin-bottom:8px"><h2 class="h2">Where the money is</h2><span class="muted small">by market · black line = group cap ${pv.cap_pct}%</span></div>
      ${g || '<div class="muted small" style="padding:6px 0">No member is in a trade: everything is free cash.</div>'}
      <div style="display:grid;grid-template-columns:170px minmax(0,1fr) 110px;gap:12px;align-items:center;padding:6px 0">
        <div class="small"><b style="font-weight:500">Free cash</b><div class="muted tiny">for the next signals</div></div>
        <div style="position:relative;height:10px;border-radius:5px;background:var(--line2)"><i style="position:absolute;left:0;top:0;bottom:0;border-radius:5px;width:${pv.free / T * 100}%;background:repeating-linear-gradient(45deg,var(--accent) 0 5px,color-mix(in srgb,var(--accent) 55%,transparent) 5px 10px);opacity:.55"></i></div>
        <div class="num small" style="text-align:right">${(pv.free / T * 100).toFixed(1)}%</div></div>
      <div class="row sb small" style="margin-top:6px"><span class="muted">Total ${U.usd(pv.total, 0)}</span><a href="#/money">Money →</a></div></section>`;
  }

  function monthsCard(ds) {
    const rows = ds.months || [];
    if (!rows.length) return '';
    const bt = (ds.check.bt || {}).ranges || {}, b1 = (bt.bands || [])[0];
    const years = [...new Set(rows.map((r) => r.y))];
    const cell = (r) => {
      if (!r) return '<td class="muted">·</td>';
      const v = r.ret * 100, out = b1 && (v < b1[1] || v > b1[3]);
      const bg = r.ret < 0 ? `color-mix(in srgb,var(--err-fg) ${out ? 26 : 12}%,transparent)` : `color-mix(in srgb,var(--ok-fg) ${out ? 24 : 12}%,transparent)`;
      return `<td class="num ${U.cls(r.ret)}" style="background:${bg}" title="${r.before_pool ? 'before the pool' : r.mixed ? 'the pool started this month' : ''}${r.partial ? ' · so far' : ''}">${pc(r.ret)}${r.before_pool ? '' : r.mixed ? '*' : ''}</td>`;
    };
    const body = years.map((y) => {
      const yr = rows.filter((r) => r.y === y).reduce((a, r) => a * (1 + r.ret), 1) - 1;
      return `<tr><td><b>${y}</b></td>${MON.map((_, i) => cell(rows.find((r) => r.y === y && r.m === i + 1))).join('')}<td class="num ${U.cls(yr)}"><b>${pc(yr)}</b></td></tr>`;
    }).join('');
    return `<section class="card"><div class="row sb"><h2 class="h2">Month by month · real</h2><span class="muted small">time-weighted · darker = outside the usual month</span></div>
      <style>.mtab th,.mtab td{padding:6px 2px!important;text-align:right}.mtab th:first-child,.mtab td:first-child{text-align:left}</style>
      <div class="tw"><table class="t mtab" style="table-layout:fixed;font-size:11px;margin-top:8px;width:100%;min-width:520px"><thead><tr><th style="width:38px">Year</th>${MON.map((m) => `<th>${m}</th>`).join('')}<th style="width:50px">Year</th></tr></thead><tbody>${body}</tbody></table></div>
      <div class="muted tiny" style="margin-top:8px">${bt.m_up != null ? `Backtest of this mix: ${bt.m_up}% of months up · usual month ${b1 ? b1[1] + '% … +' + b1[3] + '%' : '—'} · worst month ${bt.m_worst}%. ` : ''}Months before the pool ran with money fixed per strategy; * = the pool started that month.</div></section>`;
  }

  function expectCard(ds) {
    const bt = ds.check.bt || {}, rg = bt.ranges || {}, P = bt.periods || {}, A = bt.all || {}, F = bt.fixed || {};
    if (!bt.ready) return `<section class="card"><h2 class="h2">What to expect from this mix</h2><div class="muted small" style="padding:10px 0"><span class="spin"></span> The backtest of today's members is running…</div></section>`;
    if (bt.error || !A.cagr) return `<section class="card"><h2 class="h2">What to expect from this mix</h2><div class="muted small" style="padding:10px 0">${U.esc(bt.error || 'Not enough history.')}</div></section>`;
    let hc = 30;
    try { hc = +(localStorage.getItem('dash_haircut') || 30); } catch (e) { /* storage off: default haircut */ }
    const cellP = (x) => (x ? `<td class="num r ${U.cls(x.cagr)}">${x.cagr > 0 ? '+' : ''}${Math.round(x.cagr)}%</td>` : '<td class="muted r">·</td>');
    const cellD = (x) => (x ? `<td class="num r dn">${x.maxdd}%</td>` : '<td class="muted r">·</td>');
    return `<section class="card col" style="gap:10px"><div class="row sb" style="flex-wrap:wrap;gap:8px"><h2 class="h2">What to expect from this mix</h2>
      <div class="seg" id="hc">${[0, 15, 30, 50].map((x) => `<button data-hc="${x}" class="${x === hc ? 'on' : ''}">${x}%${x === 30 ? ' haircut' : ''}</button>`).join('')}</div></div>
      <div class="grid" style="--min:150px">
        <div class="fl"><div class="eyebrow">Plan a year</div><div class="num big ${U.cls(A.cagr)}">${A.cagr * (1 - hc / 100) > 0 ? '+' : ''}${(A.cagr * (1 - hc / 100)).toFixed(1)}%</div><div class="muted tiny">since-${String(A.from).slice(0, 4)} backtest ${A.cagr}% − ${hc}%</div></div>
        <div class="fl"><div class="eyebrow">Worst fall to expect</div><div class="num big dn">${A.maxdd}%</div><div class="muted tiny">since ${String(A.from).slice(0, 4)}${P['10Y'] ? ' · last 10 yrs ' + P['10Y'].maxdd + '%' : ''}</div></div>
        <div class="fl"><div class="eyebrow">A bad year (1 in 10)</div><div class="num big ${U.cls(rg.y_p10)}">${rg.y_p10 != null ? (rg.y_p10 > 0 ? '+' : '') + rg.y_p10 + '%' : '—'}</div><div class="muted tiny">any 12 months${rg.y_worst != null ? ' · worst ' + rg.y_worst + '% · ' + rg.y_down + '% of them down' : ''}</div></div></div>
      <div class="tw"><table class="t" style="font-size:12.5px;width:100%"><thead><tr><th></th><th class="r">1Y</th><th class="r">3Y</th><th class="r">5Y</th><th class="r">10Y</th><th class="r">Since ${String(A.from).slice(0, 4)}</th></tr></thead><tbody>
        <tr><td>Pool, a year</td>${['1Y', '3Y', '5Y', '10Y'].map((k) => cellP(P[k])).join('')}${cellP(A)}</tr>
        <tr><td>Worst fall</td>${['1Y', '3Y', '5Y', '10Y'].map((k) => cellD(P[k])).join('')}${cellD(A)}</tr>
        <tr><td class="muted">Fixed money each, a year</td><td class="muted r">·</td><td class="muted r">·</td><td class="muted r">·</td>${cellP(F['10Y'])}${cellP(F.all)}</tr></tbody></table></div>
      ${F.all ? `<div class="muted tiny">The same members with fixed money each fell up to ${F.all.maxdd}% (pool ${A.maxdd}%).</div>` : ''}
      <div class="muted tiny">Recent years lean on the chips and AI run, and several ETFs are modelled before they listed — plan on the since-${String(A.from).slice(0, 4)} figure. The strategies were picked on these same years, so real results are usually lower.</div></section>`;
  }

  /* ------------------------------------------------ pool alerts (app/poolalert.py): monthly reminder, add-money zone,
     real vs backtest, a member past its worst fall */
  const ord = (n) => { n = Math.floor(n); const t = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'); return n + t; };
  function alertCards(ds, pv) {
    const a = ds.alerts;
    if (!a) return '';
    const out = [];
    const btn = (id, label, cls = '') => `<button type="button" class="btn s ${cls}" data-pa="${id}" style="white-space:nowrap">${label}</button>`;
    if (a.month) {
      const m = a.month;
      out.push(`<div class="row" style="gap:14px;flex-wrap:nowrap;align-items:center;padding:14px 18px;border-radius:12px;background:var(--panel);border:1px solid color-mix(in srgb,var(--ok-fg) 40%,var(--line))" role="status">
        <span aria-hidden="true" style="font-size:20px">📅</span><div style="flex:1;min-width:0"><b>Monthly add · ${U.esc(m.name)}</b> <span class="muted small">· your reminder for the ${ord(m.day)}</span>
        <div class="small" style="margin-top:2px">Best day to add this month's savings: <b>today</b>. Waiting for a dip inside the month gained nothing since 2005 (+0.3%; −1.5% over the last 10 years).${m.pct != null ? ` Where the pool is now: ${Math.abs(m.depth).toFixed(1)}% below its high · ${ord(m.pct)} percentile.` : ''}</div></div>
        ${btn('add', 'Add money to the pool', 'p')}${btn('done', 'Done this month')}</div>`);
    }
    if (a.zone) {
      const z = a.zone, r = z.row || {};
      out.push(`<div class="row" style="gap:14px;flex-wrap:nowrap;align-items:center;padding:14px 18px;border-radius:12px;background:var(--ok-bg);border:1px solid color-mix(in srgb,var(--ok-fg) 45%,var(--line))" role="status">
        <span aria-hidden="true" style="font-size:18px">▲</span><div style="flex:1;min-width:0"><b>Good time to add extra money to the pool</b>${z.since ? ` <span class="muted small">· since ${U.day(Date.parse(z.since) / 1000)}</span>` : ''}
        <div class="small" style="margin-top:2px">Today's ${pv.members.length} members are ${Math.abs(z.depth).toFixed(1)}% below their high in the pool backtest — deeper than ${Math.floor(z.pct)}% of past days.${r.n ? ` From the first day of such falls since ${String(z.from || '').slice(0, 4)} the pool was higher a year later ${r.up} of ${r.n} times (typically ${r.med > 0 ? '+' : ''}${Math.round(r.med)}%).` : ''} For money you keep aside; regular money: add it when you have it.</div></div>
        ${btn('add', 'Add money to the pool', 'p')}<a class="small" href="#" data-pa="why" style="white-space:nowrap">Why? →</a></div>`);
    }
    if (a.gap) {
      const g = a.gap;
      out.push(`<div class="note fx warn" style="align-items:center" role="status"><div style="flex:1;min-width:0"><b>The real pool is ${Math.abs(g.gap).toFixed(1)} points behind its backtest</b>
        <div class="small">Since ${U.day(Date.parse(g.from) / 1000)}: real ${g.real > 0 ? '+' : ''}${g.real.toFixed(1)}% · backtest of the same members ${g.model > 0 ? '+' : ''}${g.model.toFixed(1)}% over the same days. Usually costs, timing or an order that did not go through. Each member's gap is on the Money page.</div></div>
        ${btn('gap', 'See the gap')}</div>`);
    }
    (a.worst || []).forEach((w) => {
      out.push(`<div class="note fx warn" style="align-items:center" role="status"><div style="flex:1;min-width:0"><b>${U.esc(w.name)}: past its backtest's worst fall</b>
        <div class="small">${w.depth}% from its high; its worst fall in ${w.years >= 10 ? '10' : w.years} years of backtest was ${w.worst}%. Worth a look: keep it, or take it out of the pool (its open trade finishes first).</div></div>
        <a class="btn s" href="#/strategies/${U.esc(w.id)}" style="white-space:nowrap">Open strategy</a>${pv.members.some((m) => m.id === w.id) ? btn('rm', 'Take it out…').replace('data-pa="rm"', `data-pa="rm" data-sid="${U.esc(w.id)}"`) : ''}</div>`);
    });
    return out.length ? `<div class="col" style="gap:12px">${out.join('')}</div>` : '';
  }

  /* ------------------------------------------------ the pool backtest of today's members: value from 100 (log scale), how
     far below its high (with the 80/85/90th percentile depths) and the percentile now; drag across either chart to zoom
     (double-click or Reset to go back), hover for the day's figures. Weekly points come with the Dashboard; every day is
     loaded the first time you zoom in under 3 years. */
  const MONS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const fmtV = (v) => (v >= 1000 ? Math.round(v).toLocaleString('en-US') : v >= 10 ? v.toFixed(0) : v.toFixed(1));
  const dstr = (t) => { const d = new Date(t * 1000); return `${d.getUTCDate()} ${MONS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
  const BW = 1100, BL = 48, BR = 72;
  function btTicks(a, b) {                                   // x-axis labels for the span shown
    const span = (b - a) / 86400, out = [];
    const da = new Date(a * 1000), db = new Date(b * 1000);
    if (span > 540) {
      const y0 = da.getUTCFullYear() + 1, y1 = db.getUTCFullYear(), st = Math.max(1, Math.ceil((y1 - y0 + 1) / 8));
      for (let y = y0; y <= y1; y += st) out.push([Date.UTC(y, 0, 1) / 1000, String(y)]);
    } else if (span > 75) {
      const st = span > 300 ? 3 : span > 150 ? 2 : 1;
      let y = da.getUTCFullYear(), m = da.getUTCMonth() + 1;
      for (; Date.UTC(y, m, 1) / 1000 <= b; m += st) { const t = Date.UTC(y, m, 1) / 1000; const dd = new Date(t * 1000); out.push([t, MONS[dd.getUTCMonth()] + (dd.getUTCMonth() === 0 || out.length === 0 ? ' ' + dd.getUTCFullYear() : '')]); }
    } else {
      const st = span > 30 ? 7 : span > 12 ? 3 : 1;
      for (let t = Math.ceil(a / 86400) * 86400; t <= b; t += st * 86400) { const d = new Date(t * 1000); out.push([t, d.getUTCDate() + ' ' + MONS[d.getUTCMonth()]]); }
    }
    return out.filter((x) => x[0] >= a && x[0] <= b);
  }
  function logTicks(lo, hi) {
    const L0 = Math.log10(lo), L1 = Math.log10(hi);
    for (const ks of [[1], [1, 2, 5]]) {
      const t = [];
      for (let e = Math.floor(L0) - 1; e <= Math.ceil(L1); e++) ks.forEach((k) => { const v = k * 10 ** e; if (v >= lo && v <= hi) t.push(v); });
      if (t.length >= 3) return t;
    }
    // a narrow range (zoomed in): round steps, about 4 of them
    const raw = (hi - lo) / 4, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
    const step = (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * mag, t = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) t.push(v);
    return t;
  }
  function btCharts(B, st, th) {
    const W = st.daily && st.win && (st.win[1] - st.win[0]) < 3 * 365.25 * 86400 ? st.daily : B.weekly;
    const last = B.weekly[B.weekly.length - 1][0];
    const yrs = { '5Y': 5, '10Y': 10 }[st.per];
    const p0 = yrs ? last - yrs * 365.25 * 86400 : B.weekly[0][0];
    const startIdx = Math.max(0, W.findIndex((p) => p[0] >= p0));
    const base = W[startIdx][1];
    const a = st.win ? Math.max(st.win[0], p0) : p0, b = st.win ? Math.min(st.win[1], last) : last;
    let pts = W.filter((p) => p[0] >= a && p[0] <= b);
    if (pts.length < 2) pts = W.filter((p) => p[0] >= p0);
    const t0 = pts[0][0], t1 = pts[pts.length - 1][0];
    const X = (t) => BL + (t - t0) / Math.max(1, t1 - t0) * (BW - BL - BR);
    const val = pts.map((p) => p[1] / base * 100);
    const vmin = Math.min(...val), vmax = Math.max(...val);
    const lo = vmin / (vmax / vmin > 1.5 ? 1.05 : 1.01), hi = vmax * (vmax / vmin > 1.5 ? 1.08 : 1.015);
    const h1 = 230, L0 = Math.log10(lo), L1 = Math.log10(hi);
    const Y1 = (v) => 10 + (h1 - 36) * (1 - (Math.log10(v) - L0) / (L1 - L0));
    const xl = (h) => btTicks(t0, t1).map(([t, l]) => `<text x="${X(t)}" y="${h}" font-size="10.5" fill="var(--muted)" text-anchor="middle">${l}</text>`).join('');
    const vline = pts.map((p, i) => `${X(p[0]).toFixed(1)},${Y1(val[i]).toFixed(1)}`).join(' ');
    const lastV = val[val.length - 1];
    const svg1 = `<svg viewBox="0 0 ${BW} ${h1}" style="width:100%;height:auto;display:block" role="img" aria-label="Pool backtest value from 100, log scale">
      ${logTicks(lo, hi).map((v) => `<line x1="${BL}" x2="${BW - BR}" y1="${Y1(v)}" y2="${Y1(v)}" stroke="var(--line2)"/><text x="${BW - BR + 6}" y="${Y1(v) + 4}" font-size="10.5" fill="var(--muted)">${fmtV(v)}</text>`).join('')}
      <polygon points="${X(t0)},${h1 - 26} ${vline} ${X(t1)},${h1 - 26}" fill="var(--ok-fg)" opacity=".08"/>
      <polyline points="${vline}" fill="none" stroke="var(--ok-fg)" stroke-width="2"/>
      <circle cx="${X(t1)}" cy="${Y1(lastV)}" r="4" fill="var(--ok-fg)"/><text x="${X(t1) - 4}" y="${Math.max(12, Math.min(Y1(lastV), Y1(vmax)) - 8)}" font-size="11" font-weight="600" fill="var(--text)" text-anchor="end">${fmtV(lastV)}</text>
      ${xl(h1 - 8)}<g class="hv"></g></svg>`;
    const deep = B.zone.deep, dmin = Math.min(...pts.map((p) => p[2]));
    const lo2 = Math.min(-15, Math.floor((Math.min(dmin, deep['90']) - 2) / 5) * 5);
    const h2 = 200, Y2 = (v) => 10 + (h2 - 36) * (v / lo2);
    const lines = [[80, 'var(--ok-fg)'], [85, '#e8590c'], [90, 'var(--err-fg)']];
    if (![80, 85, 90].includes(th) && deep[String(th)] != null) lines.push([th, 'var(--accent)']);
    const uw = pts.map((p) => `${X(p[0]).toFixed(1)},${Y2(p[2]).toFixed(1)}`).join(' ');
    const zY = Y2(deep[String(th)]);
    let grid2 = '';
    const gs = lo2 <= -40 ? 10 : 5;
    for (let v = 0; v >= lo2; v -= gs) grid2 += `<line x1="${BL}" x2="${BW - BR}" y1="${Y2(v)}" y2="${Y2(v)}" stroke="var(--line2)"/><text x="${BW - BR + 6}" y="${Y2(v) + 4}" font-size="10.5" fill="var(--muted)">${v}%</text>`;
    const atEnd = t1 === last, Z = B.zone;
    const nowLbl = atEnd && Z.pct != null ? `<text x="${X(t1) - 8}" y="${Y2(Z.depth) + 18}" font-size="11.5" font-weight="600" fill="var(--err-fg)" text-anchor="end">today ${Z.depth}% · ${ord(Z.pct)} percentile</text>` : '';
    const svg2 = `<svg viewBox="0 0 ${BW} ${h2}" style="width:100%;height:auto;display:block" role="img" aria-label="How far the pool backtest was below its high, with the percentile depths">
      ${grid2}<rect x="${BL}" y="${zY}" width="${BW - BL - BR}" height="${Math.max(0, Y2(lo2) - zY)}" fill="var(--ok-fg)" opacity=".07"/>
      <polygon points="${X(t0)},${Y2(0)} ${uw} ${X(t1)},${Y2(0)}" fill="var(--err-fg)" opacity=".18"/><polyline points="${uw}" fill="none" stroke="var(--err-fg)" stroke-width="1.2"/>
      ${lines.map(([k, c]) => `<line x1="${BL}" x2="${BW - BR}" y1="${Y2(deep[String(k)])}" y2="${Y2(deep[String(k)])}" stroke="${c}" stroke-width="1.4" stroke-dasharray="6 4"/>`).join('')}
      ${atEnd ? `<circle cx="${X(t1)}" cy="${Y2(Z.depth)}" r="4.5" fill="var(--err-fg)"/>` : ''}${nowLbl}${xl(h2 - 8)}<g class="hv"></g></svg>`;
    const vs = val[0], ve = lastV;
    return { svg1, svg2, lines, pts, val, X, Y1, Y2, t0, t1, p0, last, h1, h2, daily: W !== B.weekly,
      view: { from: t0, to: t1, ret: ve / vs - 1, deepest: dmin } };
  }
  function btCard(ds, pv, st) {
    const B = ds.btchart, a = (ds.alerts || {}).settings || {};
    if (!B || !B.weekly || !B.zone || !B.zone.deep) return '';
    const Z = B.zone, deep = Z.deep, th = a.zone_pct || 80;
    const P = { '5Y': 5, '10Y': 10 }[st.per] ? (B.periods || {})[st.per] : B.all;
    const sinceLbl = 'Since ' + String((B.all || {}).from || '').slice(0, 4);
    const W = B.weekly, last = W[W.length - 1][0], yrs = { '5Y': 5, '10Y': 10 }[st.per];
    const p0 = yrs ? last - yrs * 365.25 * 86400 : W[0][0];
    const pbase = (W.find((p) => p[0] >= p0) || W[0])[1], lastV = W[W.length - 1][1] / pbase * 100;
    const R = Z.rows || {}, ths = [...new Set([80, 85, 90, th])].sort((x, y) => x - y);
    const y0s = String(Z.from || '').slice(0, 4), y1s = String(Z.to || '').slice(0, 4);
    const cell = (x, sgn = true, cls = '') => (x == null ? '<td class="r muted">—</td>' : `<td class="r num ${cls || U.cls(x)}">${sgn && x > 0 ? '+' : ''}${x}%</td>`);
    const row = (label, r, depth, bold, dot) => `<tr style="${bold ? 'font-weight:600' : ''}"><td>${dot ? U.dot(dot, 8) + ' ' : ''}${label}</td><td class="r num">${depth == null ? '—' : Math.abs(depth).toFixed(1) + '%'}</td>
      <td class="r num">${depth == null ? '—' : r.n}</td><td class="r num">${r.n ? (depth == null ? Math.round(r.up / r.n * 100) + '%' : `${r.up} of ${r.n}`) : '—'}</td>
      ${cell(r.med != null ? Math.round(r.med) : null)}${cell(r.p10)}${cell(r.fall, false, 'dn')}</tr>`;
    const col = { 80: 'var(--ok-fg)', 85: '#e8590c', 90: 'var(--err-fg)' };
    const tbl = `<div class="tw"><table class="t" style="font-size:13px;width:100%"><thead><tr><th>When the pool is…</th><th class="r">Depth</th><th class="r">Times since ${y0s}</th><th class="r">Higher a year later</th><th class="r">Typical a year later</th><th class="r">Worst 1 in 10</th><th class="r">Fell further first</th></tr></thead><tbody>
      ${row('any day', R.any || {}, null, false)}${ths.map((k) => row(`${k}th percentile+${k === th ? ' · your alert' : ''}`, R[String(k)] || {}, deep[String(k)], k === th, col[k] || 'var(--accent)')).join('')}</tbody></table></div>`;
    const tabs = ['5Y', '10Y', 'all'].map((k) => `<button type="button" data-btp="${k}" class="${st.per === k ? 'on' : ''}">${k === 'all' ? sinceLbl : k}</button>`).join('');
    const inZone = Z.pct != null && Z.pct >= th;
    const leg = [[80, 'var(--ok-fg)'], [85, '#e8590c'], [90, 'var(--err-fg)']].concat([80, 85, 90].includes(th) ? [] : [[th, 'var(--accent)']])
      .map(([k, c]) => `<span class="row" style="gap:6px"><i style="width:18px;border-top:2px dashed ${c};display:inline-block"></i>${k}th${k === 80 ? ' percentile' : ''} · ${deep[String(k)].toFixed(1)}%</span>`).join('')
      + `<span class="row" style="gap:6px"><i style="width:14px;height:10px;background:color-mix(in srgb,var(--ok-fg) 14%,transparent);display:inline-block"></i>add-money zone (${th}th)</span>`;
    const stat = (label, v, cls = '') => `<span class="muted small">${label} <b class="num ${cls}" style="font-size:20px">${v}</b></span>`;
    return `<section class="card col" style="gap:12px" id="pool-bt"><div class="row sb" style="flex-wrap:wrap;gap:10px;align-items:flex-start"><div><h2 class="h2">Pool backtest · today's ${pv.members.length} members</h2>
      <div class="muted small">The pool's rules on each member's backtest (Webull's fee) · starts at 100 · changes when you add or remove a member</div></div><div class="seg">${tabs}</div></div>
      <div class="row" style="gap:22px;flex-wrap:wrap;align-items:baseline"><span class="muted small">100 became <b class="num" style="font-size:22px;color:var(--text)">${fmtV(lastV)}</b></span>
        ${P ? stat('a year', `${P.cagr > 0 ? '+' : ''}${P.cagr}%`, U.cls(P.cagr)) + stat('worst fall', `${P.maxdd}%`, 'dn') : ''}
        ${stat('now', `${Z.depth}%`, 'dn')}
        ${Z.pct != null ? `<span class="row" style="gap:8px;align-items:baseline;padding:4px 12px;border-radius:10px;background:${inZone ? 'var(--ok-bg)' : 'var(--panel2)'};border:1px solid ${inZone ? 'color-mix(in srgb,var(--ok-fg) 40%,var(--line))' : 'var(--line)'}">
          <span class="muted small">percentile now</span><b class="num" style="font-size:22px;color:${inZone ? 'var(--ok-fg)' : 'var(--text)'}">${ord(Z.pct)}</b>
          <span class="small" style="color:${inZone ? 'var(--ok-fg)' : 'var(--muted)'}">deeper than ${Math.floor(Z.pct)}% of past days · ${inZone ? 'in your add-money zone (' + th + 'th+)' : 'zone starts at the ' + th + 'th (' + deep[String(th)] + '%)'}</span></span>` : ''}</div>
      <div class="row sb" style="flex-wrap:wrap;gap:8px"><div class="eyebrow" id="bt-v-lbl">Value (log scale)</div><div class="row small" style="gap:10px"><span class="muted" id="bt-zoom-t">Drag across a chart to zoom</span><button type="button" class="btn s" id="bt-reset" style="display:none">Reset zoom</button></div></div>
      <div id="bt-c1" style="position:relative;touch-action:pan-y;cursor:crosshair;user-select:none"></div>
      <div class="row sb" style="flex-wrap:wrap;gap:8px"><div class="eyebrow">Under water · how far below its last high</div><div class="row small muted" style="gap:14px;flex-wrap:wrap">${leg}</div></div>
      <div id="bt-c2" style="position:relative;touch-action:pan-y;cursor:crosshair;user-select:none"></div>
      <div id="bt-tip" class="small" style="position:fixed;pointer-events:none;display:none;z-index:50;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 10px;box-shadow:0 6px 18px rgba(0,0,0,.12);min-width:180px"></div>
      <div class="muted tiny">Dashed lines = the depth reached on 80% / 85% / 90% of days since ${String((B.all || {}).from || '').slice(0, 4)}. Percentile = the share of past days that were less deep (each day against the days before it only). A backtest of strategies chosen on these same years: real results are usually lower.</div>
      <h3 class="h2" style="font-size:16px;margin-top:6px">After a fall this deep <span class="muted small" style="font-weight:400">(first day of each fall, ${y0s}–${y1s})</span></h3>${tbl}
      <div class="small" style="padding:4px 6px">Waiting for the zone with your regular money was worse than adding it every month in 84% of 5-year periods (median −4%): the pool rises most of the time. The zone is for <b>extra money you keep aside</b>.</div>
      <div class="muted tiny">A fall counts again only after the pool climbs back above the ${(a.rearm || 70)}th percentile (the alert's own rule). Each day is ranked against the days before it only, after a 3-year start.</div></section>`;
  }
  /* draw the two charts into the card and wire zoom + hover */
  function btBind(el, ds, pv, mode, st) {
    const card = el.querySelector('#pool-bt');
    if (!card) return;
    const B = ds.btchart, th = ((ds.alerts || {}).settings || {}).zone_pct || 80;
    const c1 = card.querySelector('#bt-c1'), c2 = card.querySelector('#bt-c2'), tip = card.querySelector('#bt-tip');
    let C = null;
    const draw = () => {
      C = btCharts(B, st, th);
      c1.innerHTML = C.svg1; c2.innerHTML = C.svg2;
      const z = card.querySelector('#bt-zoom-t'), rb = card.querySelector('#bt-reset');
      rb.style.display = st.win ? '' : 'none';
      z.textContent = st.win ? `${dstr(C.view.from)} – ${dstr(C.view.to)} · ${C.view.ret >= 0 ? '+' : '−'}${Math.abs(C.view.ret * 100).toFixed(1)}% · deepest ${C.view.deepest.toFixed(1)}%${C.daily ? ' · daily' : ' · weekly points'}` : 'Drag across a chart to zoom · hover for a day';
      card.querySelector('#bt-v-lbl').textContent = 'Value (log scale' + (Math.log10(Math.max(...C.val) / Math.min(...C.val)) > 1.6 ? ', so each step up is ×10)' : ')');
    };
    const needDaily = () => st.win && (st.win[1] - st.win[0]) < 3 * 365.25 * 86400 && !st.daily && !st.loading;
    const setWin = async (w) => {
      st.win = w; draw();
      if (needDaily()) {
        st.loading = true;
        try {
          const r = await U.api('/api/pool/backtest', { body: { mode, daily: true } });
          if (r && r.daily) { st.daily = r.daily; if (card.isConnected) draw(); }
        } catch (e) { /* weekly points stay */ } finally { st.loading = false; }
      }
    };
    const tOf = (box, cx) => { const r = box.getBoundingClientRect(); const x = (cx - r.left) / r.width * BW; return C.t0 + (Math.max(BL, Math.min(BW - BR, x)) - BL) / (BW - BL - BR) * (C.t1 - C.t0); };
    const near = (t) => { let lo = 0, hi = C.pts.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (C.pts[m][0] < t) lo = m; else hi = m; } return Math.abs(C.pts[lo][0] - t) < Math.abs(C.pts[hi][0] - t) ? lo : hi; };
    const hover = (t, cx, cy) => {
      const i = near(t), p = C.pts[i], x = C.X(p[0]);
      [[c1, C.h1], [c2, C.h2]].forEach(([box, h]) => { const g = box.querySelector('.hv'); if (g) g.innerHTML = `<line x1="${x}" x2="${x}" y1="6" y2="${h - 26}" stroke="var(--text)" stroke-width="1" opacity=".45"/>`; });
      card.querySelectorAll('.hv')[0].innerHTML += `<circle cx="${x}" cy="${C.Y1(C.val[i])}" r="3.5" fill="var(--ok-fg)"/>`;
      card.querySelectorAll('.hv')[1].innerHTML += `<circle cx="${x}" cy="${C.Y2(p[2])}" r="3.5" fill="var(--err-fg)"/>`;
      tip.innerHTML = `<b>${C.daily ? '' : 'week to '}${dstr(p[0])}</b><div class="row sb" style="gap:12px"><span class="muted">value</span><b class="num">${fmtV(C.val[i])}</b></div>
        <div class="row sb" style="gap:12px"><span class="muted">below its high</span><b class="num dn">${p[2].toFixed(1)}%</b></div>
        <div class="row sb" style="gap:12px"><span class="muted">percentile</span><b class="num">${p[3] == null ? '— (first 3 years)' : ord(p[3]) + (p[3] >= th ? ' · zone' : '')}</b></div>`;
      tip.style.display = 'block';
      const tw = tip.offsetWidth;
      tip.style.left = (cx + 16 + tw > window.innerWidth ? cx - tw - 16 : cx + 16) + 'px';
      tip.style.top = (cy + 12) + 'px';
    };
    const clearHover = () => { card.querySelectorAll('.hv').forEach((g) => { g.innerHTML = ''; }); tip.style.display = 'none'; };
    [c1, c2].forEach((box) => {
      let drag = null, sel = null;
      box.addEventListener('pointerdown', (e) => {
        if (e.button !== 0) return;
        drag = { x: e.clientX, t: tOf(box, e.clientX) };
        sel = document.createElement('div');
        sel.style.cssText = 'position:absolute;top:0;bottom:0;background:color-mix(in srgb,var(--accent) 16%,transparent);border-left:1px solid var(--accent);border-right:1px solid var(--accent);pointer-events:none;width:0';
        box.appendChild(sel);
        box.setPointerCapture(e.pointerId);
      });
      box.addEventListener('pointermove', (e) => {
        if (drag) {
          const r = box.getBoundingClientRect(), x0 = Math.min(drag.x, e.clientX) - r.left, x1 = Math.max(drag.x, e.clientX) - r.left;
          sel.style.left = Math.max(0, x0) + 'px'; sel.style.width = Math.max(0, x1 - x0) + 'px';
        }
        hover(tOf(box, e.clientX), e.clientX, e.clientY);
      });
      const end = (e) => {
        if (!drag) return;
        const t2 = tOf(box, e.clientX), moved = Math.abs(e.clientX - drag.x);
        if (sel) sel.remove();
        const t1 = drag.t; drag = null; sel = null;
        if (moved > 8 && Math.abs(t2 - t1) > 10 * 86400) setWin([Math.min(t1, t2), Math.max(t1, t2)]);
      };
      box.addEventListener('pointerup', end);
      box.addEventListener('pointercancel', () => { if (sel) sel.remove(); drag = null; sel = null; });
      box.addEventListener('pointerleave', () => { if (!drag) clearHover(); });
      box.addEventListener('dblclick', () => setWin(null));
    });
    card.querySelector('#bt-reset').onclick = () => setWin(null);
    U.on(card, '[data-btp]', 'click', (e, x) => {
      try { localStorage.setItem('dash_btp', x.dataset.btp); } catch (err) { /* not kept */ }
      st.per = x.dataset.btp; st.win = null;
      card.outerHTML = btCard(ds, pv, st);
      btBind(el, ds, pv, mode, st);
    });
    draw();
  }

  V.etfWatchCard = function (w) {
    if (!w || !w.t) return w && w.running ? '<section class="card"><b>New 2x ETFs</b> <span class="muted small">· the first check is running…</span></section>' : '';
    const nx = w.next ? 'Next check ' + U.dt(w.next) : '';
    if (!w.new.length) {
      return `<section class="card row sb" style="gap:10px;flex-wrap:wrap;padding:14px 18px"><span><b>New 2x ETFs</b> <span class="muted small">· ${w.first_run ? 'starting list built ' + U.day(w.t) : 'week of ' + U.day(w.t) + ': nothing new in the top 50'}</span></span>
        <span class="row small" style="gap:14px"><span class="muted">${nx}</span><a href="#/etfwatch">All 50 →</a></span></section>`;
    }
    return `<section class="card col" style="gap:12px"><div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">New 2x ETFs · week of ${U.day(w.t)}</h2>
      <div class="muted small">The bot's Saturday check of US 2x ETFs (no single stocks, no crypto) · candidates for your next strategies</div></div><a class="small" href="#/etfwatch">All 50 →</a></div>
      ${w.new.map(V.etfNewRow).join('')}
      <div class="row small" style="gap:8px;flex-wrap:wrap">${w.left.length ? `<span class="muted">Left the top 50:</span>${w.left.map((x) => `<span class="pill">${U.esc(x.t)} · ${U.esc(x.tracks)}</span>`).join('')}` : ''}<span class="muted" style="margin-left:auto">${nx} · LINE tells you when something is new</span></div></section>`;
  };
  /* the weekly notice at the top of the Dashboard: from the Saturday check until the watch page is opened or Hide */
  V.etfNotice = function (w) {
    if (!w || !w.notice) return '';
    const hideBtn = (cls) => `<button type="button" class="${cls}" data-etfhide="1" style="white-space:nowrap">Hide</button>`;
    if (!w.new.length) {
      const what = w.first_run ? `starting list built (${w.count} funds)` : 'nothing new in the top 50' + (w.left.length ? ' · ' + w.left.map((x) => x.t).join(', ') + ' left' : '');
      return `<div class="row" style="gap:12px;flex-wrap:nowrap;align-items:center;padding:10px 16px;border-radius:12px;background:var(--panel2);border:1px solid var(--line)">
        <span aria-hidden="true">🔎</span><div style="flex:1;min-width:0"><b style="font-weight:600">2x ETF watch:</b> <span class="muted">Saturday's check (${U.day(w.t)}) — ${U.esc(what)}</span></div>
        <a class="small" href="#/etfwatch" style="white-space:nowrap">Open 2x ETF watch →</a>${hideBtn('btn s')}</div>`;
    }
    return `<div class="row" style="gap:14px;flex-wrap:nowrap;align-items:center;padding:12px 16px;border-radius:12px;background:color-mix(in srgb,var(--accent) 9%,var(--panel));border:1px solid color-mix(in srgb,var(--accent) 35%,var(--line))" role="status">
      <span aria-hidden="true" style="font-size:20px">🔎</span><div style="flex:1;min-width:0"><b>${w.new.length} new 2x ETF${w.new.length > 1 ? 's' : ''} this week</b> <span class="muted small">· Saturday's check, ${U.day(w.t)}</span>
        <div class="small" style="margin-top:2px">${w.new.map((n) => `<b>${U.esc(n.t)}</b> ${U.esc(n.tracks)} · ${n.kind === 'listing' ? 'new listing' : 'entered the top 50'}${n.adv90 != null ? ' · $' + (n.adv90 < 10 ? n.adv90.toFixed(2) : n.adv90.toFixed(1)) + 'M a day' : ''}`).join(' &nbsp;·&nbsp; ')}</div></div>
      <a class="btn s p" href="#/etfwatch" style="white-space:nowrap">Open 2x ETF watch →</a>${hideBtn('btn s')}</div>`;
  };
  V.etfNewRow = function (n) {
    const facts = [n.adv90 != null ? `$${n.adv90 < 10 ? n.adv90.toFixed(2) : n.adv90.toFixed(1)}M a day (90-day)` : '', n.first ? 'listed ' + U.day(n.first) : '',
      n.years != null ? (n.years < 1 ? 'under 1 year of history' : n.years.toFixed(1) + ' years of history') : ''].filter(Boolean).join(' · ');
    return `<div style="border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--panel);display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:4px 14px;align-items:center">
      <span class="num" style="font-weight:700;font-size:16px">${U.esc(n.t)}</span>
      <div><b style="font-weight:600">${U.esc(n.tracks)}</b> ${n.kind === 'listing' ? U.pill('warn', 'New listing') : U.pill('info', 'Entered the top 50' + (n.rank ? ' · #' + n.rank : ''))}
        ${n.mark === 'research' ? U.pill('ok', 'To research') : ''}<div class="muted small">${facts}</div></div>
      <div class="row" style="gap:6px">${n.mark === 'research' ? '' : `<button class="btn s p" data-etfm="research" data-t="${U.esc(n.t)}">Research it</button>`}<button class="btn s" data-etfm="dismissed" data-t="${U.esc(n.t)}">Dismiss</button></div></div>`;
  };
  V.etfBind = function (el, reload) {
    U.on(el, '[data-etfhide]', 'click', (e, b) => U.busy(b, async () => { await U.api('/api/etfwatch/hide', { body: {} }); reload(); }));
    U.on(el, '[data-etfm]', 'click', (e, b) => U.busy(b, async () => {
      await U.api('/api/etfwatch/mark', { body: { ticker: b.dataset.t, mark: b.dataset.etfm } });
      U.toast(b.dataset.etfm === 'research' ? `${b.dataset.t}: marked to research — ask Claude when you are ready` : b.dataset.etfm === 'clear' ? `${b.dataset.t} unmarked` : `${b.dataset.t} hidden`);
      reload();
    }));
  };

  V.dashPool = async function (el, d, mode, load) {
    const ds = d.dash, b = d.bot, c = ds.check, pv = ds.pool;
    const today = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date());
    const oldPnl = el.querySelector('#pnlx');
    const real = b.real && b.real.ret;
    const btKey = mode + ':' + pv.members.map((m) => m.id).sort().join(',');
    if (el._bt && el._bt.key !== btKey) el._bt = null;                      // other members or mode: a new backtest
    const btState = el._bt || (el._bt = { key: btKey, per: (() => { try { return localStorage.getItem('dash_btp') || '10Y'; } catch (e) { return '10Y'; } })(), win: null, daily: null });
    el.innerHTML = `
      <div class="page-head"><div><div class="eyebrow">${U.esc(today)} · ${U.modeLabel[mode]} · strategy pool on</div><h1 class="h1">Dashboard</h1></div>
        <div class="row"><button class="btn p" type="button" id="add">Add money to the pool</button></div></div>
      ${attention(ds.attention)}
      ${alertCards(ds, pv)}
      ${V.etfNotice(d.etfwatch)}
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px">
        <section class="card col" style="gap:10px"><div class="eyebrow">Strategy pool · ${U.modeLabel[mode]} · ${pv.members.length} members</div>
          <div class="num huge">${U.usd(b.value)}</div>
          <div class="row" style="gap:16px;flex-wrap:wrap"><span>Today <b class="num ${U.cls(b.today)}">${b.today == null ? '—' : U.sgnUsd(b.today) + ' (' + U.pct(b.today_pct, 2) + ')'}</b></span><span>This month <b class="num ${U.cls(c.month)}">${pc(c.month)}</b></span></div>
          <div class="col" style="border-top:1px solid var(--line);padding-top:10px">
            <div class="kv"><span>Real return since start <span class="muted tiny">time-weighted</span></span><b class="num ${U.cls(real)}">${pc(real)}</b></div>
            <div class="kv"><span>Profit since start</span><b class="num ${U.cls(b.pnl)}">${U.sgnUsd(b.pnl, 0)}</b></div>
            <div class="kv"><span>Money put in</span><span class="num">${U.usd(b.net_in, 0)}</span></div>
            <div class="kv"><span>Since the pool started${ds.since ? ' · ' + U.day(ds.since) : ''}</span><b class="num ${U.cls(c.since_ret)}">${pc(c.since_ret, 2)}</b></div></div></section>
        ${checkCard(c, pv, ds.since)}
        ${nextCard(d)}
      </div>
      <section class="card col" style="gap:10px" id="rvb"><div><h2 class="h2">Real vs backtest</h2><div class="muted small">The real return (time-weighted, so adding money does not move it) against where today's mix usually was in its backtest, counted from the day the pool started</div></div>
        ${chartSvg(ds, mode)}
        <div class="row small muted" style="gap:18px;flex-wrap:wrap"><span class="row" style="gap:6px"><i style="width:16px;height:3px;background:var(--accent);display:inline-block"></i>Real</span>
          <span class="row" style="gap:6px"><i style="width:16px;height:10px;background:color-mix(in srgb,var(--ok-fg) 22%,transparent);display:inline-block"></i>Usual range (8 of 10 backtest stretches)</span>
          <span class="row" style="gap:6px"><i style="width:16px;border-top:2px dashed var(--ok-fg);display:inline-block"></i>Backtest middle</span></div></section>
      ${board(pv)}
      ${btCard(ds, pv, btState)}
      <div class="grid" style="--min:min(440px,100%)">${moneyCard(pv)}<div id="etfw">${V.etfWatchCard(d.etfwatch)}</div></div>
      <div id="pnlx"></div>
      <div class="grid" style="--min:min(440px,100%)">${monthsCard(ds)}${expectCard(ds)}</div>
      <div id="traded">${V.traded ? V.traded(d.traded) : ''}</div>
      <section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Recent activity</h2><a href="#/logs" class="small">All logs →</a></div>
        ${d.events.map((e) => `<div class="list-row">${U.pill(e.level === 'error' ? 'err' : e.level === 'warn' ? 'warn' : '', e.source)}
          <div style="flex:1;min-width:0"><div style="font-weight:500">${U.esc(e.title)}</div><div class="muted small" style="overflow:hidden;text-overflow:ellipsis">${U.esc((e.message || '').slice(0, 160))}</div></div>
          <div class="num muted small nowrap">${U.dt(e.t)}</div></div>`).join('') || '<div class="empty">No activity yet</div>'}</section>`;
    if (oldPnl && oldPnl.firstChild) { el.querySelector('#pnlx').replaceWith(oldPnl); V.renderPnl(oldPnl); } else V.renderPnl(el.querySelector('#pnlx'));
    el.querySelector('#add').onclick = () => V.fundDialog('in', load);
    btBind(el, ds, pv, mode, btState);
    U.on(el, '[data-pa]', 'click', (e, x) => {
      const k = x.dataset.pa;
      if (k === 'add') V.fundDialog('in', load);
      else if (k === 'why') { e.preventDefault(); const t = el.querySelector('#pool-bt'); if (t) t.scrollIntoView({ behavior: 'smooth' }); }
      else if (k === 'gap') { const t = el.querySelector('#rvb'); if (t) t.scrollIntoView({ behavior: 'smooth' }); }
      else if (k === 'done') U.busy(x, async () => { await U.api('/api/pool/month_done', { body: { mode } }); U.toast('Done for this month'); load(); });
      else if (k === 'rm') V.poolRemoveDialog(pv.members.find((m) => m.id === x.dataset.sid), mode, load);
    });
    U.on(el, '[data-hc]', 'click', (e, x) => { try { localStorage.setItem('dash_haircut', x.dataset.hc); } catch (err) { /* not kept */ } load(); });
    V.etfBind(el, load);
    if (V.tradedBind) V.tradedBind(el, d.traded);
    if (c.bt && !c.bt.ready && !el._btPoll) { el._btPoll = setTimeout(() => { el._btPoll = null; if (el.isConnected) load(); }, 5000); }
  };
})();
