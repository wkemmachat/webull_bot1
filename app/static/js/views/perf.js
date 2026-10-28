/* Real results and falls per strategy.
   V.renderRisk(el, sid)          — "Falls to expect": worst falls and time underwater (backtest, real values, research)
   V.dailyPnlTab(el, sid, card)   — real profit/loss per US trading day, with CSV download */
(function () {
  const V = window.Views || (window.Views = {});
  const day = (iso) => { if (!iso) return '—'; const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }); };
  const dayShort = (iso) => { const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }); };
  const pc = (v, dp) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 1 : dp) + '%');

  /* underwater chart: depth below the previous high over time, drawn as an area under zero */
  function underwaterSvg(pts, opts) {
    opts = opts || {};
    if (!pts || pts.length < 2) return '';
    const W = 1000, H = opts.h || 170, L = 44, R = 8, T = 10, B = 24;
    const t0 = Date.parse(pts[0][0]), t1 = Date.parse(pts[pts.length - 1][0]) || t0 + 1;
    const minV = Math.min(-5, ...pts.map((p) => p[1]));
    const lo = Math.floor(minV / 10) * 10;
    const x = (t) => L + (Date.parse(t) - t0) / (t1 - t0 || 1) * (W - L - R);
    const y = (v) => T + (v / lo) * (H - T - B);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join('');
    const area = `${line}L${x(pts[pts.length - 1][0]).toFixed(1)} ${y(0)}L${x(pts[0][0]).toFixed(1)} ${y(0)}Z`;
    const ticks = []; for (let v = 0; v >= lo; v -= (lo <= -40 ? 20 : 10)) ticks.push(v);
    const y0 = new Date(t0).getUTCFullYear(), y1 = new Date(t1).getUTCFullYear();
    const span = y1 - y0, stepY = span > 12 ? 4 : span > 6 ? 2 : 1;
    const years = []; for (let yy = y0 + 1; yy <= y1; yy += stepY) years.push(yy);
    const worst = pts.reduce((a, p) => (p[1] < a[1] ? p : a), pts[0]);
    const bx = opts.built && Date.parse(opts.built) > t0 ? Math.min(W - R, x(opts.built)) : null;   // prices built from the index before this day
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none" style="display:block;height:${H}px" role="img" aria-label="Underwater chart: worst ${worst[1].toFixed(1)}% on ${worst[0]}">
      ${ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line2)" stroke-width="1" vector-effect="non-scaling-stroke"/>
        <text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--dim)">${v}%</text>`).join('')}
      ${span >= 1 ? years.map((yy) => { const xx = x(yy + '-01-01'); return `<text x="${xx}" y="${H - 6}" text-anchor="middle" font-size="11" fill="var(--dim)">${yy}</text>`; }).join('') : ''}
      ${bx ? `<rect x="${L}" y="${T}" width="${(bx - L).toFixed(1)}" height="${H - T - B}" fill="var(--dim)" fill-opacity=".10"/><text x="${L + 6}" y="${T + 14}" font-size="11" fill="var(--dim)">built from the index</text>` : ''}
      <path d="${area}" fill="var(--dn)" fill-opacity=".22"/><path d="${line}" fill="none" stroke="var(--dn)" stroke-width="1.5" vector-effect="non-scaling-stroke"/>
      <circle cx="${x(worst[0])}" cy="${y(worst[1])}" r="4" fill="var(--dn)"/>
    </svg>`;
  }

  function tile(label, big, sub, cls) {
    return `<div style="border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0">
      <div class="eyebrow">${label}</div><div class="num big ${cls || ''}" style="font-size:22px;margin-top:4px">${big}</div><div class="muted small" style="margin-top:2px">${sub}</div></div>`;
  }

  V.renderRisk = async function (el, sid) {
    const mode = U.mode();
    el.innerHTML = `<section class="card col" style="gap:10px"><h2 class="h2">Falls to expect</h2><div class="empty small"><span class="spin"></span> Reading the backtest…</div></section>`;
    let d;
    try { d = await U.api(`/api/strategies/${sid}/risk?mode=${mode}`); } catch (e) { el.innerHTML = ''; return; }
    const b = d.backtest, l = d.live, rs = d.research;
    if (!b && !l) { el.innerHTML = ''; return; }
    let html = `<section class="card col" style="gap:14px">
      <div><h2 class="h2">Falls to expect</h2>
        <div class="muted small">How far this strategy has fallen below its previous high, and how long it took to get back. Decide now which fall you can sit through.</div></div>`;
    if (b) {
      const w = b.worst, lg = b.longest, ten = b.ten;
      const every20 = b.count_20 ? (b.years / b.count_20) : null;
      html += `<div class="row sb" style="gap:8px;flex-wrap:wrap"><span class="eyebrow">Backtest · ${day(b.from)} – ${day(b.to)} (${b.years} years)</span>
        ${b.years < 4 ? `<span class="tiny muted">Short history${d.family === 'signal' ? ' (Yahoo keeps only 2 years of hourly futures prices)' : ''}. ${rs && rs.maxdd != null ? `The research's longer test: worst fall ${pc(rs.maxdd)}.` : ''}</span>` : ''}</div>
      <div class="grid" style="--min:200px;gap:10px">
        ${tile('Worst fall', pc(w.depth), `${day(w.peak)} → ${day(w.trough)} · ${U.dur(w.days_down)} down${w.recovered ? ', ' + U.dur(w.days_to_recover) + ' to recover' : ', not recovered yet'}`, 'dn')}
        ${tile('Longest underwater', U.dur(lg.days_under), `${day(lg.peak)} → ${lg.recovered ? day(lg.recovered) : 'still below'} · fall of ${pc(lg.depth)}`)}
        ${tile('Time below a high', b.pct_under.toFixed(0) + '%', 'of all days: most of the time a strategy is below its last peak')}
        ${tile('Falls of 20% or more', String(b.count_20), every20 ? `about once every ${every20.toFixed(1)} years · ${b.count_30} of 30%+` : 'none in this history')}
      </div>
      ${ten && ten.worst && b.years > 10.5 ? `<div class="muted small">Last 10 years only: worst fall ${pc(ten.worst.depth)}, longest underwater ${U.dur(ten.longest.days_under)}, below a high ${ten.pct_under.toFixed(0)}% of days.</div>` : ''}
      ${Object.keys(b.built || {}).length ? `<div class="muted small">${Object.entries(b.built).map(([s, dd]) => `${U.esc(s)} before ${day(dd)}`).join(', ')}: ${Object.keys(b.built).length > 1 ? 'these did' : 'it did'} not exist yet, so ${Object.keys(b.built).length > 1 ? 'their' : 'its'} prices are built from the index (2× its daily move minus the fund's costs; BIL = the T-bill rate). Shaded on the chart.</div>` : ''}
      <div>${underwaterSvg(b.underwater, { built: Object.values(b.built || {}).sort().pop() })}</div>
      <div class="tw"><table class="t"><thead><tr><th class="r">Fall</th><th>From the high on</th><th>Bottom</th><th>Back at the high</th><th class="r">Falling</th><th class="r">Underwater</th></tr></thead><tbody>
        ${b.top.map((e) => `<tr><td class="r num dn">${pc(e.depth)}</td><td class="num">${day(e.peak)}</td><td class="num">${day(e.trough)}</td>
          <td class="num">${e.recovered ? day(e.recovered) : '<span class="pill warn">not yet</span>'}</td><td class="r num">${U.dur(e.days_down)}</td><td class="r num">${U.dur(e.days_under)}</td></tr>`).join('')}</tbody></table></div>`;
    } else if (d.backtest_error) {
      html += `<div class="muted small">Backtest not available right now (${U.esc(d.backtest_error)}).</div>`;
    }
    html += `<div class="col" style="gap:6px;border-top:1px solid var(--line2);padding-top:12px"><span class="eyebrow">Real · ${U.modeLabel[mode]}</span>
      ${l ? `<div class="small">Since ${day(l.from)}: worst fall <b class="dn num">${pc(l.worst ? l.worst.depth : 0)}</b>${l.longest ? `, longest underwater <b class="num">${U.dur(l.longest.days_under)}</b>` : ''}.
        Now <b class="num ${l.current.depth < 0 ? 'dn' : 'up'}">${l.current.depth < 0 ? pc(l.current.depth) + ' below its high' : 'at its high'}</b>${l.current.depth < 0 ? ` for ${U.dur(l.current.days)}` : ''}.
        ${b && b.worst && l.worst ? `<span class="muted">(${Math.round(l.worst.depth / b.worst.depth * 100)}% of the backtest's worst fall)</span>` : ''}</div>`
        : `<div class="muted small">No real history in ${U.modeLabel[mode]} yet: it starts with the first money in this strategy.</div>`}
      ${rs && rs.maxdd != null ? `<div class="muted small">Research: worst fall ${pc(rs.maxdd)}${rs.period ? ' (' + U.esc(rs.period) + ')' : ''}.</div>` : ''}
      <div class="tiny muted">Falls are measured on the strategy's own value with money added or withdrawn left out. The next fall can be deeper than any in the past.</div></div>
    </section>`;
    el.innerHTML = html;
  };

  /* ---------------------------------------------------------------- daily P&L */
  function barsSvg(rows) {
    const r = rows.slice(0, 66).reverse();
    if (r.length < 2) return '';
    const W = 1000, H = 150, L = 56, R = 6, T = 8, B = 20;
    const m = Math.max(1, ...r.map((x) => Math.abs(x.pnl)));
    const bw = (W - L - R) / r.length;
    const y = (v) => T + (H - T - B) / 2 - v / m * (H - T - B) / 2;
    const fmt = (v) => (Math.abs(v) >= 1000 ? '$' + (v / 1000).toFixed(1) + 'k' : '$' + Math.round(v));
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none" style="display:block;height:${H}px" role="img" aria-label="Daily profit and loss, last ${r.length} days">
      <line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" stroke="var(--line)" vector-effect="non-scaling-stroke"/>
      <text x="${L - 6}" y="${y(m) + 8}" text-anchor="end" font-size="11" fill="var(--dim)">+${fmt(m)}</text>
      <text x="${L - 6}" y="${y(-m)}" text-anchor="end" font-size="11" fill="var(--dim)">−${fmt(m)}</text>
      ${r.map((x, i) => { const top = Math.min(y(0), y(x.pnl)), h = Math.max(1, Math.abs(y(x.pnl) - y(0)));
        return `<rect x="${(L + i * bw + bw * 0.15).toFixed(1)}" y="${top.toFixed(1)}" width="${(bw * 0.7).toFixed(1)}" height="${h.toFixed(1)}" fill="${x.pnl >= 0 ? 'var(--up)' : 'var(--dn)'}" opacity="${x.today ? 0.5 : 0.9}"><title>${x.date}: ${U.sgnUsd(x.pnl)}${x.pct != null ? ' (' + U.pct(x.pct, 2) + ')' : ''}</title></rect>`; }).join('')}
      <text x="${L}" y="${H - 4}" font-size="11" fill="var(--dim)">${r[0].date}</text><text x="${W - R}" y="${H - 4}" text-anchor="end" font-size="11" fill="var(--dim)">${r[r.length - 1].date}</text>
    </svg>`;
  }

  V.dailyPnlTab = async function (el, sid, card) {
    const mode = U.mode();
    el.innerHTML = '<section class="card"><div class="empty"><span class="spin"></span></div></section>';
    let d;
    try { d = await U.api(`/api/strategies/${sid}/daily?mode=${mode}`); } catch (e) { U.error(el, e); return; }
    let showAll = false;
    function draw() {
      const rows = d.rows || [], st = d.stats, t = d.today;
      const now = new Date(), ym = now.toISOString().slice(0, 7);
      const month = rows.filter((r) => r.date.slice(0, 7) === ym).reduce((a, r) => a + r.pnl, 0);
      const list = showAll ? rows : rows.slice(0, 60);
      el.innerHTML = `<section class="card col" style="gap:14px">
        <div class="row sb" style="gap:10px;flex-wrap:wrap"><div><h2 class="h2">Daily P&amp;L · ${U.modeLabel[mode]}</h2>
          <div class="muted small">Real profit or loss of this strategy per US trading day: value change at the close, with money added or withdrawn left out.</div></div>
          ${rows.length ? `<a class="btn s" href="/api/strategies/${encodeURIComponent(sid)}/daily.csv?mode=${mode}" download>Download CSV</a>` : ''}</div>
        ${rows.length ? `<div class="grid" style="--min:180px;gap:10px">
          ${tile(t && !t.live ? 'Last session · ' + dayShort(t.day) : 'Today (US session)', t ? `<span class="${U.cls(t.pnl)}">${U.sgnUsd(t.pnl, 0)}</span>` : '—', t && t.pct != null ? U.pct(t.pct, 2) + (t.live ? ' since the ' + day(t.since) + ' close' : ' · market closed now') : 'after the first close')}
          ${tile('This month', `<span class="${U.cls(month)}">${U.sgnUsd(month, 0)}</span>`, 'sum of the days this month')}
          ${tile('Since start', `<span class="${U.cls(card.pnl)}">${U.sgnUsd(card.pnl, 0)}</span>`, `${U.pct(card.ret)} on ${U.usd(card.net_in, 0)} put in`)}
          ${st ? tile('Days up / down', `${st.up} / ${st.down}`, `${st.days ? Math.round(st.up / st.days * 100) : 0}% of ${st.days} days up · best ${U.sgnUsd(st.best.pnl, 0)}, worst ${U.sgnUsd(st.worst.pnl, 0)}`) : ''}
        </div>
        <div>${barsSvg(rows)}</div>
        <div class="tw"><table class="t"><thead><tr><th>Day (US)</th><th class="r">Value at close</th><th class="r">P&amp;L</th><th class="r">%</th><th class="r">Money in / out</th><th class="r">Total since start</th></tr></thead><tbody>
          ${list.map((r) => `<tr><td class="num">${dayShort(r.date)}${r.today ? ' ' + U.pill('info', 'so far') : ''}</td><td class="r num">${U.usd(r.value)}</td>
            <td class="r num ${U.cls(r.pnl)}" style="font-weight:600">${U.sgnUsd(r.pnl)}</td><td class="r num ${U.cls(r.pnl)}">${r.pct == null ? '—' : U.pct(r.pct, 2)}</td>
            <td class="r num muted">${Math.abs(r.flow) >= 0.01 ? U.sgnUsd(r.flow) : ''}</td><td class="r num ${U.cls(r.total)}">${U.sgnUsd(r.total)}</td></tr>`).join('')}</tbody></table></div>
        ${rows.length > 60 && !showAll ? `<button class="btn s" data-all style="align-self:flex-start">Show all ${rows.length} days</button>` : ''}
        <div class="tiny muted">The day's close is the last value the bot recorded that US day (every 30 minutes). Webull's own statement is the official record; small differences come from fees booked later and the 30-minute timing.</div>`
        : `<div class="empty small">No days recorded yet in ${U.modeLabel[mode]}. The bot records the value every 30 minutes once this strategy has money; the first full day appears after the next US close.</div>`}
      </section>`;
      const a = el.querySelector('[data-all]');
      if (a) a.onclick = () => { showAll = true; draw(); };
    }
    draw();
  };
})();
