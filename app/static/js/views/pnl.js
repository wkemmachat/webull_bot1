/* Dashboard: profit & loss by strategy. Each strategy's part of the Dashboard's Today / Since start numbers (and 1W / 1M /
   3M) as bars or as a stacked running total, plus a sortable table. The rows always add up to the Dashboard number. */
(function () {
  const V = window.Views || (window.Views = {});
  const PERIODS = [['today', 'Today'], ['1w', '1W'], ['1m', '1M'], ['3m', '3M'], ['all', 'Since start']];
  const UNITS = [['usd', '$'], ['pct', '% of its money'], ['pts', 'pts of total']];
  const st = { period: 'all', unit: 'usd', view: 'bars', hidden: {}, sort: ['pnl', -1] };
  try { Object.assign(st, JSON.parse(localStorage.getItem('pnlView') || '{}'), { hidden: {} }); } catch (e) { /* private window */ }
  const save = () => { try { localStorage.setItem('pnlView', JSON.stringify({ period: st.period, unit: st.unit, view: st.view })); } catch (e) { /* ignore */ } };
  const DAY = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short' });
  const pname = (p) => (PERIODS.find((x) => x[0] === p) || [p, p])[1];
  const pts = (v, dp) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(dp == null ? 2 : dp) + ' pts');
  const seg = (id, list, on) => `<div class="seg" id="${id}">${list.map(([k, l]) => `<button type="button" data-k="${k}" class="${k === on ? 'on' : ''}">${l}</button>`).join('')}</div>`;

  function unitVal(r, unit) { return unit === 'usd' ? r.pnl : unit === 'pct' ? r.pct : r.pts; }
  function unitTxt(v, unit) { return unit === 'usd' ? U.sgnUsd(v, 0) : unit === 'pct' ? U.pct(v, 1) : pts(v); }

  /* ---- bars: one per strategy, green right of $0 / red left, sorted best → worst, total row = the Dashboard number */
  function bars(box, d) {
    const rows = d.rows.filter((r) => r.pnl != null).slice().sort((a, b) => (unitVal(b, st.unit) ?? -1e9) - (unitVal(a, st.unit) ?? -1e9));
    if (!rows.length) { box.innerHTML = '<div class="empty small">No profit or loss in this period yet.</div>'; return; }
    const W = Math.max(280, box.clientWidth || 900), narrow = W < 760;
    const nameW = narrow ? 0 : Math.min(320, W * 0.3), rightW = narrow ? 0 : 150, L = nameW + (narrow ? 62 : 70), R = W - rightW - (narrow ? 62 : 70);
    const vals = rows.map((r) => unitVal(r, st.unit) || 0), mx = Math.max(...vals.map((v) => Math.max(v, 0)), 0), mn = Math.min(...vals.map((v) => Math.min(v, 0)), 0);
    const span = (mx - mn) || 1, zero = L + (R - L) * (-mn / span), sc = (R - L) / span;
    const h = narrow ? 46 : 32, top = 20;
    let g = `<line x1="${zero}" x2="${zero}" y1="10" y2="${top + rows.length * h}" stroke="var(--border)"/>
      <text x="${zero}" y="12" text-anchor="middle" font-size="11" fill="var(--muted)">${st.unit === 'usd' ? '$0' : '0'}</text>`;
    rows.forEach((r, i) => {
      const y = top + i * h + (narrow ? 16 : 0), v = unitVal(r, st.unit), w = Math.abs(v || 0) * sc, x = (v || 0) >= 0 ? zero : zero - w;
      const col = (v || 0) >= 0 ? 'var(--up)' : 'var(--dn)', dim = r.no_money ? 0.45 : 0.9;
      const label = `${U.esc(r.name)}${r.no_money ? ' · no money now' : ''}`;
      g += narrow
        ? `<text x="4" y="${y - 3}" font-size="12.5" fill="${r.no_money ? 'var(--muted)' : 'var(--text)'}">${label}</text>`
        : `<rect x="4" y="${y + 9}" width="10" height="10" rx="3" fill="${U.esc(r.color)}"/><text x="22" y="${y + 18}" font-size="13" fill="${r.no_money ? 'var(--muted)' : 'var(--text)'}">${label}</text>`;
      g += `<g class="pnlbar" data-id="${U.esc(r.id)}" style="cursor:pointer"><rect x="0" y="${y + 2}" width="${W}" height="${h - 4}" fill="transparent"/>
        <rect x="${x}" y="${y + 6}" width="${Math.max(w, 2)}" height="18" rx="4" fill="${col}" opacity="${dim}"/>
        <text x="${(v || 0) >= 0 ? zero + w + 8 : zero - w - 8}" y="${y + 19}" font-size="12.5" font-family="var(--mono)" text-anchor="${(v || 0) >= 0 ? 'start' : 'end'}" fill="${col}">${unitTxt(v, st.unit)}</text></g>`;
      if (!narrow) g += `<text x="${W - 4}" y="${y + 19}" font-size="12" font-family="var(--mono)" text-anchor="end" fill="var(--muted)">${st.unit === 'usd' ? U.pct(r.pct, 1) + ' · ' + pts(r.pts) : U.sgnUsd(r.pnl, 0)}</text>`;
    });
    const y = top + rows.length * h + 12;
    g += `<line x1="4" x2="${W - 4}" y1="${y}" y2="${y}" stroke="var(--line)"/>
      <text x="${narrow ? 4 : 22}" y="${y + 24}" font-size="13.5" font-weight="700" fill="var(--text)">Total = the Dashboard number</text>
      <text x="${W - 4}" y="${y + 24}" font-size="13.5" font-weight="700" font-family="var(--mono)" text-anchor="end" fill="${(d.total || 0) < 0 ? 'var(--dn)' : 'var(--up)'}">${U.sgnUsd(d.total)} (${U.pct(d.pct, 2)})</text>`;
    if (st.unit === 'pct') g += `<text x="${narrow ? 4 : 22}" y="${y + 42}" font-size="11.5" fill="var(--muted)">Each strategy's % is of its own money, so these do not add up; switch to “pts of total” for the parts that do.</text>`;
    box.innerHTML = `<svg width="${W}" height="${y + (st.unit === 'pct' ? 52 : 36)}" viewBox="0 0 ${W} ${y + (st.unit === 'pct' ? 52 : 36)}" style="display:block;max-width:100%">${g}</svg><div class="pnltip" hidden></div>`;
    const tip = box.querySelector('.pnltip');
    box.querySelectorAll('.pnlbar').forEach((el) => {
      const r = rows.find((x) => x.id === el.dataset.id);
      el.addEventListener('mousemove', (e) => {
        tip.hidden = false;
        tip.innerHTML = `<b>${U.esc(r.name)}</b>${r.no_money ? ' <span class="muted">· no money now</span>' : ''}
          ${st.period === 'all' ? `<div class="kv"><span class="muted">Money put in (total)</span><span class="num">${U.usd(r.cap_in)}</span></div>` : ''}
          <div class="kv"><span class="muted">Net money in now</span><span class="num">${U.usd(r.net_in)}</span></div>
          <div class="kv"><span class="muted">Value now</span><span class="num">${U.usd(r.value)}</span></div>
          <div class="kv"><span class="muted">P&amp;L · ${pname(st.period)}</span><span class="num ${U.cls(r.pnl)}">${U.sgnUsd(r.pnl)} · ${U.pct(r.pct, 1)}</span></div>
          <div class="kv"><span class="muted">Share of the total</span><span class="num ${U.cls(r.pts)}">${pts(r.pts)} of ${U.pct(d.pct, 2)}</span></div>
          ${st.period === 'all' ? `<div class="kv"><span class="muted">Booked · still open</span><span class="num">${U.sgnUsd(r.realised, 0)} · ${U.sgnUsd(r.open, 0)}</span></div>` : ''}
          <div class="muted small" style="margin-top:4px">Click → the strategy's Daily P&amp;L</div>`;
        const bx = box.getBoundingClientRect(), tw = tip.offsetWidth || 260;
        let x = e.clientX - bx.left + 16; if (x + tw > bx.width) x = e.clientX - bx.left - tw - 16;
        tip.style.left = Math.max(0, x) + 'px'; tip.style.top = (e.clientY - bx.top + 12) + 'px';
      });
      el.addEventListener('mouseleave', () => { tip.hidden = true; });
      el.addEventListener('click', () => { location.hash = '#/strategies/' + r.id + '?tab=pnl'; });
    });
  }

  /* ---- over time: each strategy's running P&L stacked (gains above $0, losses below); black line = the total */
  function overTime(box, d, legend) {
    const ser = d.series, n = ser.t.length;
    const rows = d.rows.filter((r) => ser.lines[r.id] && !st.hidden[r.id]);
    if (n < 2) { box.innerHTML = '<div class="empty small">The chart fills in as the bot records values every 30 minutes.</div>'; return; }
    const W = Math.max(280, box.clientWidth || 900), H = 300, L = W < 500 ? 56 : 70, R = W - 16, T = 12, B = H - 24;
    const tot = ser.t.map((_, i) => d.rows.filter((r) => ser.lines[r.id]).reduce((a, r) => a + ser.lines[r.id][i], 0));
    const posT = ser.t.map((_, i) => rows.reduce((a, r) => a + Math.max(0, ser.lines[r.id][i]), 0));
    const negT = ser.t.map((_, i) => rows.reduce((a, r) => a + Math.min(0, ser.lines[r.id][i]), 0));
    let hi = Math.max(...posT, ...tot, 0), lo = Math.min(...negT, ...tot, 0);
    const pad = (hi - lo) * 0.06 || 10; hi += pad; lo -= pad;
    const t0 = ser.t[0], t1 = ser.t[n - 1], X = (t) => L + (R - L) * (t - t0) / ((t1 - t0) || 1), Y = (v) => T + (B - T) * (hi - v) / (hi - lo);
    const nice = (x) => { const p = Math.pow(10, Math.floor(Math.log10(x))); const m = x / p; return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p; };
    const stp = nice((hi - lo) / 5);
    let g = '';
    for (let v = Math.ceil(lo / stp) * stp; v <= hi; v += stp) {
      g += `<line x1="${L}" x2="${R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${Math.abs(v) < stp / 1e6 ? 'var(--border)' : 'var(--chart-grid)'}"/>
        <text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" font-size="11" fill="var(--muted)">${U.usd(v, 0)}</text>`;
    }
    const pb = new Array(n).fill(0), nb = new Array(n).fill(0);
    rows.forEach((r) => {
      [[1, pb], [-1, nb]].forEach(([sgn, base]) => {
        const part = ser.lines[r.id].map((v) => (sgn > 0 ? Math.max(0, v) : Math.min(0, v)));
        if (part.every((v) => Math.abs(v) < 0.005)) return;
        const topv = part.map((v, i) => base[i] + v);
        const dd = 'M' + topv.map((v, i) => `${X(ser.t[i]).toFixed(1)},${Y(v).toFixed(1)}`).join(' L') + ' L' + base.map((v, i) => `${X(ser.t[i]).toFixed(1)},${Y(v).toFixed(1)}`).reverse().join(' L') + 'Z';
        g += `<path d="${dd}" fill="${U.esc(r.color)}" opacity=".8"/>`;
        topv.forEach((v, i) => { base[i] = v; });
      });
    });
    g += `<path d="M${tot.map((v, i) => `${X(ser.t[i]).toFixed(1)},${Y(v).toFixed(1)}`).join(' L')}" fill="none" stroke="var(--text)" stroke-width="2"/>`;
    const days = (t1 - t0) / 86400, ticks = 5;
    for (let k = 0; k <= ticks; k++) {
      const t = t0 + (t1 - t0) * k / ticks;
      g += `<text x="${X(t)}" y="${H - 4}" text-anchor="${k === 0 ? 'start' : k === ticks ? 'end' : 'middle'}" font-size="11" fill="var(--muted)">${days <= 2 ? U.time(t) : DAY.format(t * 1000)}</text>`;
    }
    g += `<line class="cur" x1="0" x2="0" y1="${T}" y2="${B}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/>`;
    box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="display:block;max-width:100%">${g}<rect class="hit" x="${L}" y="${T}" width="${R - L}" height="${B - T}" fill="transparent"/></svg><div class="pnltip" hidden></div>`;
    const svg = box.querySelector('svg'), tip = box.querySelector('.pnltip'), cur = svg.querySelector('.cur');
    svg.querySelector('.hit').addEventListener('mousemove', (e) => {
      const bx = svg.getBoundingClientRect(), xm = (e.clientX - bx.left) * (W / bx.width);
      let i = 0; for (let k = 0; k < n; k++) if (Math.abs(X(ser.t[k]) - xm) < Math.abs(X(ser.t[i]) - xm)) i = k;
      cur.setAttribute('x1', X(ser.t[i])); cur.setAttribute('x2', X(ser.t[i])); cur.setAttribute('visibility', 'visible');
      const parts = d.rows.filter((r) => ser.lines[r.id]).map((r) => ({ r, v: ser.lines[r.id][i], dv: i ? ser.lines[r.id][i] - ser.lines[r.id][i - 1] : 0 }))
        .sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
      const top = parts.slice(0, 6), rest = parts.slice(6);
      tip.hidden = false;
      tip.innerHTML = `<b>${i === n - 1 ? 'Now' : U.dtLong(ser.t[i])}</b>
        <div class="kv"><span>Total ${st.period === 'all' ? 'since start' : 'since ' + DAY.format(t0 * 1000)}</span><span class="num ${U.cls(tot[i])}">${U.sgnUsd(tot[i])}</span></div>
        ${top.map((p) => `<div class="kv"><span class="row" style="gap:6px;flex-wrap:nowrap">${U.dot(p.r.color, 8)}<span class="muted" style="max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(p.r.name)}</span></span><span class="num ${U.cls(p.v)}">${U.sgnUsd(p.v)}</span></div>`).join('')}
        ${rest.length ? `<div class="kv"><span class="muted">${rest.length} others</span><span class="num ${U.cls(rest.reduce((a, p) => a + p.v, 0))}">${U.sgnUsd(rest.reduce((a, p) => a + p.v, 0))}</span></div>` : ''}`;
      const tw = tip.offsetWidth || 280; let x = e.clientX - bx.left + 16; if (x + tw > bx.width) x = e.clientX - bx.left - tw - 16;
      tip.style.left = Math.max(0, x) + 'px'; tip.style.top = '10px';
    });
    svg.querySelector('.hit').addEventListener('mouseleave', () => { tip.hidden = true; cur.setAttribute('visibility', 'hidden'); });
    legend.innerHTML = d.rows.filter((r) => ser.lines[r.id]).map((r) => `<button type="button" class="pnlleg${st.hidden[r.id] ? ' off' : ''}" data-id="${U.esc(r.id)}">${U.dot(r.color, 9)}${U.esc(r.name)}</button>`).join('');
  }

  /* ---- the numbers: sortable table, last row = the Dashboard number */
  function table(box, d) {
    const cols = [['name', 'Strategy', 0], ['net_in', 'Net money in', 1], ['value', 'Value now', 1], ['pnl', 'P&L · ' + pname(st.period), 1], ['pct', '% of its money', 1], ['pts', 'Share of total', 1]];
    if (st.period === 'all') cols.push(['realised', 'Booked', 1], ['open', 'Still open', 1]);
    const [k, dir] = st.sort, val = (r) => (k === 'name' ? r.name.toLowerCase() : r[k] == null ? -1e12 : r[k]);
    const rows = d.rows.slice().sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * dir);
    const cell = (r, c) => {
      const v = r[c];
      if (c === 'name') return `<td><a href="#/strategies/${U.esc(r.id)}?tab=pnl" class="row" style="gap:8px;color:var(--text);flex-wrap:nowrap">${U.dot(r.color)}${U.esc(r.name)}${r.no_money ? ' <span class="pill">no money now</span>' : ''}</a></td>`;
      if (c === 'net_in' || c === 'value') return `<td class="r num">${U.usd(v)}</td>`;
      if (c === 'pct') return `<td class="r num ${U.cls(v)}">${U.pct(v, 1)}</td>`;
      if (c === 'pts') return `<td class="r num ${U.cls(v)}">${pts(v)}</td>`;
      return `<td class="r num ${U.cls(v)}">${U.sgnUsd(v)}</td>`;
    };
    const sumBy = (c) => d.rows.reduce((a, r) => a + (r[c] || 0), 0);
    box.innerHTML = `<div class="tw"><table class="t"><thead><tr>${cols.map(([c, l, right]) => `<th class="${right ? 'r' : ''}"><button type="button" class="th-sort${c === k ? ' on' : ''}" data-c="${c}">${l}<span class="arr">${c === k ? (dir > 0 ? '▲' : '▼') : ''}</span></button></th>`).join('')}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map(([c]) => cell(r, c)).join('')}</tr>`).join('')}</tbody>
      <tfoot><tr><td>All strategies = Bot equity</td><td class="r num">${U.usd(sumBy('net_in'))}</td><td class="r num">${U.usd(sumBy('value'))}</td>
        <td class="r num ${U.cls(d.total)}">${U.sgnUsd(d.total)}</td><td class="r num ${U.cls(d.pct)}">${U.pct(d.pct, 2)}</td><td class="r num ${U.cls(d.pct)}">${pts(d.pct)}</td>
        ${st.period === 'all' ? `<td class="r num ${U.cls(sumBy('realised'))}">${U.sgnUsd(sumBy('realised'))}</td><td class="r num ${U.cls(sumBy('open'))}">${U.sgnUsd(sumBy('open'))}</td>` : ''}</tr></tfoot></table></div>
      ${d.empty.length ? `<div class="muted small" style="padding:10px 14px">No money and no profit or loss ${st.period === 'all' ? 'yet' : 'in this period'}: ${d.empty.map(U.esc).join(', ')}</div>` : ''}`;
    U.on(box, '.th-sort', 'click', (e, b) => { const c = b.dataset.c; st.sort = [c, st.sort[0] === c ? -st.sort[1] : (c === 'name' ? 1 : -1)]; table(box, d); });
  }

  V.renderPnl = async function (el, opts) {
    if (!el) return;
    if (opts && opts.period) { st.period = opts.period; save(); }
    const mode = U.mode();
    el.innerHTML = el.innerHTML || '<section class="card"><div class="muted small">Loading profit &amp; loss by strategy…</div></section>';
    let d;
    try { d = await U.api(`/api/pnl?mode=${mode}&period=${st.period}`); } catch (e) { el.innerHTML = `<section class="card"><div class="note warn">Profit &amp; loss by strategy: ${U.esc(e.message || e)}</div></section>`; return; }
    el.innerHTML = `<section class="card col" style="gap:14px" id="pnlcard">
      <div class="row sb" style="align-items:flex-start;gap:12px">
        <div><div class="eyebrow">Profit &amp; loss by strategy</div>
          <div style="margin-top:4px;font-size:15px">${pname(st.period)} <b class="num ${U.cls(d.total)}">${d.total == null ? '—' : U.sgnUsd(d.total) + ' (' + U.pct(d.pct, 2) + ')'}</b>
            <span class="muted small">= the sum of the ${st.view === 'bars' ? 'bars' : 'bands'}${d.since ? ' · since ' + U.dtLong(d.since) : ''}</span></div></div>
        <div class="row" style="gap:8px">${seg('pnlper', PERIODS, st.period)}${st.view === 'bars' ? seg('pnlunit', UNITS, st.unit) : ''}${seg('pnlview', [['bars', 'Bars'], ['time', 'Over time']], st.view)}</div>
      </div>
      <div id="pnlchart" style="position:relative"></div>
      <div id="pnlleg" class="row" style="gap:6px 14px"></div>
      <div class="muted small">${st.view === 'bars'
        ? 'Worked out like the Dashboard: value change minus money moved in or out. Strategies that hold no money now but made or lost money earlier stay in the list, so the bars add up to the total. “% of its money” is each strategy on its own; “pts of total” is its share of the total %, and those add up.'
        : 'Each colour band is one strategy\'s running P&amp;L in dollars (gains stack above $0, losses below); the dark line is the total. Hover to see each strategy\'s part at that time; click a name to hide it.'}</div>
      <div id="pnltbl" style="margin:0 -20px -20px"></div></section>`;
    const chart = el.querySelector('#pnlchart'), leg = el.querySelector('#pnlleg');
    const draw = () => { if (st.view === 'bars') { leg.innerHTML = ''; bars(chart, d); } else overTime(chart, d, leg); };
    el._draw = draw;
    draw();
    table(el.querySelector('#pnltbl'), d);
    U.on(el, '#pnlper button', 'click', (e, b) => { st.period = b.dataset.k; save(); V.renderPnl(el); });
    U.on(el, '#pnlunit button', 'click', (e, b) => { st.unit = b.dataset.k; save(); V.renderPnl(el); });
    U.on(el, '#pnlview button', 'click', (e, b) => { st.view = b.dataset.k; save(); V.renderPnl(el); });
    U.on(el, '.pnlleg', 'click', (e, b) => { st.hidden[b.dataset.id] = !st.hidden[b.dataset.id]; draw(); });
    if (!el._resize) { el._resize = true; let tm; window.addEventListener('resize', () => { clearTimeout(tm); tm = setTimeout(() => { if (document.body.contains(el) && el._draw) el._draw(); }, 200); }); }
  };
})();
