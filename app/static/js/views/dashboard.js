(function () {
  const V = window.Views || (window.Views = {});

  function equityChart(el, series, days) {
    el.innerHTML = '';
    const since = Date.now() / 1000 - days * 86400;
    const pts = series.filter((p) => p.t >= since);
    if (pts.length < 2) { el.innerHTML = '<div class="empty small">The value chart fills in as the bot records its value every 30 minutes.</div>'; return null; }
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const ch = LightweightCharts.createChart(el, { autoSize: true, layout: { background: { type: 'solid', color: 'transparent' }, textColor: css('--chart-text'), fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: css('--chart-grid') } }, rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: days <= 7 }, crosshair: { mode: 0 }, handleScroll: false, handleScale: false,
      localization: { priceFormatter: (p) => '$' + Math.round(p).toLocaleString('en-US'), timeFormatter: (t) => U.dtLong(t) } });
    const a = ch.addAreaSeries({ lineColor: css('--accent'), topColor: css('--accent') + '30', bottomColor: css('--accent') + '00', lineWidth: 2, priceLineVisible: false });
    a.setData(pts.map((p) => ({ time: p.t, value: p.value })));
    const b = ch.addLineSeries({ color: '#7C8798', lineWidth: 2, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    b.setData(pts.filter((p) => p.bench != null).map((p) => ({ time: p.t, value: p.bench })));
    ch.timeScale().fitContent();
    return ch;
  }

  V.dashboard = async function (el) {
    const mode = U.mode();
    let chart = null, range = 90;
    async function load() {
      const d = await U.api('/api/dashboard?mode=' + mode);
      const b = d.bot, acct = d.account || {};
      const split = d.strategies.map((s) => ({ name: s.name, color: s.color, v: s.value }));
      if (d.unassigned) split.push({ name: 'Bot unassigned', color: 'var(--accent)', v: Math.max(0, d.unassigned) });
      if (d.not_bot != null) split.push({ name: 'Not for the bot', color: 'var(--line)', v: Math.max(0, d.not_bot) });
      const tot = acct.total || split.reduce((x, y) => x + y.v, 0);
      const today = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date());
      const h = d.health;
      el.innerHTML = `
      <div class="page-head"><div><div class="eyebrow">${U.esc(today)} · ${U.modeLabel[mode]} account</div><h1 class="h1">Dashboard</h1></div>
        <div class="row"><a class="btn" href="#/health">Run cross-check</a><button class="btn p" type="button" id="add">Add money</button></div></div>
      ${d.account_error ? `<div class="note warn">Account not readable: ${U.esc(d.account_error)}</div>` : ''}
      <div class="grid" style="--min:340px">
        <section class="card span2 col" style="gap:14px">
          <div class="row sb" style="align-items:flex-start">
            <div><div class="eyebrow">Bot equity · ${d.strategies.length} strategies</div>
              <div class="num huge" style="margin-top:6px">${U.usd(b.value)}</div>
              <div class="row" style="gap:18px;margin-top:8px">
                <span>Today <b class="num ${U.cls(b.today)}">${b.today == null ? '—' : U.sgnUsd(b.today) + ' (' + U.pct(b.today_pct, 2) + ')'}</b></span>
                <span>Since start <b class="num ${U.cls(b.pnl)}">${U.sgnUsd(b.pnl)} (${U.pct(b.ret, 2)})</b></span>
                <span>vs buy &amp; hold <b class="num ${U.cls((b.ret || 0) - (b.bench_ret || 0))}">${b.bench_ret == null ? '—' : ((((b.ret || 0) - b.bench_ret) * 100 >= 0 ? '+' : '') + (((b.ret || 0) - b.bench_ret) * 100).toFixed(1) + ' pts')}</b></span>
              </div></div>
            <div class="seg" id="rng"><button data-d="7">1W</button><button data-d="30">1M</button><button data-d="90" class="on">3M</button></div>
          </div>
          <div id="eq" style="height:220px"></div>
          <div class="row small muted" style="gap:18px"><span class="row" style="gap:6px"><i style="width:16px;height:3px;background:var(--accent);display:inline-block"></i>Bot</span>
            <span class="row" style="gap:6px"><i style="width:16px;border-top:2px dashed #7C8798;display:inline-block"></i>Buy &amp; hold the same ETFs</span></div>
        </section>
        <section class="card col" style="gap:12px">
          <div class="eyebrow">${U.modeLabel[mode]} account split</div>
          <div class="num big">${U.usd(tot)}</div>
          <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;gap:2px">${split.map((s) => `<div style="flex:${Math.max(s.v, 0.0001)};background:${s.color}" title="${U.esc(s.name)}"></div>`).join('')}</div>
          <div>${split.map((s) => `<div class="kv" style="padding:7px 0"><span class="row" style="gap:10px;flex-wrap:nowrap;min-width:0">${U.dot(s.color)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(s.name)}</span></span>
            <span class="row" style="gap:12px"><span class="num">${U.usd(s.v, 0)}</span><span class="num muted" style="width:50px;text-align:right">${tot ? (s.v / tot * 100).toFixed(1) + '%' : '—'}</span></span></div>`).join('')}</div>
          <a href="#/money" class="small" style="font-weight:500">Manage money →</a>
        </section>
      </div>
      <div id="alloc"></div>
      <div class="grid" style="--min:230px">
        <a class="card" href="#/money" style="color:var(--text)"><div class="eyebrow">Bot unassigned</div><div class="num big" style="margin-top:6px">${U.usd(d.unassigned)}</div><div class="muted small">Given to the bot, not yet to a strategy${d.not_bot != null ? ' · ' + U.usd(d.not_bot, 0) + ' not for the bot' : ''}</div></a>
        <a class="card" href="#/orders" style="color:var(--text)"><div class="eyebrow">Order plans</div><div class="num big" style="margin-top:6px">${d.plans.length} active</div>
          <div class="muted small">${d.plans[0] ? U.esc(d.plans[0].name) + ' · ' + (d.plans[0].state === 'queued' ? 'starts ' + U.time(d.plans[0].start_at) : 'running') : 'Nothing waiting'}</div></a>
        <a class="card" href="#/health" style="color:var(--text)"><div class="eyebrow">Last cross-check${h ? ' · ' + U.dt(h.t) : ''}</div>
          <div class="big" style="margin-top:6px">${h ? `${h.counts.ok} ok${h.counts.warn ? ` · <span style="color:var(--warn-fg)">${h.counts.warn} warning${h.counts.warn > 1 ? 's' : ''}</span>` : ''}${h.counts.error ? ` · <span class="dn">${h.counts.error} problem${h.counts.error > 1 ? 's' : ''}</span>` : ''}` : 'Not run yet'}</div>
          <div class="muted small">${h && h.first ? U.esc(h.first.title) : 'Runs after every US close'}</div></a>
        <a class="card" href="#/line" style="color:var(--text)"><div class="eyebrow">LINE · last 24 h</div><div class="num big" style="margin-top:6px">${d.line.sent_24h} sent · ${d.line.failed_24h} failed</div>
          <div class="muted small">${d.line.configured ? 'Next digest ' + (d.line.next_digest || '—') : 'Not set up yet'}${d.line.quota && d.line.quota.limit ? ` · ${d.line.quota.used}/${d.line.quota.limit} this month` : ''}</div></a>
      </div>
      <div class="row sb"><h2 class="h2" style="font-size:18px">Strategies</h2><a href="#/strategies" class="small">All strategies →</a></div>
      <div class="grid" style="--min:300px">${d.strategies.map((s) => `
        <a class="card scard" href="#/strategies/${s.id}">
          <div class="row" style="gap:10px">${U.dot(s.color, 10)}<b style="font-size:15px">${U.esc(s.name)}</b><span class="pill" style="margin-left:auto">${s.type === 'momentum_basket' ? 'Stock basket' : s.family === 'regime' ? 'Daily regime' : '4H signal'}</span></div>
          <div class="row sb" style="align-items:flex-end">
            <div><div class="num big" style="font-size:22px">${U.usd(s.value, 0)}</div><div class="num small ${U.cls(s.pnl)}">${U.sgnUsd(s.pnl, 0)} · ${U.pct(s.ret)}</div></div>
            ${U.spark(s.spark, s.color)}</div>
          <div class="row sb" style="gap:8px;align-items:flex-end">${U.stateBlock(s)}
            <div class="col" style="gap:4px;align-items:flex-end">${s.control !== 'active' ? U.pill('warn', s.control) : ''}
            <span class="muted small" style="text-align:right">${s.next_check ? 'Next check ' + U.dt(s.next_check) : ''}</span></div></div>
        </a>`).join('')}</div>
      <div class="grid" style="--min:380px">
        <section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Next up (Bangkok time)</h2><a href="#/execution" class="small">Schedule →</a></div>
          ${d.next.map((n) => `<div class="list-row"><div class="num" style="width:96px;font-weight:600;color:var(--accent)">${U.dt(n.t).replace('Today ', '')}</div>
            <div style="flex:1;min-width:0"><div style="font-weight:500">${U.esc(n.title)}</div><div class="muted small">${U.esc(n.sub)}</div></div></div>`).join('') || '<div class="empty">Nothing scheduled</div>'}</section>
        <section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">Recent activity</h2><a href="#/logs" class="small">All logs →</a></div>
          ${d.events.map((e) => `<div class="list-row">${U.pill(e.level === 'error' ? 'err' : e.level === 'warn' ? 'warn' : '', e.source)}
            <div style="flex:1;min-width:0"><div style="font-weight:500">${U.esc(e.title)}</div><div class="muted small" style="overflow:hidden;text-overflow:ellipsis">${U.esc((e.message || '').slice(0, 160))}</div></div>
            <div class="num muted small nowrap">${U.dt(e.t)}</div></div>`).join('') || '<div class="empty">No activity yet</div>'}</section>
      </div>`;
      if (chart) chart.remove();
      V.renderAlloc(el.querySelector('#alloc'), d.strategies);
      chart = equityChart(el.querySelector('#eq'), d.series, range);
      el.querySelector('#rng').onclick = (e) => {
        const btn = e.target.closest('button'); if (!btn) return;
        range = +btn.dataset.d;
        el.querySelectorAll('#rng button').forEach((x) => x.classList.toggle('on', x === btn));
        if (chart) chart.remove();
        chart = equityChart(el.querySelector('#eq'), d.series, range);
      };
      el.querySelector('#add').onclick = () => (d.unassigned > 0 ? V.splitDialog(load) : V.fundDialog('in', load));
    }
    await load();
    return { cleanup: () => { if (chart) chart.remove(); }, refresh: () => load().catch(() => {}), every: 60000 };
  };
})();
