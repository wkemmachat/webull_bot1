/* 2x ETF watch page: the Saturday ranking of US index / sector / commodity 2x ETFs by money traded a day, what is new,
   and a weekly log. It only reports (app/etfwatch.py). */
(function () {
  const V = window.Views || (window.Views = {});
  const ST = { pool: ['ok', 'In the pool'], bot: ['info', 'In the bot'], researched: ['', 'Researched before'],
    to_research: ['ok', 'To research'], not_researched: ['warn', 'Not researched'] };

  V.etfWatch = async function (el) {
    let filter = 'all';
    async function load() {
      const w = await U.api('/api/etfwatch');
      const rows = w.top.filter((r) => filter === 'all' || (filter === 'open' ? ['not_researched', 'to_research'].includes(r.status) : ['pool', 'bot'].includes(r.status)));
      const mv = (r) => (r.was == null ? (w.first_run ? '—' : '<span class="pill warn">new</span>') : r.was === r.rank ? '—' : r.was > r.rank ? `<span class="up">▲${r.was - r.rank}</span>` : `<span class="dn">▼${r.rank - r.was}</span>`);
      const money = (x) => (x == null ? '—' : x < 10 ? x.toFixed(2) : x.toFixed(1));
      el.innerHTML = `
        <div class="page-head"><div><div class="eyebrow">Monitor${w.t ? ' · checked ' + U.dt(w.t) + ' Bangkok' : ''}</div><h1 class="h1">2x ETF watch</h1>
          <div class="muted" style="margin-top:4px;max-width:820px">Every Saturday 09:40 Bangkok the bot ranks US-listed 2x long ETFs by money traded a day (90-day average). Single-stock and crypto funds are left out (not tradable for you on Webull Thailand). New names are flagged here, on the Dashboard and on LINE. It only reports — you decide what to research.</div></div>
          <div class="row"><button class="btn" id="chk" ${w.running ? 'disabled' : ''}>${w.running ? 'Checking…' : 'Check now'}</button></div></div>
        ${!w.t ? `<div class="note">${w.running ? '<span class="spin"></span> The first check is running (a minute or two: Yahoo is asked about each fund).' : 'No check yet. The first one runs on Saturday 09:40 Bangkok, or press Check now.'}</div>` : ''}
        ${w.t ? `<section class="card col" style="gap:12px"><div class="row sb"><h2 class="h2">New this week</h2><span class="muted small">${w.new.length} new · ${w.left.length} left${w.first_run ? ' · first check: this is the starting list' : ''}</span></div>
          ${w.new.length ? w.new.filter((n) => n.mark !== 'dismissed').map(V.etfNewRow).join('') || '<div class="muted small">All dismissed.</div>' : '<div class="muted small">Nothing new this week.</div>'}
          ${w.left.length ? `<div class="row small" style="gap:8px;flex-wrap:wrap"><span class="muted">Left the top 50:</span>${w.left.map((x) => `<span class="pill">${U.esc(x.t)} · ${U.esc(x.tracks)}</span>`).join('')}</div>` : ''}</section>
        <section class="card flush"><div class="row sb" style="padding:16px 20px 6px;flex-wrap:wrap;gap:8px"><h2 class="h2">Top ${w.top.length} · index, sector and commodity 2x ETFs</h2>
          <div class="seg" id="flt"><button data-f="all" class="${filter === 'all' ? 'on' : ''}">All</button><button data-f="open" class="${filter === 'open' ? 'on' : ''}">Not researched · ${w.counts.not_researched + w.counts.to_research}</button><button data-f="bot" class="${filter === 'bot' ? 'on' : ''}">In the bot · ${w.counts.pool + w.counts.bot}</button></div></div>
          <div class="tw"><table class="t"><thead><tr><th>#</th><th>Week</th><th>ETF</th><th>Tracks</th><th>Group</th><th class="r">$M a day</th><th class="r">History</th><th>Status</th><th></th></tr></thead><tbody>
          ${rows.map((r) => `<tr><td class="num muted">${r.rank}</td><td class="num small">${mv(r)}</td><td class="num" style="font-weight:700">${U.esc(r.t)}</td><td>${U.esc(r.tracks)}</td><td class="muted small">${U.esc(r.group)}</td>
            <td class="r num">${money(r.adv90)}</td><td class="r num muted">${r.years == null ? '—' : r.years < 1 ? '<1 y' : Math.floor(r.years) + ' y'}</td><td>${U.pill(ST[r.status][0], ST[r.status][1])}</td>
            <td class="r">${r.status === 'not_researched' ? `<button class="btn s" data-etfm="research" data-t="${U.esc(r.t)}">Research it</button>` : r.status === 'to_research' ? `<button class="btn s" data-etfm="clear" data-t="${U.esc(r.t)}">Unmark</button>` : ''}</td></tr>`).join('')}
          </tbody></table></div>
          <div class="muted small" style="padding:10px 20px 14px">Rank ${w.top.length} trades $${money(w.cutoff)}M a day; funds near the bottom move in and out often. "Research it" only marks a fund for you — ask Claude to research it like the others. History = years of trading (a strategy can often use the index's longer history).</div></section>
        <section class="card"><h2 class="h2">Weekly log</h2>${w.log.map((x) => `<div class="list-row"><div class="num" style="width:120px;font-weight:600">${U.dt(x.t)}</div>
          <div style="flex:1">${x.first_run ? 'Starting list' : x.new.length ? 'New: ' + x.new.join(', ') : 'Nothing new'}${x.left.length ? ' · Left: ' + x.left.join(', ') : ''}${x.cutoff != null ? ` · rank 50 at $${money(x.cutoff)}M a day` : ''}</div></div>`).join('') || '<div class="empty">No checks yet</div>'}</section>` : ''}
        <div class="muted small">Next check ${U.dt(w.next)} · data from Yahoo; a brand-new fund with very little trading can show up a week or two late.</div>`;
      el.querySelector('#chk').onclick = (e) => U.busy(e.target, async () => { await U.api('/api/etfwatch/check', { body: {} }); U.toast('Checking… this takes a minute or two'); setTimeout(load, 4000); });
      U.on(el, '[data-f]', 'click', (e, b) => { filter = b.dataset.f; load(); });
      V.etfBind(el, load);
      return w;
    }
    await load();
    U.api('/api/etfwatch/seen', { body: {} }).then(() => { const ce = document.getElementById('cnt-etfwatch'); if (ce) ce.classList.add('hidden'); }).catch(() => {});
    return { refresh: () => load().catch(() => {}), every: 60000 };
  };
})();
