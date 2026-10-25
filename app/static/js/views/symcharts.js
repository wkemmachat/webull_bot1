/* Strategy page → Stock charts tab (stock-basket strategies): a candle chart of every symbol the strategy trades,
   with the backtest's buys and sells and the bot's own fills, to cross-check each trade (app/symcharts.py). */
(function () {
  const V = window.Views || (window.Views = {});
  const DAY = 86400;
  const tOf = (s) => Math.floor(Date.parse(s + 'T00:00:00Z') / 1000);
  const dayTxt = (s) => s ? new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(tOf(s) * 1000)) : '—';
  const px = (v) => v == null ? '—' : '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const P = (v) => v == null || isNaN(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%';
  const RANGES = [['6M', 182], ['1Y', 365], ['3Y', 1095], ['5Y', 1826], ['ALL', 0]];
  const KIND = { signal: 'Signal', stock: 'Stock', '2x ETF': '2x ETF', parking: 'Parking' };

  V.symbolChartsTab = function (host, sid, d, startSym) {
    const st = { data: null, sym: startSym || null, range: '1Y', chart: null, candle: null };

    function destroy() { if (st.chart) { try { st.chart.remove(); } catch (e) {} st.chart = null; } }

    async function load(sym) {
      destroy();
      const first = !st.data;
      if (first) host.innerHTML = `<section class="card col" style="gap:10px;align-items:center;padding:40px 20px"><span class="spin"></span>
        <div class="muted small" style="text-align:center;max-width:460px">Loading the backtest and the price history. The first time can take up to a minute.</div></section>`;
      else { const b = host.querySelector('#sc-box'); if (b) b.style.opacity = '.5'; }
      let r;
      try {
        r = await U.api(`/api/backtest/${sid}/chart` + (sym ? '?sym=' + encodeURIComponent(sym) : ''));
      } catch (e) { r = { ok: false, error: e.message }; }
      if (!r.ok) {
        if (st.data) { U.toast(r.error, 'err'); const b = host.querySelector('#sc-box'); if (b) b.style.opacity = '1'; return; }
        host.innerHTML = `<div class="note err" style="flex-direction:column;align-items:flex-start;gap:6px"><b>Charts not available yet</b><span>${U.esc(r.error)}</span>
          <span class="muted">They come from the backtest. Open the Backtest tab once, then come back.</span></div>`;
        return;
      }
      st.data = r; st.sym = r.sym;
      render();
    }

    function chips() {
      const g = { signal: [], held: [], before: [], parking: [] };
      st.data.symbols.forEach((s) => (s.kind === 'signal' ? g.signal : s.kind === 'parking' ? g.parking : s.held ? g.held : g.before).push(s));
      const chip = (s) => `<button class="tg ${s.sym === st.sym ? 'on' : ''}" data-sym="${U.esc(s.sym)}" aria-pressed="${s.sym === st.sym}"
        title="${U.esc((KIND[s.kind] || s.kind) + (s.under ? ' of ' + s.under : '') + ' · bought ' + s.buys + ' times')}">
        ${s.held ? '<i style="background:var(--up)"></i>' : ''}<b>${U.esc(s.sym)}</b><span class="muted small num">${s.kind === 'signal' ? 'on ' + s.buys + '×' : s.buys + '×'}</span></button>`;
      const grp = (title, arr, hint) => arr.length ? `<div class="col" style="gap:6px"><div class="eyebrow">${title}${hint ? ` <span class="muted" style="text-transform:none;letter-spacing:0">· ${hint}</span>` : ''}</div>
        <div class="row" style="gap:6px;flex-wrap:wrap">${arr.map(chip).join('')}</div></div>` : '';
      return `<section class="card col" style="gap:12px"><div class="row sb"><h2 class="h2">Every trade on its chart</h2>
          <span class="muted small">Backtest ${dayTxt(st.data.backtest_from)} – now · number = times bought · green mark = held now</span></div>
        ${grp('Signal', g.signal, 'when the strategy goes in and out')}
        ${grp('Held now', g.held)}
        ${grp('Traded before', g.before)}
        ${grp('Parking when off', g.parking)}</section>`;
    }

    function chartCard() {
      const r = st.data, i = r.info || {};
      const sig = i.kind === 'signal';
      return `<section class="card col" id="sc-box" style="gap:10px;padding:16px">
        <div class="row sb" style="gap:8px;flex-wrap:wrap"><div class="row" style="gap:10px;flex-wrap:wrap"><span class="h2">${U.esc(r.sym)}</span>
          ${U.pill(sig ? 'info' : i.kind === 'parking' ? '' : 'ok', KIND[i.kind] || i.kind || '')}${i.under ? U.pill('', '2x of ' + i.under) : ''}
          ${i.held ? U.pill('ok', 'held now') : ''}${r.drawn_on !== r.sym ? U.pill('warn', 'drawn on ' + r.drawn_on) : ''}</div>
          <a class="btn s" href="${U.esc(r.tv)}" target="_blank" rel="noopener">Open ${U.esc(r.tv_symbol)} in TradingView ↗</a></div>
        <div class="row sb" style="gap:8px;flex-wrap:wrap"><div class="seg" id="sc-rng">${RANGES.map(([k]) => `<button data-r="${k}" class="${st.range === k ? 'on' : ''}">${k === 'ALL' ? 'All' : k}</button>`).join('')}</div>
          <div class="row muted small" style="gap:14px;flex-wrap:wrap">${sig
            ? '<span><b style="color:#2962FF">▲ On</b> signal in</span><span><b style="color:#E040FB">▼ Off</b> signal out</span>'
            : '<span><b style="color:#26A69A">▲ Buy</b> backtest</span><span><b style="color:#EF5350">▼ Sell</b> backtest</span>'}
            <span><b style="color:#2962FF">●</b> the bot's own fill</span></div></div>
        <div class="tvwrap"><div id="sc-chart" style="height:${window.innerWidth < 600 ? 340 : 460}px;position:relative"><div class="tvlegend" id="sc-leg"></div></div></div>
        ${r.notes.length ? `<ul class="muted small" style="margin:0;padding-left:18px;display:flex;flex-direction:column;gap:3px">${r.notes.map((n) => `<li>${U.esc(n)}</li>`).join('')}</ul>` : ''}
        <div class="muted small">Candles: Yahoo daily, split-adjusted, without dividends — the same prices as TradingView and Webull. ${sig
          ? 'Each marker is the close where the signal changed; the stocks are bought or sold at the next open.'
          : 'Each marker is the day of the trade: the backtest buys and sells at that day\'s open (the price shown in the table).'}</div></section>`;
    }

    function tripsTable() {
      const r = st.data;
      if (r.info.kind === 'signal') {
        return `<section class="card col" style="gap:8px"><h2 class="h2">Signal changes (${r.events.length})</h2>
          <div class="tw"><table class="t"><thead><tr><th>Signal on the close of</th><th></th><th class="r">${U.esc(r.sym)} close</th><th>Stocks traded at the open of</th><th>Why</th></tr></thead><tbody>
          ${r.events.map((e) => `<tr class="click" data-go="${e.day}" data-to="${e.day}"><td class="num">${dayTxt(e.day)}</td><td>${U.pill(e.side === 'ON' ? 'ok' : 'err', e.side === 'ON' ? 'On' : 'Off')}</td>
            <td class="r num">${px(e.price)}</td><td class="num">${dayTxt(e.fill_day)}</td><td class="muted small wrap" style="max-width:380px">${U.esc(e.why || e.reason)}</td></tr>`).join('')
            || '<tr><td colspan="5" class="muted">No signal changes</td></tr>'}</tbody></table></div></section>`;
      }
      const tr = r.trips;
      const won = tr.filter((x) => x.sell_day && x.ret > 0).length, closed = tr.filter((x) => x.sell_day).length;
      return `<section class="card col" style="gap:8px"><div class="row sb"><h2 class="h2">Round trips in ${U.esc(r.sym)} (${tr.length})</h2>
          <span class="muted small">${closed ? won + ' of ' + closed + ' closed trips made money' : ''} · tap a row to see it on the chart</span></div>
        <div class="tw"><table class="t"><thead><tr><th>Bought (open)</th><th class="r">Price</th><th>Sold (open)</th><th class="r">Price</th><th class="r">Change</th><th class="r">Days</th><th>Why in → why out</th></tr></thead><tbody>
        ${tr.map((x) => `<tr class="click" data-go="${x.buy_day}" data-to="${x.sell_day || r.last}"><td class="num">${dayTxt(x.buy_day)}${x.sim ? ' <span class="muted small">2x sim</span>' : ''}</td>
          <td class="r num">${px(x.buy_price)}</td><td class="num">${x.sell_day ? dayTxt(x.sell_day) : U.pill('ok', 'still held')}</td>
          <td class="r num">${px(x.sell_price)}${x.sell_day ? '' : ' <span class="muted small">last</span>'}</td>
          <td class="r num ${x.ret > 0 ? 'up' : x.ret < 0 ? 'dn' : ''}">${P(x.ret)}</td><td class="r num">${x.days == null ? '—' : x.days}</td>
          <td class="muted small wrap" style="max-width:320px">${U.esc(x.in)} → ${U.esc(x.out)}</td></tr>`).join('') || '<tr><td colspan="7" class="muted">Never bought in the backtest</td></tr>'}
        </tbody></table></div>
        <div class="muted small">Change uses the plain prices (no dividends), so it can differ a little from the backtest, which counts dividends.</div></section>`;
    }

    function liveTable() {
      const l = st.data.live;
      if (!l.length) return `<section class="card col" style="gap:6px"><h2 class="h2">The bot's own trades in ${U.esc(st.data.sym)}</h2>
        <div class="muted small">None yet. When the bot trades ${U.esc(st.data.sym)} for this strategy (Paper, Webull test or Live), its fills appear here and as ● on the chart.</div></section>`;
      return `<section class="card col" style="gap:8px"><h2 class="h2">The bot's own trades in ${U.esc(st.data.sym)} (${l.length})</h2>
        <div class="tw"><table class="t"><thead><tr><th>Day (New York)</th><th>Mode</th><th></th><th class="r">Shares</th><th class="r">Average price</th><th class="r">Orders</th></tr></thead><tbody>
        ${l.map((f) => `<tr class="click" data-go="${f.day}" data-to="${f.day}"><td class="num">${dayTxt(f.day)}</td><td>${U.esc(f.mode_label)}</td><td>${U.pill(f.side === 'BUY' ? 'ok' : 'err', f.side === 'BUY' ? 'Buy' : 'Sell')}</td>
          <td class="r num">${U.n(f.qty, 4)}</td><td class="r num">${px(f.price)}</td><td class="r num">${f.orders}</td></tr>`).join('')}</tbody></table></div></section>`;
    }

    function setRange(k) {
      st.range = k;
      if (!st.chart) return;
      const cs = st.data.candles;
      if (!cs.length) return;
      const last = cs[cs.length - 1].time, days = (RANGES.find((x) => x[0] === k) || [0, 0])[1];
      if (!days) st.chart.timeScale().fitContent();
      else st.chart.timeScale().setVisibleRange({ from: Math.max(cs[0].time, last - days * DAY), to: last + 3 * DAY });
      host.querySelectorAll('#sc-rng button').forEach((b) => b.classList.toggle('on', b.dataset.r === k));
    }

    function draw() {
      destroy();
      const r = st.data, el = host.querySelector('#sc-chart');
      const ch = Charts.base(el, { daily: true, timeVisible: true });
      const cd = ch.addCandlestickSeries({ upColor: '#26A69A', downColor: '#EF5350', borderVisible: false, wickUpColor: '#26A69A', wickDownColor: '#EF5350' });
      cd.setData(r.candles);
      cd.setMarkers(r.markers);
      st.chart = ch; st.candle = cd;
      const leg = host.querySelector('#sc-leg');
      const byT = new Map(r.candles.map((x) => [x.time, x]));
      const mk = new Map();
      r.markers.forEach((m) => mk.set(m.time, (mk.get(m.time) ? mk.get(m.time) + ' · ' : '') + m.text));
      const f = (v) => Number(v).toLocaleString('en-US', { maximumFractionDigits: v < 100 ? 3 : 2 });
      const show = (bar) => {
        if (!bar) return;
        const col = bar.close >= bar.open ? '#26A69A' : '#EF5350';
        const day = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(bar.time * 1000));
        leg.innerHTML = `<span>${U.esc(r.drawn_on)} · ${day}</span>` + ['open', 'high', 'low', 'close'].map((k) => `<span style="color:${col}">${k[0].toUpperCase()} <b class="num" style="font-weight:500">${f(bar[k])}</b></span>`).join('')
          + (mk.get(bar.time) ? `<span><b>${U.esc(mk.get(bar.time))}</b></span>` : '');
      };
      show(r.candles[r.candles.length - 1]);
      ch.subscribeCrosshairMove((p) => show(p.time ? byT.get(p.time) : r.candles[r.candles.length - 1]));
      setRange(st.range);
    }

    function render() {
      host.innerHTML = `${st.data.source === 'csv' ? '<div class="note warn"><span>Demo prices (random, not real) — this copy runs without internet.</span></div>' : ''}
        ${chips()}${chartCard()}${tripsTable()}${liveTable()}`;
      draw();
      U.on(host, '[data-sym]', 'click', (e, b) => { if (b.dataset.sym !== st.sym) load(b.dataset.sym); });
      U.on(host, '#sc-rng button', 'click', (e, b) => setRange(b.dataset.r));
      U.on(host, 'tr[data-go]', 'click', (e, tr) => {
        if (!st.chart) return;
        const a = tOf(tr.dataset.go), z = tOf(tr.dataset.to || tr.dataset.go);
        const pad = Math.max(25 * DAY, (z - a) * 0.4);
        st.chart.timeScale().setVisibleRange({ from: a - pad, to: z + pad });
        host.querySelectorAll('#sc-rng button').forEach((b) => b.classList.remove('on'));
        host.querySelector('#sc-box').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    load(st.sym);
    return destroy;
  };
})();
