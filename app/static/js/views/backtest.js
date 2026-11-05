/* Strategy page → Backtest tab: the strategy's own code run over past prices (app/backtest.py). */
(function () {
  const V = window.Views || (window.Views = {});
  const RL = { '1Y': '1 year', '3Y': '3 years', '5Y': '5 years', '10Y': '10 years', MAX: 'All' };
  const P = (v, dp) => v == null || isNaN(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 1 : dp) + '%';
  const PP = (v, dp) => v == null || isNaN(v) ? '—' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(dp == null ? 1 : dp) + '%';
  const tOf = (s) => Math.floor(Date.parse(s + 'T00:00:00Z') / 1000);
  const dayTxt = (s) => s ? new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(tOf(s) * 1000)) : '—';
  const BENCH_COL = ['#8592A3', '#E46AA8'];

  V.backtestTab = function (host, sid, d) {
    const c = d.card;
    const st = { data: null, range: null, log: true, show: {}, custom: null, charts: [], allTrades: false, size: 'C', extra: null, stress: null };
    const rules = d.type.params.filter((p) => p.group === 'Rules' || p.group === 'Weights');

    function destroyCharts() { st.charts.forEach((x) => { try { x.remove(); } catch (e) {} }); st.charts = []; }

    async function load(params) {
      destroyCharts();
      host.innerHTML = `<section class="card col" style="gap:10px;align-items:center;padding:40px 20px"><span class="spin"></span>
        <div class="muted small" style="text-align:center;max-width:460px">Running ${U.esc(c.name)} over past prices with the same code that trades.
        The first run downloads the price history and can take up to a minute.</div></section>`;
      try {
        st.data = params ? await U.api(`/api/backtest/${sid}`, { body: { params } }) : await U.api(`/api/backtest/${sid}`);
        st.custom = params || null;
      } catch (e) {
        host.innerHTML = `<div class="note err">${U.esc(e.message)}</div>`;
        return;
      }
      const r = st.data;
      if (r.ok) {
        if (!st.range || !r.ranges.includes(st.range)) st.range = r.ranges.includes('10Y') ? '10Y' : 'MAX';
        Object.keys(r.series.bench).forEach((k, i) => { if (st.show[k] == null) st.show[k] = i === 0; });
      }
      render();
    }

    function win() {
      const r = st.data, s = r.series;
      const from = r.stats[st.range].strategy.from;
      const t0 = tOf(from);
      let i0 = s.t.findIndex((t) => t >= t0);
      if (i0 < 0) i0 = 0;
      return i0;
    }

    /* "Fixed $10,000" (like trading 1 contract): the position stays $10,000, profit is taken out each day (a loss topped up) */
    function fixedOf(arr, i0) {
      const out = [];
      let acc = 10000, prev = null;
      for (let j = i0; j < arr.length; j++) {
        const v = arr[j];
        if (v != null && prev != null && prev > 0) acc += 10000 * (v / prev - 1);
        out.push(v == null ? null : acc);
        if (v != null) prev = v;
      }
      return out;
    }

    function tiles(S, B) {
      const main = st.data.vs || st.data.main, idx = st.data.index !== main ? st.data.index : null;
      const bm = B[main], bi = idx ? B[idx] : null;
      const tile = (k, v, sub, cls) => `<div class="card" style="padding:14px 16px"><div class="eyebrow">${k}</div>
        <div class="num big ${cls || ''}" style="margin-top:6px">${v}</div><div class="muted small" style="margin-top:2px">${sub}</div></div>`;
      return `<div class="grid" style="--min:150px;gap:12px">
        ${tile('A year (CAGR)', P(S.cagr), `${U.esc(main)} held ${P(bm && bm.cagr)}${bi ? ' · ' + U.esc(idx) + ' ' + P(bi.cagr) : ''}`, S.cagr > 0 ? 'up' : 'dn')}
        ${tile('Worst fall', PP(S.maxdd), `${U.esc(main)} held ${PP(bm && bm.maxdd)} · ${dayTxt(S.dd_peak)} → ${dayTxt(S.dd_trough)}`, 'dn')}
        ${tile('$10,000 became', U.usd(S.end_value, 0), `profit reinvested · ${P(S.total, 0)} in ${S.years.toFixed(1)} years`)}
        ${(() => { const f = fixedOf(st.data.series.strategy, win()); const end = f[f.length - 1] || 10000; return tile('Fixed $10,000', U.sgnUsd(end - 10000, 0), `profit taken out · ${U.sgnUsd((end - 10000) / Math.max(S.years, 0.1), 0)} a year`, end >= 10000 ? 'up' : 'dn'); })()}
        ${tile('Sharpe', S.sharpe == null ? '—' : S.sharpe.toFixed(2), `${U.esc(main)} held ${bm && bm.sharpe != null ? bm.sharpe.toFixed(2) : '—'} · above T-bills`)}
        ${tile('In the market', PP(S.exposure, 0), `of the days in ${U.esc(st.data.main)}`)}
        ${tile('Trades', S.trades, `${S.per_year} a year${S.win_rate != null ? ` · ${PP(S.win_rate, 0)} of round trips won` : ''}`)}</div>`;
    }

    function compareTable(R) {
      const cols = ['strategy'].concat(Object.keys(st.data.series.bench).filter((k) => R[k]));
      const name = (k) => k === 'strategy' ? U.esc(c.name) : U.esc(k) + ' held';
      const rows = [['A year (CAGR)', (x) => P(x.cagr)], ['Total return', (x) => P(x.total, 0)], ['$10,000 became', (x) => U.usd(x.end_value, 0)],
        ['Worst fall', (x) => PP(x.maxdd)], ['Worst fall dates', (x) => `${dayTxt(x.dd_peak)} → ${dayTxt(x.dd_trough)}`],
        ['Back at the old high', (x) => x.dd_recovered ? dayTxt(x.dd_recovered) : (x.maxdd < 0 ? 'not yet' : '—')],
        ['Volatility (a year)', (x) => PP(x.vol)], ['Sharpe (above T-bills)', (x) => x.sharpe == null ? '—' : x.sharpe.toFixed(2)]];
      return `<div class="tw"><table class="t"><thead><tr><th></th>${cols.map((k) => `<th class="r">${name(k)}</th>`).join('')}</tr></thead><tbody>
        ${rows.map(([lab, f]) => `<tr><td class="muted">${lab}</td>${cols.map((k) => `<td class="r num">${f(R[k])}</td>`).join('')}</tr>`).join('')}
        <tr><td class="muted">Trades · round trips won</td><td class="r num">${R.strategy.trades} · ${R.strategy.win_rate == null ? '—' : PP(R.strategy.win_rate, 0)}</td>${cols.slice(1).map(() => '<td class="r muted">1 buy</td>').join('')}</tr>
        </tbody></table></div>`;
    }

    function research() {
      const rs = st.data.research;
      if (!rs) return '';
      const m = st.data.stats.MAX.strategy;
      const bits = [];
      if (rs.cagr != null) bits.push(`<b>${P(rs.cagr)}</b> a year`);
      if (rs.maxdd != null) bits.push(`worst fall <b>${PP(rs.maxdd)}</b>`);
      if (rs.sharpe != null) bits.push(`Sharpe <b>${rs.sharpe.toFixed(2)}</b>`);
      return `<section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">Compared with the research</h2>
        ${rs.same_settings ? U.pill('ok', 'same settings as the research') : U.pill('warn', 'your settings differ from the research')}</div>
        <div class="grid" style="--min:260px;gap:12px">
          <div class="card" style="padding:12px 14px;background:var(--panel2)"><div class="eyebrow">Research · ${U.esc(rs.period)}</div>
            <div style="margin-top:6px">${bits.join(' · ') || '—'}</div><div class="muted small" style="margin-top:4px">${U.esc(rs.source)}${rs.bench ? ' · ' + U.esc(rs.bench) : ''}</div></div>
          <div class="card" style="padding:12px 14px;background:var(--panel2)"><div class="eyebrow">This backtest · ${dayTxt(m.from)} – ${dayTxt(m.to)}</div>
            <div style="margin-top:6px"><b>${P(m.cagr)}</b> a year · worst fall <b>${PP(m.maxdd)}</b> · Sharpe <b>${m.sharpe == null ? '—' : m.sharpe.toFixed(2)}</b></div>
            <div class="muted small" style="margin-top:4px">${U.esc(st.data.data.note)}</div></div></div>
        <div class="muted small">Different periods and price data give different numbers; what matters is that the shape agrees (beats or protects against simply holding, similar worst falls).
        ${st.data.family === 'signal' ? ' Yahoo keeps only about 2 years of hourly futures prices, so this backtest is much shorter than the research.' : ''}</div></section>`;
    }

    function yearsTable() {
      const ys = st.data.years.slice().reverse();
      const cols = ['strategy'].concat(Object.keys(st.data.series.bench));
      const cell = (v, best) => {
        if (v == null) return '<td class="r muted">—</td>';
        const a = Math.min(1, Math.abs(v) / 60);
        const bg = v >= 0 ? `color-mix(in srgb, var(--up) ${Math.round(a * 28)}%, transparent)` : `color-mix(in srgb, var(--dn) ${Math.round(a * 28)}%, transparent)`;
        return `<td class="r num" style="background:${bg};${best ? 'font-weight:600' : ''}">${P(v)}</td>`;
      };
      return `<section class="card col" style="gap:8px"><h2 class="h2">Year by year</h2>
        <div class="tw"><table class="t"><thead><tr><th>Year</th>${cols.map((k) => `<th class="r">${k === 'strategy' ? 'Strategy' : U.esc(k) + ' held'}</th>`).join('')}</tr></thead><tbody>
        ${ys.map((y) => `<tr><td class="num">${y.year}${y.partial ? ' <span class="muted small">part</span>' : ''}</td>${cols.map((k) => cell(y[k], k === 'strategy' && cols.every((o) => y[o] == null || y[k] >= y[o]))).join('')}</tr>`).join('')}
        </tbody></table></div></section>`;
    }

    function tradesTable(i0) {
      const r = st.data, t0 = r.series.t[i0];
      let tr = r.trades.filter((x) => x.t >= t0).reverse();
      const n = tr.filter((x) => x.kind !== 'START').length, full = tr.length;
      if (!st.allTrades) tr = tr.slice(0, 25);
      const pos = (o) => Object.entries(o).sort((a, b) => b[1] - a[1]).map(([s, w]) => `${(w * 100).toFixed(0)}% ${s}`).join(' + ') || 'cash';
      const kind = { BUY: ['ok', 'Buy'], SELL: ['err', 'Sell'], REBALANCE: ['info', 'Rebalance'], START: ['', 'Start'], LIST: ['info', 'List change'] };
      const px = r.main !== 'stocks';
      return `<section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">Trades in this period (${n})</h2>
        ${full > 25 ? `<button class="btn s" id="bt-all">${st.allTrades ? 'Show the last 25' : 'Show all ' + n}</button>` : ''}</div>
        <div class="tw"><table class="t"><thead><tr><th>When (Bangkok)</th><th></th><th>From</th><th>To</th>${px ? `<th class="r">${U.esc(r.main)}</th>` : ''}<th class="r">Value</th><th>Why</th></tr></thead><tbody>
        ${tr.map((x) => { const k = kind[x.kind] || ['', x.kind]; return `<tr><td class="num">${U.esc(new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(x.t * 1000)))}</td>
          <td>${U.pill(k[0], k[1])}</td><td class="small">${U.esc(pos(x.from))}</td><td class="small">${U.esc(pos(x.to))}</td>
          ${px ? `<td class="r num">${x.prices[r.main] != null ? U.usd(x.prices[r.main]) : '—'}</td>` : ''}<td class="r num">${U.usd(x.value, 0)}</td>
          <td class="muted small wrap" style="max-width:340px">${U.esc(x.why || '')}</td></tr>`; }).join('') || '<tr><td colspan="7" class="muted">No trades in this period: the position did not change.</td></tr>'}
        </tbody></table></div></section>`;
    }

    function tryBox() {
      const cur = Object.assign({}, d.row.params, st.custom || {});
      return `<section class="card col" style="gap:12px"><div class="row sb"><h2 class="h2">Try other settings</h2>
        <span class="muted small">Only for this backtest — nothing is saved or traded</span></div>
        <div class="fs">${rules.map((p) => `<div class="f"><label for="bt-${p.key}">${U.esc(p.label)}</label>
          <input class="in num" id="bt-${p.key}" value="${U.esc(cur[p.key])}" placeholder="${U.esc(d.row.params[p.key])}"></div>`).join('')}</div>
        <div class="row" style="justify-content:flex-end;gap:8px">${st.custom ? '<button class="btn" id="bt-reset">Back to the saved settings</button>' : ''}
          <button class="btn p" id="bt-run">Run backtest with these settings</button></div></section>`;
    }

    function assumptions() {
      const r = st.data, e = r.exec || {};
      const timing = r.parking
        ? 'The on/off signal is decided on each US close; the list of stocks comes from each Friday\'s Nasdaq-100 ranking. Trades happen at the next day\'s open: sell names that left the list, buy new names with 1/' + (d.row.params.hold || 7) + ' of the money, no top-ups; when off, everything goes to the parking ETFs. Fees: ' + r.cost_pct.toFixed(2) + '% per side on stocks and parking ETFs, ' + (r.cost_2x_pct || r.cost_pct).toFixed(2) + '% on 2x ETFs (wider spread) — set in Settings → Fees.'
        : r.family === 'regime'
        ? 'Decided on each US close (same code as the bot), traded at the next day\'s open. Rebalanced when a holding drifts more than the rebalance band.'
        : `A signal counts when its 4H futures bar closes (+ Yahoo's delay). Entries start ${e.start_mode === 'time' ? 'not before ' + U.esc(e.start_time) + ' Bangkok' : 'at the market open'}, exits ${e.exit_mode === 'asap' ? 'as soon as the US market is open' : 'at the same time as entries'}; priced as ${e.lots} lots every ${e.interval_min} min from hourly ETF prices.`;
      return `<section class="card col" style="gap:6px"><h2 class="h2">How this backtest works</h2><ul class="muted small" style="margin:0;padding-left:18px;display:flex;flex-direction:column;gap:4px">
        <li>The signals come from the same strategy code the bot trades with${st.custom ? ' (with the settings you are trying)' : ''}. ${timing}</li>
        <li>Prices include dividends (total return), so T-bill ETFs earn their interest. Fee ${r.cost_pct.toFixed(2)}% per side on every trade (Webull TH 0.107% + a little spread; change it in <a href="#/settings">Settings → Fees</a>) — ${U.usd(r.fees, 0)} in total on $10,000.</li>
        <li>Data: ${U.esc(r.data.note)}, ${dayTxt(r.data.from)} – ${dayTxt(r.data.to)}${r.data.source === 'csv' ? ' · <b>demo prices (not real)</b>' : ''}.</li>
        <li>Not included: whole-share rounding, partial fills, the money guard, money added or withdrawn, and taxes. Past results do not promise future ones.</li></ul></section>`;
    }

    function chartBox() {
      const r = st.data;
      return `<section class="card col" style="gap:10px;padding:16px">
        <div class="row sb" style="gap:8px;flex-wrap:wrap"><div class="row" style="gap:8px;flex-wrap:wrap"><div class="seg" id="bt-rng">${r.ranges.map((k) => `<button data-r="${k}" class="${st.range === k ? 'on' : ''}">${RL[k]}</button>`).join('')}</div>
          <div class="seg" id="bt-size" role="group" aria-label="Sizing"><button data-size="C" class="${st.size === 'C' ? 'on' : ''}" title="Profit stays in: the position grows with the money, like Auto adding contracts">Compounding</button><button data-size="F" class="${st.size === 'F' ? 'on' : ''}" title="The position stays $10,000 and the profit is taken out, like trading 1 contract">Fixed $10,000</button></div></div>
          <div class="row" style="gap:8px;flex-wrap:wrap"><button class="tg on" aria-pressed="true" disabled><i style="background:${c.color}"></i>${U.esc(c.name.split(' · ')[0])}</button>
          ${Object.keys(r.series.bench).map((k, i) => `<button class="tg ${st.show[k] ? 'on' : ''}" data-bm="${U.esc(k)}" aria-pressed="${!!st.show[k]}"><i style="background:${BENCH_COL[i % 2]}"></i>${U.esc(k)} held</button>`).join('')}
          <button class="tg ${st.log && st.size === 'C' ? 'on' : ''}" id="bt-log" aria-pressed="${st.log}" ${st.size === 'F' ? 'disabled' : ''}>Log scale</button></div></div>
        <div class="muted small">${st.size === 'C' ? 'Compounding: profit stays in and the position grows with the money (like Auto adding contracts). On a log scale the same slope means the same % gain.' : 'Fixed $10,000: the position stays $10,000 and the profit is taken out each day, a loss topped back up (like trading 1 contract). The line is $10,000 plus the profit taken out so far, so every year counts the same.'}</div>
        <div class="tvwrap"><div id="bt-main" style="height:360px;position:relative"><div class="tvlegend" id="bt-leg"></div></div>
          <div class="tvpane" id="bt-dd" style="height:120px;position:relative"><div class="tvlegend" id="bt-ddleg"></div></div>
          <div class="tvpane" id="bt-ex" style="height:80px;position:relative"><div class="tvlegend" id="bt-exleg"></div></div></div></section>`;
    }

    function drawChart(i0) {
      destroyCharts();
      const r = st.data, s = r.series, t = s.t.slice(i0);
      const reb = st.size === 'F' ? (arr) => fixedOf(arr, i0) : (arr) => { const b = arr[i0]; return arr.slice(i0).map((v) => v == null || !b ? null : v / b * 10000); };
      const strat = reb(s.strategy);
      const mainEl = host.querySelector('#bt-main');
      const ch = Charts.base(mainEl, { daily: true, timeVisible: false });
      ch.priceScale('right').applyOptions({ mode: st.log && st.size === 'C' ? LightweightCharts.PriceScaleMode.Logarithmic : LightweightCharts.PriceScaleMode.Normal });
      ch.applyOptions({ localization: { priceFormatter: (p) => '$' + Math.round(p).toLocaleString('en-US') } });
      const lines = [];
      Object.keys(s.bench).forEach((k, i) => {
        if (!st.show[k]) return;
        const ser = ch.addLineSeries({ color: BENCH_COL[i % 2], lineWidth: 2, lineStyle: i === 1 ? 2 : 0, priceLineVisible: false, crosshairMarkerVisible: false });
        const v = reb(s.bench[k]);
        ser.setData(t.map((x, j) => v[j] == null ? { time: x } : { time: x, value: v[j] }));
        lines.push({ k: k + ' held', color: BENCH_COL[i % 2], v });
      });
      const sm = ch.addLineSeries({ color: c.color, lineWidth: 3, priceLineVisible: false });
      sm.setData(t.map((x, j) => ({ time: x, value: strat[j] })));
      lines.unshift({ k: c.name.split(' · ')[0], color: c.color, v: strat });
      sm.createPriceLine({ price: 10000, color: '#787B86', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' });
      // drawdown of the window (always of the compounding curve: the % below the last high)
      let pk = -Infinity;
      const ddBase = st.size === 'F' ? s.strategy.slice(i0) : strat;
      const dd = ddBase.map((v) => { pk = Math.max(pk, v); return (v / pk - 1) * 100; });
      const ddc = Charts.base(host.querySelector('#bt-dd'), { daily: true, timeVisible: false, noLogo: true });
      const dds = ddc.addAreaSeries({ lineColor: '#EF5350', topColor: '#EF535010', bottomColor: '#EF535055', lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, invertFilledArea: true });
      dds.setData(t.map((x, j) => ({ time: x, value: Math.round(dd[j] * 100) / 100 })));
      ddc.applyOptions({ localization: { priceFormatter: (p) => p.toFixed(0) + '%' } });
      const exc = Charts.base(host.querySelector('#bt-ex'), { daily: true, timeVisible: true, noLogo: true });
      const exs = exc.addAreaSeries({ lineColor: c.color, topColor: c.color + '66', bottomColor: c.color + '10', lineWidth: 1, lineType: 1, priceLineVisible: false, crosshairMarkerVisible: false });
      const ex = s.expo.slice(i0);
      exs.setData(t.map((x, j) => ({ time: x, value: Math.round(ex[j] * 1000) / 10 })));
      exc.applyOptions({ localization: { priceFormatter: (p) => p.toFixed(0) + '%' } });
      st.charts = [ch, ddc, exc];
      let syncing = false;
      st.charts.forEach((src) => src.timeScale().subscribeVisibleLogicalRangeChange((rg) => {
        if (syncing || !rg) return;
        syncing = true; st.charts.forEach((dst) => { if (dst !== src) dst.timeScale().setVisibleLogicalRange(rg); }); syncing = false;
      }));
      const leg = host.querySelector('#bt-leg'), ddleg = host.querySelector('#bt-ddleg'), exleg = host.querySelector('#bt-exleg');
      const at = (time) => {
        let j = time == null ? t.length - 1 : t.indexOf(time);
        if (j < 0) j = t.length - 1;
        const day = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(t[j] * 1000));
        leg.innerHTML = `<span>${day}</span>` + lines.map((l) => `<span style="color:${l.color}">${U.esc(l.k)} <b class="num" style="font-weight:500">${l.v[j] == null ? '—' : '$' + Math.round(l.v[j]).toLocaleString('en-US')}</b></span>`).join('');
        ddleg.innerHTML = `<span>Fall from the high</span><span style="color:#EF5350"><b class="num" style="font-weight:500">${dd[j].toFixed(1)}%</b></span>`;
        exleg.innerHTML = `<span>Money in ${U.esc(r.main)}</span><span style="color:${c.color}"><b class="num" style="font-weight:500">${(ex[j] * 100).toFixed(0)}%</b></span>`;
      };
      at(null);
      ch.subscribeCrosshairMove((p) => at(p.time));
      st.charts.forEach((x) => { x.timeScale().applyOptions({ minBarSpacing: 0.01, rightOffset: 2 }); x.timeScale().fitContent(); });
    }

    /* the 12 months before each day: what a year in the strategy felt like, whatever day you started */
    function rollBox(i0) {
      const r = st.data, t = r.series.t.slice(i0), v = r.series.strategy.slice(i0);
      const n = 252, roll = [];
      for (let j = n; j < v.length; j++) if (v[j] != null && v[j - n]) roll.push({ time: t[j], value: Math.round((v[j] / v[j - n] - 1) * 1000) / 10 });
      st.roll = roll;
      if (roll.length < 20) return '';
      const vals = roll.map((x) => x.value).sort((a, b) => a - b);
      const pos = roll.filter((x) => x.value > 0).length / roll.length * 100;
      const tile = (k, v2, cls) => `<div class="card" style="padding:10px 14px;background:var(--panel2)"><div class="eyebrow">${k}</div><div class="num" style="font-size:18px;margin-top:4px">${v2}</div></div>`;
      return `<section class="card col" style="gap:10px"><div><h2 class="h2">Any 12 months in a row · ${RL[st.range]}</h2>
        <div class="muted small" style="margin-top:2px;max-width:860px">The return over the 12 months before each day. Above zero you made money over that year, below it you lost: it shows what a year in this strategy felt like, whatever day you started.</div></div>
        <div class="grid" style="--min:150px;gap:10px">${tile('Years that made money', pos.toFixed(0) + '%')}${tile('Worst 12 months', `<span class="dn">${P(vals[0], 0)}</span>`)}${tile('Typical 12 months', P(vals[Math.floor(vals.length / 2)], 0))}${tile('Best 12 months', `<span class="up">${P(vals[vals.length - 1], 0)}</span>`)}</div>
        <div class="tvwrap"><div id="bt-roll" style="height:180px;position:relative"></div></div></section>`;
    }
    function drawRoll() {
      const host2 = host.querySelector('#bt-roll');
      if (!host2 || !st.roll || !st.roll.length) return;
      const ch = Charts.base(host2, { daily: true, timeVisible: true, noLogo: true });
      ch.applyOptions({ localization: { priceFormatter: (p) => p.toFixed(0) + '%' } });
      const ser = ch.addBaselineSeries({ baseValue: { type: 'price', price: 0 }, topLineColor: '#26A69A', bottomLineColor: '#EF5350', topFillColor1: '#26A69A33', topFillColor2: '#26A69A05', bottomFillColor1: '#EF535005', bottomFillColor2: '#EF535033', lineWidth: 2, priceLineVisible: false });
      ser.setData(st.roll);
      ch.timeScale().fitContent();
      st.charts.push(ch);
    }

    /* each month's return in the window (UTC month ends) */
    function monthsBox(i0) {
      const r = st.data, t = r.series.t.slice(i0), v = r.series.strategy.slice(i0);
      const ends = {};
      t.forEach((x, j) => { if (v[j] != null) { const d0 = new Date(x * 1000); ends[d0.getUTCFullYear() * 100 + d0.getUTCMonth()] = v[j]; } });
      const keys = Object.keys(ends).map(Number).sort((a, b) => a - b);
      if (keys.length < 3) return '';
      const ret = {}, yrs = {};
      let prev = v.find((x) => x != null);
      keys.forEach((k) => { ret[k] = (ends[k] / prev - 1) * 100; prev = ends[k]; yrs[Math.floor(k / 100)] = 1; });
      const ylist = Object.keys(yrs).map(Number).sort((a, b) => b - a);
      const yearRet = (y) => { const ks = keys.filter((k) => Math.floor(k / 100) === y); return ks.reduce((a, k) => a * (1 + ret[k] / 100), 1) * 100 - 100; };
      const cell = (x) => {
        if (x == null) return '<td></td>';
        const a = Math.min(1, Math.abs(x) / 25);
        return `<td class="num" style="text-align:center;border-radius:4px;background:color-mix(in srgb, ${x >= 0 ? 'var(--up)' : 'var(--dn)'} ${Math.round(10 + a * 70)}%, transparent);${a > 0.6 ? 'color:var(--bg)' : ''}">${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(0)}</td>`;
      };
      return `<section class="card col" style="gap:8px"><div><h2 class="h2">Month by month · ${RL[st.range]}</h2>
        <div class="muted small" style="margin-top:2px;max-width:860px">Each month's return in %, deeper green or red = a bigger month. A run of red is how a bad stretch feels from inside.</div></div>
        <div class="tw"><table style="border-collapse:separate;border-spacing:2px;font-size:12px;width:100%;min-width:680px"><thead><tr class="muted"><th style="text-align:left">Year</th>${['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'].map((m) => `<th style="font-weight:500">${m}</th>`).join('')}<th class="r" style="font-weight:600">Year</th></tr></thead>
        <tbody>${ylist.map((y) => `<tr><td class="num">${y}</td>${Array.from({ length: 12 }, (_, m) => cell(ret[y * 100 + m])).join('')}<td class="r num ${U.cls(yearRet(y))}" style="font-weight:600;padding-left:8px">${P(yearRet(y), 0)}</td></tr>`).join('')}</tbody></table></div></section>`;
    }

    /* range of outcomes, stress test and good / bad markets: computed on the server, filled in when ready */
    function extraBoxes() {
      if (st.custom) return '<div class="note"><span>Range of outcomes, stress test and good / bad markets are shown for the saved settings.</span></div>';
      const box = (id, title, sub) => `<section class="card col" style="gap:10px" id="${id}"><div><h2 class="h2">${title}</h2><div class="muted small" style="margin-top:2px;max-width:900px">${sub}</div></div>
        <div class="empty small" data-slot><span class="spin"></span> Working it out…</div></section>`;
      return box('bt-boot', 'Range of outcomes · 2,000 shuffled decades', 'The strategy\'s own last 10 years (or all it has) cut into 3-month pieces and put back together in random order, 2,000 times. The band holds the middle 80% of those paths, the dashed line is the middle one, the solid line is what really happened: it shows how much luck was in the real line. It cannot invent a market unlike these years, so a crash worse than any in them is not inside.')
        + box('bt-stress', 'What if trading goes worse than planned?', 'The same backtest with higher fees and with every order late: one trading day for daily and weekly strategies, one 4-hour bar for gold and silver. A strategy whose return collapses when orders are late depends on the bot trading on time: keep the server healthy and do not pause it on signal days.')
        + box('bt-reg', 'Good markets and bad markets', 'Return a year while its index was above its 200-day average (an up-trend) and below it (a down-trend), next to simply holding the ETF. A good strategy keeps most of the up-trend and loses far less than the ETF in the down-trend.');
    }
    function fanSvg(b) {
      const all = b.p10.concat(b.p90, b.actual).filter((x) => x > 0);
      const lo = Math.log10(Math.min(...all, 10000) * 0.9), hi = Math.log10(Math.max(...all) * 1.05);
      const Y = (x) => (10 + 220 - (Math.log10(x) - lo) / (hi - lo) * 220).toFixed(1);
      const X = (f) => (f * 1000).toFixed(1);
      const band = b.x.map((f, i) => `${X(f)},${Y(b.p90[i])}`).join(' ') + ' ' + b.x.map((f, i) => `${X(f)},${Y(b.p10[i])}`).reverse().join(' ');
      const med = b.x.map((f, i) => `${X(f)},${Y(b.p50[i])}`).join(' ');
      const act = b.actual.map((v, i) => `${X(i / (b.actual.length - 1))},${Y(v)}`).join(' ');
      const ticks = [1e4, 2e4, 5e4, 1e5, 2e5, 5e5, 1e6, 2e6, 5e6, 1e7, 2e7, 5e7].filter((t) => Math.log10(t) >= lo && Math.log10(t) <= hi);
      const tk = ticks.length > 5 ? ticks.filter((_, i) => i % 2 === 0) : ticks;
      return `<div style="position:relative;height:250px"><svg viewBox="0 0 1000 240" preserveAspectRatio="none" role="img" aria-label="Band of shuffled paths with the real path" style="position:absolute;inset:0;width:100%;height:240px">
        ${tk.map((t) => `<line x1="0" x2="1000" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--chart-grid)"/>`).join('')}
        <polygon points="${band}" fill="color-mix(in srgb, var(--info) 22%, transparent)"/>
        <polyline points="${med}" fill="none" stroke="var(--info)" stroke-width="1.6" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"/>
        <polyline points="${act}" fill="none" stroke="var(--text)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>
        ${tk.map((t) => `<span class="tiny muted num" style="position:absolute;left:4px;top:calc(${Y(t)}px - 15px)">${t >= 1e6 ? '$' + t / 1e6 + 'M' : '$' + t / 1e3 + 'k'}</span>`).join('')}
        <span class="tiny muted" style="position:absolute;left:4px;bottom:-4px">start</span><span class="tiny muted" style="position:absolute;right:4px;bottom:-4px">${b.years} years</span></div>
        <div class="row small muted" style="gap:16px;flex-wrap:wrap"><span><i style="display:inline-block;width:14px;height:10px;background:color-mix(in srgb, var(--info) 22%, transparent);vertical-align:middle"></i> middle 80% of ${b.paths.toLocaleString('en-US')} decades</span>
          <span><i style="display:inline-block;width:14px;border-top:2px dashed var(--info);vertical-align:middle"></i> middle one</span><span><i style="display:inline-block;width:14px;border-top:2px solid var(--text);vertical-align:middle"></i> what really happened</span></div>`;
    }
    async function fillExtra() {
      if (st.custom) return;
      const put = (id, html) => { const x = host.querySelector('#' + id + ' [data-slot]'); if (x) { x.outerHTML = html; } };
      try {
        st.extra = st.extra || await U.api(`/api/backtest/${sid}/extra`);
        const x = st.extra;
        if (!x.ok) throw new Error(x.error || 'not available');
        const b = x.boot;
        const tile = (k, v, sub, cls) => `<div class="card" style="padding:10px 14px;background:var(--panel2)"><div class="eyebrow">${k}</div><div class="num ${cls || ''}" style="font-size:18px;margin-top:4px">${v}</div><div class="muted small">${sub}</div></div>`;
        put('bt-boot', b ? `<div class="grid" style="--min:180px;gap:10px">${tile('Bad case · 1 in 10 worse', P(b.cagr.p10) + ' a year', '$10,000 → ' + U.usd(b.end.p10, 0))}${tile('Middle case', P(b.cagr.p50) + ' a year', '$10,000 → ' + U.usd(b.end.p50, 0))}
            ${tile('Worst fall · middle case', PP(b.fall.p50), '1 in 10 paths: ' + PP(b.fall.p10) + ' or worse', 'dn')}${tile('Chance of a fall past −40%', b.chance.fall40.toFixed(0) + '%', `past −30%: ${b.chance.fall30.toFixed(0)}% · past −50%: ${b.chance.fall50.toFixed(0)}% · losing money: ${b.chance.loss.toFixed(0)}%`)}</div>${fanSvg(b)}
            <div class="muted small">Weekly returns ${dayTxt(x.from)} – ${dayTxt(x.to)}${x.src === 'research' ? ' from the research (OANDA prices, these settings): Yahoo keeps only about 2 years of hourly gold and silver prices' : ''}.</div>`
          : '<div class="muted small">Not enough history for this yet.</div>');
        const g = x.regime;
        if (g) {
          const mx = Math.max(...[g.good, g.bad, g.hgood, g.hbad].filter((v) => v != null).map(Math.abs), 1);
          const bar = (v) => v == null ? '' : `<div style="position:absolute;top:0;bottom:0;border-radius:3px;background:${v >= 0 ? 'var(--up)' : 'var(--dn)'};${v >= 0 ? 'left:50%;width:' + (v / mx * 50) + '%' : 'right:50%;width:' + (-v / mx * 50) + '%'}"></div>`;
          const line = (l, v) => `<span class="small">${l}</span><div style="height:16px;position:relative;background:var(--panel2);border-radius:4px">${bar(v)}<div style="position:absolute;left:50%;top:-3px;bottom:-3px;border-left:1px solid var(--text)"></div></div><b class="num r ${U.cls(v)}">${P(v)}</b>`;
          const card = (title, a, h) => `<div class="card" style="padding:12px 14px;background:var(--panel2)"><div style="font-weight:600;margin-bottom:8px">${title}</div>
            <div style="display:grid;grid-template-columns:120px minmax(0,1fr) 72px;gap:8px;align-items:center">${line('This strategy', a)}${line(U.esc(g.etf) + ' held', h)}</div></div>`;
          put('bt-reg', `<div class="grid" style="--min:300px;gap:12px">${card('Good market · ' + U.esc(g.index) + ' above its 200-day average', g.good, g.hgood)}${card('Bad market · ' + U.esc(g.index) + ' below its 200-day average', g.bad, g.hbad)}</div>
            <div class="muted small">Since ${dayTxt(g.from)} · bad markets were ${g.bad_share}% of the days · the state is taken from the day before, as the bot would know it.</div>`);
        } else put('bt-reg', '<div class="muted small">Not enough history for this yet.</div>');
      } catch (e) { put('bt-boot', `<div class="muted small">${U.esc(e.message)}</div>`); put('bt-reg', ''); }
      try {
        st.stress = st.stress || await U.api(`/api/backtest/${sid}/stress`);
        const x = st.stress;
        if (!x.ok) throw new Error(x.error || 'not available');
        const base = x.rows[0].cagr, mx = Math.max(...x.rows.filter((r) => r.cagr != null).map((r) => Math.abs(r.cagr)), 1);
        put('bt-stress', `<div class="col" style="gap:8px">${x.rows.map((r) => {
          if (r.cagr == null) return `<div style="display:grid;grid-template-columns:minmax(0,260px) minmax(0,1fr) 200px;gap:12px;align-items:center"><span class="small">${U.esc(r.t)}</span><span class="muted small">${U.esc(r.na || 'not available')}</span><span></span></div>`;
          const col = r.cagr >= base * 0.8 ? 'var(--up)' : r.cagr > 0 ? 'var(--warn-fg)' : 'var(--dn)';
          return `<div style="display:grid;grid-template-columns:minmax(0,260px) minmax(0,1fr) 200px;gap:12px;align-items:center"><span class="small">${U.esc(r.t)}</span>
            <div style="height:18px;background:var(--panel2);border-radius:4px;overflow:hidden"><div style="height:100%;border-radius:4px;width:${Math.max(2, Math.abs(r.cagr) / mx * 100)}%;background:${col}"></div></div>
            <span class="num r"><b style="color:${col}">${P(r.cagr)}</b> <span class="muted tiny">${r.base ? 'a year' : P(r.cagr - base) + ' vs tested'}</span><span class="tiny dn" style="display:block">worst fall ${PP(r.maxdd)}</span></span></div>`; }).join('')}</div>
          ${x.short ? `<div class="note warn"><span><b>Only the last ${x.years != null ? x.years.toFixed(1) : '~2'} years</b> (${dayTxt(x.from)} – ${dayTxt(x.to)}): all the hourly prices Yahoo keeps for this strategy. Compare the rows with each other, not with the 10-year numbers above or in Expected returns — a short stretch (such as gold's 2025–26 run) can make every row look much better, or worse, than 10 years would.</span></div>` : ''}
          <div class="muted small">${x.short ? 'Return a year over those years' : 'Last 10 years, return a year'}. Green: keeps at least 80% of the tested return · amber: less · red: loses money.${x.at ? ' Worked out ' + U.ago(x.at) + ' (once a day after the US close).' : ''}</div>`);
      } catch (e) { put('bt-stress', `<div class="muted small">${U.esc(e.message)}</div>`); }
    }

    function render() {
      destroyCharts();
      const r = st.data;
      if (!r.ok) {
        host.innerHTML = `<div class="note err" style="flex-direction:column;align-items:flex-start;gap:6px"><b>Backtest not possible yet</b><span>${U.esc(r.error)}</span>
          <span class="muted">It needs the price history (downloaded from Yahoo by the server). Try again in a minute; if it repeats, open Health check → Data.</span></div>
          ${st.custom ? tryBox() : ''}`;
        bindTry();
        return;
      }
      const R = r.stats[st.range];
      const i0 = win();
      host.innerHTML = `
        ${st.custom ? `<div class="note warn"><span>Showing a backtest with <b>other settings</b>: ${U.esc(Object.entries(st.custom).map(([k, v]) => ((rules.find((p) => p.key === k) || {}).label || k) + ' = ' + v).join(' · '))}. They are <b>not saved</b> — use the Parameters tab to save them.</span></div>` : ''}
        ${r.data.source === 'csv' ? '<div class="note warn"><span>Demo prices (random, not real) — this copy runs without internet.</span></div>' : ''}
        ${tiles(R.strategy, R)}
        ${chartBox()}
        ${rollBox(i0)}
        ${extraBoxes()}
        <div id="bt-risk"></div>
        <section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">Strategy vs simply holding · ${RL[st.range]}</h2>
          <span class="muted small">${dayTxt(R.strategy.from)} – ${dayTxt(R.strategy.to)} · $10,000 at the start</span></div>${compareTable(R)}</section>
        ${research()}
        ${yearsTable()}
        ${monthsBox(i0)}
        ${tradesTable(i0)}
        ${tryBox()}
        ${assumptions()}`;
      drawChart(i0);
      drawRoll();
      fillExtra();
      { const rk = host.querySelector('#bt-risk'); if (rk && V.renderRisk && !st.custom) V.renderRisk(rk, sid); }
      U.on(host, '#bt-rng button', 'click', (e, b) => { st.range = b.dataset.r; render(); });
      U.on(host, '#bt-size button', 'click', (e, b) => { st.size = b.dataset.size; render(); });
      U.on(host, '[data-bm]', 'click', (e, b) => { st.show[b.dataset.bm] = !st.show[b.dataset.bm]; render(); });
      host.querySelector('#bt-log').onclick = () => { if (st.size === 'F') return; st.log = !st.log; render(); };
      const all = host.querySelector('#bt-all');
      if (all) all.onclick = () => { st.allTrades = !st.allTrades; render(); };
      bindTry();
    }

    function bindTry() {
      const run = host.querySelector('#bt-run');
      if (run) run.onclick = () => {
        const params = {};
        rules.forEach((p) => {
          const v = host.querySelector('#bt-' + p.key).value.trim();
          if (v !== '' && String(v) !== String(d.row.params[p.key])) params[p.key] = v;
        });
        if (!Object.keys(params).length) { U.toast('Change at least one setting first'); return; }
        load(params);
      };
      const rs = host.querySelector('#bt-reset');
      if (rs) rs.onclick = () => load(null);
    }

    load(null);
    return destroyCharts;
  };
})();
