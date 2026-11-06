/* Dashboard: what the money in the strategies is really in (holdings grouped by what each ETF follows, 2x counted twice).
   V.renderExposure(el, x) — x: dashboard.exposure from the API ({total, rows, us_tech}). */
(function () {
  const V = window.Views || (window.Views = {});
  const pc = (x, d) => (x == null ? '—' : (x * 100).toFixed(d == null ? 0 : d) + '%');

  V.renderExposure = function (el, x) {
    if (!el) return;
    if (!x || !x.rows || !x.rows.length || !(x.total > 0.5)) { el.innerHTML = ''; return; }
    const t = x.us_tech || {};
    const head = t.pct > 0.005
      ? `<div class="note ${t.acts_like >= 1 ? 'warn' : 'info'} small" style="margin:0;display:block;line-height:1.55">
          <b>${pc(t.pct)}</b> of the money in your strategies is in <b>US tech</b> (Nasdaq-100, tech, semiconductors${x.rows.some((r) => r.key === 'stocks') ? ', Nasdaq-100 stocks' : ''})
          across ${t.strategies} strateg${t.strategies === 1 ? 'y' : 'ies'}${t.leveraged_pct > 0.005 ? `, ${pc(t.leveraged_pct)} of it through 2x ETFs` : ''}.
          They rise and fall together, so it moves like <b>${pc(t.acts_like)}</b> of your money in US tech:
          a 10% fall in US tech ≈ <b class="dn num">${U.sgnUsd(t.fall10, 0)}</b> (${pc(t.fall10 / x.total, 1)}).</div>`
      : '';
    const bar = x.rows.filter((r) => r.value > 0).map((r) => `<i title="${U.esc(r.label)} · ${U.usd(r.value, 0)} · ${pc(r.pct, 1)}"
        style="width:${Math.max(0.5, r.pct * 100).toFixed(2)}%;background:${U.esc(r.color)}"></i>`).join('');
    const row = (r) => `<div class="exrow ${r.us_tech ? 'tech' : ''}">
        <div class="col" style="gap:2px;min-width:0"><span class="row" style="gap:8px;flex-wrap:nowrap">${U.dot(r.color)}<b>${U.esc(r.label)}</b>${r.follows ? `<span class="muted small">${U.esc(r.follows)}</span>` : ''}</span>
          <span class="muted small">${r.symbols.map((s) => `${U.esc(s.symbol)}${s.lev >= 2 ? ' <b>' + s.lev + 'x</b>' : ''} ${U.usd(s.value, 0)}`).join(' · ')}${r.symbols.length && r.strategies.length ? ' — ' : ''}${r.key === 'cash' ? `in ${r.strategies.length} strateg${r.strategies.length === 1 ? 'y' : 'ies'}` : r.strategies.map((s) => U.esc(s.name)).join(', ')}</span></div>
        <div class="num" style="text-align:right">${U.usd(r.value, 0)}<div class="muted small">${pc(r.pct, 1)}</div></div>
        <div class="num" style="text-align:right" title="Value × leverage, as a share of all the money">${r.key === 'cash' || r.key === 'tbills' ? '<span class="muted">—</span>' : pc(r.acts_like)}
          <div class="muted small">acts like</div></div></div>`;
    el.innerHTML = `<section class="card col" style="gap:12px">
      <div class="row sb" style="gap:8px;flex-wrap:wrap"><h2 class="h2">What your money is in</h2>
        <span class="muted small">All strategies together, by what each ETF follows · 2x ETFs count twice in “acts like”</span></div>
      ${head}
      <div class="exbar" role="img" aria-label="Money by what it follows">${bar}</div>
      <div>${x.rows.map(row).join('')}</div>
      ${t.pct > 0.005 ? `<div class="exrow total"><div><b>US tech together</b></div><div class="num" style="text-align:right">${U.usd(t.value, 0)}<div class="muted small">${pc(t.pct, 1)}</div></div>
        <div class="num" style="text-align:right"><b>${pc(t.acts_like)}</b><div class="muted small">acts like</div></div></div>` : ''}
      <div class="muted small">Total in strategies ${U.usd(x.total, 0)} (their cash included). The 10% line is a rough guide: semiconductors usually move more than the Nasdaq-100.</div>
    </section>`;
  };
})();
