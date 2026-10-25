(function () {
  const V = window.Views || (window.Views = {});
  const PALETTE = ['#3DC9C0', '#E8875A', '#E46AA8', '#9BCB4E', '#F2C14E', '#5B8DEF', '#B084F5', '#D5DBE3'];

  /* ---------------------------------------------------------------- list */
  V.strategies = async function (el) {
    const mode = U.mode();
    let filter = 'all';
    async function load() {
      const d = await U.api('/api/strategies?mode=' + mode);
      const fam = { all: d.strategies.length, signal: d.strategies.filter((s) => s.family === 'signal').length, regime: d.strategies.filter((s) => s.family === 'regime').length };
      const rows = d.strategies.filter((s) => filter === 'all' || s.family === filter);
      el.innerHTML = `
      <div class="page-head"><div><div class="eyebrow">${d.strategies.length} active · ${d.archived.length} archived · ${U.modeLabel[mode]}</div><h1 class="h1">Strategies</h1>
        <div class="muted" style="margin-top:4px">Each strategy is a sub-account inside your Webull account: its own money, positions, orders and LINE switch.</div></div>
        <a class="btn p" href="#/strategies/new">+ Add strategy</a></div>
      <div class="seg" id="fam" style="align-self:flex-start"><button data-f="all" class="${filter === 'all' ? 'on' : ''}">All ${fam.all}</button>
        <button data-f="signal" class="${filter === 'signal' ? 'on' : ''}">Gold &amp; silver · 4H signal · ${fam.signal}</button>
        <button data-f="regime" class="${filter === 'regime' ? 'on' : ''}">US · daily · ${fam.regime}</button></div>
      <section class="card flush" style="overflow-x:auto">
        <div class="srow head"><span>Strategy</span><span>Signal → trades</span><span>Now</span><span>Value · return</span><span>Control · LINE</span></div>
        ${rows.map((s) => `
        <div class="srow">
          <a href="#/strategies/${s.id}" class="row" style="gap:12px;align-items:flex-start;color:var(--text);flex-wrap:nowrap">${U.dot(s.color, 12)}
            <span class="col" style="gap:3px;min-width:0"><b style="font-size:15px">${U.esc(s.name)}</b><span class="muted small">${U.esc(s.rule || '')}</span></span></a>
          <div class="col" style="gap:3px"><span class="num small">${U.esc(s.flow || '')}</span><span class="muted small">${U.esc(s.exec)}</span></div>
          <div class="col" style="gap:5px;align-items:flex-start">${U.pill(s.state_cls, s.label || '—')}<span class="muted small">${s.signal_time ? 'since ' + U.dt(s.signal_time) : ''}</span></div>
          <div class="col" style="gap:2px"><span class="num" style="font-weight:600;font-size:15px">${U.usd(s.value)}</span>
            <span class="num small ${U.cls(s.pnl)}">${U.sgnUsd(s.pnl, 0)} · ${U.pct(s.ret)}</span><span class="muted num small">capital ${U.usd(s.net_in, 0)}</span></div>
          <div class="row" style="gap:14px">
            <div class="seg" role="group" aria-label="Control" data-id="${s.id}">
              <button data-c="active" class="${s.control === 'active' ? 'on' : ''}">Active</button>
              <button data-c="paused" class="gi ${s.control === 'paused' ? 'on' : ''}">Pause buys</button>
              <button data-c="stopping" class="live ${s.control === 'stopping' || s.control === 'stopped' ? 'on' : ''}">${s.control === 'stopped' ? 'Stopped' : 'Stop &amp; sell'}</button></div>
            <span class="row muted small" style="gap:8px"><button class="sw ${s.line_on ? 'on' : ''}" role="switch" aria-checked="${s.line_on}" aria-label="LINE alerts for ${U.esc(s.name)}" data-line="${s.id}"></button>LINE</span>
          </div>
        </div>`).join('')}
      </section>
      <div class="grid" style="--min:340px">
        <section class="card col" style="gap:10px"><h2 class="h2">What the three controls do</h2>
          <div><b>Active</b> <span class="muted">— follows every signal: buys, sells and rebalances.</span></div>
          <div><b>Pause buys</b> <span class="muted">— exits still run; no new buys. Cash waits.</span></div>
          <div><b>Stop &amp; sell</b> <span class="muted">— sells everything with a split plan, then rests with cash only. Its money can then be moved.</span></div>
          <div class="muted small">Every change asks for confirmation, is written to Logs and sent to LINE. Controls apply to all trading modes.</div></section>
        <section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">Archived</h2>${U.pill('', 'read-only')}</div>
          ${d.archived.map((a) => `<div class="list-row">${U.dot(a.color, 12)}<b style="flex:1">${U.esc(a.name)}</b><button class="btn s" data-unarch="${a.id}">Restore</button></div>`).join('') || '<div class="muted small">Nothing archived. Archive a strategy from its page once it holds no money.</div>'}
        </section>
      </div>`;
      U.on(el, '#fam button', 'click', (e, b) => { filter = b.dataset.f; load(); });
      U.on(el, '.seg[data-id] button', 'click', async (e, b) => {
        const id = b.parentElement.dataset.id, c = b.dataset.c;
        const words = { active: ['Make it active?', 'It follows every signal again: buys, sells and rebalances.'],
          paused: ['Pause buys?', 'Exits and stops still run. No new buys; cash waits.'],
          stopping: ['Stop & sell?', 'Everything this strategy holds is sold with a split plan (all modes). Then it rests with cash only.'] };
        if (!(await U.confirm(words[c][0], words[c][1], { ok: b.textContent, danger: c === 'stopping', word: c === 'stopping' ? 'STOP' : null }))) return;
        await U.api(`/api/strategies/${id}/control`, { body: { control: c } });
        U.toast('Saved'); load();
      });
      U.on(el, '[data-line]', 'click', async (e, b) => {
        const on = !b.classList.contains('on');
        await U.api('/api/strategies/' + b.dataset.line, { method: 'PATCH', body: { line_on: on } });
        b.classList.toggle('on', on); b.setAttribute('aria-checked', on);
      });
      U.on(el, '[data-unarch]', 'click', async (e, b) => { await U.api(`/api/strategies/${b.dataset.unarch}/archive`, { body: { archive: false } }); load(); });
    }
    await load();
    return { cleanup: () => {}, refresh: () => load().catch(() => {}), every: 60000 };
  };

  /* ---------------------------------------------------------------- detail */
  const RANGES = { signal: [['2W', '2W'], ['1M', '1M'], ['3M', '3M'], ['1Y', '1Y']], regime: [['3M', '3M'], ['8M', '8M'], ['1Y', '1Y'], ['2Y', '2Y'], ['ALL', 'All']] };

  V.strategy = async function (el, params) {
    const sid = params[0], mode = U.mode();
    let tab = 'overview', chartObj = null, spec = null, btClean = null, chartSym = null;
    const cs = { range: null, hideLines: [], hidePanes: [], hideMarkers: false };
    const d = await U.api(`/api/strategies/${sid}?mode=${mode}`);
    const c = d.card, st = d.state || {}, fam = c.family;
    cs.range = fam === 'regime' ? '8M' : '1M';

    function header() {
      return `<div class="crumb"><a href="#/strategies">Strategies</a> / ${U.esc(c.name)}</div>
      <div class="page-head" style="align-items:flex-start"><div class="col" style="gap:8px;min-width:0;max-width:100%">
        <div class="row">${U.dot(c.color, 14)}<h1 class="h1">${U.esc(c.name)}</h1></div>
        <div class="row" style="gap:8px">${U.pill('', c.type === 'momentum_basket' ? 'Stock basket' : fam === 'regime' ? 'Daily regime' : '4H signal')}<span class="pill" style="white-space:normal;max-width:100%">${U.esc(c.flow)}</span>
          ${U.pill(c.control === 'active' ? 'ok' : 'warn', c.control === 'active' ? 'Active' : c.control === 'paused' ? 'Buys paused' : c.control)}
          ${U.pill(c.line_on ? 'info' : '', c.line_on ? 'LINE on' : 'LINE off')}</div>
        <div class="muted small">${U.esc(d.describe.rule || '')}</div></div>
        <div class="row"><button class="btn" data-money="withdraw">Withdraw</button><button class="btn" data-money="add">Add money</button>
          <button class="btn" data-ctl="${c.control === 'paused' ? 'active' : 'paused'}">${c.control === 'paused' ? 'Resume buys' : 'Pause buys'}</button>
          <button class="btn d" data-ctl="stopping">Stop &amp; sell</button></div></div>
      <nav class="tabs">${[['overview', 'Overview'], ['backtest', 'Backtest']].concat(c.type === 'momentum_basket' ? [['charts', 'Stock charts']] : [], [['params', 'Parameters'], ['exec', 'Execution'], ['history', 'History']]).map(([k, l]) =>
        `<button data-tab="${k}" class="${tab === k ? 'on' : ''}">${l}</button>`).join('')}</nav>`;
    }

    function kpis() {
      const pos = Object.entries(c.positions || {});
      return `<div class="grid" style="--min:210px">
        <div class="card"><div class="eyebrow">Value · ${U.modeLabel[mode]}</div><div class="num big" style="margin-top:6px">${U.usd(c.value)}</div>
          <div class="num small ${U.cls(c.pnl)}">${U.sgnUsd(c.pnl)} · ${U.pct(c.ret)} on ${U.usd(c.net_in, 0)}</div></div>
        <div class="card"><div class="eyebrow">Holding</div><div class="num big" style="margin-top:6px">${pos.length ? pos.map(([k, p]) => `${U.n(p.qty, 0)} ${k}`).join(' · ') : 'Cash'}</div>
          <div class="muted num small">${U.usd(c.cash)} cash${pos.length ? ' · ' + pos.map(([k, p]) => `${k} ${U.usd(p.price)}`).join(' · ') : ''}</div></div>
        <div class="card"><div class="eyebrow">Signal now</div><div style="margin-top:8px">${U.pill(c.state_cls + ' big', st.ok ? (fam === 'regime' ? st.state : (st.state || '').toUpperCase()) : 'ERROR')}</div>
          <div class="muted small" style="margin-top:6px">${st.ok ? U.esc(st.label) + (st.signal_time ? ' · since ' + U.dt(st.signal_time) : '') : U.esc(st.error || 'not evaluated yet')}</div></div>
        <div class="card"><div class="eyebrow">Next check</div><div class="num big" style="margin-top:6px">${c.next_check ? U.dt(c.next_check) : '—'}</div>
          <div class="muted small">${U.esc(d.exec_text)}</div></div></div>`;
    }

    function regimeTiles() {
      const p = d.row.params, det = st.detail || {};
      if (det.tiles) return `<section class="card col" style="gap:14px">
        <div class="row sb"><h2 class="h2">${U.esc(det.title || 'State')}</h2><span class="muted small">${det.date ? 'Last decision on the ' + U.esc(det.date) + ' close' : ''}</span></div>
        <div class="grid" style="--min:220px;gap:12px">${det.tiles.map((x) => `<div class="state ${st.state === x.k ? 'cur' : ''}">
          <div class="row sb"><b style="font-size:18px" class="row"><i style="width:10px;height:10px;border-radius:2px;background:${x.color};display:inline-block"></i>${U.esc(x.title)}</b>${st.state === x.k ? U.pill('info', 'NOW') : ''}</div>
          <div class="muted small">${U.esc(x.text)}</div><div style="font-weight:500">${U.esc(x.hold)}</div></div>`).join('')}</div>
        <div class="grid" style="--min:240px;gap:12px">${(det.checks || []).map((g) => `<div class="card" style="padding:12px 14px;background:var(--panel2)">
          <div class="muted small">${U.esc(g.k)}</div><div class="num ${g.cls || ''}" style="font-size:16px;font-weight:600">${U.esc(g.v)}</div><div class="muted small">${U.esc(g.h || '')}</div></div>`).join('')}</div>
      </section>`;
      const tiles = [['2x', 'Trend on, confirmed, calm', `${p.calm_weight}% ${p.trade}`], ['0.5x', `Trend on, confirmed, jumpy (vol ≥ ${p.vol_gate_pct}%)`, `${p.jumpy_weight}% ${p.trade} · rest ${p.cash_symbol}`],
        ['1x', `Trend on, not confirmed (SMA${p.confirm_days} ≤ SMA${p.ma_days})`, `${p.unconfirmed_weight}% ${p.trade} · rest ${p.cash_symbol}`], ['off', `${p.signal} at or below SMA${p.ma_days}`, `100% ${p.off_symbol}`]];
      const colors = { '2x': '#5B8DEF', '1x': '#34508A', '0.5x': '#F5C76B', off: '#B9852C' };
      return `<section class="card col" style="gap:14px">
        <div class="row sb"><h2 class="h2">Regime state · decided after each US close</h2><span class="muted small">${det.date ? 'Last decision on the ' + U.esc(det.date) + ' close' : ''}</span></div>
        <div class="grid" style="--min:200px;gap:12px">${tiles.map(([k, t, h]) => `<div class="state ${st.state === k ? 'cur' : ''}">
          <div class="row sb"><b style="font-size:18px" class="row"><i style="width:10px;height:10px;border-radius:2px;background:${colors[k]};display:inline-block"></i>${k === 'off' ? 'Off' : k}</b>${st.state === k ? U.pill('info', 'NOW') : ''}</div>
          <div class="muted small">${U.esc(t)}</div><div style="font-weight:500">${U.esc(h)}</div></div>`).join('')}</div>
        <div class="grid" style="--min:240px;gap:12px">${(det.checks || []).map((g) => `<div class="card" style="padding:12px 14px;background:var(--panel2)">
          <div class="muted small">${U.esc(g.k)}</div><div class="num ${g.cls || ''}" style="font-size:16px;font-weight:600">${U.esc(g.v)}</div><div class="muted small">${U.esc(g.h || '')}</div></div>`).join('')}</div>
      </section>`;
    }

    function basketTable(b) {
      const rows = b.rows || [];
      return `<section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">This week's list</h2>
        <span class="muted small">Ranking of ${U.esc(b.week)} · strongest ${U.esc(d.row.params.hold)} of the ${U.esc(d.row.params.pool)} largest by ${U.esc(d.row.params.lookback)}-day return</span></div>
        <div class="tw"><table class="t"><thead><tr><th class="r">Size rank</th><th>Stock</th><th class="r">Market cap</th><th class="r">${U.esc(d.row.params.lookback)}-day return</th><th>On the list</th>${b.leverage === '2x' ? '<th>Held as</th>' : ''}</tr></thead><tbody>
        ${rows.map((r) => `<tr><td class="r num">${r.rank}</td><td><a href="#" data-symc="${U.esc(r.picked && r.inst ? r.inst : r.symbol)}" title="Candle chart with every buy and sell"><b>${U.esc(r.symbol)}</b> <span class="small">📈</span></a></td><td class="r num">${r.mcap != null ? '$' + U.n(r.mcap, 0) + ' bn' : '—'}</td>
          <td class="r num ${U.cls(r.mom)}">${r.mom == null ? '—' : U.pct(r.mom)}</td><td>${r.picked ? U.pill('ok', 'yes') : '<span class="muted">—</span>'}</td>
          ${b.leverage === '2x' ? `<td class="mono">${U.esc(r.inst || '')}${r.picked && r.inst === r.symbol ? ' <span class="muted small">(no 2x ETF)</span>' : ''}</td>` : ''}</tr>`).join('')}</tbody></table></div>
        <div class="muted small">The list is fixed for the week after each Friday's ranking. Held only while the signal is in; names already held are never topped up.
          Tap a stock for its candle chart with every buy and sell (Stock charts tab).</div></section>`;
    }

    function chartToolbar() {
      const toggles = [];
      if (spec && spec.charts && spec.charts[0]) {
        const c0 = spec.charts[0];
        const seen = new Set();
        (c0.lines || []).forEach((l) => { const g = l.name.split(' (')[0]; if (seen.has(g)) return; seen.add(g); toggles.push({ k: 'line', v: g, label: g, color: l.color }); });
        (c0.panes || []).forEach((p) => toggles.push({ k: 'pane', v: p.id, label: p.title, color: p.lines[0].color }));
        toggles.push({ k: 'markers', v: 'm', label: fam === 'regime' ? 'State changes' : 'Signals', color: '#2962FF' });
      }
      const on = (t) => t.k === 'line' ? !cs.hideLines.includes(t.v) : t.k === 'pane' ? !cs.hidePanes.includes(t.v) : !cs.hideMarkers;
      return `<div class="row sb"><div class="row" style="gap:8px">
        <div class="seg" id="rng">${RANGES[fam].map(([k, l]) => `<button data-r="${k}" class="${cs.range === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        ${toggles.map((t) => `<button class="tg ${on(t) ? 'on' : ''}" data-tk="${t.k}" data-tv="${U.esc(t.v)}" aria-pressed="${on(t)}"><i style="background:${t.color}"></i>${U.esc(t.label)}</button>`).join('')}</div>
        ${fam === 'signal' && spec && spec.charts[0] ? `<a class="btn s" target="_blank" rel="noopener" href="${U.esc(spec.charts[0].tv)}">Open ${U.esc(spec.charts[0].tv_symbol)} in TradingView ↗</a>` : ''}</div>`;
    }

    async function drawChart() {
      const host = el.querySelector('#chart');
      if (!host) return;
      if (chartObj) chartObj.destroy();
      const hideLines = [];
      if (spec && spec.charts[0]) spec.charts[0].lines.forEach((l) => { if (cs.hideLines.includes(l.name.split(' (')[0])) hideLines.push(l.name); });
      chartObj = Charts.render(host, spec, { hideLines, hidePanes: cs.hidePanes, hideMarkers: cs.hideMarkers, titles: fam === 'regime' });
      el.querySelector('#ctool').innerHTML = chartToolbar();
      U.on(el, '#rng button', 'click', async (e, b) => { cs.range = b.dataset.r; spec = await U.api(`/api/strategies/${sid}/chart?range=${cs.range}`); drawChart(); });
      U.on(el, '.tg', 'click', (e, b) => {
        const k = b.dataset.tk, v = b.dataset.tv;
        const flip = (arr) => arr.includes(v) ? arr.splice(arr.indexOf(v), 1) : arr.push(v);
        if (k === 'line') flip(cs.hideLines); else if (k === 'pane') flip(cs.hidePanes); else cs.hideMarkers = !cs.hideMarkers;
        drawChart();
      });
    }

    function overview() {
      const checks = (st.detail && st.detail.checks) || [];
      const sig = d.signals || [];
      return `${kpis()}
      ${fam === 'regime' ? regimeTiles() : ''}
      ${st.detail && st.detail.basket ? basketTable(st.detail.basket) : ''}
      <section class="card col" style="gap:12px;padding:16px"><div id="ctool"></div><div id="chart" class="col" style="gap:18px"><div class="empty"><span class="spin"></span></div></div>
        <div class="muted small">Built with TradingView Lightweight Charts™. Lines are the bot's own calculations, the numbers the strategy trades on${fam === 'signal' ? '; futures prices are back-adjusted for contract rolls in the indicators.' : '.'}</div></section>
      <div class="grid" style="--min:360px">
        ${fam === 'signal' ? `<section class="card"><div class="eyebrow" style="margin-bottom:6px">Signal check · bar closed ${U.dt(st.bar_time)}</div>
          ${checks.map((r) => `<div class="kv"><span class="muted">${U.esc(r.k)}</span><span class="num ${r.cls || ''}">${U.esc(r.v)}</span></div>`).join('')}
          <a class="btn s" href="#/health" style="margin-top:10px">Cross-check with TradingView</a></section>` : ''}
        <section class="card ${fam === 'signal' ? 'span2' : ''}"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Holdings vs target · ${U.modeLabel[mode]}</h2></div>
          <div class="tw"><table class="t"><thead><tr><th>Holding</th><th class="r">Shares</th><th class="r">Value</th><th class="r">Now</th><th class="r">Target</th></tr></thead><tbody>
          ${d.holdings.map((h) => `<tr><td>${U.esc(h.symbol)}</td><td class="r num">${h.qty == null ? '—' : U.n(h.qty, 0)}</td><td class="r num">${U.usd(h.value)}</td>
            <td class="r num">${(h.now * 100).toFixed(1)}%</td><td class="r num">${(h.target * 100).toFixed(1)}%</td></tr>`).join('')}</tbody></table></div>
          <div class="muted small">${c.type === 'momentum_basket' ? 'Trades when the signal turns on or off, or when the weekly list changes. Names already held are never topped up or trimmed; new names get 1/' + U.esc(d.row.params.hold) + ' of the money.' : 'Trades on a new signal, or when a holding drifts more than ' + U.esc(d.row.params.rebalance_band_pct) + '% from target (e.g. after Add money).'}</div></section>
        ${fam === 'regime' ? `<section class="card"><h2 class="h2" style="margin-bottom:6px">State changes</h2>${sig.slice(0, 7).map((x) => `<div class="list-row" style="align-items:center">
          <span class="num muted small" style="width:64px;flex:none">${U.day(x.t)}</span>${x.kind === 'LIST' ? U.pill('', 'list') : U.pill('', x.from_state) + '<span class="muted">→</span>' + U.pill('info', x.to_state)}
          <span class="muted small wrap" style="margin-left:auto;text-align:right;min-width:0">${U.esc(x.text)}</span></div>`).join('') || '<div class="muted">None yet</div>'}</section>` : ''}
      </div>
      ${fam === 'regime' ? regimeLog() : signalsTable()}`;
    }

    function signalsTable() {
      const s = (d.signals || []).slice().sort((a, b) => a.t - b.t);
      const trades = [];
      let open = null;
      s.forEach((x) => { if (x.kind === 'BUY') open = x; else if (x.kind === 'SELL' && open) { trades.push([open, x]); open = null; } });
      if (open) trades.push([open, null]);
      trades.reverse();
      return `<section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Signals (${U.esc(d.row.params.symbol)}=F futures)</h2><a href="#/trades" class="small">ETF fills in Trades →</a></div>
        <div class="tw"><table class="t"><thead><tr><th>Buy signal (bar close)</th><th class="r">Close</th><th>Sell signal</th><th class="r">Close</th><th class="r">Move</th><th>Why</th></tr></thead><tbody>
        ${trades.map(([a, b]) => { const mv = b ? b.price / a.price - 1 : null; return `<tr><td class="num">${U.dt(a.t)}</td><td class="r num">${U.n(a.price, 2)}</td>
          <td class="num">${b ? U.dt(b.t) : U.pill('ok', 'open')}</td><td class="r num">${b ? U.n(b.price, 2) : '—'}</td><td class="r num ${U.cls(mv)}">${mv == null ? '—' : U.pct(mv, 2)}</td>
          <td class="muted small wrap">${U.esc((b || a).text)}</td></tr>`; }).join('') || '<tr><td colspan="6" class="muted">No signals yet</td></tr>'}</tbody></table></div></section>`;
    }

    function regimeLog() {
      const log = (st.detail && st.detail.log) || [];
      const p = d.row.params;
      const cols = st.detail && st.detail.log_cols;
      if (cols) {
        const f = (v, k) => k === 'n1' ? U.n(v, 1) : U.n(v, 2);
        return `<section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Daily log — the numbers each decision used</h2></div>
        <div class="tw"><table class="t"><thead><tr><th>Date (NY)</th>${cols.map((c) => `<th class="r">${U.esc(c.label)}</th>`).join('')}<th>State</th><th>Action</th></tr></thead><tbody>
        ${log.slice(0, 15).map((r) => `<tr><td class="num">${U.esc(r.date)}</td>${cols.map((c) => `<td class="r num">${f(r[c.k], c.fmt)}</td>`).join('')}
          <td>${U.pill(r.state === 'out' ? '' : r.state === 'dip' ? 'warn' : 'ok', r.state)}</td><td class="muted">${r.changed ? U.esc(r.from) + ' → ' + U.esc(r.state) + ' · ' + (r.state === 'out' ? 'sell plan' : 'buy plan') : 'no trade'}</td></tr>`).join('')}</tbody></table></div></section>`;
      }
      return `<section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Daily log — the numbers each decision used</h2></div>
        <div class="tw"><table class="t"><thead><tr><th>Date (NY)</th><th class="r">${U.esc(p.signal)}</th><th class="r">SMA${p.ma_days}</th><th class="r">SMA${p.confirm_days}</th><th class="r">Vol ${p.vol_days}d</th><th>State</th><th>Action</th></tr></thead><tbody>
        ${log.slice(0, 15).map((r) => `<tr><td class="num">${U.esc(r.date)}</td><td class="r num">${U.n(r.close, 2)}</td><td class="r num">${U.n(r.sma_long, 2)}</td><td class="r num">${U.n(r.sma_short, 2)}</td>
          <td class="r num">${(r.vol * 100).toFixed(1)}%</td><td>${U.pill('info', r.state)}</td><td class="muted">${r.changed ? 'state ' + U.esc(r.from) + ' → ' + U.esc(r.state) + ' · rebalance plan' : 'no trade'}</td></tr>`).join('')}</tbody></table></div></section>`;
    }

    function paramsForm() {
      const t = d.type;
      const groups = {};
      t.params.forEach((p) => (groups[p.group || 'Settings'] = groups[p.group || 'Settings'] || []).push(p));
      return `<section class="card col" style="gap:18px">
        <div class="note warn">Changing rules changes future signals only. The bot re-evaluates at the next tick and may trade if the new target differs from what it holds.</div>
        <div class="fs"><div class="f"><label for="nm">Name</label><input class="in" id="nm" value="${U.esc(c.name)}"></div>
          <div class="f"><label>Colour</label><div class="row" style="gap:8px">${PALETTE.map((x) => `<button type="button" class="dot" data-col="${x}" aria-label="Colour ${x}" style="width:26px;height:26px;border:0;cursor:pointer;background:${x};${x === c.color ? 'outline:2px solid var(--text);outline-offset:2px' : ''}"></button>`).join('')}</div></div></div>
        ${Object.entries(groups).map(([g, ps]) => `<div class="eyebrow">${U.esc(g)}</div><div class="fs">${ps.map((p) => field(p, d.row.params[p.key])).join('')}</div>`).join('')}
        <div class="row" style="justify-content:space-between"><button class="btn d s" id="arch">Archive strategy…</button><button class="btn p" id="savep">Save parameters</button></div></section>`;
    }

    function execForm() {
      const e = d.exec, ov = d.row.exec || {};
      return `<section class="card col" style="gap:16px"><h2 class="h2">Execution for this strategy</h2>
        <div class="muted small">Empty fields follow the defaults in <a href="#/execution">Execution settings</a>. Now: ${U.esc(d.exec_text)}.</div>
        <div class="fs">
          <div class="f"><label for="x-lots">Lots</label><input class="in num" id="x-lots" placeholder="${e.lots}" value="${U.esc(ov.lots || '')}"></div>
          <div class="f"><label for="x-int">Minutes between lots</label><input class="in num" id="x-int" placeholder="${e.interval_min}" value="${U.esc(ov.interval_min || '')}"></div>
          <div class="f"><label for="x-sm">Entries start</label><select class="in" id="x-sm"><option value="">default (${e.start_mode === 'time' ? 'at ' + e.start_time : 'market open'})</option>
            <option value="time" ${ov.start_mode === 'time' ? 'selected' : ''}>At a set Bangkok time</option><option value="asap" ${ov.start_mode === 'asap' ? 'selected' : ''}>As soon as the market is open</option></select></div>
          <div class="f"><label for="x-st">Start time (Bangkok)</label><input class="in num" id="x-st" placeholder="${e.start_time}" value="${U.esc(ov.start_time || '')}"></div>
          <div class="f"><label for="x-ex">Exits start</label><select class="in" id="x-ex"><option value="">default (${e.exit_mode === 'asap' ? 'as soon as open' : 'same as entries'})</option>
            <option value="asap" ${ov.exit_mode === 'asap' ? 'selected' : ''}>As soon as the market is open</option><option value="same" ${ov.exit_mode === 'same' ? 'selected' : ''}>Same as entries</option></select></div>
        </div><div class="row" style="justify-content:flex-end"><button class="btn p" id="savex">Save execution</button></div></section>`;
    }

    function history() {
      return `<section class="card"><h2 class="h2" style="margin-bottom:6px">Order plans · ${U.modeLabel[mode]}</h2>
        ${(d.plans || []).map((p) => V.planCard(p, true)).join('') || '<div class="muted">No plans yet</div>'}</section>
        <section class="card"><h2 class="h2" style="margin-bottom:6px">Money</h2><div class="tw"><table class="t"><thead><tr><th>When</th><th>Type</th><th class="r">Amount</th><th>Status</th><th>Note</th></tr></thead><tbody>
        ${(d.money || []).map((m) => `<tr><td class="num">${U.dt(m.t)}</td><td>${U.esc(m.kind)}</td><td class="r num">${U.usd(m.amount)}</td><td>${U.pill(m.status === 'done' ? 'ok' : 'warn', m.status)}</td><td class="muted small">${U.esc(m.note || '')}</td></tr>`).join('') || '<tr><td colspan="5" class="muted">None</td></tr>'}</tbody></table></div></section>`;
    }

    async function render() {
      if (chartObj) { chartObj.destroy(); chartObj = null; }
      if (btClean) { btClean(); btClean = null; }
      el.innerHTML = header() + (tab === 'overview' ? overview() : tab === 'backtest' || tab === 'charts' ? '<div id="bt" class="col" style="gap:20px"></div>' : tab === 'params' ? paramsForm() : tab === 'exec' ? execForm() : history());
      if (tab === 'backtest') btClean = V.backtestTab(el.querySelector('#bt'), sid, d);
      if (tab === 'charts') { btClean = V.symbolChartsTab(el.querySelector('#bt'), sid, d, chartSym); chartSym = null; }
      U.on(el, '[data-symc]', 'click', (e, b) => { e.preventDefault(); chartSym = b.dataset.symc; tab = 'charts'; render(); window.scrollTo(0, 0); });
      U.on(el, '[data-tab]', 'click', (e, b) => { tab = b.dataset.tab; render(); });
      U.on(el, '[data-money]', 'click', (e, b) => V.moneyDialog(b.dataset.money, sid, () => V.strategy(el, params)));
      U.on(el, '[data-ctl]', 'click', async (e, b) => {
        const cc = b.dataset.ctl;
        if (!(await U.confirm(cc === 'stopping' ? 'Stop & sell?' : cc === 'paused' ? 'Pause buys?' : 'Resume buys?',
          cc === 'stopping' ? 'Everything this strategy holds is sold with a split plan, in every trading mode.' : cc === 'paused' ? 'Exits still run; no new buys.' : 'It follows every signal again.',
          { danger: cc === 'stopping', word: cc === 'stopping' ? 'STOP' : null, ok: b.textContent }))) return;
        await U.api(`/api/strategies/${sid}/control`, { body: { control: cc } });
        U.toast('Saved'); V.strategy(el, params);
      });
      if (tab === 'overview') {
        el.querySelector('#ctool').innerHTML = chartToolbar();
        try { spec = spec || (await U.api(`/api/strategies/${sid}/chart?range=${cs.range}`)); } catch (e) { spec = { charts: [], error: e.message }; }
        drawChart();
      }
      if (tab === 'params') {
        let color = c.color;
        U.on(el, '[data-col]', 'click', (e, b) => { color = b.dataset.col; el.querySelectorAll('[data-col]').forEach((x) => (x.style.outline = x === b ? '2px solid var(--text)' : 'none')); });
        el.querySelector('#savep').onclick = (e) => U.busy(e.target, async () => {
          await U.api('/api/strategies/' + sid, { method: 'PATCH', body: { name: el.querySelector('#nm').value, color, params: readParams(el, d.type) } });
          U.toast('Parameters saved'); V.strategy(el, params);
        });
        el.querySelector('#arch').onclick = async () => {
          if (!(await U.confirm('Archive this strategy?', 'It must hold no money in any mode. Its history stays visible.', { danger: true, ok: 'Archive' }))) return;
          try { await U.api(`/api/strategies/${sid}/archive`, { body: { archive: true } }); location.hash = '#/strategies'; } catch (e) { U.toast(e.message, 'err'); }
        };
      }
      if (tab === 'exec') {
        el.querySelector('#savex').onclick = (e) => U.busy(e.target, async () => {
          const v = (id) => el.querySelector(id).value.trim();
          const ov = { lots: v('#x-lots'), interval_min: v('#x-int'), start_mode: v('#x-sm'), start_time: v('#x-st'), exit_mode: v('#x-ex') };
          await U.api('/api/settings/execution', { body: { overrides: { [sid]: ov } } });
          U.toast('Execution saved'); V.strategy(el, params);
        });
      }
    }
    await render();
    return () => { if (chartObj) chartObj.destroy(); if (btClean) btClean(); };
  };

  function field(p, val) {
    const v = val == null ? p.default : val;
    const id = 'p-' + p.key;
    let input;
    if (p.kind === 'select') input = `<select class="in" id="${id}">${p.options.map((o) => `<option ${o === v ? 'selected' : ''}>${U.esc(o)}</option>`).join('')}</select>`;
    else if (p.kind === 'bool') input = `<button type="button" class="sw ${v ? 'on' : ''}" id="${id}" role="switch" aria-checked="${!!v}"></button>`;
    else input = `<input class="in ${p.kind !== 'text' ? 'num' : ''}" id="${id}" value="${U.esc(v)}">`;
    return `<div class="f"><label for="${id}">${U.esc(p.label)}</label>${input}${p.help ? `<span class="h">${U.esc(p.help)}</span>` : ''}</div>`;
  }

  function readParams(el, type) {
    const out = {};
    type.params.forEach((p) => {
      const x = el.querySelector('#p-' + p.key);
      if (!x) return;
      out[p.key] = p.kind === 'bool' ? x.classList.contains('on') : x.value;
    });
    return out;
  }

  /* ---------------------------------------------------------------- add strategy wizard */
  V.strategyNew = async function (el) {
    const types = (await U.api('/api/strategy-types')).types;
    const w = { step: 1, type: null, name: '', color: PALETTE[0], params: {}, exec: {}, money: 10000 };
    let pv = null, timer = null;
    const T = () => types.find((t) => t.type === w.type);

    function steps() {
      return `<div class="row" style="gap:18px">${['Template', 'Rules & symbols', 'Money & execution', 'Review'].map((s, i) => {
        const n = i + 1, cls = n < w.step ? 'ok' : n === w.step ? 'warn' : '';
        return `<span class="row" style="gap:8px;color:${n === w.step ? 'var(--text)' : 'var(--muted)'};font-weight:500"><span class="pill ${cls}" style="width:26px;justify-content:center">${n < w.step ? '✓' : n}</span>${s}</span>`;
      }).join('')}</div>`;
    }

    function preview() {
      if (!pv) return '<div class="muted small">Fill in the rules to see what this strategy would hold today.</div>';
      if (!pv.ok) return `<div class="note warn">${U.esc(pv.error || 'No preview')}</div>`;
      return `<div class="muted small">With today's data it would be in:</div><div style="font-weight:600;font-size:16px">${U.esc(pv.label)}</div>
        ${(pv.checks || []).map((r) => `<div class="kv"><span class="muted">${U.esc(r.k)}</span><span class="num ${r.cls || ''}">${U.esc(r.v)}</span></div>`).join('')}
        ${pv.changes_12m != null ? `<div class="kv"><span class="muted">Signals / state changes, last 12 months</span><span class="num">${pv.changes_12m}</span></div>` : ''}`;
    }

    async function refreshPreview() {
      const box = el.querySelector('#pv');
      if (!box) return;
      box.innerHTML = '<span class="spin"></span>';
      try { pv = await U.api('/api/strategies/preview', { body: { type: w.type, params: w.params, name: w.name } }); } catch (e) { pv = { ok: false, error: e.message }; }
      if (el.querySelector('#pv')) el.querySelector('#pv').innerHTML = preview();
    }

    function body() {
      if (w.step === 1) return `<div class="grid" style="--min:240px">${types.map((t) => `<button type="button" class="card col" data-type="${t.type}" style="text-align:left;cursor:pointer;gap:6px;color:var(--text);${w.type === t.type ? 'border-color:var(--accent)' : ''}">
        <b>${U.esc(t.label)}</b><span class="muted small">${U.esc(t.description)}</span><span class="pill" style="align-self:flex-start">${t.timeframe}</span></button>`).join('')}
        <div class="card col" style="gap:6px"><b>Custom Python plugin</b><span class="muted small">Put a module in app/strategies/ with a class marked @register. Its PARAMS build this form automatically. See Docs → Add a strategy plugin.</span></div></div>`;
      const t = T();
      if (w.step === 2) {
        const groups = {};
        t.params.forEach((p) => (groups[p.group || 'Settings'] = groups[p.group || 'Settings'] || []).push(p));
        return `<div class="grid" style="--min:380px"><section class="card span2 col" style="gap:18px">
          <div class="fs"><div class="f"><label for="w-name">Name</label><input class="in" id="w-name" value="${U.esc(w.name)}" placeholder="e.g. TQQQ regime (test)"></div>
            <div class="f"><label>Colour</label><div class="row" style="gap:8px">${PALETTE.map((x) => `<button type="button" class="dot" data-col="${x}" aria-label="Colour" style="width:26px;height:26px;border:0;cursor:pointer;background:${x};${x === w.color ? 'outline:2px solid var(--text);outline-offset:2px' : ''}"></button>`).join('')}</div></div></div>
          ${Object.entries(groups).map(([g, ps]) => `<div class="eyebrow">${U.esc(g)}</div><div class="fs">${ps.map((p) => field(p, w.params[p.key])).join('')}</div>`).join('')}
        </section><section class="card col" style="gap:10px;align-self:flex-start"><h2 class="h2">Live preview</h2><div id="pv" class="col" style="gap:6px">${preview()}</div></section></div>`;
      }
      if (w.step === 3) return `<section class="card col" style="gap:16px">
        <div class="fs"><div class="f"><label for="w-money">Paper money to start with</label><input class="in num" id="w-money" value="${w.money}"><span class="h">Only the Paper account gets money now. For Webull test or Live, use Money → Add money when you are ready.</span></div></div>
        <div class="eyebrow">Execution (empty = defaults${t.exec_defaults && Object.keys(t.exec_defaults).length ? '; this type suggests ' + U.esc(Object.entries(t.exec_defaults).map(([k, v]) => k + ' ' + v).join(', ')) : ''})</div>
        <div class="fs"><div class="f"><label for="w-lots">Lots</label><input class="in num" id="w-lots" value="${U.esc(w.exec.lots || '')}"></div>
          <div class="f"><label for="w-int">Minutes between lots</label><input class="in num" id="w-int" value="${U.esc(w.exec.interval_min || '')}"></div>
          <div class="f"><label for="w-sm">Entries start</label><select class="in" id="w-sm"><option value="">default</option><option value="time">At a set Bangkok time</option><option value="asap">As soon as the market is open</option></select></div>
          <div class="f"><label for="w-st">Start time (Bangkok)</label><input class="in num" id="w-st" value="${U.esc(w.exec.start_time || '')}" placeholder="22:00"></div></div></section>`;
      return `<section class="card col" style="gap:10px"><h2 class="h2">Review</h2>
        <div class="kv"><span class="muted">Name</span><span>${U.dot(w.color)} ${U.esc(w.name)}</span></div>
        <div class="kv"><span class="muted">Type</span><span>${U.esc(t.label)}</span></div>
        ${t.params.map((p) => `<div class="kv"><span class="muted">${U.esc(p.label)}</span><span class="num">${U.esc(w.params[p.key] == null ? p.default : w.params[p.key])}</span></div>`).join('')}
        <div class="kv"><span class="muted">Paper money</span><span class="num">${U.usd(+w.money)}</span></div>
        <div id="pv" class="col" style="gap:6px;margin-top:8px">${preview()}</div>
        <div class="note info">The strategy starts Active in Paper mode. Watch it for a while before giving it real money.</div></section>`;
    }

    function collect() {
      if (w.step === 2) {
        w.name = el.querySelector('#w-name').value.trim();
        w.params = readParams(el, T());
      }
      if (w.step === 3) {
        w.money = el.querySelector('#w-money').value;
        w.exec = { lots: el.querySelector('#w-lots').value, interval_min: el.querySelector('#w-int').value, start_mode: el.querySelector('#w-sm').value, start_time: el.querySelector('#w-st').value };
        Object.keys(w.exec).forEach((k) => { if (!w.exec[k]) delete w.exec[k]; });
      }
    }

    function render() {
      el.innerHTML = `<div class="crumb"><a href="#/strategies">Strategies</a> / New strategy</div>
        <div class="page-head"><div><h1 class="h1">Add a strategy</h1><div class="muted" style="margin-top:4px">New strategies start in Paper mode. You decide when they get real money.</div></div><a class="btn" href="#/strategies">Cancel</a></div>
        ${steps()}${body()}
        <div class="row" style="justify-content:flex-end">${w.step > 1 ? '<button class="btn" id="back">Back</button>' : ''}
          ${w.step < 4 ? `<button class="btn p" id="next" ${w.step === 1 && !w.type ? 'disabled' : ''}>Next</button>` : '<button class="btn p" id="create">Create strategy</button>'}</div>`;
      U.on(el, '[data-type]', 'click', (e, b) => { w.type = b.dataset.type; w.params = {}; T().params.forEach((p) => (w.params[p.key] = p.default)); w.exec = Object.assign({}, T().exec_defaults); render(); });
      U.on(el, '[data-col]', 'click', (e, b) => { collect(); w.color = b.dataset.col; render(); });
      const nx = el.querySelector('#next');
      if (nx) nx.onclick = () => { collect(); if (w.step === 2 && !w.name) { U.toast('Give it a name', 'err'); return; } w.step++; render(); if (w.step === 4) refreshPreview(); };
      const bk = el.querySelector('#back');
      if (bk) bk.onclick = () => { collect(); w.step--; render(); };
      if (w.step === 2) {
        el.querySelectorAll('.in, .sw').forEach((x) => x.addEventListener(x.classList.contains('sw') ? 'click' : 'input', () => {
          if (x.classList.contains('sw')) x.classList.toggle('on');
          clearTimeout(timer); timer = setTimeout(() => { collect(); refreshPreview(); }, 600);
        }));
        refreshPreview();
      }
      const cr = el.querySelector('#create');
      if (cr) cr.onclick = (e) => U.busy(e.target, async () => {
        const r = await U.api('/api/strategies', { body: { type: w.type, name: w.name, color: w.color, params: w.params, exec: w.exec, paper_money: +w.money || 0 } });
        U.toast('Strategy created'); location.hash = '#/strategies/' + r.id;
      });
    }
    render();
  };
})();
