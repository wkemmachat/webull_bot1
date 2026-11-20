/* "Good time to add money?" (app/addmoney.py): on a strategy's Overview, and the Dashboard's "Where to put extra money now".
   In plain words: how deep it is now, what happened the last times it was this deep (one bar per time), what $1,000 became,
   and the rule (extra money now; don't hold money back waiting for it). Display only. */
(function () {
  const V = window.Views || (window.Views = {});
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dTxt = (s) => (s ? `${+s.slice(8, 10)} ${MON[+s.slice(5, 7) - 1]} ${s.slice(0, 4)}` : '');
  const P = (v, dp = 0) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(dp) + '%';
  const $k = (r) => '$' + (Math.round(100 * (1 + r)) * 10).toLocaleString('en-US');   // to the nearest $10
  const OPEN = new Set();                                  // "Show why" stays open across refreshes
  const M = (v) => (v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%';
  const PILL = { 'Good time': 'ok', 'OK, safer': 'ok', Mixed: 'warn', 'Not yet': '', 'No signal': '' };

  function bars(a, W, H) {
    const es = a.entries.slice(-40), n = es.length;
    if (!n) return '';
    const vals = es.map((e) => e[1]), mx = Math.max(0.2, ...vals), mn = Math.min(0, ...vals);
    const L = 6, R = 84, T = 14, B = 20, bw = (W - L - R) / n, Y = (v) => T + (mx - v) * (H - T - B) / (mx - mn);
    let h = `<line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" class="am-axis"/>`;
    let lastY = '', lastX = -99;
    es.forEach(([d, v], i) => {
      const gap = Math.min(3, bw * 0.18), x = L + i * bw + gap, w = Math.max(2, bw - 2 * gap), y0 = Y(0), y1 = Y(v);
      h += `<rect x="${x.toFixed(1)}" y="${Math.min(y0, y1).toFixed(1)}" width="${w.toFixed(1)}" height="${Math.max(1.5, Math.abs(y1 - y0)).toFixed(1)}" rx="2" class="${v > 0 ? 'am-up' : 'am-dn'}"><title>Reached the add zone ${dTxt(d)} → ${P(v)} a year later</title></rect>`;
      const yr = d.slice(0, 4), cx = x + w / 2;
      if (yr !== lastY && cx - lastX >= 36) { h += `<text x="${cx.toFixed(1)}" y="${H - 5}" text-anchor="middle" class="am-ax">${yr}</text>`; lastX = cx; }
      lastY = yr;
    });
    const med = a.entry_med;
    if (med != null) h += `<line x1="${L}" x2="${W - R + 6}" y1="${Y(med)}" y2="${Y(med)}" class="am-med"/><text x="${W - R + 10}" y="${Y(med) - 2}" class="am-ax">typical</text><text x="${W - R + 10}" y="${Y(med) + 11}" class="am-ax am-strong">${P(med)}</text>`;
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="max-width:100%;display:block" role="img" aria-label="Result a year after each past time it reached the add zone">${h}</svg>`;
  }

  function gauge(a) {
    const now = a.now, p = now ? Math.max(0, Math.min(100, now.pct)) : null;
    const al = p == null ? '' : p > 70 ? 'right:0;text-align:right' : p < 20 ? 'left:0' : `left:${p}%;transform:translateX(-50%)`;
    return `<div class="am-gauge" role="img" aria-label="How deep it is below its high now">
      <div class="am-glabels"><span>at its high</span><span style="left:77.5%">cheap</span><span class="am-strong" style="left:92.5%">add money</span></div>
      <div class="am-gbar"><i class="z1" style="left:70%;width:15%"></i><i class="z2" style="left:85%;width:15%"></i>${p == null ? '' : `<b style="left:${p}%"></b>`}</div>
      ${p == null ? '' : `<div class="am-gnow"><span style="${al}">today ${now.depth < 0 ? '−' : ''}${Math.abs(now.depth).toFixed(1)}%: deeper than ${Math.round(now.pct)}% of its past days</span></div>`}
      <div class="muted small">The add zone starts at about ${M(a.zone_depth)} below its high (its 85th percentile); "cheap" from ${M(a.buy_depth)}.</div></div>`;
  }

  function headline(a) {
    const now = a.now, d = now ? Math.abs(now.depth).toFixed(0) : '?';
    const every = a.up_n === a.n ? 'it was higher a year later every time' : `it was higher a year later ${a.up_n} of ${a.n} times`;
    if (a.verdict === 'none' && a.n < 6) return { cls: 'grey', icon: '▼', t: 'No add-money signal for this strategy', s: `It reached the add zone only ${a.n} time${a.n === 1 ? '' : 's'} in its backtest (${a.up_n} up a year later): too few to judge.` };
    if (a.verdict === 'none') return { cls: 'grey', icon: '▼', t: 'No add-money signal for this strategy', s: `The last ${a.n} times it fell this deep, ${a.up_n} were up a year later (typical ${P(a.entry_med || 0)}), not better than on other days. Being cheap is not a reason to add here.` };
    if (!a.in_zone) return { cls: 'plain', icon: '', t: 'Not a special time to add', s: `It is ${now ? d + '% below its high (' + U.ordinal(now.pct) + ' percentile)' : 'near its high'}. The add window opens at about ${M(a.zone_depth)} (the 85th percentile). The last ${a.n} times it got there, ${every}.` };
    if (a.verdict === 'mixed') return { cls: 'amber', icon: '▲', t: 'Cheap, but no clear edge', s: `It is ${d}% below its high. The last ${a.n} times it was this deep, ${every}, about like any other day.` };
    return { cls: 'green', icon: '▲▲', t: a.verdict === 'good' ? 'Good time to add extra money' : 'OK time to add extra money (safer, not bigger)', s: `It is ${d}% below its high${now && now.pct >= 99.5 ? ', deeper than ever before' : ''}. The last ${a.n} times it fell this deep, ${every}.` };
  }

  function steps(a) {
    const z = a.zone_days || {}, y = a.any_day || {}, w = a.wait, now = a.now;
    const step = (n, t) => `<div class="am-step"><span class="am-num">${n}</span><b>${t}</b></div>`;
    const money = (lab, key, strong) => `<div class="am-m ${strong ? 'on' : ''}"><span class="muted small">${lab}</span><span class="row" style="gap:8px;align-items:baseline"><span class="num am-big">${$k(z[key])}</span><b class="${strong ? '' : 'muted'}">${P(z[key])}</b></span><span class="muted small">normal day: ${$k(y[key])} (${P(y[key])})</span></div>`;
    return `${step(1, now && now.pct >= 85 ? 'Why now: it is on sale' : 'Where it is now')}${gauge(a)}
      ${step(2, `What happened the last ${a.n} times it got this cheap`)}
      <div><div class="am-bars" data-n="1"></div><div class="muted small" style="text-align:center">Each bar = one time it reached the add zone (${(a.entries[Math.max(0, a.entries.length - 40)] || [''])[0].slice(0, 4)} → ${(a.entries[a.entries.length - 1] || [''])[0].slice(0, 4)}), and how much it was up a year later. <b class="${a.up_n === a.n ? 'up' : ''}">${a.up_n} of ${a.n} were up.</b></div></div>
      ${step(3, 'If you add $1,000 on a day like this, a year later it was usually…')}
      <div class="am-grid3">${money('Bad year (1 in 10)', 'p10')}${money('Typical year', 'med', true)}${money('Good year (1 in 10)', 'p90')}</div>
      <div class="muted small">↘ It may dip a bit more first: typically to about ${$k(z.fall_med)}, rarely below ${$k(z.fall_p10)}. On a normal day it dipped to ${$k(y.fall_med)}, rarely ${$k(y.fall_p10)}.</div>
      ${step(4, 'The rule')}
      <div class="am-grid2"><div class="am-m on"><b>✓ Add extra money ${a.in_zone ? 'now' : 'when it gets there'}</b><span class="small">Money you keep aside for chances like this.</span></div>
        <div class="am-m"><b>✕ Don't hold money back for a dip</b><span class="muted small">${w ? `Waiting for a dip with money you'd add anyway was better only ${Math.round(w.better * 100)}% of the time and cost ${Math.abs(w.mean * 100).toFixed(1)}% on average (a wait of ${w.wait_days} trading days in the middle case; in ${Math.round(w.never * 100)}% of cases the dip didn't come within a year).` : 'Waiting usually cost more than it saved.'}</span></div></div>`;
  }

  /* a: /api/strategies/{sid} → add (addmoney.get) */
  V.addMoneyCard = function (host, a) {
    if (!host) return;
    if (!a || !a.n) { host.innerHTML = ''; return; }
    const h = headline(a), open = (a.in_zone && a.verdict !== 'none') || OPEN.has(a.sid);
    const honest = `<div class="muted small am-honest">Honest check: this is the bot's backtest since ${U.esc(String(a.since || '').slice(0, 4))}${a.verdict === 'good' || a.verdict === 'safer' ? ', for a strategy picked on those same years, so real results will be less tidy' : ''}.${a.now && a.now.pct >= 99.5 ? ' No past day was quite this deep.' : ''} History, not a promise. <a href="#/docs/strategy-dips">How it works</a></div>`;
    host.innerHTML = `<section class="card col am" style="gap:14px">
      <div class="am-head ${h.cls}">${h.icon ? `<span class="am-ico">${h.icon}</span>` : ''}<div style="min-width:0"><div class="am-t">${U.esc(h.t)}</div><div class="am-s">${U.esc(h.s)}</div></div>
        ${(a.in_zone && a.verdict !== 'none') ? '' : `<button class="btn s" id="amtog" aria-expanded="${open}">${open ? 'Hide' : 'Show why'}</button>`}</div>
      <div id="ambody" class="col" style="gap:14px;${open ? '' : 'display:none'}">${steps(a)}${honest}</div></section>`;
    const draw = () => { const b = host.querySelector('.am-bars'); if (b && b.offsetWidth) b.innerHTML = bars(a, Math.max(300, b.offsetWidth), 150); };
    draw();
    const tg = host.querySelector('#amtog');
    if (tg) tg.onclick = () => { const b = host.querySelector('#ambody'), on = b.style.display === 'none'; b.style.display = on ? '' : 'none'; tg.textContent = on ? 'Hide' : 'Show why'; tg.setAttribute('aria-expanded', on); if (on) OPEN.add(a.sid); else OPEN.delete(a.sid); draw(); };
  };

  /* Dashboard: "just got cheap" alert (a strategy entered the add window in the last 7 days, until dismissed) and
     "Good places for extra money now" as cards (good / safer), "Less sure" lines (mixed). '' when none is in the window.
     Dismiss and Hide are remembered in this browser (Hide opens again when a new strategy enters). */
  const LS = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private */ } } };
  const daysAgo = (iso) => { if (!iso) return 99; const [y, m, d] = iso.split('-').map(Number); return (Date.now() - Date.UTC(y, m - 1, d)) / 864e5; };
  const isNew = (s) => s.dip && s.dip.add_since && daysAgo(s.dip.add_since) <= 7.5;
  const dismissed = (s) => LS.get(`amDis:${s.id}:${s.dip.add_since}`) === '1';
  const depthTxt = (s) => (s.dip ? `−${Math.abs(s.dip.depth).toFixed(0)}% · ${s.dip.pct >= 99.5 ? 'deepest ever' : U.ordinal(s.dip.pct) + ' pct'}` : '');
  const dots = (x, size, cols) => { const n = Math.min(x.n, 30), up = Math.round(x.up_n * n / x.n);
    return `<span class="am-dots" style="grid-template-columns:repeat(${Math.min(cols, n)},${size}px)">${Array.from({ length: n }, (_, j) => `<i class="${j < up ? '' : 'r'}" style="width:${size}px;height:${size}px"></i>`).join('')}</span>`; };

  function alertHtml(news) {
    if (!news.length) return '';
    const a = news[0], x = a.add;
    if (news.length === 1) {
      return `<div class="am-alert" role="status"><div class="am-aic">▲</div>
        <div style="min-width:0"><div class="am-akick">New ${daysAgo(a.dip.add_since) < 1.5 ? 'today' : 'this week'}</div>
          <div class="am-at">${U.esc(a.name)} just got cheap</div>
          <div class="am-as">It's ${Math.abs(a.dip.depth).toFixed(0)}% below its high${a.dip.pct >= 99.5 ? ', deeper than ever before' : ''}. ${x.up_n === x.n ? 'That has always been a good time to add extra money' : `When it was this cheap before, it was higher a year later ${x.up_n} of ${x.n} times`}${x.typical != null ? `: typically <b>${P(x.typical)}</b> a year later ($1,000 → ${$k(x.typical)})` : ''}.</div>
          <div class="row" style="gap:8px;margin-top:10px;flex-wrap:wrap"><button class="btn p s am-btn" data-am-add="${U.esc(a.id)}">Add money to it</button>
            <a class="btn s" href="#/strategies/${U.esc(a.id)}">Why?</a><button class="am-link" data-am-dis="${U.esc(a.id + '|' + a.dip.add_since)}">Dismiss</button></div></div>
        <div class="am-proof"><div class="muted small">times it got this cheap</div>${dots(x, 8, 10)}
          <div class="am-pn">${x.up_n} of ${x.n}</div><div class="muted small">were higher a year later</div></div></div>`;
    }
    return `<div class="am-alert" role="status"><div class="am-aic">▲</div>
      <div style="min-width:0"><div class="am-akick">New this week</div>
        <div class="am-at">${news.length} strategies just got cheap</div>
        <div class="am-as">${news.map((s) => `<b>${U.esc(s.name)}</b> (${Math.abs(s.dip.depth).toFixed(0)}% below its high, ${s.add.up_n} of ${s.add.n} times up a year later)`).join(' · ')}.</div>
        <div class="row" style="gap:8px;margin-top:10px;flex-wrap:wrap"><button class="btn s" data-am-scroll="1">See them below</button><button class="am-link" data-am-dis="${news.map((s) => U.esc(s.id + '|' + s.dip.add_since)).join(',')}">Dismiss</button></div></div>
      <div class="am-proof"><div class="muted small">best record</div>${dots(news[0].add, 8, 10)}<div class="am-pn">${news[0].add.up_n} of ${news[0].add.n}</div><div class="muted small">${U.esc(news[0].name)}</div></div></div>`;
  }

  const groupOf = (s) => (s.control === 'stopped' ? 's' : (s.value || 0) >= 0.5 ? 'g' : 'b');
  const GROUPS = [['g', 'You have money in it'], ['b', 'On, but no money yet'], ['s', 'Stopped (not trading)']];
  const pctTxt = (r) => (r == null ? '—' : P(r));

  function tile(s, fresh) {
    const x = s.add, pct = s.dip ? s.dip.pct : 0, g = groupOf(s);
    const pill = fresh && g !== 's' ? '<span class="pill am-newp">new</span>'
      : `<span class="pill am-p-${g}">${g === 's' ? 'Stopped' : x.verdict === 'good' ? 'Good time' : 'Safer'}</span>`;
    const btn = g === 's' ? `<a class="btn s" style="align-self:flex-start" href="#/strategies/${U.esc(s.id)}">Open to start</a>`
      : `<button class="btn s am-btn" style="align-self:flex-start" data-am-add="${U.esc(s.id)}">Add money</button>`;
    return `<div class="am-tile am-${g} ${fresh && g !== 's' ? 'new' : ''}"><div class="row sb" style="gap:8px;flex-wrap:nowrap;align-items:flex-start"><a class="am-tn" href="#/strategies/${U.esc(s.id)}">${U.esc(s.name)}</a>${pill}</div>
      <div class="am-gain"><div><div class="am-pct">${pctTxt(x.typical)}</div><div class="muted small" style="margin-top:3px">a year later, typically</div></div>
        <div class="am-money"><span class="muted small">$1,000 became</span><b>${x.typical != null ? $k(x.typical) : '—'}</b></div></div>
      <div class="row" style="gap:8px;flex-wrap:nowrap">${dots(x, 6, 15)}<span class="muted small" style="white-space:nowrap">${x.up_n} of ${x.n} up</span></div>
      <div><div class="am-meter"><i style="width:${Math.max(4, Math.min(100, pct))}%"></i></div>
        <div class="row sb small muted" style="margin-top:4px;gap:8px"><span>${depthTxt(s)}</span><span>${g === 'g' ? 'you have ' + U.usd(s.value, 0) : g === 'b' ? 'no money yet' : 'stopped'}</span></div></div>
      ${btn}</div>`;
  }

  /* Dashboard: every strategy in the add window (85th+) in three colours: green = you have money in it, blue = on but no
     money yet, grey dashed = stopped (open it to start). Good time and Safer as cards, Mixed as "Less sure" lines. */
  V.addMoneyList = function (list) {
    const rows = (list || []).filter((s) => s.add && s.add.in_zone && s.dip);
    const rank = { good: 0, safer: 1, mixed: 2 };
    const sort = (a, b) => (isNew(b) - isNew(a)) || (rank[a.add.verdict] - rank[b.add.verdict]) || (b.dip.pct - a.dip.pct) || ((b.add.up_n / b.add.n) - (a.add.up_n / a.add.n));
    const go = rows.filter((s) => s.add.verdict === 'good' || s.add.verdict === 'safer').sort(sort);
    const less = rows.filter((s) => s.add.verdict === 'mixed').sort(sort);
    if (!go.length && !less.length) return '';
    const news = rows.filter((s) => s.add.verdict !== 'mixed' && s.control !== 'stopped' && isNew(s) && !dismissed(s));
    const newest = rows.filter((s) => s.control !== 'stopped').map((s) => s.dip.add_since || '').sort().pop() || '';
    const hidden = LS.get('amHide') && LS.get('amHide') >= newest;
    const on = go.filter((s) => s.control !== 'stopped').length;
    const head = `<div class="row sb" style="gap:8px;flex-wrap:wrap;align-items:flex-end"><div><h2 class="h2">Good places for extra money now</h2>
        <div class="muted small" style="margin-top:2px">${hidden ? `${on} strateg${on === 1 ? 'y is' : 'ies are'} cheap now${go.length > on ? ` (and ${go.length - on} stopped)` : ''}, and when they were this cheap before they were almost always higher a year later.`
          : 'Cheap right now, and when they were this cheap before, they were almost always higher a year later.'}</div></div>
      <button class="am-link" data-am-hide="${hidden ? '' : U.esc(newest || '0')}">${hidden ? 'Show' : 'Hide'}</button></div>`;
    const present = GROUPS.filter(([g]) => go.some((s) => groupOf(s) === g));
    const legend = present.length > 1 ? `<div class="row am-legend" style="gap:6px;flex-wrap:wrap">${present.map(([g, t]) => `<span class="am-lg am-p-${g}"><i class="am-sw-${g}"></i>${t.replace(' (not trading)', '')}</span>`).join('')}</div>` : '';
    const groups = present.map(([g, t]) => { const gs = go.filter((s) => groupOf(s) === g);
      return `<div class="am-grp"><i class="am-sw-${g}"></i>${t}<span class="muted small"> · ${gs.length}</span></div><div class="am-tiles">${gs.map((s) => tile(s, isNew(s))).join('')}</div>`; }).join('');
    return `${alertHtml(news)}<section class="col am-sec" id="amsec" style="gap:10px">${head}
      ${hidden ? '' : `${legend}${groups}
      ${less.map((s) => `<div class="am-less"><span class="pill warn">Less sure</span><span style="flex:1;min-width:0"><a href="#/strategies/${U.esc(s.id)}"><b>${U.esc(s.name)}</b></a>${s.control === 'stopped' ? ' (stopped)' : ''} is cheap too (${depthTxt(s)}), but only ${s.add.up_n} of ${s.add.n} times were up a year later${s.add.typical != null ? ` (typically ${P(s.add.typical)})` : ''}.</span>
        ${s.control === 'stopped' ? `<a class="btn s" href="#/strategies/${U.esc(s.id)}">Open</a>` : `<button class="btn s" data-am-add="${U.esc(s.id)}">Add</button>`}</div>`).join('')}
      <div class="muted small">% and $1,000 → the typical result a year later on days this cheap, from each strategy's backtest. Stopped strategies don't trade: open one and press Start before adding money. For extra money you keep aside. History, not a promise. <a href="#/docs/strategy-dips">How it works</a></div>`}</section>`;
  };

  /* Dashboard buttons: Add money (the usual form, this strategy picked), Dismiss, Hide/Show, See them */
  V.addMoneyBind = function (el, reload) {
    U.on(el, '[data-am-add]', 'click', (e, b) => V.moneyDialog('add', b.dataset.amAdd, reload));
    U.on(el, '[data-am-dis]', 'click', (e, b) => { (b.dataset.amDis || '').split(',').forEach((k) => { const [id, since] = k.split('|'); LS.set(`amDis:${id}:${since}`, '1'); }); reload(); });
    U.on(el, '[data-am-hide]', 'click', (e, b) => { LS.set('amHide', b.dataset.amHide || ''); reload(); });   // remembers the newest entry seen: a newer one opens it again
    U.on(el, '[data-am-scroll]', 'click', () => { const s = el.querySelector('#amsec'); if (s) s.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  };
})();
