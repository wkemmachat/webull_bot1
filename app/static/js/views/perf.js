/* Real results and falls per strategy.
   V.renderRisk(el, sid)          — "Falls to expect": worst falls and time underwater (backtest, real values, research)
   V.dailyPnlTab(el, sid, card)   — real profit/loss per US trading day, with CSV download */
(function () {
  const V = window.Views || (window.Views = {});
  const day = (iso) => { if (!iso) return '—'; const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }); };
  const dayShort = (iso) => { const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }); };
  const pc = (v, dp) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 1 : dp) + '%');

  /* underwater chart: depth below the previous high over time, drawn as an area under zero */
  const ML = 50, MR = 8;                         /* left/right margins shared by the growth and underwater charts (years line up) */
  function underwaterSvg(pts, opts) {
    opts = opts || {};
    if (!pts || pts.length < 2) return '';
    const W = opts.w || 1000, H = opts.h || 170, L = ML, R = MR, T = 10, B = 24;
    const t0 = Date.parse(pts[0][0]), t1 = Date.parse(pts[pts.length - 1][0]) || t0 + 1;
    const minV = Math.min(-5, ...pts.map((p) => p[1]));
    const lo = Math.floor(minV / 10) * 10;
    const x = (t) => L + (Date.parse(t) - t0) / (t1 - t0 || 1) * (W - L - R);
    const y = (v) => T + (v / lo) * (H - T - B);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join('');
    const area = `${line}L${x(pts[pts.length - 1][0]).toFixed(1)} ${y(0)}L${x(pts[0][0]).toFixed(1)} ${y(0)}Z`;
    const ticks = []; for (let v = 0; v >= lo; v -= (lo <= -40 ? 20 : 10)) ticks.push(v);
    const y0 = new Date(t0).getUTCFullYear(), y1 = new Date(t1).getUTCFullYear();
    const span = y1 - y0, stepY = yearStep(span, W);
    const years = []; for (let yy = y0 + 1; yy <= y1; yy += stepY) years.push(yy);
    const worst = pts.reduce((a, p) => (p[1] < a[1] ? p : a), pts[0]);
    const bx = opts.built && Date.parse(opts.built) > t0 ? Math.min(W - R, x(opts.built)) : null;   // prices built from the index before this day
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="none" style="display:block;height:${H}px;overflow:visible" role="img" aria-label="Underwater chart: worst ${worst[1].toFixed(1)}% on ${worst[0]}">
      ${ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line2)" stroke-width="1" vector-effect="non-scaling-stroke"/>
        <text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--dim)">${v}%</text>`).join('')}
      ${span >= 1 ? years.map((yy) => { const xx = x(yy + '-01-01'); return `<text x="${xx}" y="${H - 6}" text-anchor="middle" font-size="11" fill="var(--dim)">${yy}</text>`; }).join('') : ''}
      ${bx ? `<rect x="${L}" y="${T}" width="${(bx - L).toFixed(1)}" height="${H - T - B}" fill="var(--dim)" fill-opacity=".10"/><text x="${L + 6}" y="${T + 14}" font-size="11" fill="var(--dim)">built from the index</text>` : ''}
      <path d="${area}" fill="var(--dn)" fill-opacity=".22"/><path d="${line}" fill="none" stroke="var(--dn)" stroke-width="1.5" vector-effect="non-scaling-stroke"/>
      <circle cx="${x(worst[0])}" cy="${y(worst[1])}" r="4" fill="var(--dn)"/>
    </svg>`;
  }

  function yearStep(span, W) {
    const fit = Math.max(2, Math.floor((W - ML - MR) / 46));          // a year label needs about 46 px
    for (const st of [1, 2, 4, 5, 10]) if (span / st <= fit) return st;
    return 10;
  }
  const money = (v) => {
    if (v == null) return '—';
    const a = Math.abs(v);
    const t = a >= 1e6 ? '$' + (+(a / 1e6).toFixed(a >= 1e7 ? 0 : 1)) + 'M' : a >= 1e5 ? '$' + Math.round(a / 1e3) + 'k' : a >= 1e3 ? '$' + (+(a / 1e3).toFixed(1)) + 'k' : '$' + Math.round(a);
    return (v < 0 ? '−' : '') + t;
  };
  const pcf = (f) => (f == null ? '—' : pc(f * 100));

  /* growth of $10,000: the strategy, the ETFs held, the real result, the worst fall in red; log or linear scale */
  function growthSvg(g, o) {
    const W = o.w, H = o.h, L = ML, R = MR, T = 12, B = 24;
    const days = g.days, n = days.length;
    const t0 = Date.parse(days[0]), t1 = Date.parse(days[n - 1]) || t0 + 1;
    const x = (d) => L + (Date.parse(d) - t0) / (t1 - t0 || 1) * (W - L - R);
    const lines = [g.strategy, ...g.bench.map((b) => b.values), g.real ? g.real.values : []];
    const all = lines.flat().filter((v) => v != null && v > 0);
    let lo = Math.min(g.start, ...all), hi = Math.max(g.start, ...all);
    let ticks = [];
    if (o.log) {
      lo = Math.pow(10, Math.floor(Math.log10(lo)));
      hi = Math.pow(10, Math.ceil(Math.log10(hi)));
      if (hi / lo < 10) hi = lo * 10;
      for (let p = lo; p <= hi * 1.0001; p *= 10) { ticks.push(p); if (p * 3 < hi && hi / lo <= 1e4) ticks.push(p * 3); }
    } else {
      lo = 0;
      const raw = hi / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
      const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((st) => st >= raw);
      hi = Math.ceil(hi / step) * step;
      for (let v = 0; v <= hi + 1e-6; v += step) ticks.push(v);
    }
    const f = (v) => (o.log ? Math.log(v) : v);
    const y = (v) => T + (1 - (f(v) - f(lo)) / (f(hi) - f(lo))) * (H - T - B);
    const path = (vals, ds) => { let out = '', on = false; vals.forEach((v, i) => { if (v == null || v <= 0) { on = false; return; } out += `${on ? 'L' : 'M'}${x(ds[i]).toFixed(1)} ${y(v).toFixed(1)}`; on = true; }); return out; };
    const y0 = new Date(t0).getUTCFullYear(), y1 = new Date(t1).getUTCFullYear(), span = y1 - y0, st = yearStep(span, W);
    const years = []; for (let yy = y0 + 1; yy <= y1; yy += st) years.push(yy);
    const bx = o.built && Date.parse(o.built) > t0 ? Math.min(W - R, x(o.built)) : null;
    const wk = g.worst, wseg = g.strategy.map((v, i) => (days[i] >= wk.peak && days[i] <= wk.trough ? v : null));
    const ti = days.indexOf(wk.trough), tx = x(wk.trough), tv = g.strategy[ti];
    const lab = `worst fall ${pc(wk.depth, 0)}`, labRight = tx > W - 150;
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block;height:${H}px;overflow:visible" role="img" aria-label="Growth of $10,000: ${money(g.end)} at the end">
      ${ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--line2)"/><text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--dim)">${money(v)}</text>`).join('')}
      ${years.map((yy) => `<text x="${x(yy + '-01-01').toFixed(1)}" y="${H - 6}" text-anchor="middle" font-size="11" fill="var(--dim)">${yy}</text>`).join('')}
      ${bx ? `<rect x="${L}" y="${T}" width="${(bx - L).toFixed(1)}" height="${H - T - B}" fill="var(--dim)" fill-opacity=".10"/><text x="${L + 6}" y="${T + 14}" font-size="11" fill="var(--dim)">built from the index</text>` : ''}
      <line x1="${L}" x2="${W - R}" y1="${y(g.start).toFixed(1)}" y2="${y(g.start).toFixed(1)}" stroke="var(--dim)" stroke-dasharray="4 4"/>
      ${g.bench.map((b, j) => `<path d="${path(b.values, days)}" fill="none" stroke="var(--dim)" stroke-opacity="${j ? 0.55 : 0.85}" ${j ? 'stroke-dasharray="5 4"' : ''} stroke-width="1.3"/>`).join('')}
      <path d="${path(g.strategy, days)}" fill="none" stroke="${o.color}" stroke-width="2.2" stroke-linejoin="round"/>
      <path d="${path(wseg, days)}" fill="none" stroke="var(--dn)" stroke-width="2.6" stroke-linejoin="round"/>
      ${g.real ? `<path d="${path(g.real.values, g.real.days)}" fill="none" stroke="var(--text)" stroke-width="2.4" stroke-linejoin="round"/><circle cx="${x(g.real.days[0]).toFixed(1)}" cy="${y(g.real.values[0]).toFixed(1)}" r="3.5" fill="var(--text)"/>` : ''}
      ${tv ? `<circle cx="${tx.toFixed(1)}" cy="${y(tv).toFixed(1)}" r="4" fill="var(--dn)"/><text x="${(labRight ? tx - 8 : tx + 8).toFixed(1)}" y="${(y(tv) + 16 > H - B - 4 ? y(tv) - 8 : y(tv) + 16).toFixed(1)}" text-anchor="${labRight ? 'end' : 'start'}" font-size="11" fill="var(--dn)">${lab}</text>` : ''}
      <line class="gx" x1="0" x2="0" y1="${T}" y2="${H - B}" stroke="var(--text2)" stroke-width="1" style="display:none"/>
      <rect class="ghit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>
    </svg>`;
  }

  /* calendar-year returns under the growth chart (lighter = part of a year) */
  function yearsSvg(g, W) {
    const yrs = g.years || [];
    if (yrs.length < 2) return '';
    const H = 64, L = ML, R = MR, mid = 32;
    const t0 = Date.parse(g.days[0]), t1 = Date.parse(g.days[g.days.length - 1]);
    const x = (d) => Math.min(W - R, Math.max(L, L + (Date.parse(d) - t0) / (t1 - t0 || 1) * (W - L - R)));
    const m = Math.max(0.05, ...yrs.map((q) => Math.abs(q.ret)));
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block;height:${H}px" role="img" aria-label="Calendar-year returns">
      <line x1="${L}" x2="${W - R}" y1="${mid}" y2="${mid}" stroke="var(--line)"/>
      <text x="${L - 6}" y="12" text-anchor="end" font-size="10" fill="var(--dim)">+${Math.round(m * 100)}%</text><text x="${L - 6}" y="${H - 2}" text-anchor="end" font-size="10" fill="var(--dim)">−${Math.round(m * 100)}%</text>
      ${yrs.map((q) => { const xa = x(q.year + '-01-01'), xb = x((q.year + 1) + '-01-01'), h = Math.max(1, Math.abs(q.ret) / m * (mid - 4));
        return `<rect x="${(xa + 1.5).toFixed(1)}" y="${(q.ret >= 0 ? mid - h : mid).toFixed(1)}" width="${Math.max(1, xb - xa - 3).toFixed(1)}" height="${h.toFixed(1)}" fill="${q.ret >= 0 ? 'var(--up)' : 'var(--dn)'}" opacity="${q.part ? 0.4 : 0.85}"><title>${q.year}${q.part ? ' (part year)' : ''}: ${pcf(q.ret)}</title></rect>`; }).join('')}
    </svg>`;
  }

  function growthCard(d, W, log) {
    const g = d.growth, b = d.backtest;
    if (!g || !b) return '';
    const color = d.color || 'var(--accent)';
    const b0 = g.bench[0];
    const full = (g.years || []).filter((q) => !q.part);
    const up = full.filter((q) => q.ret > 0).length;
    const best = full.reduce((a, q) => (!a || q.ret > a.ret ? q : a), null), worstY = full.reduce((a, q) => (!a || q.ret < a.ret ? q : a), null);
    let vs = '';
    if (b0) {
      const r = g.end / b0.end;
      vs = r >= 0.9 && r <= 1.1 ? 'about the same as the strategy' : r > 1 ? `the strategy made ${r.toFixed(1)}× as much` : `${(1 / r).toFixed(1)}× more than the strategy`;
    }
    const built = Object.values(b.built || {}).sort().pop();
    const mode = U.mode();
    const legend = `<div class="row small" style="gap:16px;flex-wrap:wrap">
      <span class="row" style="gap:6px"><span style="width:18px;height:3px;background:${color};border-radius:2px"></span><b style="font-weight:500">${U.esc(d.name)}</b> <span class="num">${money(g.end)}</span></span>
      ${g.bench.map((q, j) => `<span class="row" style="gap:6px;color:var(--text2)"><span style="width:18px;height:0;border-top:2px ${j ? 'dashed' : 'solid'} var(--dim);opacity:${j ? 0.7 : 1}"></span>${U.esc(q.symbol)} held <span class="num">${money(q.end)}</span></span>`).join('')}
      ${g.real ? `<span class="row" style="gap:6px"><span style="width:18px;height:3px;background:var(--text);border-radius:2px"></span>Real · ${U.esc(U.modeLabel[mode])} since ${day(g.real.from)} <span class="num ${U.cls(g.real.ret)}">${pcf(g.real.ret)}</span></span>` : ''}
      <span class="row" style="gap:6px;color:var(--dn)"><span style="width:18px;height:3px;background:var(--dn);border-radius:2px"></span>worst fall</span></div>`;
    const narrow = W < 560;
    return `<section class="card col" style="gap:14px" id="growth">
      <div class="row sb" style="gap:10px;flex-wrap:wrap;align-items:flex-start"><div><h2 class="h2">Growth of $10,000</h2>
        <div class="muted small">The same backtest as <i>Falls to expect</i> below, after fees: what $10,000 put in on ${day(b.from)} would be worth, next to simply holding the ETF.</div></div>
        <div class="seg" id="gscale"><button data-s="log" class="${log ? 'on' : ''}">Log</button><button data-s="lin" class="${log ? '' : 'on'}">Linear</button></div></div>
      <span class="eyebrow">Backtest · ${day(b.from)} – ${day(b.to)} (${g.years_n} years)</span>
      <div class="grid" style="--min:200px;gap:10px">
        ${tile('$10,000 became', money(g.end), g.cagr != null ? `${pcf(g.cagr)} a year for ${g.years_n} years` : '', g.end >= g.start ? 'up' : 'dn')}
        ${b0 ? tile(`Holding ${U.esc(b0.symbol)} instead`, money(b0.end), `${pcf(b0.cagr)} a year · ${vs}`) : ''}
        ${full.length ? tile('Up years', `${up} of ${full.length}`, `best ${best.year} ${pcf(best.ret)} · worst ${worstY.year} ${pcf(worstY.ret)}`) : ''}
        ${tile('Worst fall', pc(g.worst.depth), `${day(g.worst.peak)} → ${day(g.worst.trough)} · drawn in red`, 'dn')}
      </div>
      ${legend}
      <div class="gchart" style="position:relative">${growthSvg(g, { w: W, h: narrow ? 220 : 270, log, built, color })}
        <div class="gtip" style="display:none;position:absolute;top:8px;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;box-shadow:0 4px 14px rgba(0,0,0,.14);font-size:12px;min-width:170px;z-index:2"></div></div>
      <div class="col" style="gap:2px"><span class="tiny muted">Calendar-year returns (lighter = part of a year)</span>${yearsSvg(g, W)}</div>
      <div class="tiny muted">${built ? `Before ${day(built)} prices are built from the index (shaded), as in the falls chart below. ` : ''}${g.real ? `The real line starts at the backtest's value on its first day, so you can see whether real follows the backtest. ` : ''}Past growth is no promise; the day-by-day real result is on the Daily P&amp;L tab.</div>
    </section>`;
  }

  function growthHover(box, g, W, log) {
    const svg = box.querySelector('.gchart svg'), tip = box.querySelector('.gtip'), gx = box.querySelector('.gx'), hit = box.querySelector('.ghit');
    if (!svg || !hit) return;
    const days = g.days, t0 = Date.parse(days[0]), t1 = Date.parse(days[days.length - 1]);
    const xs = days.map((d) => ML + (Date.parse(d) - t0) / (t1 - t0 || 1) * (W - ML - MR));
    const realAt = (d) => { if (!g.real) return null; let v = null; for (let i = 0; i < g.real.days.length && g.real.days[i] <= d; i++) v = g.real.values[i]; return d >= g.real.from ? v : null; };
    const move = (ev) => {
      const r = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
      const sx = px * W / r.width;
      let lo = 0, hi = xs.length - 1;
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xs[m] < sx) lo = m; else hi = m; }
      const i = Math.abs(xs[lo] - sx) < Math.abs(xs[hi] - sx) ? lo : hi;
      gx.setAttribute('x1', xs[i]); gx.setAttribute('x2', xs[i]); gx.style.display = '';
      const rv = realAt(days[i]);
      tip.innerHTML = `<div class="muted">${day(days[i])}</div>
        <div class="row sb" style="gap:12px"><span>Strategy</span><b class="num">${money(g.strategy[i])}</b></div>
        ${g.bench.map((q) => `<div class="row sb muted" style="gap:12px"><span>${U.esc(q.symbol)} held</span><span class="num">${q.values[i] != null ? money(q.values[i]) : '—'}</span></div>`).join('')}
        ${rv != null ? `<div class="row sb" style="gap:12px"><span>Real</span><b class="num">${money(rv)}</b></div>` : ''}`;
      tip.style.display = '';
      const left = xs[i] / W * r.width;
      tip.style.left = (left > r.width - 200 ? left - tip.offsetWidth - 12 : left + 12) + 'px';
    };
    const out = () => { tip.style.display = 'none'; gx.style.display = 'none'; };
    hit.addEventListener('mousemove', move); hit.addEventListener('mouseleave', out);
    hit.addEventListener('touchstart', move, { passive: true }); hit.addEventListener('touchmove', move, { passive: true }); hit.addEventListener('touchend', out);
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
    let log = true;
    try { log = localStorage.getItem('growthScale') !== 'lin'; } catch (e) { /* private mode */ }
    const draw = () => {
      const W = Math.max(300, Math.round((el.clientWidth || 1000) - 42));
      el.innerHTML = growthCard(d, W, log) + fallsHtml(W);
      const gb = el.querySelector('#growth');
      if (gb) {
        growthHover(gb, d.growth, W, log);
        U.on(gb, '#gscale button', 'click', (e, btn) => {
          log = btn.dataset.s === 'log';
          try { localStorage.setItem('growthScale', log ? 'log' : 'lin'); } catch (er) { /* ignore */ }
          draw();
        });
      }
    };
    let lastW = 0, rt = null;
    const onResize = () => {
      if (!document.body.contains(el)) { window.removeEventListener('resize', onResize); return; }
      clearTimeout(rt);
      rt = setTimeout(() => { if (Math.abs(el.clientWidth - lastW) > 30) { lastW = el.clientWidth; draw(); } }, 200);
    };
    lastW = el.clientWidth;
    window.addEventListener('resize', onResize);
    draw();

    function fallsHtml(W) {
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
      <div>${underwaterSvg(b.underwater, { w: W, built: Object.values(b.built || {}).sort().pop() })}</div>
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
    return html;
    }
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
