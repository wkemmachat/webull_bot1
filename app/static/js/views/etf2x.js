/* Weekly 2x ETF search for C2-7 Momentum 2x: V.renderEtf2x(el, sid). It only suggests: Add writes the pair into the
   strategy's "2x ETFs" list, then a Test trade proves Webull allows it. */
(function () {
  const V = window.Views || (window.Views = {});
  const usdM = (v) => (v == null ? '—' : '$' + (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + 'M');
  const mon = (iso) => { if (!iso) return '—'; const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }); };

  V.renderEtf2x = async function (el, sid) {
    let d, poll = null;
    async function load() { d = await U.api('/api/etf2x/' + sid); draw(); }

    function facts(b) {
      return `beta ${b.beta ?? '—'} · correlation ${b.corr ?? '—'} · ${usdM(b.adv)} a day · trading since ${mon(b.since)}${b.spread != null ? ` · spread ${b.spread.toFixed(2)}%` : ''}`;
    }

    function draw() {
      if (!d.applies) { el.innerHTML = ''; return; }
      const rows = d.rows || [], found = rows.filter((r) => r.status === 'found');
      const R = d.rules;
      el.innerHTML = `<section class="card col" style="gap:12px">
        <div class="row sb" style="gap:10px;flex-wrap:wrap;align-items:flex-start"><div style="min-width:0;flex:1 1 320px"><h2 class="h2">2x ETF search · weekly</h2>
          <div class="muted small">After each weekend's Nasdaq-100 ranking the bot looks for a 2x ETF for every large stock it would hold as shares.
            It only suggests: nothing changes until you press <b>Add</b>.</div></div>
          <div class="col" style="gap:4px;align-items:flex-end">
            <button class="btn s" data-scan ${d.running || !d.can_scan ? 'disabled' : ''} title="${d.can_scan ? '' : 'Needs real prices from Yahoo'}">${d.running ? '<span class="spin"></span> Searching…' : 'Search now'}</button>
            <span class="tiny muted">${d.at ? `Last search ${U.dt(d.at)}${d.week ? ' · ranking of ' + U.esc(d.week) : ''}` : 'Not searched yet — runs after the next weekend ranking'}</span></div></div>
        ${found.length ? found.map((r) => `<div class="note ok" style="margin:0;display:block">
            <div class="row sb" style="gap:10px;flex-wrap:wrap"><div style="min-width:0;flex:1 1 300px">
              <b>${U.esc(r.stock)} → ${U.esc(r.best.etf)}</b> <span class="small">${U.esc(r.best.name || '')}</span>
              <div class="small num" style="margin-top:2px">${facts(r.best)}</div>
              ${r.picked ? `<div class="small" style="margin-top:2px">${U.esc(r.stock)} is on this week's list: adding it switches its shares to ${U.esc(r.best.etf)} at the next plan.</div>` : ''}</div>
              <div class="row" style="gap:6px"><button class="btn p s" data-add="${U.esc(r.stock)}" data-etf="${U.esc(r.best.etf)}">Add</button>
                <button class="btn s" data-dismiss="${U.esc(r.stock)}">Dismiss</button></div></div></div>`).join('')
          : (d.at ? '<div class="muted small">No new 2x ETF to add this week.</div>' : '')}
        ${rows.length ? `<div class="tw"><table class="t"><thead><tr><th class="r">Size rank</th><th>Stock</th><th>Held as</th><th>Search result</th></tr></thead><tbody>
          ${rows.map((r) => {
            let res;
            if (r.status === 'mapped') res = `<span class="muted">in your 2x list</span>`;
            else if (r.status === 'found') res = `${U.pill('ok', 'found ' + r.best.etf)}`;
            else if (r.status === 'dismissed') res = `<span class="muted">dismissed ${U.esc(r.best.etf)}</span>`;
            else {
              const tried = (r.checked || []).map((c) => `${U.esc(c.etf)}: ${U.esc(c.why.join('; '))}`).join(' · ');
              res = `<span class="muted">none found</span>${tried ? `<div class="tiny muted" style="white-space:normal;max-width:520px">Checked ${tried}</div>` : ''}`;
            }
            return `<tr><td class="r num">${r.rank}${r.in_pool ? '' : ' <span class="tiny muted">(next)</span>'}</td><td><b>${U.esc(r.stock)}</b>${r.picked ? ' ' + U.pill('info', 'this week') : ''}</td>
              <td class="mono">${r.status === 'mapped' ? U.esc(r.etf) : `${U.esc(r.stock)} <span class="muted small">(shares)</span>`}</td><td class="wrap">${res}</td></tr>`;
          }).join('')}</tbody></table></div>` : ''}
        <div class="tiny muted">A suggestion must be a 2x long ETF on the stock, move like 2x the stock (beta ${R.beta[0]}–${R.beta[1]}, correlation ≥ ${R.min_corr} over 60 days),
          have traded ${R.min_days}+ days, trade ${usdM(R.min_adv)}+ a day and, when Yahoo shows one, have a spread under ${R.max_spread}%. You get a LINE message when one is found.
          After adding, run <a href="#/golive">Go-live → Test trade</a> for it on Live.</div>
      </section>`;
      const sc = el.querySelector('[data-scan]');
      if (sc) sc.onclick = async () => { try { await U.api(`/api/etf2x/${sid}/scan`, { body: {} }); d.running = true; draw(); watch(); } catch (e) { U.toast(e.message, 'err'); } };
      U.on(el, '[data-add]', 'click', async (e, b) => {
        const st = b.dataset.add, etf = b.dataset.etf;
        if (!(await U.confirm(`Hold ${st} through ${etf}?`, `${etf} is added to this strategy's 2x list. Whenever ${st} is on the weekly list the bot buys ${etf} instead of the shares${rows.find((r) => r.stock === st && r.picked) ? ` — it is on this week's list, so the shares switch to ${etf} at the next plan` : ''}. Next, run a Test trade of ${etf} on Live.`, { ok: 'Add' }))) return;
        try {
          await U.api(`/api/etf2x/${sid}/add`, { body: { stock: st, etf } });
          U.toast(`${st} now uses ${etf}. Run Go-live → Test trade for ${etf}.`);
          await load();
        } catch (er) { U.toast(er.message, 'err'); }
      });
      U.on(el, '[data-dismiss]', 'click', async (e, b) => {
        try { await U.api(`/api/etf2x/${sid}/dismiss`, { body: { stock: b.dataset.dismiss } }); await load(); } catch (er) { U.toast(er.message, 'err'); }
      });
    }

    function watch() {
      if (poll) return;
      poll = setInterval(async () => {
        if (!document.body.contains(el)) { clearInterval(poll); poll = null; return; }
        const x = await U.api('/api/etf2x/' + sid).catch(() => null);
        if (x && !x.running) { clearInterval(poll); poll = null; d = x; draw(); }
      }, 4000);
    }

    try { await load(); if (d.running) watch(); } catch (e) { el.innerHTML = ''; }
  };
})();
