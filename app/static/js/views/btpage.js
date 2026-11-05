/* Backtest page (#/backtest): every strategy side by side — table, return vs worst fall, growth of $10,000, how the
   strategies move together, and "Try a mix". Data: /api/backtest-overview (the expected-returns check, nothing re-run). */
(function () {
  const V = window.Views || (window.Views = {});
  const P = (v, dp) => v == null || isNaN(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 1 : dp) + '%';
  const PP = (v, dp) => v == null || isNaN(v) ? '—' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 1 : dp) + '%';
  const GROUPS = [['all', 'All'], ['money', 'With money'], ['usd', 'Semis · USD'], ['qld', 'Nasdaq · QLD'], ['rom', 'Tech · ROM'],
    ['stocks', 'Stocks'], ['gold', 'Gold'], ['silver', 'Silver']];
  const SYM_COL = { USD: '#2563EB', QLD: '#0D9488', ROM: '#059669', UGL: '#B45309', GLD: '#CA8A04', AGQ: '#64748B', SLV: '#94A3B8', SGOV: '#A3A3A3', BIL: '#A3A3A3', cash: '#9CA3AF' };
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
  // keep the part that tells strategies apart ("Gold · Trend calm" → "Gold · Trend calm", long names cut with …)
  const short = (n) => n.length > 24 ? n.slice(0, 22).trim() + '…' : n;
  const tOf = (s) => Math.floor(Date.parse(s + 'T00:00:00Z') / 1000);
  const dayTxt = (s) => s ? new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(tOf(s) * 1000)) : '—';
  const money = (v) => v >= 1e6 ? '$' + (v / 1e6).toFixed(2) + 'M' : U.usd(v, 0);

  const COLS = [
    // your money, and under it what you would lose if the 10-year worst fall came back (folded in so the table fits a laptop)
    { k: 'value', l: 'Your money', s: 'worst fall in $', f: (r) => r.value > 0.5 ? `${U.usd(r.value, 0)}${r.worst_usd ? `<div class="tiny dn" title="If the 10-year worst fall came back: ${U.usd(r.value, 0)} → ${U.usd(r.value - r.worst_usd, 0)}">−${U.usd(r.worst_usd, 0)}</div>` : ''}` : '<span class="muted">$0</span>' },
    { k: 'r1', l: '1 year', f: (r) => `<span class="${U.cls(r.r1)}">${P(r.r1)}</span>` },
    { k: 'r3', l: '3 years', s: 'a year', f: (r) => `<span class="${U.cls(r.r3)}">${P(r.r3)}</span>` },
    { k: 'r10', l: '10 years', s: 'a year', f: (r) => `<b class="${U.cls(r.r10)}">${P(r.r10)}</b><div class="tiny muted">${r.src === 'research' ? 'research' : r.r10 == null ? (r.years ? r.years + ' yr only' : '') : 'bot backtest'}</div>` },
    { k: 'dd10', l: 'Worst fall', s: '10 years', f: (r) => `<span class="dn">${PP(r.dd10)}</span>`, neg: true },
    { k: 'ret_dd', l: 'Return ÷ fall', f: (r) => `<b>${r.ret_dd == null ? '—' : r.ret_dd.toFixed(2)}</b>` },
    { k: 'up', l: 'Years up', f: (r) => r.of ? `${r.up} of ${r.of}` : '—', get: (r) => r.of ? r.up / r.of : null },
    { k: 'below', l: 'Below a high', s: '% of weeks', f: (r) => r.below == null ? '—' : r.below + '%', lowGood: true },
    { k: 'now', l: 'Now', s: 'below its high', f: (r) => r.now == null ? '—' : `<span class="dn">${PP(r.now)}</span>${r.pct != null ? `<div style="margin-top:3px">${zonePill(r) }</div>` : ''}`, neg: true },
  ];
  // the dip zone, short (the depth is already on the line above): "▲▲ Strong buy", the percentile under it; full text on hover
  function zonePill(r) {
    const d = r.dip;
    if (!d || !d.zone) return `<span class="tiny muted">${U.ordinal(r.pct)} pct</span>`;
    const full = U.dipPill(d), tip = (full.match(/title="([^"]*)"/) || [])[1] || '';
    return `<span class="pill ${d.zone === 'deep' ? 'dip2' : 'dip1'}" title="${tip}">${d.zone === 'deep' ? '▲▲ Strong buy' : '▲ Buy zone'}</span><div class="tiny muted" style="margin-top:2px">${U.ordinal(d.pct)} pct</div>`;
  }

  V.backtestAll = async function (el) {
    const mode = U.mode();
    const d = await U.api('/api/backtest-overview?mode=' + mode);
    const st = { f: store.get('btF', 'all'), sort: store.get('btSort', { k: 'ret_dd', dir: -1 }), idle: U.showIdle(), w: null, charts: [] };
    const byId = {};
    d.rows.forEach((r) => { byId[r.id] = r; });
    const T = d.dates.map(tOf);

    function destroy() { st.charts.forEach((c) => { try { c.remove(); } catch (e) {} }); st.charts = []; }
    const visibleAll = () => d.rows.filter((r) => st.idle || !r.idle);
    const inFilter = (r) => st.f === 'all' || (st.f === 'money' ? r.value > 0.5 : r.group === st.f);
    function shown() {
      const col = COLS.find((c) => c.k === st.sort.k) || COLS[5];
      const get = col.get || ((r) => r[col.k]);
      return visibleAll().filter(inFilter).sort((a, b) => {
        const x = get(a), y = get(b);
        if (x == null && y == null) return 0;
        if (x == null) return 1;
        if (y == null) return -1;
        return (x - y) * st.sort.dir;
      });
    }

    function summary() {
      const s = d.summary, tot = s.total || 0;
      const syms = Object.entries(s.by_symbol);
      const top = syms.filter(([k]) => k !== 'cash')[0];
      const topShare = top && tot ? top[1] / tot * 100 : 0;
      const holders = top ? d.rows.filter((r) => r.holdings && r.holdings[top[0]] > 0.5).length : 0;
      const tile = (k, v, sub, cls) => `<div class="card" style="padding:14px 16px"><div class="eyebrow">${k}</div><div class="num big ${cls || ''}" style="margin-top:6px">${v}</div><div class="muted small" style="margin-top:2px">${sub}</div></div>`;
      return `<div class="grid" style="--min:220px;gap:12px">
        ${tile('Money in strategies', U.usd(tot, 0), `${s.n} ${s.n === 1 ? 'strategy' : 'strategies'} with money · ${U.esc(U.modeLabel[mode])}`)}
        ${tile('If every worst fall came back at once', s.worst_usd ? '−' + U.usd(s.worst_usd, 0) + (tot ? ' · −' + (s.worst_usd / tot * 100).toFixed(0) + '%' : '') : '—', 'each strategy\'s worst 10-year fall × its money now', 'dn')}
        <div class="card" style="padding:14px 16px"><div class="eyebrow">Money by holding now</div>
          <div role="img" aria-label="${U.esc(syms.map(([k, v]) => k + ' ' + (v / (tot || 1) * 100).toFixed(0) + '%').join(', '))}" style="display:flex;height:12px;border-radius:6px;overflow:hidden;gap:2px;margin-top:10px">
            ${syms.map(([k, v]) => `<div title="${U.esc(k)}" style="flex:${v};background:${SYM_COL[k] || '#8592A3'}"></div>`).join('') || '<div style="flex:1;background:var(--line)"></div>'}</div>
          <div class="muted small" style="margin-top:6px">${syms.map(([k, v]) => `${U.esc(k)} ${(v / (tot || 1) * 100).toFixed(0)}%`).join(' · ') || 'No money yet'}</div></div>
        <div class="card" style="padding:14px 16px"><div class="eyebrow">Worth a look</div>
          ${topShare > 50 ? `<div class="note warn" style="margin-top:8px"><span>${topShare.toFixed(0)}% of your money is in ${U.esc(top[0])}${holders > 1 ? ` through ${holders} strategies: they rise and fall together (see the grid below)` : ''}.</span></div>`
            : `<div class="muted small" style="margin-top:8px">No single holding has more than half of your money.</div>`}</div></div>`;
    }

    function table() {
      const rows = shown(), nIdle = d.rows.filter((r) => r.idle).length;
      const counts = (k) => visibleAll().filter((r) => k === 'all' || (k === 'money' ? r.value > 0.5 : r.group === k)).length;
      const th = (c) => `<th class="r" style="cursor:pointer" data-sort="${c.k}" aria-sort="${st.sort.k === c.k ? (st.sort.dir < 0 ? 'descending' : 'ascending') : 'none'}">${c.l}${st.sort.k === c.k ? (st.sort.dir < 0 ? ' ▼' : ' ▲') : ''}${c.s ? `<div class="tiny muted" style="font-weight:400">${c.s}</div>` : ''}</th>`;
      return `<div class="row" style="gap:8px;flex-wrap:wrap;align-items:center">
          <div class="seg" id="bt-f">${GROUPS.filter(([k]) => k === 'all' || k === 'money' || counts(k)).map(([k, l]) => `<button data-f="${k}" class="${st.f === k ? 'on' : ''}">${l} · ${counts(k)}</button>`).join('')}</div>
          <span style="flex:1"></span>${nIdle ? U.idleToggle(nIdle, st.idle) : ''}</div>
        <section class="card" style="padding:4px 0">
          <div class="tw"><table class="t bt-t"><thead><tr><th>Strategy</th>${COLS.map(th).join('')}</tr></thead><tbody>
          ${rows.map((r) => `<tr><td><a href="#/strategies/${encodeURIComponent(r.id)}?tab=backtest" style="display:flex;gap:9px;align-items:flex-start;color:var(--text);white-space:normal;min-width:150px;max-width:230px">${U.dot(r.color)}<span><span style="font-weight:500">${U.esc(r.name)}</span>
              <span class="tiny muted" style="display:block">${U.esc(r.etf)} · ${r.timeframe === '1d' ? 'daily' : U.esc(r.timeframe || '')}${r.control === 'stopped' ? ' · stopped' : ''}</span></span></a></td>
              ${COLS.map((c) => `<td class="r num">${c.f(r)}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="${COLS.length + 1}" class="muted">No strategy in this filter.</td></tr>`}
          </tbody></table></div>
          <div class="muted small" style="padding:8px 16px 12px">How to read: <b>Return ÷ fall</b> = 10-year return a year ÷ 10-year worst fall: more return for each 1% you had to sit through is better. <b>Your money</b>: the red line under it is what you would lose if the 10-year worst fall came back. <b>Below a high</b> = share of weeks under the last peak. <b>Now</b> = how far below its high today, and where that ranks among all past days (Buy zone from the 70th, Strong buy from the 90th).
            Gold and silver: Yahoo keeps only about 2 years of hourly futures, so their 10 years come from the research on OANDA prices (<i>research</i>). Click a column to sort, a strategy for its own backtest.</div>
        </section>`;
    }

    function scatter() {
      const rows = shown().filter((r) => r.r10 != null && r.dd10 != null);
      if (rows.length < 2) return '';
      const xs = rows.map((r) => Math.abs(r.dd10)), ys = rows.map((r) => r.r10);
      const x0 = Math.max(0, Math.floor((Math.min(...xs) - 5) / 10) * 10), x1 = Math.ceil((Math.max(...xs) + 5) / 10) * 10;
      const y0 = Math.min(0, Math.floor(Math.min(...ys) / 10) * 10), y1 = Math.ceil((Math.max(...ys) + 5) / 10) * 10;
      const X = (v) => 60 + (v - x0) / (x1 - x0) * 900, Y = (v) => 20 + (y1 - v) / (y1 - y0) * 300;
      const maxM = Math.max(...rows.map((r) => r.value), 1);
      const rad = (r) => 6 + Math.sqrt(Math.max(r.value, 0) / maxM) * 20;
      const gx = [], gy = [];
      for (let v = x0; v <= x1; v += 10) gx.push(v);
      for (let v = y0; v <= y1; v += (y1 - y0 > 60 ? 20 : 10)) gy.push(v);
      return `<section class="card col" style="gap:8px"><div><h2 class="h2">Return against worst fall</h2>
        <div class="muted small" style="margin-top:2px;max-width:860px">Each circle is a strategy: higher = more return a year, further left = a smaller worst fall (10 years). Top-left is best. The size is your money in it now (a small dot = no money).</div></div>
        <div style="position:relative;width:100%;aspect-ratio:1000/350">
          <svg viewBox="0 0 1000 350" role="img" aria-label="10-year return a year against worst fall for each strategy" style="position:absolute;inset:0;width:100%;height:100%">
            ${gy.map((v) => `<line x1="60" x2="960" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--chart-grid)"/>`).join('')}
            ${gx.map((v) => `<line y1="20" y2="320" x1="${X(v)}" x2="${X(v)}" stroke="var(--chart-grid)"/>`).join('')}
            ${rows.map((r) => `<circle cx="${X(Math.abs(r.dd10))}" cy="${Y(r.r10)}" r="${rad(r)}" fill="${U.esc(r.color)}" fill-opacity=".8" stroke="var(--panel)" stroke-width="2"><title>${U.esc(r.name)}: ${P(r.r10)} a year, worst fall ${PP(r.dd10)}</title></circle>`).join('')}
          </svg>
          ${gy.map((v) => `<span class="tiny muted num" style="position:absolute;left:0;top:calc(${Y(v) / 3.5}% - 8px)">${v}%</span>`).join('')}
          ${gx.map((v) => `<span class="tiny muted num" style="position:absolute;top:93%;left:${X(v) / 10}%;transform:translateX(-50%)">−${v}%</span>`).join('')}
          ${rows.map((r) => `<span class="tiny" style="position:absolute;white-space:nowrap;left:${(X(Math.abs(r.dd10)) + rad(r) + 3) / 10}%;top:calc(${Y(r.r10) / 3.5}% - 8px)">${U.esc(short(r.name))}</span>`).join('')}
        </div><div class="muted tiny">Up: return a year · across: worst fall.</div></section>`;
    }

    function growthBox() {
      return `<section class="card col" style="gap:8px"><div><h2 class="h2">Growth of $10,000, every strategy</h2>
        <div class="muted small" style="margin-top:2px;max-width:860px">Profit reinvested, weekly closes, log scale: the same slope means the same % gain, so a steady line is a steady strategy. Flat stretches are time in cash; steps down are its falls.</div></div>
        <div class="tvwrap"><div id="bt-grow" style="height:340px;position:relative"><div class="tvlegend" id="bt-growleg"></div></div></div></section>`;
    }

    function corrBox() {
      const ids = d.corr.ids.filter((id) => byId[id] && shown().includes(byId[id]));
      if (ids.length < 2) return '';
      const ix = (id) => d.corr.ids.indexOf(id);
      const cell = (a, b) => {
        if (a === b) return '<td style="background:var(--text);width:52px;height:30px;border-radius:4px"></td>';
        const v = d.corr.m[ix(a)][ix(b)];
        if (v == null) return '<td class="muted" style="text-align:center">—</td>';
        return `<td class="num" title="${U.esc(byId[a].name)} × ${U.esc(byId[b].name)}" style="text-align:center;width:52px;height:30px;border-radius:4px;background:color-mix(in srgb, var(--info) ${Math.round(Math.max(v, 0) * 85)}%, transparent);${v > 0.55 ? 'color:var(--bg)' : ''}">${v.toFixed(2).replace('0.', '.')}</td>`;
      };
      return `<section class="card col" style="gap:8px"><div><h2 class="h2">Do they move together?</h2>
        <div class="muted small" style="margin-top:2px;max-width:860px">Correlation of weekly returns over 10 years. 1.00 = always up and down together; below .30 = mostly independent. Money spread over dark squares is <i>not</i> really spread: those strategies fall at the same time.</div></div>
        <div class="tw"><table style="border-collapse:separate;border-spacing:2px;font-size:11.5px"><thead><tr><th></th>${ids.map((id) => `<th class="tiny muted" style="font-weight:500;width:52px;vertical-align:bottom">${U.esc(short(byId[id].name))}</th>`).join('')}</tr></thead>
        <tbody>${ids.map((a) => `<tr><th class="small" style="text-align:left;font-weight:500;padding-right:8px;white-space:nowrap">${U.dot(byId[a].color)} ${U.esc(short(byId[a].name))}</th>${ids.map((b) => cell(a, b)).join('')}</tr>`).join('')}</tbody></table></div></section>`;
    }

    // ---- Try a mix: each strategy keeps its own money, never rebalanced (as the bot runs it)
    const mixable = () => visibleAll().filter((r) => d.series[r.id]);
    function nowMix() { const w = {}; mixable().forEach((r) => { w[r.id] = Math.max(0, Math.round(r.value)); }); return w; }
    function mixSeries(w) {
      const ids = Object.keys(w).filter((k) => w[k] > 0 && d.series[k]);
      const sum = ids.reduce((a, k) => a + w[k], 0);
      if (!sum) return null;
      const start = Math.max(...ids.map((k) => d.series[k].findIndex((x) => x != null)));
      const out = [];
      for (let i = start; i < T.length; i++) {
        let v = 0;
        ids.forEach((k) => { const s = d.series[k]; const x = s[i] != null ? s[i] : null; if (x != null) v += w[k] / sum * x / s[start]; });
        out.push({ time: T[i], value: v });
      }
      return { start, pts: out };
    }
    function mixStats(m) {
      if (!m || m.pts.length < 60) return null;
      const v = m.pts.map((p) => p.value), n = v.length, yrs = (n - 1) / 52.18;
      let hi = v[0], dd = 0, w12 = Infinity;
      for (let i = 0; i < n; i++) { hi = Math.max(hi, v[i]); dd = Math.min(dd, v[i] / hi - 1); if (i >= 52) w12 = Math.min(w12, v[i] / v[i - 52] - 1); }
      const cagr = Math.pow(v[n - 1] / v[0], 1 / yrs) - 1;
      return { cagr: cagr * 100, dd: dd * 100, ratio: cagr / Math.abs(dd || 1e-9), w12: isFinite(w12) ? w12 * 100 : null, from: d.dates[m.start] };
    }
    function mixBox() {
      const rows = mixable();
      if (!rows.length) return '';
      const w = st.w || nowMix(), sum = Object.values(w).reduce((a, b) => a + b, 0);
      return `<section class="card col" style="gap:12px"><div><h2 class="h2">Try a mix</h2>
        <div class="muted small" style="margin-top:2px;max-width:900px">Set how much each strategy gets and see the past as one portfolio. Each strategy keeps its own money and is never rebalanced, exactly as the bot runs it. Blue = your money as it is split now; green = the mix you set. Nothing here moves money: use Money → Move for that.</div></div>
        <div class="row" style="gap:8px;flex-wrap:wrap">${[['now', 'Your mix now'], ['top3', 'Top 3 by return ÷ fall'], ['equal', 'Equal, best 6'], ['spread', 'Spread: best 4 + gold + silver']].map(([k, l]) => `<button class="btn s" data-mix="${k}">${l}</button>`).join('')}</div>
        <div class="row" style="gap:20px;flex-wrap:wrap;align-items:flex-start">
          <div class="col" style="flex:1 1 330px;gap:6px">
            ${rows.map((r) => `<label style="display:grid;grid-template-columns:12px minmax(0,1fr) 120px 46px;gap:8px;align-items:center" class="small">${U.dot(r.color)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(r.name)}</span>
              <input type="range" min="0" max="100" step="5" value="${Math.round((w[r.id] || 0) / (sum || 1) * 100)}" data-w="${r.id}" style="accent-color:var(--accent)" aria-label="Share of ${U.esc(r.name)}"><span class="num r" data-wp="${r.id}">${Math.round((w[r.id] || 0) / (sum || 1) * 100)}%</span></label>`).join('')}
            <div class="muted tiny">Shares are scaled so they add up to 100%.</div></div>
          <div class="col" style="flex:999 1 520px;min-width:0;gap:10px">
            <div class="tvwrap"><div id="bt-mix" style="height:300px;position:relative"><div class="tvlegend" id="bt-mixleg"></div></div></div>
            <div id="bt-mixstats"></div></div></div></section>`;
    }
    function mixPreset(k) {
      const rows = mixable().filter((r) => r.ret_dd != null).sort((a, b) => b.ret_dd - a.ret_dd), w = {};
      if (k === 'now') return nowMix();
      if (k === 'top3') rows.slice(0, 3).forEach((r) => { w[r.id] = 1; });
      if (k === 'equal') rows.slice(0, 6).forEach((r) => { w[r.id] = 1; });
      if (k === 'spread') {
        rows.filter((r) => r.group !== 'gold' && r.group !== 'silver').slice(0, 4).forEach((r) => { w[r.id] = 20; });
        const g = rows.find((r) => r.group === 'gold'), s = rows.find((r) => r.group === 'silver');
        if (g) w[g.id] = 10;
        if (s) w[s.id] = 10;
      }
      return w;
    }
    function drawMix() {
      const host = el.querySelector('#bt-mix');
      if (!host) return;
      const old = st.charts.find((c) => c._mix);
      if (old) { try { old.remove(); } catch (e) {} st.charts = st.charts.filter((c) => c !== old); }
      const tot = d.summary.total > 0 ? d.summary.total : 10000;
      const a = mixSeries(nowMix()), b = mixSeries(st.w || nowMix());
      const ch = Charts.base(host, { daily: true, timeVisible: true });
      ch._mix = true;
      ch.priceScale('right').applyOptions({ mode: LightweightCharts.PriceScaleMode.Logarithmic });
      ch.applyOptions({ localization: { priceFormatter: (p) => money(p) } });
      const add = (m, color, w) => { if (!m) return; const s = ch.addLineSeries({ color, lineWidth: w, priceLineVisible: false }); s.setData(m.pts.map((p) => ({ time: p.time, value: p.value * tot }))); };
      add(a, '#2563EB', 2); add(b, '#059669', 3);
      ch.timeScale().fitContent();
      st.charts.push(ch);
      const sa = mixStats(a), sb = mixStats(b);
      const row = (l, f, cls) => `<tr><td class="muted">${l}</td><td class="r num ${cls || ''}">${sa ? f(sa) : '—'}</td><td class="r num ${cls || ''}" style="font-weight:600">${sb ? f(sb) : '—'}</td></tr>`;
      el.querySelector('#bt-mixleg').innerHTML = `<span style="color:#2563EB">Your mix now</span><span style="color:#059669">The mix you set</span>`;
      el.querySelector('#bt-mixstats').innerHTML = `<div class="tw"><table class="t"><thead><tr><th>${sb ? 'Since ' + dayTxt(sb.from) : ''}</th><th class="r" style="color:#2563EB">Your mix now</th><th class="r" style="color:#059669">The mix you set</th></tr></thead><tbody>
        ${row('A year', (s) => P(s.cagr))}${row('Worst fall', (s) => PP(s.dd), 'dn')}${row('Return ÷ fall', (s) => s.ratio.toFixed(2))}
        ${row(`${U.usd(tot, 0)} in its worst fall`, (s) => '−' + U.usd(tot * Math.abs(s.dd) / 100, 0), 'dn')}${row('Worst 12 months', (s) => P(s.w12, 0))}</tbody></table></div>
        <div class="muted tiny" style="margin-top:4px">Weekly closes. The window starts when every strategy in the mix has data${sb && sb.from > d.dates[0] ? ` (here ${dayTxt(sb.from)})` : ''}. ${!sb && b ? ' This mix has under 60 weeks of shared history, too short for these numbers.' : ''} A mix only lowers the fall if its parts do not fall together.</div>`;
    }

    function drawGrowth() {
      const host = el.querySelector('#bt-grow');
      if (!host) return;
      const rows = shown().filter((r) => d.series[r.id]);
      const ch = Charts.base(host, { daily: true, timeVisible: true });
      ch.priceScale('right').applyOptions({ mode: LightweightCharts.PriceScaleMode.Logarithmic });
      ch.applyOptions({ localization: { priceFormatter: (p) => money(p) } });
      const lines = rows.map((r) => {
        const s = d.series[r.id], i0 = s.findIndex((x) => x != null), b = s[i0];
        const ser = ch.addLineSeries({ color: r.color, lineWidth: r.value > 0.5 ? 3 : 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        const data = [];
        for (let i = i0; i < T.length; i++) if (s[i] != null) data.push({ time: T[i], value: s[i] / b * 10000 });
        ser.setData(data);
        return { r, data };
      });
      ch.timeScale().fitContent();
      st.charts.push(ch);
      const leg = el.querySelector('#bt-growleg');
      const at = (time) => {
        leg.innerHTML = lines.slice().sort((a, b) => (b.data[b.data.length - 1] || {}).value - (a.data[a.data.length - 1] || {}).value).slice(0, 12).map((l) => {
          const p = time == null ? l.data[l.data.length - 1] : l.data.find((x) => x.time === time);
          return `<span style="color:${U.esc(l.r.color)}">${U.esc(short(l.r.name))} <b class="num" style="font-weight:500">${p ? money(p.value) : '—'}</b></span>`;
        }).join('');
      };
      at(null);
      ch.subscribeCrosshairMove((p) => at(p.time));
    }

    function render() {
      destroy();
      el.innerHTML = `<div class="col" style="gap:18px">
        <div><div class="eyebrow">Trade</div><h1 class="h1" style="margin:2px 0 4px">Backtest</h1>
          <div class="muted" style="max-width:880px">Every strategy's own rules over the last 10 years: decided at the close, filled at the next open, Webull's real fee. Use it to choose which strategies get money and how much. Click a strategy for its full backtest: equity curve with or without reinvesting, range of outcomes, stress test and falls.</div></div>
        ${d.check && d.check.running ? '<div class="note info"><span>The yearly backtest check is running; this page fills in when it finishes.</span></div>' : ''}
        ${summary()}${table()}${scatter()}${growthBox()}${corrBox()}${mixBox()}
        <div class="muted small">Charts use weekly closes from the last backtest check, so falls look a little shallower than the daily worst fall in the table. Backtests are history, not a promise: plan on less.</div></div>`;
      drawGrowth();
      drawMix();
      U.on(el, '#bt-f button', 'click', (e, b) => { st.f = b.dataset.f; store.set('btF', st.f); render(); });
      U.on(el, '[data-sort]', 'click', (e, b) => {
        const k = b.dataset.sort, col = COLS.find((c) => c.k === k);
        st.sort = st.sort.k === k ? { k, dir: -st.sort.dir } : { k, dir: col && (col.lowGood || col.neg) ? (col.neg ? -1 : 1) : -1 };
        store.set('btSort', st.sort); render();
      });
      U.on(el, '[data-idle]', 'click', () => { st.idle = !st.idle; U.showIdle(st.idle); render(); });
      U.on(el, '[data-mix]', 'click', (e, b) => { st.w = mixPreset(b.dataset.mix); render(); });
      U.on(el, '[data-w]', 'input', (e, inp) => {
        const w = Object.assign({}, st.w || nowMix()), sum0 = Object.values(w).reduce((a, b) => a + b, 0) || 1;
        Object.keys(w).forEach((k) => { w[k] = w[k] / sum0 * 100; });             // work in % of the mix
        w[inp.dataset.w] = Number(inp.value);
        st.w = w;
        const sum = Object.values(w).reduce((a, b) => a + b, 0) || 1;
        el.querySelectorAll('[data-wp]').forEach((x) => { x.textContent = Math.round((w[x.dataset.wp] || 0) / sum * 100) + '%'; });
        drawMix();
      });
    }

    render();
    return destroy;
  };
})();
