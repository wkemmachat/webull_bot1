(function () {
  const V = window.Views || (window.Views = {});

  V.health = async function (el) {
    const strats = (await U.api('/api/strategies?mode=' + U.mode())).strategies;
    let pick = strats[0] && strats[0].id;
    async function load() {
      const d = await U.api('/api/health/report');
      const r = d.latest;
      const hist = d.history.slice(-20);
      const col = (h) => h.err ? 'var(--dn)' : h.warn ? 'var(--warn-fg)' : 'var(--up)';
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">Error cross-check</div><h1 class="h1">Health check</h1>
        <div class="muted" style="margin-top:4px">Runs every trading day after the US close (16:45 New York). It only reads: it never places, changes or cancels an order.</div></div>
        <div class="row"><button class="btn p" id="run">Run check now</button></div></div>
        <div class="grid" style="--min:320px">
          <section class="card col" style="gap:10px"><div class="eyebrow">Last run${r ? ' · ' + U.dtLong(r.t) + ' · ' + r.took + ' s' : ''}</div>
            ${r ? `<div class="row" style="gap:14px"><span style="font-size:30px;font-weight:600">${r.counts.error ? 'Needs attention' : 'All good'}</span>
              ${r.counts.warn ? U.pill('warn', r.counts.warn + ' warning' + (r.counts.warn > 1 ? 's' : '')) : ''}${r.counts.error ? U.pill('err', r.counts.error + ' problem' + (r.counts.error > 1 ? 's' : '')) : ''}</div>
              <div class="row num" style="gap:18px"><span class="up">${r.counts.ok} ok</span><span style="color:var(--warn-fg)">${r.counts.warn} warning</span><span class="${r.counts.error ? 'dn' : 'muted'}">${r.counts.error} problems</span></div>` : '<div class="muted">Not run yet. Press Run check now.</div>'}
            <div class="muted small">Problems go to LINE at once (critical). Warnings go in the digest.</div></section>
          <section class="card span2 col" style="gap:10px"><div class="row sb"><span class="eyebrow">Last ${hist.length} runs</span></div>
            <div class="days">${hist.map((h) => `<span title="${U.dtLong(h.t)}: ${h.ok} ok, ${h.warn} warn, ${h.err} problems" style="background:${col(h)};opacity:.85"></span>`).join('')}</div>
            <div class="row sb muted small num"><span>${hist[0] ? U.day(hist[0].t) : ''}</span><span>${hist.length ? U.day(hist[hist.length - 1].t) : ''}</span></div></section>
        </div>
        ${r ? `<section class="card" style="padding:6px 20px">${r.items.map((i) => `<div class="chk"><div class="ic ${i.status}">${i.status === 'ok' ? '✓' : '!'}</div>
          <div class="col" style="gap:3px;min-width:0"><div class="row" style="gap:10px"><b style="font-weight:500">${i.n}. ${U.esc(i.title)}</b><span class="muted small">${U.esc(i.group)}</span></div>
            <span class="muted small">${U.esc(i.detail)}</span>${i.fix ? `<div class="note warn" style="margin-top:6px;font-size:13px"><span><b>What to do</b> · ${U.esc(i.fix)}</span></div>` : ''}</div>
          ${i.link ? `<a class="btn s" href="${U.esc(i.link)}">Open</a>` : '<span></span>'}</div>`).join('')}</section>` : ''}
        <section class="card col" style="gap:10px;min-width:0"><div class="row sb"><h2 class="h2">Indicator cross-check</h2>
          <div class="seg" id="ip">${strats.map((s) => `<button data-s="${s.id}" class="${pick === s.id ? 'on' : ''}">${U.esc(s.name.split(' · ')[0])}</button>`).join('')}</div></div>
          <div class="muted small">"Bot" is what the strategy used. "Check" is recomputed from the raw bars by a second, separately written routine. Type the TradingView value in the last column to compare by eye.</div>
          <div id="itab"><div class="empty"><span class="spin"></span></div></div></section>`;
      el.querySelector('#run').onclick = (e) => U.busy(e.target, async () => { await U.api('/api/health/run', { body: {} }); U.toast('Check finished'); load(); App.refreshTop(); });
      U.on(el, '#ip button', 'click', (e, b) => { pick = b.dataset.s; el.querySelectorAll('#ip button').forEach((x) => x.classList.toggle('on', x === b)); itab(); });
      itab();
    }
    async function itab() {
      const box = el.querySelector('#itab');
      if (!pick) { box.innerHTML = '<div class="muted">No strategies</div>'; return; }
      const want = pick;
      box.innerHTML = '<div class="empty"><span class="spin"></span></div>';
      let t;
      try { t = await U.api('/api/health/indicators?strategy=' + want); } catch (e) { t = { error: 'Could not load: ' + e.message, rows: [] }; }
      if (want !== pick || !document.body.contains(box)) return;
      if (t.error || !t.rows.length) { box.innerHTML = `<div class="muted">${U.esc(t.error || 'No data yet')}</div>`; return; }
      box.innerHTML = `<div class="tw"><table class="t"><thead><tr><th>Bar close (BKK)</th>${t.cols.map((c) => `<th class="r">${U.esc(c)}</th>`).join('')}<th class="r">TradingView</th><th>Result</th></tr></thead><tbody>
        ${t.rows.map((r) => `<tr><td class="num">${U.dt(r.t)}</td>${r.vals.map((v) => `<td class="r num">${typeof v === 'number' ? U.n(v, 2) : U.esc(v)}</td>`).join('')}
          <td class="r"><input class="in num" style="width:110px;height:32px;text-align:right" placeholder="type…" aria-label="TradingView value"></td><td>${U.pill(r.ok ? 'ok' : 'err', r.ok ? 'match' : 'differs')}</td></tr>`).join('')}</tbody></table></div>`;
    }
    await load();
  };

  V.logs = async function (el) {
    const f = { level: 'all', source: 'all', q: '' };
    let timer;
    async function load() {
      const q = new URLSearchParams({ level: f.level, source: f.source, q: f.q, limit: 200 });
      const d = await U.api('/api/events?' + q);
      const cnt = d.counts_24h || {};
      const body = el.querySelector('#lgbody');
      const rows = d.events.map((e) => `<div class="lg" data-id="${e.id}" style="cursor:pointer"><span class="num muted">${U.dt(e.t)}</span>
        <span>${U.pill(e.level === 'error' ? 'err' : e.level === 'warn' ? 'warn' : '', e.level)}</span><span class="muted">${U.esc(e.source)}</span>
        <span><b style="font-weight:500">${U.esc(e.title)}</b>${e.message ? ' <span class="muted">· ' + U.esc(e.message.split('\n')[0].slice(0, 200)) + '</span>' : ''}</span></div>
        <div class="hidden" data-detail="${e.id}" style="padding:0 16px 14px"><div class="code">${U.esc(e.message || '')}${e.detail ? '\n\n' + U.esc(e.detail) : ''}${e.strategy ? '\nstrategy: ' + U.esc(e.strategy) : ''}${e.mode ? '\nmode: ' + U.esc(e.mode) : ''}</div></div>`).join('');
      if (body) { body.innerHTML = rows || '<div class="empty">Nothing matches</div>'; bind(); return; }
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">Everything the bot did · kept 180 days</div><h1 class="h1">Logs</h1></div>
        <a class="btn" href="/api/events.log?days=1">Download today (.log)</a></div>
        <div class="row" style="gap:10px"><input class="in" id="q" placeholder="Search: symbol, strategy, message…" style="flex:1 1 280px">
          <div class="seg" id="lv">${[['all', 'All'], ['info', 'Info'], ['warn', 'Warnings · ' + (cnt.warn || 0)], ['error', 'Errors · ' + (cnt.error || 0)]].map(([k, l]) => `<button data-v="${k}" class="${f.level === k ? 'on' : ''}">${l}</button>`).join('')}</div>
          <select class="in" id="src" style="width:auto"><option value="all">All sources</option>${d.sources.map((s) => `<option>${U.esc(s)}</option>`).join('')}</select></div>
        <section class="card flush"><div class="lg" style="font-size:12px;color:var(--dim);font-weight:500"><span>Time (BKK)</span><span>Level</span><span>Source</span><span>Message · click a row for details</span></div>
          <div id="lgbody">${rows || '<div class="empty">No events yet</div>'}</div></section>`;
      U.on(el, '#lv button', 'click', (e, b) => { f.level = b.dataset.v; el.querySelectorAll('#lv button').forEach((x) => x.classList.toggle('on', x === b)); load(); });
      el.querySelector('#src').onchange = (e) => { f.source = e.target.value; load(); };
      el.querySelector('#q').oninput = (e) => { clearTimeout(timer); timer = setTimeout(() => { f.q = e.target.value; load(); }, 300); };
      bind();
    }
    function bind() { U.on(el, '.lg[data-id]', 'click', (e, r) => el.querySelector(`[data-detail="${r.dataset.id}"]`).classList.toggle('hidden')); }
    await load();
    return { cleanup: () => {}, refresh: () => load().catch(() => {}), every: 30000 };
  };
})();
