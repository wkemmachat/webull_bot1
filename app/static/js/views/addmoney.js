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
    const money = (lab, key, strong) => `<div class="am-m ${strong ? 'on' : ''}"><span class="muted small">${lab}</span><span class="num am-big">${$k(z[key])}</span><span class="muted small">normal day: ${$k(y[key])}</span></div>`;
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

  /* Dashboard: strategies in the add window (85th+), best first; '' when none */
  V.addMoneyList = function (list) {
    const rows = (list || []).filter((s) => s.add && s.add.in_zone && s.control !== 'stopped' && !s.idle);
    const go = rows.filter((s) => s.add.verdict !== 'none').sort((a, b) => ({ good: 0, safer: 1, mixed: 2 }[a.add.verdict] - { good: 0, safer: 1, mixed: 2 }[b.add.verdict]) || (b.dip ? b.dip.pct : 0) - (a.dip ? a.dip.pct : 0));
    const no = rows.filter((s) => s.add.verdict === 'none');
    if (!go.length) return '';
    const mini = (x) => { const n = Math.min(x.n, 30), up = Math.round(x.up_n * n / x.n), w = 120 / n;
      return `<svg viewBox="0 0 120 12" width="120" height="12" aria-hidden="true">${Array.from({ length: n }, (_, j) => `<rect x="${(j * w).toFixed(1)}" y="0" width="${Math.max(1, w - 1).toFixed(1)}" height="12" rx="1" class="${j < up ? 'am-up' : 'am-dn'}"/>`).join('')}</svg>`; };
    return `<section class="card col am-list" style="gap:4px">
      <div class="row sb" style="gap:8px;flex-wrap:wrap"><h2 class="h2">Where to put extra money now</h2><a class="small" href="#/docs/strategy-dips">How it works</a></div>
      <div class="muted small">Strategies 85th percentile or deeper below their high. The bars: every past time it got this deep, and whether it was up a year later. For extra money you keep aside; not a promise.</div>
      ${go.map((s) => `<a class="am-li" href="#/strategies/${U.esc(s.id)}"><span style="min-width:0"><span class="row" style="gap:8px;flex-wrap:nowrap">${U.dot(s.color, 9)}<b class="ell">${U.esc(s.name)}</b></span>
          <span class="muted small">${s.dip ? s.dip.depth.toFixed(0) + '% · ' + (s.dip.pct >= 99.5 ? 'deepest ever' : U.ordinal(s.dip.pct) + ' pct') : ''}${(s.value || 0) >= 0.5 ? ' · you have ' + U.usd(s.value, 0) : ''}</span></span>
        <span class="col am-mini">${mini(s.add)}<span class="muted small">${s.add.up_n} of ${s.add.n} up · typical ${P(s.add.entry_med || 0)}${s.add.typical != null ? ' · $1,000 → ' + $k(s.add.typical) : ''}</span></span>
        <span>${U.pill(PILL[s.add.label] || '', s.add.label)}</span></a>`).join('')}
      ${no.length ? `<div class="muted small" style="padding-top:8px">Also this deep, but no add signal: ${no.map((s) => `<a href="#/strategies/${U.esc(s.id)}">${U.esc(s.name)}</a> (${s.add.n < 6 ? 'only ' + s.add.n + ' past falls' : s.add.up_n + ' of ' + s.add.n + ' up, no better than other days'})`).join(' · ')}.</div>` : ''}
    </section>`;
  };
})();
