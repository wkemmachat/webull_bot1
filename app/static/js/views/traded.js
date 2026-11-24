/* Dashboard → Traded: the last 3 US sessions, one line per strategy (app/traded.py). */
(function () {
  const V = window.Views || (window.Views = {});
  let pick = 0;                                  // the session shown on a phone (kept across Dashboard refreshes)
  const SHOW = 4;
  const open = {};                               // sessions with "+ N more" opened
  const q = (x) => { const r = Math.round(x * 10000) / 10000; return Number.isInteger(r) ? String(r) : r.toFixed(r < 10 ? 2 : 2).replace(/\.?0+$/, ''); };
  const usd0 = (v) => '$' + Math.round(v).toLocaleString('en-US');

  function leg(g) {
    const side = g.side === 'BUY' ? '<span class="tr-buy">Buy</span>' : '<span class="tr-sell">Sell</span>';
    return `<span class="tr-leg">${side} ${q(g.qty)} ${U.esc(g.symbol)}${g.avg ? ' @ ' + U.usd(g.avg) : ''}</span>`;
  }

  function line(s) {
    const legs = s.legs.length === 1 ? leg(s.legs[0]) : s.legs.map((g) => leg(g).replace(/ @ \$[\d,.]+/, '')).join(' · ');
    const inside = s.legs.reduce((a, g) => a + (g.inside ? 1 : 0), 0);
    const tags = s.why.map((w) => `<span class="tr-why">${U.esc(w)}</span>`).join('') + (inside ? '<span class="tr-why">inside the bot</span>' : '');
    return `<a class="tr-r" href="#/strategies/${encodeURIComponent(s.id)}"><span class="tr-dot" style="background:${U.esc(s.color || '#94a3b8')}"></span>
      <div style="min-width:0"><div class="tr-nm" title="${U.esc(s.name)}">${U.esc(s.name)}</div><div class="tr-ac">${legs}${tags}</div></div>
      <span class="tr-amt num">${usd0(s.value)}</span></a>`;
  }

  function day(d, i) {
    const lines = open[d.date] ? d.strategies : d.strategies.slice(0, SHOW);
    const more = d.strategies.length - lines.length;
    const head = `<div><span class="tr-dt">${U.esc(d.label)}</span>${d.last ? '<span class="tr-last">last trade</span>' : ''}
      <div class="muted small">${d.fills ? `${U.esc(d.from)} – ${U.esc(d.to)} · ${d.fills} fill${d.fills === 1 ? '' : 's'}` : 'no trades'}</div></div>`;
    if (!d.fills) return `<div class="tr-day${i === pick ? ' on' : ''}" data-trday="${i}">${head}<div class="tr-none">Every strategy kept what it held.</div></div>`;
    return `<div class="tr-day${d.last ? ' last' : ''}${i === pick ? ' on' : ''}" data-trday="${i}">${head}
      <div class="tr-sum"><span class="tr-chip b num">Bought ${usd0(d.bought)}</span><span class="tr-chip s num">Sold ${usd0(d.sold)}</span><span class="tr-chip num">fees ${U.usd(d.fees)}</span></div>
      ${lines.map(line).join('')}
      ${more > 0 ? `<button class="tr-more" type="button" data-trmore="${U.esc(d.date)}">+ ${more} more ${more === 1 ? 'strategy' : 'strategies'}</button>` : ''}
      ${d.short.map((n) => `<div class="tr-warn">${U.esc(n.name)} bought ${n.pct}% of what its signal asked for. <a href="#/orders">Orders</a> shows why.</div>`).join('')}
      <a class="tr-link small" href="#/orders">That day's orders →</a></div>`;
  }

  V.traded = function (t) {
    if (!t || !t.days || !t.days.length) return '';
    if (pick >= t.days.length) pick = 0;
    return `<section class="card tr" id="traded-card"><div class="row sb" style="margin-bottom:12px;gap:8px;flex-wrap:wrap"><div><b class="h3" style="font-size:16px">Traded</b>
      <span class="muted small"> last ${t.days.length} US sessions · times in Bangkok</span></div><a class="small" href="#/orders">All orders →</a></div>
      <div class="tr-tabs" role="tablist">${t.days.map((d, i) => `<button type="button" role="tab" aria-selected="${i === pick}" class="${i === pick ? 'on' : ''}" data-trtab="${i}">${U.esc(d.label)}</button>`).join('')}</div>
      <div class="tr-cols">${t.days.map(day).join('')}</div></section>`;
  };

  V.tradedBind = function (el, t) {
    const host = el.querySelector('#traded');
    if (!host) return;
    host.onclick = (e) => {
      const tab = e.target.closest('[data-trtab]');
      const more = e.target.closest('[data-trmore]');
      if (tab) { pick = +tab.dataset.trtab; host.innerHTML = V.traded(t); }
      else if (more) { open[more.dataset.trmore] = true; host.innerHTML = V.traded(t); }
    };
  };
})();
