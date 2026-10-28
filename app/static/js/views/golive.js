/* Go-live checklist: readiness for real money, measured from the bot's own records (+ the user's own ticks). */
(function () {
  const V = window.Views || (window.Views = {});
  let gmode = null;
  let ttTimer = null;

  V.golive = async function (el) {
    gmode = gmode || (U.mode() === 'paper' ? 'test' : U.mode());
    async function load(d) {
      d = d || await U.api('/api/golive?mode=' + gmode);
      const pct = Math.round(d.pct * 100);
      const col = d.ready ? 'var(--up)' : pct >= 60 ? 'var(--warn-fg)' : 'var(--muted)';
      el.innerHTML = `
      <div class="page-head"><div><div class="eyebrow">Before real money</div><h1 class="h1">Go-live checklist</h1>
        <div class="muted" style="margin-top:4px;max-width:780px">Measured from what the bot actually did in <b>${U.esc(U.modeLabel[gmode])}</b> since ${U.day(d.since)}. Planned tests tick themselves when you do them. Aim for 90% with every <b>must</b> item done, then start Live small.</div></div>
        <div class="row"><div class="seg" id="gm">${['test', 'paper', 'live'].map((m) => `<button data-m="${m}" class="${gmode === m ? 'on' : ''}">${U.esc(U.modeLabel[m])}</button>`).join('')}</div>
          <button class="btn" id="grs">Count from today</button></div></div>
      <section class="card row" style="gap:24px;align-items:center;flex-wrap:wrap">
        <div style="min-width:150px"><div class="eyebrow">Readiness</div><div class="num big" style="font-size:44px;color:${col}">${pct}%</div></div>
        <div class="col" style="flex:1;min-width:260px;gap:8px">
          <div style="height:12px;border-radius:6px;background:var(--line2);overflow:hidden;position:relative">
            <div style="height:100%;width:${pct}%;background:${col}"></div><div style="position:absolute;left:90%;top:-3px;bottom:-3px;width:2px;background:var(--text2)" title="90% target"></div></div>
          <div class="row sb small"><span>${d.passed} of ${d.total} items · <b>${d.must_ok} of ${d.must_total}</b> must-items</span><span class="muted">target 90% ▸</span></div>
          <div>${d.ready ? U.pill('ok big', 'Ready for a small Live start') : U.pill('warn big', 'Not ready yet — keep testing')}</div></div>
      </section>
      <section class="card col" style="gap:10px" id="tt"><span class="spin"></span></section>
      ${d.sections.map((s) => `<section class="card col" style="gap:4px">
        <div class="row sb" style="margin-bottom:6px"><h2 class="h2">${U.esc(s.title)}</h2><span class="muted small">${U.esc(s.sub)} · ${s.items.filter((i) => i.status === 'ok').length}/${s.items.length}</span></div>
        ${s.items.map((i) => row(i, s.id === 'mine' && i.key !== 'm_floor')).join('')}</section>`).join('')}
      <section class="card col" style="gap:10px"><h2 class="h2">Then: Live with small money (2–4 weeks)</h2>
        <div class="muted">Connect the Live key → set the protected cash floor → allocate to 2–3 strategies only (at least $1,000 each) → switch Live on (type LIVE) → every few days compare Trades with your Webull statement → after 2 good weeks add the other strategies and raise the amounts step by step.</div></section>`;
      U.on(el, '#gm button', 'click', (e, b) => { gmode = b.dataset.m; load(); });
      el.querySelector('#grs').onclick = async () => {
        if (!(await U.confirm('Count from today?', `The checklist for ${U.esc(U.modeLabel[gmode])} starts again from now (your ticks are kept).`, { ok: 'Count from today' }))) return;
        load(await U.api('/api/golive/restart', { body: { mode: gmode } }));
      };
      U.on(el, '[data-tick]', 'change', async (e, c) => {
        load(await U.api('/api/golive/tick', { body: { key: c.dataset.tick, done: c.checked, mode: gmode } }));
      });
      ttLoad();
    }

    /* ---- Test trade: buy 1 share of an ETF and sell it back (paid from bot unassigned) */
    let ttQty = 1, ttRunning = false;
    async function ttLoad(d) {
      const box = el.querySelector('#tt');
      if (!box) return;
      try { d = d || await U.api('/api/testtrade?mode=' + gmode); } catch (e) { box.innerHTML = `<div class="note err">${U.esc(e.message)}</div>`; return; }
      ttRender(box, d);
      clearTimeout(ttTimer);
      if (d.running) ttTimer = setTimeout(() => { if (document.body.contains(box)) ttLoad(); }, 4000);
      if (ttRunning && !d.running) { ttRunning = false; load().catch(() => {}); }
      ttRunning = d.running;
    }
    function ttState(r) {
      if (!r) return '<span class="muted small">not tested</span>';
      const when = U.dt(r.finished_at || r.updated_at);
      if (r.status === 'ok') return `${U.pill('ok', 'OK')} <span class="muted small">${U.esc(when)}</span>`;
      if (r.status === 'queued') return `${U.pill('', 'Queued')} <span class="muted small">${U.esc(r.error || '')}</span>`;
      if (r.status === 'buying' || r.status === 'selling') return `${U.pill('warn', r.status === 'buying' ? 'Buying…' : 'Selling…')} <span class="spin"></span>`;
      if (r.status === 'holding') return `${U.pill('err', `Holding ${+(+r.left).toFixed(6)} share${r.left > 1 ? 's' : ''}`)}`;
      return `${U.pill('err', r.code === 'OPENAPI_IS_TH_FIRST_ETF_PLACE' ? 'Needs permission' : r.code ? 'Refused' : 'Failed')} <span class="muted small">${U.esc(when)}</span>`;
    }
    function frHtml(d) {
      const f = d.fractional || {}, tests = d.fractional_tests || [];
      const busy = tests.some((r) => ['queued', 'buying', 'selling', 'holding'].includes(r.status));
      const one = (k, label) => { const x = f[k]; return `<div class="row" style="gap:8px"><span class="small" style="width:120px">${label}</span>${x ? U.pill(x.ok ? 'ok' : 'err', x.ok ? 'Accepted' : 'Refused') + ` <span class="muted small">${U.esc(x.symbol)} · ${U.esc(U.dt(x.at))}</span>` : '<span class="muted small">not tested</span>'}</div>`; };
      const syms = d.symbols.map((s) => s.symbol);
      const def = syms.includes('QLD') ? 'QLD' : syms[0];
      return `<div class="col" style="gap:10px;border-top:1px solid var(--line2);padding-top:14px;margin-top:4px">
        <div><h3 style="margin:0;font-size:15px;font-weight:600">Fractional shares: buy 0.5 share, sell it back</h3>
          <div class="muted small" style="max-width:760px;margin-top:4px">Checks whether Webull accepts fractions through the API — first as a limit order (what the bot uses), then, if refused, as a market order. Once the limit test passes, the bot adds the leftover fraction to the last lot of each buy, so a small strategy does not keep up to one share of cash idle (Execution → Fractional shares).</div></div>
        ${one('LIMIT', 'Limit order')}${one('MARKET', 'Market order')}
        <div class="small" style="color:var(--text2)">→ ${U.esc(f.verdict || '')}</div>
        <div class="row" style="gap:8px;flex-wrap:wrap;align-items:center"><select class="in" id="frs" style="width:auto">${syms.map((x) => `<option ${x === def ? 'selected' : ''}>${U.esc(x)}</option>`).join('')}</select>
          <button class="btn p" data-fr="LIMIT" ${busy ? 'disabled' : ''}>Fractional test · limit</button>
          <button class="btn" data-fr="MARKET" ${busy ? 'disabled' : ''}>Fractional test · market</button></div>
        ${tests.length ? `<div class="tw"><table class="t"><thead><tr><th>When</th><th>ETF</th><th>Order</th><th>Result</th><th></th></tr></thead><tbody>${tests.map((r) => `<tr>
          <td class="num small">${U.esc(U.dt(r.created_at))}</td><td class="mono">${U.esc(r.symbol)}</td><td class="small">${U.esc((r.order_type || 'LIMIT').toLowerCase())} · ${r.qty}</td>
          <td style="white-space:normal">${ttState(r)}<div class="small muted">${U.esc(r.result || r.error || '')}</div>${r.raw && r.status === 'failed' ? `<details><summary class="muted small" style="cursor:pointer">Webull's own answer</summary><pre class="mono small" style="white-space:pre-wrap;word-break:break-all;margin:6px 0">${U.esc(r.raw)}</pre></details>` : ''}</td>
          <td class="r">${r.status === 'holding' ? `<button class="btn s" data-sell="${r.id}">Sell again</button> <button class="btn s" data-gone="${r.id}">I sold it</button>` : ''}</td></tr>`).join('')}</tbody></table></div>` : ''}
      </div>`;
    }
    let hkLots = 1;
    function hkHtml(h) {
      if (!h) return '';
      const live = gmode === 'live';
      const low = h.bot_hkd < 700;
      const hkd = (x) => x == null ? '—' : 'HK$' + (+x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      const res = (r) => {
        if (!r || !r.state) return '<span class="muted small">not tested</span>';
        if (r.state === 'ok') return `${U.pill('ok', 'Can buy')} <span class="muted small">${U.esc(U.dt(r.at))}</span>`;
        return `${U.pill('err', r.state === 'refused' ? 'Refused by Webull' : 'Not filled')} <span class="muted small">${U.esc(U.dt(r.at))}</span>`;
      };
      return `<div class="col" style="gap:10px;border-top:1px solid var(--line2);padding-top:14px;margin-top:4px">
        <div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h3 style="margin:0;font-size:15px;font-weight:600">Hong Kong: can the bot buy 7234, 7226 and 7233?</h3>
          <div class="muted small" style="max-width:760px;margin-top:4px">Buys ${hkLots} board lot${hkLots > 1 ? 's' : ''} (100 shares each) with Webull's Hong Kong order type (enhanced limit, HKEX price steps) and sells straight back. Paid in <b>Hong Kong dollars</b> from <b>bot HKD</b> (${hkd(h.bot_hkd)} now). Webull Thailand's API documents US trading only, so this test is how we find out. Not counted in readiness.</div></div>
          <div>${h.market.open ? U.pill('ok', 'Hong Kong market open') : U.pill('', 'Closed')}</div></div>
        ${h.market.open ? '' : `<div class="muted small">${U.esc(h.market.text)} · ${U.esc(h.market.hours)}</div>`}
        ${low ? `<div class="note warn">Bot HKD has ${hkd(h.bot_hkd)}. Convert USD to HKD in the Webull app (Assets → Currency exchange), then <a href="#/money">Money → Hong Kong dollars → Allocate HKD to the bot</a> (about HK$1,500 covers all three tests).</div>` : ''}
        <div class="tw"><table class="t"><thead><tr><th>ETF</th><th>Tracks</th><th class="r">1 lot ≈</th><th>Result</th><th class="r">Cost</th><th></th></tr></thead><tbody>
        ${h.symbols.map((s) => {
          const r = s.last, ok = s.last_ok;
          const busy = r && ['queued', 'buying', 'selling', 'holding'].includes(r.status);
          return `<tr><td><b class="mono">${U.esc(s.symbol)}</b></td><td class="small">${U.esc(s.name)}<div class="muted">lot ${s.lot} · ${s.price ? 'HK$' + (+s.price).toFixed(3) : 'no price'}</div></td>
            <td class="r num small">${hkd(s.lot_value)}</td>
            <td style="white-space:nowrap">${busy ? ttState(r) : res(s.result)}</td>
            <td class="r num small">${ok ? hkd(ok.cost) : '—'}</td>
            <td class="r" style="white-space:nowrap">${r && r.status === 'holding'
              ? `<button class="btn s" data-sell="${r.id}">Sell again</button> <button class="btn s" data-gone="${r.id}">I sold it</button>`
              : `<button class="btn s" data-hk="${U.esc(s.symbol)}" ${busy ? 'disabled' : ''}>Test</button>`}</td></tr>
            ${s.result && s.result.state && s.result.state !== 'ok' && !busy ? `<tr><td></td><td colspan="5" class="small" style="padding-top:0;white-space:normal">
              <div style="color:var(--text2)">${U.esc(s.result.text || '')}</div>${s.result.hint ? `<div class="muted">→ ${U.esc(s.result.hint)}</div>` : ''}
              ${r && r.raw ? `<details><summary class="muted" style="cursor:pointer">Webull's own answer</summary><pre class="mono small" style="white-space:pre-wrap;word-break:break-all;margin:6px 0">${U.esc(r.raw)}</pre></details>` : ''}</td></tr>` : ''}
            ${r && ['queued', 'buying', 'selling'].includes(r.status) ? `<tr><td></td><td colspan="5" class="small muted" style="padding-top:0;white-space:normal">${(r.log || []).slice(-3).map((l) => `${U.esc(U.time(l[0]))} ${U.esc(l[1])}`).join('<br>')}</td></tr>` : ''}`;
        }).join('')}</tbody></table></div>
        <div class="row" style="gap:10px;flex-wrap:wrap;align-items:center">
          <label class="small muted" for="hkl">Lots per test</label>
          <select class="in" id="hkl" style="width:auto">${Array.from({ length: h.max_lots }, (_, i) => i + 1).map((n) => `<option ${n === hkLots ? 'selected' : ''}>${n}</option>`).join('')}</select>
          <button class="btn p" id="hkall" ${h.running ? 'disabled' : ''}>Test all 3 Hong Kong ETFs</button>
          ${live ? '<span class="small" style="color:var(--warn-fg)">Live: real orders on your Webull account, in HKD.</span>' : ''}</div>
      </div>`;
    }
    function ttRender(box, d) {
      const lowPool = d.pool < 150;
      const live = gmode === 'live';
      box.innerHTML = `
        <div class="row sb" style="flex-wrap:wrap;gap:8px"><div><h2 class="h2">Test trade: buy ${ttQty} share${ttQty > 1 ? 's' : ''}, sell it straight back</h2>
          <div class="muted small" style="max-width:760px;margin-top:4px">Proves that Webull accepts, fills and reports every ETF the strategies use — before a strategy needs it.
          Paid from <b>bot unassigned</b> (${U.usd(d.pool)} now) — no strategy's money or shares are touched. You lose only the spread + fees (usually under $0.50 a test).
          US market hours only; the money guard and protected floor apply.</div></div>
          <div>${d.market_open ? U.pill('ok', 'Market open') : U.pill('', 'Market closed: tests wait for the open')}</div></div>
        ${lowPool ? `<div class="note warn">Bot unassigned has ${U.usd(d.pool)}. Put about $200 there first: <a href="#/money">Money → Webull → bot</a> (one share of QLD ≈ $90–110).</div>` : ''}
        ${live ? '<div class="note warn">Live mode: these are real orders on your own Webull account.</div>' : ''}
        <div class="tw"><table class="t"><thead><tr><th>ETF</th><th>Used by</th><th>Last test</th><th class="r">Cost</th><th class="r">Buy fill</th><th></th></tr></thead><tbody>
        ${d.symbols.map((s) => {
          const r = s.last, ok = s.last_ok;
          const busy = r && ['queued', 'buying', 'selling', 'holding'].includes(r.status);
          return `<tr><td><b class="mono">${U.esc(s.symbol)}</b></td>
            <td class="small muted" style="white-space:normal;min-width:170px;max-width:280px">${s.strategies.map((n) => U.esc(n)).join('<br>')}</td>
            <td style="white-space:nowrap">${ttState(r)}${ok && r && r.status !== 'ok' ? `<div class="small muted">last OK ${U.esc(U.dt(ok.finished_at))}</div>` : ''}</td>
            <td class="r num small">${ok ? U.usd(ok.cost) : '—'}</td>
            <td class="r num small">${ok && ok.buy_secs != null ? ok.buy_secs + ' s' : '—'}</td>
            <td class="r" style="white-space:nowrap">${r && r.status === 'holding'
              ? `<button class="btn s" data-sell="${r.id}">Sell again</button> <button class="btn s" data-gone="${r.id}">I sold it</button>`
              : `<button class="btn s" data-tt="${U.esc(s.symbol)}" ${busy ? 'disabled' : ''}>Test</button>`}</td></tr>
            ${r && ['failed', 'holding'].includes(r.status) ? `<tr><td></td><td colspan="5" class="small" style="padding-top:0;white-space:normal">
              <div style="color:var(--text2)">${U.esc(r.result || r.error || '')}</div>
              ${s.blocked && s.blocked.hint ? `<div class="muted">→ ${U.esc(s.blocked.hint)}</div>` : ''}
              ${r.raw ? `<details><summary class="muted" style="cursor:pointer">Webull's own answer</summary><pre class="mono small" style="white-space:pre-wrap;word-break:break-all;margin:6px 0">${U.esc(r.raw)}</pre></details>` : ''}</td></tr>` : ''}
            ${r && ['queued', 'buying', 'selling'].includes(r.status) ? `<tr><td></td><td colspan="5" class="small muted" style="padding-top:0;white-space:normal">${(r.log || []).slice(-3).map((l) => `${U.esc(U.time(l[0]))} ${U.esc(l[1])}`).join('<br>')}</td></tr>` : ''}`;
        }).join('')}</tbody></table></div>
        <div class="row" style="gap:10px;flex-wrap:wrap;align-items:center">
          <label class="small muted" for="ttq">Shares per test</label>
          <select class="in" id="ttq" style="width:auto">${Array.from({ length: d.max_qty }, (_, i) => i + 1).map((n) => `<option ${n === ttQty ? 'selected' : ''}>${n}</option>`).join('')}</select>
          <button class="btn p" id="ttall" ${d.running ? 'disabled' : ''}>Test all ${d.symbols.length} ETFs</button>
          <span class="muted small">One at a time; each takes about 10–60 seconds when the market is open.</span></div>
        ${frHtml(d)}
        ${hkHtml(d.hk)}`;
      box.querySelector('#ttq').onchange = (e) => { ttQty = +e.target.value; ttRender(box, d); };
      const hkl = box.querySelector('#hkl');
      if (hkl) hkl.onchange = (e) => { hkLots = +e.target.value; ttRender(box, d); };
      const hkGo = async (syms, btn) => {
        const what = syms.length === 1 ? syms[0] : syms.join(', ');
        const ok = await U.confirm(`Hong Kong test trade in ${U.modeLabel[gmode]}?`,
          `Buy ${hkLots} lot${hkLots > 1 ? 's' : ''} (${hkLots * 100} shares) of ${U.esc(what)} in Hong Kong, then sell straight back. Paid in HKD from bot HKD; you lose the spread + fees.`
          + (gmode === 'live' ? '<br><br><b>These are real orders on your Webull account.</b>' : ''), { ok: 'Buy and sell', word: gmode === 'live' ? 'TEST' : undefined });
        if (!ok) return;
        await U.busy(btn, async () => { ttLoad(await U.api('/api/testtrade/start', { body: { mode: gmode, symbols: syms, qty: hkLots } })); U.toast('Hong Kong test started'); });
      };
      U.on(box, '[data-hk]', 'click', (e, b) => hkGo([b.dataset.hk], b));
      const hka = box.querySelector('#hkall');
      if (hka) hka.onclick = (e) => hkGo(d.hk.symbols.filter((s) => !(s.last && ['queued', 'buying', 'selling', 'holding'].includes(s.last.status))).map((s) => s.symbol), e.target);
      const go = async (syms, btn) => {
        const what = syms.length === 1 ? syms[0] : `${syms.length} ETFs (${syms.join(', ')})`;
        const ok = await U.confirm(`Test trade in ${U.modeLabel[gmode]}?`,
          `Buy ${ttQty} share${ttQty > 1 ? 's' : ''} of ${U.esc(what)}, then sell straight back. Paid from bot unassigned; you lose the spread + fees.`
          + (live ? '<br><br><b>These are real orders on your Webull account.</b>' : ''), { ok: 'Buy and sell', word: live ? 'TEST' : undefined });
        if (!ok) return;
        await U.busy(btn, async () => { ttLoad(await U.api('/api/testtrade/start', { body: { mode: gmode, symbols: syms, qty: ttQty } })); U.toast('Test trade started'); });
      };
      U.on(box, '[data-tt]', 'click', (e, b) => go([b.dataset.tt], b));
      U.on(box, '[data-fr]', 'click', async (e, b) => {
        const sym = box.querySelector('#frs').value, ot = b.dataset.fr;
        const ok = await U.confirm(`Fractional test in ${U.modeLabel[gmode]}?`,
          `Buy <b>0.5 share</b> of ${U.esc(sym)} with a <b>${ot === 'MARKET' ? 'market' : 'limit'}</b> order, then sell the 0.5 straight back. It checks whether Webull accepts fractional orders through the API. Paid from bot unassigned.`
          + (live ? '<br><br><b>These are real orders on your Webull account.</b>' : ''), { ok: 'Buy and sell 0.5', word: live ? 'TEST' : undefined });
        if (!ok) return;
        await U.busy(b, async () => { ttLoad(await U.api('/api/testtrade/start', { body: { mode: gmode, symbols: [sym], fractional: true, order_type: ot } })); U.toast('Fractional test started'); });
      });
      box.querySelector('#ttall').onclick = (e) => go(d.symbols.filter((s) => !(s.last && ['queued', 'buying', 'selling', 'holding'].includes(s.last.status))).map((s) => s.symbol), e.target);
      U.on(box, '[data-sell]', 'click', (e, b) => U.busy(b, async () => ttLoad(await U.api('/api/testtrade/sell', { body: { id: +b.dataset.sell } }))));
      U.on(box, '[data-gone]', 'click', async (e, b) => {
        if (!(await U.confirm('You sold it in the Webull app?', 'The test is closed. The sale\'s cash stays in Webull outside the bot; move it back with Money → Webull → bot if you want.', { ok: 'Yes, I sold it' }))) return;
        U.busy(b, async () => ttLoad(await U.api('/api/testtrade/closed', { body: { id: +b.dataset.gone } })));
      });
    }
    function row(i, manual) {
      const icon = i.status === 'ok' ? '<span class="gl ok">✓</span>' : i.status === 'warn' ? '<span class="gl warn">!</span>' : '<span class="gl">○</span>';
      return `<div class="list-row" style="align-items:flex-start;gap:12px;padding:10px 0">
        ${manual ? `<input type="checkbox" data-tick="${i.key}" ${i.status === 'ok' ? 'checked' : ''} aria-label="Done" style="width:20px;height:20px;margin-top:2px;accent-color:var(--accent);flex:none">` : icon}
        <div class="col" style="flex:1;gap:2px;min-width:0"><div><b style="font-weight:500">${U.esc(i.title)}</b> ${i.must ? U.pill('', 'must') : ''}</div>
          ${i.detail ? `<div class="muted small">${U.esc(i.detail)}</div>` : ''}
          ${i.status !== 'ok' && i.how ? `<div class="small" style="color:var(--text2)">→ ${U.esc(i.how)}</div>` : ''}</div>
        <div class="col" style="align-items:flex-end;gap:4px;flex:none"><span class="num small ${i.status === 'ok' ? 'up' : ''}">${U.esc(i.value)}</span>
          ${i.link ? `<a class="small" href="${U.esc(i.link)}">Open →</a>` : ''}</div></div>`;
    }
    await load();
    return { cleanup: () => clearTimeout(ttTimer), refresh: () => load().catch(() => {}), every: 60000 };
  };
})();
