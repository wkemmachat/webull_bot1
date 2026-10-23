/* Go-live checklist: readiness for real money, measured from the bot's own records (+ the user's own ticks). */
(function () {
  const V = window.Views || (window.Views = {});
  let gmode = null;

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
    return { cleanup: () => {}, refresh: () => load().catch(() => {}), every: 60000 };
  };
})();
