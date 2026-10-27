/* Router, top bar and sidebar. Views register in window.Views: Views[name] = async function (el, params) { ... return cleanup? } */
(function () {
  const V = window.Views || (window.Views = {});
  const view = document.getElementById('view');
  let cleanup = null, top = null, timer = null, routeGen = 0;

  const routes = [
    [/^\/?$/, 'dashboard'], [/^\/strategies\/new$/, 'strategyNew'], [/^\/strategies\/([\w-]+)$/, 'strategy'], [/^\/strategies$/, 'strategies'],
    [/^\/money$/, 'money'], [/^\/orders$/, 'orders'], [/^\/execution$/, 'execution'], [/^\/trades$/, 'trades'],
    [/^\/positions$/, 'positions'], [/^\/health$/, 'health'], [/^\/logs$/, 'logs'], [/^\/line$/, 'line'], [/^\/webull$/, 'webull'],
    [/^\/settings$/, 'settings'], [/^\/golive$/, 'golive'], [/^\/docs\/?([\w-]*)$/, 'docs'],
  ];

  async function route() {
    const h = (location.hash || '#/').slice(1).split('?')[0];
    let name = 'dashboard', params = [];
    for (const [re, n] of routes) { const m = h.match(re); if (m) { name = n; params = m.slice(1); break; } }
    const sect = h.split('/')[1] || '';
    document.querySelectorAll('[data-r]').forEach((a) => a.classList.toggle('on', a.dataset.r === sect));
    document.getElementById('side').classList.remove('open');
    if (cleanup) { try { cleanup(); } catch (e) {} cleanup = null; }
    clearInterval(timer);
    // each visit renders into its own box, so a slow page that finishes late cannot draw over the newer one
    const gen = ++routeGen;
    const box = document.createElement('div');
    box.className = 'page';
    view.replaceChildren(box);
    U.loading(box);
    window.scrollTo(0, 0);
    try {
      const fn = V[name];
      const r = await fn(box, params);
      const done = typeof r === 'function' ? r : (r && r.cleanup) || null;
      if (gen !== routeGen) { if (done) { try { done(); } catch (e) {} } return; }
      cleanup = done;
      if (r && r.refresh) timer = setInterval(r.refresh, r.every || 30000);
    } catch (e) { if (gen === routeGen) U.error(box, e); }
  }
  window.App = { route, refreshTop };

  async function refreshTop() {
    try { top = await U.api('/api/topbar'); } catch (e) { return; }
    const mode = U.mode();
    if (!top.modes.includes(mode)) { U.setMode(top.modes[0] || 'paper'); }
    document.querySelectorAll('#modeseg button').forEach((b) => {
      const m = b.dataset.m;
      b.classList.toggle('on', m === U.mode());
      b.disabled = !top.modes.includes(m);
      b.title = top.modes.includes(m) ? '' : 'Switch this mode on in Settings';
    });
    const mk = document.getElementById('mkt');
    mk.innerHTML = `${U.dot(top.market.open ? 'var(--up)' : 'var(--warn-fg)')}${U.esc(top.market.text)}`;
    const m = U.mode();
    const wb = document.getElementById('wb');
    if (m === 'paper') wb.innerHTML = `${U.dot('var(--up)')}Paper broker`;
    else {
      const c = top.conn[m] || {};
      wb.innerHTML = `${U.dot(c.status === 'connected' ? 'var(--up)' : 'var(--dn)')}Webull ${m === 'test' ? 'test ' : ''}${U.esc(c.status)}`;
    }
    const sc = document.getElementById('sch');
    sc.innerHTML = top.scheduler.enabled ? `${U.dot(top.scheduler.ok ? 'var(--up)' : 'var(--dn)')}Scheduler ${top.scheduler.ok ? 'running' : 'late'}`
      : `${U.dot('var(--dn)')}Scheduler off on this copy`;
    document.getElementById('clock').textContent = `BKK ${top.bkk} · NY ${top.ny}`;
    document.getElementById('who').textContent = top.username;
    document.getElementById('ver').textContent = `v${top.version}${top.data_source !== 'yahoo' ? ' · data: ' + top.data_source : ''}`;
    document.getElementById('pausedbar').classList.toggle('hidden', !top.paused);
    const pb = document.getElementById('pauseall');
    pb.innerHTML = top.paused ? 'Resume<span class="hide-s"> trading</span>' : 'Pause<span class="hide-s"> all trading</span>';
    pb.className = top.paused ? 'btn p s' : 'btn d s';
    const cp = document.getElementById('cnt-plans');
    const np = top.issues.plans_by_mode ? (top.issues.plans_by_mode[U.mode()] || 0) : top.issues.plans;   // the mode you are looking at
    cp.textContent = np; cp.classList.toggle('hidden', !np);
    const ch = document.getElementById('cnt-health');
    ch.textContent = top.issues.health; ch.classList.toggle('hidden', !top.issues.health);
  }

  async function setPaused(on) {
    if (on && !(await U.confirm('Pause all trading?', 'No order lots are sent until you resume. Plans stay queued and new signals are still recorded.',
      { ok: 'Pause all trading', danger: true }))) return;
    await U.api('/api/pause', { body: { paused: on } });
    U.toast(on ? 'All trading paused' : 'Trading resumed');
    refreshTop(); route();
  }

  document.getElementById('modeseg').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    U.setMode(b.dataset.m); refreshTop(); route();
  });
  document.getElementById('pauseall').onclick = () => setPaused(!(top && top.paused));
  document.getElementById('resume').onclick = (e) => { e.preventDefault(); setPaused(false); };
  document.getElementById('logout').onclick = async () => { await U.api('/api/logout', { body: {} }); location.href = '/login'; };
  document.getElementById('burger').onclick = () => document.getElementById('side').classList.toggle('open');
  document.getElementById('more').onclick = (e) => { e.preventDefault(); document.getElementById('side').classList.toggle('open'); };
  document.addEventListener('click', (e) => {
    const s = document.getElementById('side');
    if (s.classList.contains('open') && !s.contains(e.target) && !e.target.closest('#burger,#more')) s.classList.remove('open');
  });
  window.addEventListener('hashchange', route);
  refreshTop().then(route);
  setInterval(refreshTop, 30000);
})();
