/* Portfolio: all the money in one mode, together — mix vs plan (with Moves), what it holds underneath, the mix in the
   backtest (computed here from each strategy's weekly backtest values), which strategies fall together, try a mix, and
   the real result so far. Nothing here trades: Move / Give open the usual Money dialog. */
(function () {
  const V = window.Views || (window.Views = {});
  const WK = 7 * 86400000;

  /* weekly values of one strategy for the window ('w' = last 10 years, 'm' = all of its history) */
  function ser(s, key) {
    const d0 = s[key + '0'], v = s[key + 'v'];
    if (!d0 || !v || !v.length) return null;
    const t0 = Date.parse(d0 + 'T00:00:00Z');
    return { t0, v };
  }

  /* each strategy's money grows on its own (never rebalanced), like the bot's sub-accounts */
  function combine(series, weights, key) {
    let ids = Object.keys(weights).filter((k) => weights[k] > 0 && series[k] && ser(series[k], key));
    const all = ids.reduce((a, k) => a + weights[k], 0);
    // a strategy with a much shorter backtest (the metals: about 2 years of 4H futures) would cut the whole mix to its
    // history; it is left out (and named) instead, and the rest is scaled to 100%
    const len = (k) => ser(series[k], key).v.length;
    const longest = Math.max(0, ...ids.map(len));
    const leftOut = ids.filter((k) => len(k) < 0.6 * longest).map((k) => ({ id: k, share: weights[k] / all, years: len(k) / 52.18 }));
    ids = ids.filter((k) => len(k) >= 0.6 * longest);
    const tot = ids.reduce((a, k) => a + weights[k], 0);
    if (!ids.length || tot <= 0) return null;
    const ss = ids.map((k) => ser(series[k], key));
    const start = Math.max(...ss.map((s) => s.t0));
    const end = Math.min(...ss.map((s) => s.t0 + (s.v.length - 1) * WK));
    const n = Math.round((end - start) / WK) + 1;
    if (n < 26) return null;
    const off = ss.map((s) => Math.round((start - s.t0) / WK));
    const vals = [], times = [];
    for (let i = 0; i < n; i++) {
      let x = 0;
      ids.forEach((k, j) => { const s = ss[j]; x += weights[k] / tot * s.v[off[j] + i] / s.v[off[j]]; });
      vals.push(x); times.push(Math.round((start + i * WK) / 1000));
    }
    return { ids, times, vals, leftOut, ...stats(times, vals) };
  }

  function stats(times, vals) {
    const n = vals.length, years = (times[n - 1] - times[0]) / (365.25 * 86400);
    let peak = vals[0], maxdd = 0, under = 0, longest = 0, ddAt = times[0];
    const dd = [];
    for (let i = 0; i < n; i++) {
      if (vals[i] >= peak) { peak = vals[i]; under = 0; } else { under++; longest = Math.max(longest, under); }
      const d = vals[i] / peak - 1;
      dd.push(d);
      if (d < maxdd) { maxdd = d; ddAt = times[i]; }
    }
    let worst12 = null;
    for (let i = 52; i < n; i++) { const r = vals[i] / vals[i - 52] - 1; if (worst12 == null || r < worst12) worst12 = r; }
    const cagr = Math.pow(vals[n - 1] / vals[0], 1 / Math.max(years, 0.1)) - 1;
    return { cagr, maxdd, ddAt, longestWeeks: longest, worst12, years, dd, from: times[0], to: times[n - 1],
      retdd: maxdd < 0 ? cagr * 100 / Math.abs(maxdd * 100) : null };
  }

  const P = (x, d) => x == null || isNaN(x) ? '—' : (x * 100).toFixed(d == null ? 1 : d) + '%';
  const yrs = (w) => w >= 104 ? (w / 52.18).toFixed(1) + ' years' : Math.round(w / 4.35) + ' months';
  const fall = (x) => x == null ? '—' : '−' + Math.abs(x * 100).toFixed(1) + '%';
  const dayOf = (t) => new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', month: 'short', year: 'numeric' }).format(new Date(t * 1000));

  V.portfolio = async function (el) {
    const mode = U.mode();
    const d = await U.api('/api/portfolio?mode=' + mode);
    const series = d.series || {};
    const rows = d.rows || [];
    const now = {};
    rows.forEach((r) => { if (r.value > 0.5) now[r.id] = r.value; });
    const allIds = Object.keys(series).sort((a, b) => (now[b] || 0) - (now[a] || 0) || series[a].name.localeCompare(series[b].name));
    const tryW = {};
    const nowTot = Object.values(now).reduce((a, b) => a + b, 0);
    allIds.forEach((k) => { tryW[k] = nowTot > 0 ? Math.round((now[k] || 0) / nowTot * 1000) / 10 : 0; });
    let win = 'w', charts = [];

    function kill() { charts.forEach((c) => { try { c.remove(); } catch (e) {} }); charts = []; }

    function mixTable() {
      if (!rows.length) return '<div class="empty">No money in any strategy in this mode yet.</div>';
      const plan = !!d.plan;
      return `<div class="tw"><table class="t"><thead><tr><th>Strategy</th><th class="r">Value</th><th style="min-width:160px">Share now</th>
        ${plan ? '<th class="r">Plan</th><th class="r">To plan</th>' : ''}<th class="r">P&amp;L</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td><a class="row" style="gap:8px" href="#/strategies/${U.esc(r.id)}">${U.dot(r.color)}${U.esc(r.name)}</a>
            ${r.control !== 'active' ? ' ' + U.pill('warn', r.control) : ''}${r.running ? ' ' + U.pill('info', 'plan running') : ''}</td>
          <td class="r num">${U.usd(r.value, 0)}</td>
          <td><div class="row" style="gap:8px"><div style="flex:1;height:8px;border-radius:4px;background:var(--panel2);position:relative;overflow:hidden">
            <div style="position:absolute;left:0;top:0;bottom:0;width:${Math.min(100, r.now_pct)}%;background:${U.esc(r.color)}"></div>
            ${plan && r.plan_pct ? `<div title="plan ${r.plan_pct}%" style="position:absolute;top:-2px;bottom:-2px;left:calc(${Math.min(100, r.plan_pct)}% - 1px);width:2px;background:var(--text)"></div>` : ''}</div>
            <span class="num small" style="width:44px;text-align:right">${r.now_pct.toFixed(1)}%</span></div></td>
          ${plan ? `<td class="r num">${r.plan_pct ? r.plan_pct + '%' : '—'}</td><td class="r num ${Math.abs(r.gap) < 50 ? 'muted' : r.gap > 0 ? 'up' : 'dn'}">${Math.abs(r.gap) < 50 ? 'on plan' : U.sgnUsd(r.gap, 0)}</td>` : ''}
          <td class="r num ${U.cls(r.pnl)}">${U.sgnUsd(r.pnl, 0)}</td></tr>`).join('')}
        </tbody></table></div>`;
    }

    function movesHtml() {
      if (!d.plan) return `<div class="note info small" style="margin:0">No ratio planned yet. Set one in <b>Try a mix</b> below (or Dashboard → Expected return → ratio planner) and press <b>Save as my plan</b>; this table then shows the gaps and the moves that close them.</div>`;
      if (!d.moves.length) return `<div class="note ok small" style="margin:0">Every strategy is within $50 of your plan${d.plan.saved_at ? ' (saved ' + U.day(d.plan.saved_at) + ')' : ''}.</div>`;
      const nm = (id) => { const r = rows.find((x) => x.id === id); return r ? r.name : id; };
      return `<div class="col" style="gap:8px"><div class="small muted">Moves that bring the mix back to your plan (plan = ${U.usd(d.total + d.unassigned, 0)} × ratio). Nothing moves until you press a button; moving out of a strategy that holds shares sells some of them.</div>
        ${d.moves.map((m, i) => `<div class="row sb" style="gap:10px;padding:8px 12px;border:1px solid var(--line2);border-radius:10px;flex-wrap:wrap">
          <span>${m.kind === 'give' ? `Give <b>${U.usd(m.amount, 0)}</b> from bot unassigned to <b>${U.esc(nm(m.to))}</b>` : `Move <b>${U.usd(m.amount, 0)}</b> from <b>${U.esc(nm(m.from))}</b> to <b>${U.esc(nm(m.to))}</b>`}</span>
          <button class="btn s" data-mv="${i}">${m.kind === 'give' ? 'Give…' : 'Move…'}</button></div>`).join('')}</div>`;
    }

    function exposureHtml() {
      const ex = d.exposure || [];
      if (!ex.length) return '';
      return `<section class="card col" style="gap:12px"><div><h2 class="h2">What the money holds</h2>
        <div class="muted small">By market, across all strategies (two strategies holding USD both count as semiconductors 2x).</div></div>
        <div style="display:flex;height:16px;border-radius:8px;overflow:hidden;gap:2px">${ex.map((m) => `<div title="${U.esc(m.market)} ${m.pct.toFixed(1)}%" style="flex:${Math.max(m.pct, 0.3)};background:${U.esc(m.color)}"></div>`).join('')}</div>
        <div class="grid" style="--min:200px;gap:6px 18px">${ex.map((m) => `<div class="row sb"><span class="row" style="gap:8px">${U.dot(m.color)}${U.esc(m.market)}</span><span class="num">${U.usd(m.usd, 0)} · ${m.pct.toFixed(1)}%</span></div>`).join('')}</div></section>`;
    }

    function statCards(a, b) {
      const one = (label, x, y, f, better) => {
        const diff = y == null || x == null ? '' : (better(y, x) ? 'up' : better(x, y) ? 'dn' : '');
        return `<div class="card" style="padding:12px 14px;background:var(--panel2)"><div class="muted small">${label}</div>
          <div class="num" style="font-size:20px;font-weight:600">${f(x)}</div>${b ? `<div class="num small ${diff}">try: ${f(y)}</div>` : ''}</div>`;
      };
      const hi = (p, q) => p > q + 1e-9, lo = (p, q) => p < q - 1e-9;
      return `<div class="grid" style="--min:150px;gap:10px">
        ${one('A year', a.cagr, b && b.cagr, (x) => P(x), hi)}
        ${one('Worst fall', a.maxdd, b && b.maxdd, fall, (p, q) => p > q + 1e-9)}
        ${one('Longest under water', a.longestWeeks, b && b.longestWeeks, (x) => x == null ? '—' : yrs(x), lo)}
        ${one('Worst 12 months', a.worst12, b && b.worst12, (x) => P(x), hi)}
        ${one('Return ÷ fall', a.retdd, b && b.retdd, (x) => x == null ? '—' : x.toFixed(2), hi)}</div>`;
    }

    function btHtml() {
      return `<section class="card col" style="gap:12px" id="bt">
        <div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">Your mix in the backtest</h2>
          <div class="muted small">Today's split, each strategy's money growing on its own (as in the bot), from each strategy's backtest at the real fee. A history, not a promise.</div></div>
          <div class="seg" id="win"><button data-w="w" class="${win === 'w' ? 'on' : ''}">10 years</button><button data-w="m" class="${win === 'm' ? 'on' : ''}" ${d.check_full ? '' : 'disabled title="Filled in by the next expected-returns check"'}>All years</button></div></div>
        <div id="btbody"></div></section>`;
    }

    function drawBt() {
      kill();
      const host = el.querySelector('#btbody');
      const a = combine(series, now, win);
      const tryOn = allIds.some((k) => Math.abs((tryW[k] || 0) - (nowTot > 0 ? (now[k] || 0) / nowTot * 100 : 0)) > 0.05);
      const b = tryOn ? combine(series, tryW, win) : null;
      if (!a) { host.innerHTML = `<div class="empty small">${Object.keys(series).length ? 'Not enough shared backtest history for this split.' : 'The expected-returns check has not run yet (Dashboard → Expected return → Check now).'}</div>`; return; }
      const lo = a.leftOut.length ? `<div class="note info small" style="margin:0">Left out because their backtest is much shorter: ${a.leftOut.map((x) => `${U.esc(series[x.id].name)} (${x.years.toFixed(1)} years)`).join(', ')} — ${(a.leftOut.reduce((t, x) => t + x.share, 0) * 100).toFixed(0)}% of the money. The rest is scaled to 100%.</div>` : '';
      host.innerHTML = `<div class="muted small">${dayOf(a.from)} – ${dayOf(a.to)} · ${a.years.toFixed(1)} years, the weeks every strategy in the split has a backtest${b && b.from !== a.from ? ` (try: from ${dayOf(b.from)})` : ''}.</div>${lo}
        ${statCards(a, b)}
        <div style="height:280px;position:relative" id="btc"></div><div style="height:110px" id="btd"></div>
        <div class="row small muted" style="gap:14px"><span class="row" style="gap:6px"><i style="width:14px;height:3px;background:var(--accent);display:inline-block"></i>Your split now</span>${b ? '<span class="row" style="gap:6px"><i style="width:14px;height:0;border-top:2px dashed #E0B04B;display:inline-block"></i>Try a mix</span>' : ''}<span>Growth of $100 · bottom: fall from the high</span></div>
        ${aloneTable(a)}`;
      const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
      const ch = Charts.base(host.querySelector('#btc'), { daily: true, timeVisible: false });
      const sa = ch.addLineSeries({ color: css('--accent'), lineWidth: 2, priceLineVisible: false });
      sa.setData(a.times.map((t, i) => ({ time: t, value: a.vals[i] * 100 })));
      if (b) {
        const sb = ch.addLineSeries({ color: '#E0B04B', lineWidth: 2, lineStyle: 2, priceLineVisible: false });
        const k0 = b.times.findIndex((t) => t >= a.from);
        const base = a.vals[a.times.indexOf(b.times[Math.max(k0, 0)])] || 1;
        sb.setData(b.times.map((t, i) => ({ time: t, value: b.vals[i] / b.vals[Math.max(k0, 0)] * base * 100 })).filter((p) => p.time >= a.from));
      }
      ch.timeScale().fitContent();
      const dc = Charts.base(host.querySelector('#btd'), { daily: true, timeVisible: true, noLogo: true });
      const ds = dc.addAreaSeries({ lineColor: '#EF5350', topColor: '#EF535010', bottomColor: '#EF535055', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, invertFilledArea: true });
      ds.setData(a.times.map((t, i) => ({ time: t, value: a.dd[i] * 100 })));
      dc.timeScale().fitContent();
      charts.push(ch, dc);
    }

    function aloneTable(a) {
      const per = a.ids.map((k) => {
        return { k, s: series[k], one: combine(series, { [k]: 1 }, win) };
      });
      return `<details><summary class="small" style="cursor:pointer">Each strategy alone over its own history (${win === 'w' ? '10 years' : 'all years'})</summary>
        <div class="tw" style="margin-top:8px"><table class="t"><thead><tr><th>Strategy</th><th class="r">Share</th><th class="r">A year</th><th class="r">Worst fall</th><th class="r">Longest under water</th></tr></thead><tbody>
        ${per.map((x) => `<tr><td><span class="row" style="gap:8px">${U.dot(x.s.color)}${U.esc(x.s.name)}</span></td><td class="r num">${nowTot > 0 ? ((now[x.k] || 0) / nowTot * 100).toFixed(1) + '%' : '—'}</td>
          <td class="r num">${x.one ? P(x.one.cagr) : '—'}</td><td class="r num">${x.one ? fall(x.one.maxdd) : '—'}</td><td class="r num">${x.one ? yrs(x.one.longestWeeks) : '—'}</td></tr>`).join('')}
        <tr><td><b>Your split together</b></td><td class="r num">100%</td><td class="r num"><b>${P(a.cagr)}</b></td><td class="r num"><b>${fall(a.maxdd)}</b></td><td class="r num"><b>${yrs(a.longestWeeks)}</b></td></tr>
        </tbody></table></div></details>`;
    }

    function corrHtml() {
      const c = d.corr || {};
      const set = allIds.filter((k) => (now[k] || 0) > 0 || (tryW[k] || 0) > 0).filter((k) => (c.ids || []).includes(k));
      if (set.length < 2) return '';
      const at = (a, b) => c.m[c.ids.indexOf(a)][c.ids.indexOf(b)];
      const pairs = [];
      set.forEach((a, i) => set.slice(i + 1).forEach((b) => pairs.push([a, b, at(a, b)])));
      pairs.sort((x, y) => y[2] - x[2]);
      const nm = (k) => series[k].name;
      const cell = (v) => { const a = Math.max(0, Math.min(1, v)); return `background:rgba(239,83,80,${(a * 0.55).toFixed(2)})`; };
      return `<section class="card col" style="gap:12px"><div><h2 class="h2">Which strategies fall together</h2>
        <div class="muted small">Correlation of weekly backtest returns (10 years). 1 = they move together (they fall together too); 0 = unrelated. Mixing low numbers lowers the combined worst fall.</div></div>
        <div class="small">${pairs.length ? `Most together: <b>${U.esc(nm(pairs[0][0]))}</b> + <b>${U.esc(nm(pairs[0][1]))}</b> (${pairs[0][2].toFixed(2)}). Least: <b>${U.esc(nm(pairs[pairs.length - 1][0]))}</b> + <b>${U.esc(nm(pairs[pairs.length - 1][1]))}</b> (${pairs[pairs.length - 1][2].toFixed(2)}).` : ''}</div>
        <div class="tw"><table class="t" style="width:auto"><thead><tr><th></th>${set.map((k) => `<th class="r" title="${U.esc(nm(k))}">${U.dot(series[k].color)}</th>`).join('')}</tr></thead><tbody>
          ${set.map((a) => `<tr><td class="small"><span class="row" style="gap:6px">${U.dot(series[a].color)}${U.esc(nm(a))}</span></td>${set.map((b) => `<td class="r num small" style="${a === b ? '' : cell(at(a, b))}">${a === b ? '—' : at(a, b).toFixed(2)}</td>`).join('')}</tr>`).join('')}
        </tbody></table></div></section>`;
    }

    function tryHtml() {
      const sum = allIds.reduce((a, k) => a + (+tryW[k] || 0), 0);
      return `<section class="card col" style="gap:12px"><div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">Try a mix</h2>
          <div class="muted small">Change the percentages: the backtest above compares your split now (solid) with this one (dashed). Nothing moves.</div></div>
          <div class="row" style="gap:8px"><button class="btn s" id="tnow">Reset to now</button>${d.plan ? '<button class="btn s" id="tplan">Load my plan</button>' : ''}<button class="btn s p" id="tsave">Save as my plan</button></div></div>
        <div class="grid" style="--min:250px;gap:8px 18px">${allIds.map((k) => `<label class="row sb" style="gap:8px"><span class="row small" style="gap:8px;min-width:0">${U.dot(series[k].color)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(series[k].name)}</span></span>
          <span class="row" style="gap:4px"><input class="in num" data-tw="${k}" value="${tryW[k] || 0}" inputmode="decimal" style="width:76px;height:34px;text-align:right">%</span></label>`).join('')}</div>
        <div class="small ${Math.abs(sum - 100) > 0.5 ? 'dn' : 'muted'}" id="tsum">Total ${sum.toFixed(1)}%${Math.abs(sum - 100) > 0.5 ? ' — the backtest scales it to 100%; a saved plan keeps the rest as bot unassigned' : ''}</div></section>`;
    }

    function realHtml() {
      const r = d.real;
      if (!r) return '';
      return `<section class="card col" style="gap:10px"><div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">Real result so far</h2>
        <div class="muted small">All strategies in ${U.esc(U.modeLabel[mode])} since ${U.esc(r.from)}, time-weighted: money you add or take out is not counted as gain or loss.</div></div>
        <div class="row" style="gap:18px"><div><div class="muted small">Return</div><div class="num ${U.cls(r.ret)}" style="font-size:20px;font-weight:600">${U.pct(r.ret)}</div></div>
          <div><div class="muted small">Worst fall so far</div><div class="num" style="font-size:20px;font-weight:600">${fall(r.worst)}</div></div>
          <div><div class="muted small">Below its high now</div><div class="num" style="font-size:20px;font-weight:600">${fall(r.now_dd)}</div></div></div></div>
        ${r.days.length >= 5 ? '<div style="height:180px" id="realc"></div>' : '<div class="muted small">The chart fills in after a few trading days.</div>'}</section>`;
    }

    function drawReal() {
      const host = el.querySelector('#realc');
      if (!host || !d.real) return;
      const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
      const ch = Charts.base(host, { daily: true, timeVisible: true, noLogo: true });
      const s = ch.addAreaSeries({ lineColor: css('--accent'), topColor: css('--accent') + '30', bottomColor: css('--accent') + '00', lineWidth: 2, priceLineVisible: false });
      s.setData(d.real.days.map((x, i) => ({ time: Math.round(Date.parse(x + 'T00:00:00Z') / 1000), value: d.real.idx[i] * 100 })));
      ch.timeScale().fitContent();
      charts.push(ch);
    }

    const sg = (x) => x == null ? '—' : (x >= 0 ? '+' : '−') + U.usd(Math.abs(x));
    const neg = (cost) => cost == null || Math.abs(cost) < 0.005 ? '' : cost > 0 ? 'dn' : 'up';   // a cost is red, a saving green
    const pp = (x, dp) => x == null ? '—' : (x >= 0 ? '+' : '−') + Math.abs(x * 100).toFixed(dp == null ? 2 : dp) + '%';

    function weeklyHtml(w) {
      const r = (w.reports || [])[0], c = w.costs || {};
      const rep = r ? `<div class="col" style="gap:8px"><div class="row sb" style="flex-wrap:wrap;gap:8px"><b>Week ${U.esc(r.from)} – ${U.esc(r.to)}</b>
          <span class="muted small">made ${U.dt(r.at)} · strategies ${U.usd(r.value, 0)} · week ${pp(r.ret, 1)}${r.usd != null ? ' (' + sg(r.usd) + ')' : ''}</span></div>
        <div class="tw"><table class="t"><thead><tr><th>Strategy</th><th class="r">Real</th><th class="r">Backtest</th><th class="r">Gap</th><th class="r">$</th></tr></thead><tbody>
        ${(r.strategies || []).map((x) => `<tr><td><span class="row" style="gap:8px">${U.dot(x.color)}${U.esc(x.name)}</span></td><td class="r num ${U.cls(x.real)}">${pp(x.real, 1)}</td>
          <td class="r num">${pp(x.backtest, 1)}</td><td class="r num ${x.gap == null ? '' : Math.abs(x.gap) < 0.01 ? 'muted' : x.gap > 0 ? 'up' : 'dn'}">${x.gap == null ? '—' : (x.gap * 100 >= 0 ? '+' : '−') + Math.abs(x.gap * 100).toFixed(1) + ' pts'}</td>
          <td class="r num ${U.cls(x.usd)}">${sg(x.usd)}</td></tr>`).join('')}</tbody></table></div>
        ${(w.reports || []).length > 1 ? `<details><summary class="small" style="cursor:pointer">Earlier weeks (${w.reports.length - 1})</summary>${w.reports.slice(1).map((x) => `<pre class="small" style="white-space:pre-wrap;margin:8px 0 0">${U.esc(x.text || '')}</pre>`).join('')}</details>` : ''}</div>`
        : '<div class="muted small">The first report arrives on LINE on Saturday morning (after Friday\'s US close). Press <b>Make this week\'s report</b> to see it now.</div>';
      return `<div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">Weekly report and trading costs</h2>
          <div class="muted small">Every Saturday on LINE: each strategy's real week next to its backtest over the same days, fees, and what trading really cost.</div></div>
          <div class="row" style="gap:8px"><button class="btn s" data-wk="0">Make this week's report</button><button class="btn s" data-wk="1">Send it to LINE</button></div></div>
        ${rep}
        <div class="grid" style="--min:170px;gap:10px">
          <div class="card" style="padding:12px 14px;background:var(--panel2)"><div class="muted small">Traded since ${U.esc(w.since || '—')}</div><div class="num" style="font-size:20px;font-weight:600">${U.usd(c.traded || 0, 0)}</div><div class="muted small">${c.fills || 0} fills</div></div>
          <div class="card" style="padding:12px 14px;background:var(--panel2)"><div class="muted small">Fees</div><div class="num" style="font-size:20px;font-weight:600">${U.usd(c.fees || 0)}</div><div class="muted small">${c.fee_pct != null ? (c.fee_pct * 100).toFixed(3) + '% of traded' : '—'}</div></div>
          <div class="card" style="padding:12px 14px;background:var(--panel2)"><div class="muted small">Fills vs the day's open</div><div class="num ${neg(c.cost)}" style="font-size:20px;font-weight:600">${sg(c.cost == null ? null : -c.cost)}</div><div class="muted small">${pp(c.cost_pct == null ? null : -c.cost_pct)} · − = cost, + = better than the open</div></div></div>
        ${(w.by_strategy || []).length ? `<div class="tw"><table class="t"><thead><tr><th>Strategy</th><th class="r">Fills</th><th class="r">Traded</th><th class="r">Fees</th><th class="r">vs the open</th></tr></thead><tbody>
          ${w.by_strategy.map((x) => `<tr><td>${U.esc(x.name)}</td><td class="r num">${x.fills}</td><td class="r num">${U.usd(x.traded, 0)}</td><td class="r num">${U.usd(x.fees)}</td><td class="r num ${neg(x.cost)}">${sg(x.cost == null ? null : -x.cost)} · ${pp(x.cost_pct == null ? null : -x.cost_pct)}</td></tr>`).join('')}</tbody></table></div>` : ''}
        ${(w.fills || []).length ? `<details><summary class="small" style="cursor:pointer">Latest fills vs the open (${w.fills.length})</summary><div class="tw" style="margin-top:8px"><table class="t"><thead><tr><th>Day</th><th>Strategy</th><th>Fill</th><th class="r">Price</th><th class="r">Open</th><th class="r">Cost</th></tr></thead><tbody>
          ${w.fills.map((f) => `<tr><td class="num small">${U.esc(f.day)}</td><td class="small">${U.esc((rows.find((x) => x.id === f.strategy) || {}).name || f.strategy)}</td><td class="small">${f.side === 'BUY' ? 'Buy' : 'Sell'} ${U.qty(f.qty)} ${U.esc(f.symbol)}</td>
            <td class="r num">${U.usd(f.avg)}</td><td class="r num">${f.open ? U.usd(f.open) : '—'}</td><td class="r num ${neg(f.cost)}">${f.cost == null ? '—' : sg(-f.cost) + ' · ' + pp(-f.cost_pct)}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
        <div class="muted small">The daily backtests buy and sell at the day's open, so "vs the open" is what Live gains or pays compared with the backtest: red (−) = a cost (spread, limit offset, timing, retries), green (+) = a better price than the open. The 4H metals strategies trade at other times: their numbers are a rough guide.</div>`;
    }

    async function loadWeekly() {
      const box = el.querySelector('#weekly');
      if (!box) return;
      try {
        const w = await U.api('/api/weekly?mode=' + mode);
        box.innerHTML = weeklyHtml(w);
        U.on(box, '[data-wk]', 'click', (e, b) => U.busy(b, async () => {
          const line = b.dataset.wk === '1';
          if (line && !(await U.confirm('Send to LINE?', 'This week so far (Monday to today) goes to LINE now. The Saturday report still comes as usual.', { ok: 'Send' }))) return;
          await U.api('/api/weekly/send', { body: { mode, line } });
          U.toast(line ? 'Sent to LINE' : 'Report made'); loadWeekly();
        }));
      } catch (e) { box.innerHTML = `<div class="note err small">${U.esc(e.message || e)}</div>`; }
    }

    function render() {
      kill();
      const a = combine(series, now, 'w');
      const top = (d.exposure || [])[0];
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">${U.esc(U.modeLabel[mode])} account · all strategies together</div><h1 class="h1">Portfolio</h1>
          <div class="muted" style="margin-top:4px">Your mix now, what it holds underneath, how it did in the backtest, and how it compares with your plan.</div></div>
          <a class="btn" href="#/money">Money</a></div>
        <div class="grid" style="--min:200px">
          <div class="card"><div class="eyebrow">In strategies</div><div class="num big" style="margin-top:6px">${U.usd(d.total, 0)}</div><div class="muted small num">+ ${U.usd(d.unassigned, 0)} bot unassigned</div></div>
          <div class="card"><div class="eyebrow">Real result</div><div class="num big ${d.real ? U.cls(d.real.ret) : ''}" style="margin-top:6px">${d.real ? U.pct(d.real.ret) : '—'}</div><div class="muted small">${d.real ? 'since ' + U.esc(d.real.from) + ' · worst fall ' + fall(d.real.worst) : 'after the first recorded day'}</div></div>
          <div class="card"><div class="eyebrow">Your split · 10-year backtest</div><div class="num big" style="margin-top:6px">${a ? P(a.cagr) + ' a year' : '—'}</div><div class="muted small">${a ? 'worst fall ' + fall(a.maxdd) + ' · under water up to ' + yrs(a.longestWeeks) : 'needs the expected-returns check'}</div></div>
          <div class="card"><div class="eyebrow">Biggest market</div><div class="num big" style="margin-top:6px">${top ? top.pct.toFixed(0) + '%' : '—'}</div><div class="muted small">${top ? U.esc(top.market) : ''}</div></div></div>
        <section class="card col" style="gap:12px"><div><h2 class="h2">Mix now${d.plan ? ' vs your plan' : ''}</h2></div>${mixTable()}${movesHtml()}</section>
        ${exposureHtml()}
        ${btHtml()}
        ${tryHtml()}
        ${corrHtml()}
        ${realHtml()}
        <section class="card col" style="gap:12px" id="weekly"><div class="empty small"><span class="spin"></span></div></section>`;
      drawBt();
      drawReal();
      loadWeekly();
      U.on(el, '#win button', 'click', (e, b) => { if (b.disabled) return; win = b.dataset.w; el.querySelectorAll('#win button').forEach((x) => x.classList.toggle('on', x === b)); drawBt(); });
      U.on(el, '[data-mv]', 'click', (e, b) => {
        const m = d.moves[+b.dataset.mv];
        if (m.kind === 'give') V.moneyDialog('add', m.to, () => V.portfolio(el), { amount: m.amount });
        else V.moneyDialog('move', m.from, () => V.portfolio(el), { to: m.to, amount: m.amount });
      });
      el.querySelectorAll('[data-tw]').forEach((inp) => inp.addEventListener('input', () => {
        tryW[inp.dataset.tw] = Math.max(0, parseFloat(inp.value) || 0);
        const sum = allIds.reduce((x, k) => x + (+tryW[k] || 0), 0);
        const t = el.querySelector('#tsum');
        t.className = 'small ' + (Math.abs(sum - 100) > 0.5 ? 'dn' : 'muted');
        t.textContent = `Total ${sum.toFixed(1)}%` + (Math.abs(sum - 100) > 0.5 ? ' — the backtest scales it to 100%; a saved plan keeps the rest as bot unassigned' : '');
        clearTimeout(inp._t); inp._t = setTimeout(drawBt, 250);
      }));
      const setTry = (src) => { allIds.forEach((k) => { tryW[k] = src(k); }); render(); };
      el.querySelector('#tnow').onclick = () => setTry((k) => nowTot > 0 ? Math.round((now[k] || 0) / nowTot * 1000) / 10 : 0);
      if (el.querySelector('#tplan')) el.querySelector('#tplan').onclick = () => setTry((k) => d.plan.pct[k] || 0);
      el.querySelector('#tsave').onclick = (e) => U.busy(e.target, async () => {
        const pct = {};
        allIds.forEach((k) => { if (tryW[k] > 0) pct[k] = tryW[k]; });
        if (!(await U.confirm('Save as my plan?', `The ratio planner and this page will use these percentages as your plan (of ${U.usd(d.total + d.unassigned, 0)}). Nothing is bought or sold.`, { ok: 'Save plan' }))) return;
        await U.api('/api/expected/plan', { body: { pct, total: d.total + d.unassigned } });
        U.toast('Plan saved'); V.portfolio(el);
      });
    }

    render();
    return { cleanup: kill };
  };
})();
