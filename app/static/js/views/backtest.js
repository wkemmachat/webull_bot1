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
    const st = { data: null, range: null, log: true, show: {}, custom: null, charts: [], allTrades: false };
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

    function tiles(S, B) {
      const main = st.data.vs || st.data.main, idx = st.data.index !== main ? st.data.index : null;
      const bm = B[main], bi = idx ? B[idx] : null;
      const tile = (k, v, sub, cls) => `<div class="card" style="padding:14px 16px"><div class="eyebrow">${k}</div>
        <div class="num big ${cls || ''}" style="margin-top:6px">${v}</div><div class="muted small" style="margin-top:2px">${sub}</div></div>`;
      return `<div class="grid" style="--min:150px;gap:12px">
        ${tile('A year (CAGR)', P(S.cagr), `${U.esc(main)} held ${P(bm && bm.cagr)}${bi ? ' · ' + U.esc(idx) + ' ' + P(bi.cagr) : ''}`, S.cagr > 0 ? 'up' : 'dn')}
        ${tile('Worst fall', PP(S.maxdd), `${U.esc(main)} held ${PP(bm && bm.maxdd)} · ${dayTxt(S.dd_peak)} → ${dayTxt(S.dd_trough)}`, 'dn')}
        ${tile('$10,000 became', U.usd(S.end_value, 0), `${P(S.total, 0)} in ${S.years.toFixed(1)} years`)}
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
        <div class="row sb" style="gap:8px;flex-wrap:wrap"><div class="seg" id="bt-rng">${r.ranges.map((k) => `<button data-r="${k}" class="${st.range === k ? 'on' : ''}">${RL[k]}</button>`).join('')}</div>
          <div class="row" style="gap:8px;flex-wrap:wrap"><button class="tg on" aria-pressed="true" disabled><i style="background:${c.color}"></i>${U.esc(c.name.split(' · ')[0])}</button>
          ${Object.keys(r.series.bench).map((k, i) => `<button class="tg ${st.show[k] ? 'on' : ''}" data-bm="${U.esc(k)}" aria-pressed="${!!st.show[k]}"><i style="background:${BENCH_COL[i % 2]}"></i>${U.esc(k)} held</button>`).join('')}
          <button class="tg ${st.log ? 'on' : ''}" id="bt-log" aria-pressed="${st.log}">Log scale</button></div></div>
        <div class="tvwrap"><div id="bt-main" style="height:360px;position:relative"><div class="tvlegend" id="bt-leg"></div></div>
          <div class="tvpane" id="bt-dd" style="height:120px;position:relative"><div class="tvlegend" id="bt-ddleg"></div></div>
          <div class="tvpane" id="bt-ex" style="height:80px;position:relative"><div class="tvlegend" id="bt-exleg"></div></div></div></section>`;
    }

    function drawChart(i0) {
      destroyCharts();
      const r = st.data, s = r.series, t = s.t.slice(i0);
      const reb = (arr) => { const b = arr[i0]; return arr.slice(i0).map((v) => v == null || !b ? null : v / b * 10000); };
      const strat = reb(s.strategy);
      const mainEl = host.querySelector('#bt-main');
      const ch = Charts.base(mainEl, { daily: true, timeVisible: false });
      ch.priceScale('right').applyOptions({ mode: st.log ? LightweightCharts.PriceScaleMode.Logarithmic : LightweightCharts.PriceScaleMode.Normal });
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
      // drawdown of the window
      let pk = -Infinity;
      const dd = strat.map((v) => { pk = Math.max(pk, v); return (v / pk - 1) * 100; });
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
        <section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">Strategy vs simply holding · ${RL[st.range]}</h2>
          <span class="muted small">${dayTxt(R.strategy.from)} – ${dayTxt(R.strategy.to)} · $10,000 at the start</span></div>${compareTable(R)}</section>
        ${research()}
        ${yearsTable()}
        ${tradesTable(i0)}
        ${tryBox()}
        ${assumptions()}`;
      drawChart(i0);
      U.on(host, '#bt-rng button', 'click', (e, b) => { st.range = b.dataset.r; render(); });
      U.on(host, '[data-bm]', 'click', (e, b) => { st.show[b.dataset.bm] = !st.show[b.dataset.bm]; render(); });
      host.querySelector('#bt-log').onclick = () => { st.log = !st.log; render(); };
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
