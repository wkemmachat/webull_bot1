(function () {
  const V = window.Views || (window.Views = {});

  /* ---------------------------------------------------------------- LINE */
  V.line = async function (el) {
    const d = await U.api('/api/line');
    const s = d.settings;
    const ev = {};
    s.events.forEach((e) => (ev[e.key] = e.mode));
    let rec = s.recipients.slice(), times = s.digest_times.slice();
    const strat = {};
    d.strategies.forEach((x) => (strat[x.id] = x.line_on));
    const q = d.summary.quota || {};
    function render() {
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">LINE Messaging API</div><h1 class="h1">LINE alerts</h1>
        <div class="muted" style="margin-top:4px">Choose what arrives at once, what waits for the digest, and what never comes.</div></div>
        <div class="row"><button class="btn" id="test">Send test message</button><button class="btn p" id="save">Save</button></div></div>
      ${!d.summary.configured ? '<div class="note warn">Not set up yet: paste the channel access token and add yourself as a recipient (your user ID starts with U). Docs → LINE alerts shows where to find them.</div>' : ''}
      <div class="grid" style="--min:380px">
        <section class="card col" style="gap:14px"><div class="row sb"><h2 class="h2">Connection</h2>${U.pill(d.summary.configured ? 'ok' : 'warn', d.summary.configured ? 'Ready' : 'Not set up')}</div>
          <div class="f"><label for="tok">Channel access token (long-lived)</label><input class="in num" id="tok" type="password" placeholder="${s.token_set ? 'saved · ' + U.esc(s.token_hint) + ' (leave empty to keep)' : 'paste the token from the LINE Developers console'}"></div>
          <div class="f"><label>Send to</label><div class="col" style="gap:8px" id="recs">${rec.map((r, i) => `<div class="row" style="gap:10px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;flex-wrap:nowrap">
              <button class="sw ${r.enabled !== false ? 'on' : ''}" data-ren="${i}" role="switch" aria-label="Enabled"></button>
              <input class="in" style="height:34px;flex:1 1 90px" data-rname="${i}" value="${U.esc(r.name || '')}" placeholder="Name">
              <input class="in num" style="height:34px;flex:2 1 140px" data-rid="${i}" value="${U.esc(r.id)}" placeholder="U… or C…">
              <select class="in" style="height:34px;width:auto" data-rscope="${i}"><option value="all" ${r.scope !== 'reports' ? 'selected' : ''}>everything</option><option value="reports" ${r.scope === 'reports' ? 'selected' : ''}>reports only</option></select>
              <button class="x" data-rdel="${i}" aria-label="Remove">×</button></div>`).join('')}
            <button class="btn s" id="addrec" style="align-self:flex-start">+ Add recipient</button></div></div>
          <div class="col" style="gap:6px"><div class="row sb small"><span class="muted">Messages this month</span><span class="num">${q.limit ? q.used + ' / ' + q.limit : q.used != null ? q.used + ' (no limit)' : '—'}</span></div>
            <div class="bar"><div style="position:absolute;left:0;top:0;bottom:0;width:${q.limit ? Math.min(100, q.used / q.limit * 100) : 0}%;background:var(--accent)"></div></div>
            <span class="muted small">From LINE's quota API (<a href="#" id="rq">refresh</a>). At 90% non-critical instant alerts move to the digest.</span></div>
        </section>
        <section class="card col" style="gap:16px"><h2 class="h2">When to send</h2>
          <div class="f"><label>Digest times (Bangkok)</label><div class="row" style="gap:8px" id="times">${times.map((t, i) => `<span class="pill num" style="font-size:13.5px;padding:7px 12px">${t} <button class="x" style="width:20px;height:20px;font-size:14px" data-tdel="${i}" aria-label="Remove">×</button></span>`).join('')}
            <input class="in num" id="newt" placeholder="HH:MM" style="width:90px;height:34px"><button class="btn s" id="addt">+ Add</button></div>
            <span class="h">Everything set to "Digest" since the last one, in one message${s.per_strategy ? ' per strategy' : ''}.</span></div>
          <div class="row" style="gap:12px;flex-wrap:nowrap;align-items:flex-start"><button class="sw ${s.quiet ? 'on' : ''}" id="quiet" role="switch" aria-label="Quiet hours"></button>
            <div><b style="font-weight:500">Quiet hours</b> <input class="in num" id="qf" value="${s.quiet_from}" style="width:76px;height:30px"> – <input class="in num" id="qt" value="${s.quiet_to}" style="width:76px;height:30px">
            <div class="muted small">Instant alerts wait until quiet hours end — except critical ones (failed order, Webull disconnected, new sign-in, health problem).</div></div></div>
          <div class="row" style="gap:12px"><button class="sw ${s.per_strategy ? 'on' : ''}" id="per" role="switch" aria-label="One message per strategy"></button><span>One digest message per strategy <span class="muted small">(off = one combined message)</span></span></div>
        </section>
      </div>
      <div class="g2">
        <section class="card"><div class="row sb" style="margin-bottom:6px"><h2 class="h2">What to send</h2><span class="muted small"><b style="color:var(--err-fg)">critical</b> alerts ignore quiet hours and cannot be switched off</span></div>
          ${s.events.map((e) => `<div class="kv" style="align-items:center;padding:12px 4px"><div style="min-width:0"><div class="row" style="gap:8px"><b style="font-weight:500">${U.esc(e.label)}</b>${e.critical ? U.pill('err', 'critical') : ''}</div><div class="muted small">${U.esc(e.desc)}</div></div>
            <div class="seg" data-ev="${e.key}"><button data-v="instant" class="${ev[e.key] === 'instant' ? 'on' : ''}">Instant</button><button data-v="digest" class="gi ${ev[e.key] === 'digest' ? 'on' : ''}">Digest</button>
              <button data-v="off" class="${ev[e.key] === 'off' ? 'on' : ''}" ${e.critical ? 'disabled' : ''}>Off</button></div></div>`).join('')}</section>
        <div class="col" style="gap:20px">
          <section class="card col" style="gap:12px"><h2 class="h2">Preview</h2>${d.preview.map((p) => `<div class="row" style="align-items:flex-start;gap:10px;flex-wrap:nowrap"><img class="logo-img" src="/static/icons/favicon.svg?v=4" alt="" width="32" height="32">
            <div style="background:var(--seg);border-radius:4px 16px 16px 16px;padding:12px 14px;font-size:13px;white-space:pre-line">${U.esc(p)}</div></div>`).join('')}</section>
          <section class="card"><h2 class="h2" style="margin-bottom:6px">Strategies sending alerts</h2>${d.strategies.map((x) => `<div class="kv" style="align-items:center"><span class="row" style="gap:8px">${U.dot(x.color)}${U.esc(x.name)}</span>
            <button class="sw ${strat[x.id] ? 'on' : ''}" data-strat="${x.id}" role="switch" aria-label="LINE for ${U.esc(x.name)}"></button></div>`).join('')}</section>
          <section class="card"><h2 class="h2" style="margin-bottom:6px">Recently sent</h2>${d.recent.slice(0, 8).map((r) => `<div class="kv small"><span class="num muted" style="width:96px">${U.dt(r.t)}</span>
            <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(r.title)}</span>${U.pill(r.status === 'sent' ? 'ok' : r.status === 'failed' ? 'err' : r.status === 'skipped' ? '' : 'warn', r.status === 'held' ? 'held · quiet hours' : r.status === 'pending' && r.delivery === 'digest' ? 'in next digest' : r.status)}</div>`).join('') || '<div class="muted small">Nothing yet</div>'}</section>
        </div>
      </div>`;
      U.on(el, '[data-ev] button', 'click', (e, b) => { ev[b.parentElement.dataset.ev] = b.dataset.v; b.parentElement.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); });
      U.on(el, '.sw', 'click', (e, b) => { b.classList.toggle('on'); if (b.dataset.strat) strat[b.dataset.strat] = b.classList.contains('on'); });
      const readRec = () => { rec = rec.map((r, i) => ({ id: el.querySelector(`[data-rid="${i}"]`).value.trim(), name: el.querySelector(`[data-rname="${i}"]`).value.trim(),
        scope: el.querySelector(`[data-rscope="${i}"]`).value, enabled: el.querySelector(`[data-ren="${i}"]`).classList.contains('on') })); };
      el.querySelector('#addrec').onclick = () => { readRec(); rec.push({ id: '', name: rec.length ? '' : 'Me', enabled: true, scope: 'all' }); render(); };
      U.on(el, '[data-rdel]', 'click', (e, b) => { readRec(); rec.splice(+b.dataset.rdel, 1); render(); });
      U.on(el, '[data-tdel]', 'click', (e, b) => { readRec(); times.splice(+b.dataset.tdel, 1); render(); });
      el.querySelector('#addt').onclick = () => { const v = el.querySelector('#newt').value.trim(); if (!/^\d{1,2}:\d{2}$/.test(v)) { U.toast('Use HH:MM', 'err'); return; } readRec(); times.push(v); times.sort(); render(); };
      el.querySelector('#rq').onclick = async (e) => { e.preventDefault(); try { await U.api('/api/line/quota', { body: {} }); V.line(el); } catch (x) { U.toast(x.message, 'err'); } };
      el.querySelector('#save').onclick = (e) => U.busy(e.target, async () => {
        readRec();
        await U.api('/api/line', { body: { token: el.querySelector('#tok').value.trim() || undefined, recipients: rec.filter((r) => r.id), digest_times: times,
          quiet: el.querySelector('#quiet').classList.contains('on'), quiet_from: el.querySelector('#qf').value, quiet_to: el.querySelector('#qt').value,
          per_strategy: el.querySelector('#per').classList.contains('on'), events: ev, strategies: strat } });
        U.toast('LINE settings saved'); V.line(el);
      });
      el.querySelector('#test').onclick = (e) => U.busy(e.target, async () => { await U.api('/api/line/test', { body: {} }); U.toast('Test message sent'); });
    }
    render();
  };

  /* ---------------------------------------------------------------- Webull */
  V.webull = async function (el) {
    let d = await U.api('/api/webull');
    let poll = null;
    function envCard(env, title, desc, sub) {
      const st = d[env] || {};
      const on = d.modes.includes(env);
      const conn = env === 'paper' ? true : st.connected;
      return `<div class="card col" style="gap:8px;${env === 'live' && on ? 'border-color:color-mix(in srgb, var(--dn) 45%, var(--line))' : ''}">
        <div class="row sb"><b style="font-size:16px;${env === 'live' ? 'color:var(--err-fg)' : ''}">${title}</b>${U.pill(conn ? 'ok' : st.status === 'connecting' ? 'warn' : '', env === 'paper' ? 'ready' : (st.status || 'not connected'))}${on ? U.pill('info', 'on') : ''}</div>
        <div class="muted small">${desc}</div><div class="num muted small">${sub}</div></div>`;
    }
    function keys(env) {
      const st = d[env];
      return `<section class="card col" style="gap:14px"><div class="row sb"><h2 class="h2">${env === 'live' ? 'Live' : 'Test'} API keys</h2>${U.pill(st.connected ? 'ok' : st.status === 'connecting' ? 'warn' : '', st.status || 'not connected')}</div>
        ${st.status === 'connecting' ? `<div class="note warn"><span class="spin"></span><span>${U.esc(st.msg)}</span></div>` : st.status === 'error' ? `<div class="note err">${U.esc(st.msg)}</div>` : ''}
        <div class="f"><label for="${env}-k">App Key</label><input class="in num" id="${env}-k" placeholder="${st.key_hint ? 'saved · ' + U.esc(st.key_hint) + ' (leave empty to keep)' : 'App Key'}"></div>
        <div class="f"><label for="${env}-s">App Secret</label><input class="in num" id="${env}-s" type="password" placeholder="${st.has_keys ? 'saved (leave empty to keep)' : 'App Secret'}"></div>
        <div class="fs"><div class="f"><label for="${env}-a">Account ID (optional)</label><input class="in num" id="${env}-a" value="${U.esc(st.account_id || '')}" placeholder="found automatically"></div>
          ${env === 'test' ? `<div class="f"><label for="test-e">Test server</label><input class="in num" id="test-e" value="${U.esc(st.endpoint || '')}"></div>` : ''}</div>
        ${env === 'test' ? `<div class="row" style="gap:6px"><span class="muted small">Webull's shared test accounts (public, no application needed):</span>${[1, 2, 3].map((n) => `<button class="btn s" data-shared="${n}">Use #${n}</button>`).join('')}</div>` : ''}
        <div class="muted small">${env === 'live' ? 'webull.co.th → your photo → Developer Tool → API Management → API Keys Management. Tick <b>Market data</b> and <b>Trading</b>; IP whitelist: your server\'s IP. Stored encrypted on your server.'
          : 'Test server th-api.uat.webullbroker.com. Shared accounts are used by everyone: orders and positions there can change at any time.'}</div>
        <div class="row"><button class="btn" data-a="keys" data-env="${env}">Save keys</button><button class="btn p" data-a="connect" data-env="${env}">${st.connected ? 'Reconnect' : 'Connect'}</button>
          <button class="btn" data-a="test" data-env="${env}">Test connection</button>${st.connected ? `<button class="btn d" data-a="disconnect" data-env="${env}">Disconnect</button>` : ''}</div>
        <div class="kv"><span class="muted">Last used</span><span class="num">${U.dt(st.used_at || st.at)}</span></div>
        <div class="kv"><span class="muted">Webull token valid until</span><span class="num">${st.lapses_at ? U.dtLong(st.lapses_at) : '—'}${st.token_status ? ' · ' + U.esc(st.token_status) : ''}</span></div></section>`;
    }
    function render() {
      el.innerHTML = `<div class="page-head"><div><div class="eyebrow">Webull OpenAPI · region ${U.esc(d.region)}</div><h1 class="h1">Webull connection</h1>
        <div class="muted" style="margin-top:4px">Each mode keeps its own keys, login and books, so test trades never mix with real ones. Switch modes on in Settings.</div></div><a class="btn" href="#/settings">Trading modes</a></div>
        <div class="grid" style="--min:280px">${envCard('paper', 'Paper', 'Pretend money inside the bot at live prices. Nothing is sent to Webull.', 'Start balance ' + U.usd(d.paper.start_cash, 0) + ' · cash now ' + U.usd(d.paper.cash, 0))}
          ${envCard('test', 'Webull test', "Webull's test server with a test account. Real API calls, no real money.", U.esc(d.test.endpoint))}
          ${envCard('live', 'Live', 'Your real Webull Thailand account. Switching it on asks you to type LIVE.', 'Real money · region ' + U.esc(d.region))}</div>
        <div class="grid" style="--min:400px">${keys('live')}${keys('test')}</div>
        <section class="card col" style="gap:12px"><div class="eyebrow">How connecting works</div>
          <div class="row" style="gap:12px;flex-wrap:nowrap;align-items:flex-start">${U.pill('ok', '1')}<div><b style="font-weight:500">Paste App Key and Secret, then press Connect</b></div></div>
          <div class="row" style="gap:12px;flex-wrap:nowrap;align-items:flex-start">${U.pill('ok', '2')}<div><b style="font-weight:500">Approve the prompt in the Webull app within 5 minutes</b><div class="muted small">Webull app → Menu → Messages → OpenAPI Notifications (SMS code).</div></div></div>
          <div class="row" style="gap:12px;flex-wrap:nowrap;align-items:flex-start">${U.pill('ok', '3')}<div><b style="font-weight:500">The token is saved on the server</b><div class="muted small">Webull sets how long it lasts (shown above). Before it ends, the Health check and LINE remind you to press Reconnect. The bot never starts a new login by itself.</div></div></div></section>
        <div id="acct"></div>`;
      U.on(el, '[data-shared]', 'click', (e, b) => U.busy(b, async () => {
        d = await U.api('/api/webull/test/keys', { body: { shared: +b.dataset.shared } });
        U.toast(`Shared test account #${b.dataset.shared} filled in. Press Connect, then Test connection.`); render();
      }));
      U.on(el, '[data-a]', 'click', (e, b) => U.busy(b, async () => {
        const env = b.dataset.env, a = b.dataset.a;
        if (a === 'keys') {
          const body = { app_key: el.querySelector(`#${env}-k`).value.trim() || undefined, app_secret: el.querySelector(`#${env}-s`).value.trim() || undefined,
            account_id: el.querySelector(`#${env}-a`).value.trim() };
          if (env === 'test') body.endpoint = el.querySelector('#test-e').value.trim();
          d = await U.api(`/api/webull/${env}/keys`, { body }); U.toast('Keys saved'); render();
        } else if (a === 'test') {
          const r = await U.api(`/api/webull/${env}/test`, { body: {} });
          const acc = r.account;
          el.querySelector('#acct').innerHTML = `<section class="card"><h2 class="h2" style="margin-bottom:6px">Account (from Webull ${env}) · ${r.ms} ms</h2>
            <div class="kv"><span class="muted">Account</span><span class="num">${U.esc(acc.account_id)}</span></div><div class="kv"><span class="muted">Total value</span><span class="num">${U.usd(acc.total)}</span></div>
            <div class="kv"><span class="muted">Cash</span><span class="num">${U.usd(acc.cash)}</span></div><div class="kv"><span class="muted">Buying power</span><span class="num">${U.usd(acc.buying_power)}</span></div>
            <div class="kv"><span class="muted">Positions</span><span class="num">${Object.entries(acc.positions || {}).map(([k, p]) => `${k} ${U.n(p.qty, 0)}`).join(', ') || 'none'}</span></div></section>`;
        } else {
          if (a === 'disconnect' && !(await U.confirm('Disconnect?', 'The saved login is put aside. Orders cannot be sent in this mode until you connect again.', { danger: true, ok: 'Disconnect' }))) return;
          d = await U.api(`/api/webull/${env}/${a}`, { body: {} });
          render();
          if (a === 'connect') { U.toast('Approve the login in the Webull app (5 minutes)'); startPoll(); }
        }
      }));
    }
    function startPoll() {
      clearInterval(poll);
      poll = setInterval(async () => {
        d = await U.api('/api/webull');
        if (!['connecting'].includes(d.live.status) && !['connecting'].includes(d.test.status)) clearInterval(poll);
        render(); App.refreshTop();
      }, 4000);
    }
    render();
    if (d.live.status === 'connecting' || d.test.status === 'connecting') startPoll();
    return () => clearInterval(poll);
  };

  /* ---------------------------------------------------------------- settings */
  V.settings = async function (el) {
    const d = await U.api('/api/settings');
    let theme = (localStorage.getItem('theme') || d.display.theme || 'light');
    const sec = (id, title, inner, extra) => `<section class="card" id="${id}" ${extra || ''}><h2 class="h2" style="margin-bottom:4px">${title}</h2>${inner}</section>`;
    const set = (t, h, c) => `<div style="display:grid;grid-template-columns:minmax(200px,1fr) minmax(240px,1.3fr);gap:16px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line2)"><div><b style="font-weight:500">${t}</b>${h ? `<div class="muted small">${h}</div>` : ''}</div><div>${c}</div></div>`;
    el.innerHTML = `<div><div class="eyebrow">Configure</div><h1 class="h1">Settings</h1></div>
    <div class="row" style="gap:24px;align-items:flex-start;flex-wrap:wrap">
      <nav class="toc" style="flex:1 1 180px;max-width:220px;position:sticky;top:80px">${[['modes', 'Trading modes'], ['sec', 'Login & security'], ['disp', 'Display'], ['data', 'Data'], ['srv', 'Server & backups'], ['dz', 'Danger zone']].map(([k, l]) => `<a href="#/settings" data-jump="${k}">${l}</a>`).join('')}</nav>
      <div class="col" style="flex:999 1 560px;min-width:0;gap:20px">
        ${sec('modes', 'Trading modes', `<div class="muted small" style="margin-bottom:6px">Every mode that is on runs at the same time, each with its own money and books. The switch at the top of each page chooses which one you look at.</div>
          ${set('Paper', 'Pretend money inside the bot, live prices.', `<button class="sw ${d.modes.paper ? 'on' : ''}" data-mode="paper" role="switch"></button>`)}
          ${set('Webull test', 'Webull test server and test account.', `<button class="sw ${d.modes.test ? 'on' : ''}" data-mode="test" role="switch"></button>`)}
          ${set('Live — real money', 'Your Webull account. Asks you to type LIVE.', `<button class="sw ${d.modes.live ? 'on' : ''}" data-mode="live" role="switch"></button>`)}`)}
        ${sec('sec', 'Login & security', `${set('Username', 'Used with your password to sign in', `<span class="num">${U.esc(d.user.username)}</span>`)}
          ${set('Password', 'Changed ' + U.dt(d.user.pw_changed_at) + ' · at least 10 characters', '<button class="btn s" id="pw">Change password</button>')}
          ${set('Lock after wrong passwords', 'Then wait 15 minutes · LINE is told', '<span class="num">5 tries</span>')}
          <div class="col" style="gap:8px;padding-top:14px"><b style="font-weight:500">Signed-in devices</b>${d.sessions.map((s) => `<div class="row sb" style="padding:10px 12px;border:1px solid var(--line);border-radius:10px">
            <div><b style="font-weight:500">${U.esc(s.device)}</b> ${s.current ? U.pill('info', 'this device') : ''}<div class="muted small">${U.esc(s.ip)} · last seen ${U.ago(s.last_seen)}</div></div>
            ${s.current ? '' : `<button class="btn s" data-rev="${s.id}">Sign out</button>`}</div>`).join('')}</div>`)}
        ${sec('disp', 'Display', `${set('Language', 'The app is in English. LINE messages follow the LINE page.', '<span class="pill">English</span>')}
          ${set('Theme', '', `<div class="seg" id="th">${[['dark', 'Dark'], ['light', 'Light'], ['auto', 'Follow device']].map(([k, l]) => `<button data-v="${k}" class="${theme === k ? 'on' : ''}">${l}</button>`).join('')}</div>`)}
          ${set('Time shown', 'New York time is shown next to it where it matters', 'Bangkok (UTC+7)')}`)}
        ${sec('data', 'Data', `${set('Price source', d.data.source === 'csv' ? 'OFFLINE demo files (DATA_SOURCE=csv in .env)' : 'Yahoo Finance: GC=F / SI=F hourly futures, ETF daily bars, 1-minute quotes', `<span class="pill ${d.data.source === 'csv' ? 'warn' : 'ok'}">${U.esc(d.data.source)}</span> <button class="btn s" id="refresh">Refresh now</button>`)}
          <div class="tw" style="margin-top:10px"><table class="t"><thead><tr><th>Series</th><th>Status</th><th>Updated</th></tr></thead><tbody>${Object.entries(d.data.status).map(([k, v]) => `<tr><td class="num">${U.esc(k)}</td>
            <td>${U.pill(v.ok ? 'ok' : 'err', v.ok ? 'ok' : 'error')}${v.error ? ' <span class="muted small">' + U.esc(v.error) + '</span>' : ''}</td><td class="num">${U.dt(v.at)}</td></tr>`).join('')}</tbody></table></div>
          <div class="muted small" style="margin-top:10px">Contract rolls removed from the futures history: ${d.data.rolls.length ? d.data.rolls.map((r) => `${r.symbol} ${U.day(r.t)} ${(r.gap * 100).toFixed(2)}%`).join(' · ') : 'none detected yet'}.</div>`)}
        ${sec('srv', 'Server & backups', `${set('Scheduler on this copy', 'Only ONE copy may run it. Turn it off on your Mac (SCHEDULER_ENABLED=0 in .env) once the server is live.', `${U.pill(d.server.scheduler ? 'ok' : 'err', d.server.scheduler ? 'running here' : 'off here')}`)}
          ${set('Version', '', `<span class="num">v${U.esc(d.server.version)} · started ${U.dt(d.server.started)}</span>`)}
          ${set('Public address', 'PUBLIC_URL in .env, used in LINE messages', `<span class="num small">${U.esc(d.server.public_url)}</span>`)}
          ${set('Nightly backup', '03:30 Bangkok · kept 30 days · ' + (d.server.backups.length ? 'last ' + U.esc(d.server.backups[d.server.backups.length - 1].name) : 'none yet'), '<a class="btn s" href="/api/backup">Download backup now</a>')}`)}
        ${sec('dz', 'Danger zone', `${set('Paper settings', 'Start balance and money per strategy for the next reset', `<div class="row"><input class="in num" id="pc" value="${U.esc(d.paper.start_cash)}" style="width:120px"><input class="in num" id="ps" value="${U.esc(d.paper.strategy_cash)}" style="width:110px"></div>`)}
          ${set('Reset the paper account', 'Clears paper trades and money; test and live are untouched. Asks you to type RESET.', '<button class="btn d s" id="reset">Reset paper…</button>')}
          ${set('Sell everything and stop', 'All strategies: Stop & sell, in every mode that is on. Asks you to type STOP.', '<button class="btn d s" id="stopall">Stop all…</button>')}`, 'style="border-color:color-mix(in srgb, var(--dn) 35%, var(--line))"')}
      </div></div>`;
    U.on(el, '[data-jump]', 'click', (e, a) => { e.preventDefault(); el.querySelector('#' + a.dataset.jump).scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    U.on(el, '[data-mode]', 'click', async (e, b) => {
      const m = b.dataset.mode, on = !b.classList.contains('on');
      let confirm;
      if (m === 'live' && on) { confirm = await U.confirm('Switch on LIVE trading?', 'The bot will place real orders in your Webull account for every strategy that has live money.', { danger: true, word: 'LIVE', ok: 'Switch on live' }); if (!confirm) return; }
      try { await U.api('/api/settings', { body: { modes: { [m]: on }, confirm } }); b.classList.toggle('on', on); U.toast('Saved'); App.refreshTop(); } catch (x) { U.toast(x.message, 'err'); }
    });
    U.on(el, '#th button', 'click', async (e, b) => {
      theme = b.dataset.v;
      try { localStorage.setItem('theme', theme); } catch (x) {}
      document.documentElement.dataset.theme = theme === 'auto' ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark') : theme;
      el.querySelectorAll('#th button').forEach((x) => x.classList.toggle('on', x === b));
      await U.api('/api/settings', { body: { theme } });
    });
    U.on(el, '[data-rev]', 'click', async (e, b) => { await U.api(`/api/sessions/${b.dataset.rev}/revoke`, { body: {} }); U.toast('Signed out'); V.settings(el); });
    el.querySelector('#refresh').onclick = async () => { await U.api('/api/data/refresh', { body: {} }); U.toast('Refreshing prices…'); };
    el.querySelector('#pw').onclick = () => U.modal('Change password', `<div class="f"><label for="o">Current password</label><input class="in" type="password" id="o" autocomplete="current-password"></div>
      <div class="f"><label for="n1">New password (10+ characters)</label><input class="in" type="password" id="n1" autocomplete="new-password"></div>
      <div class="f"><label for="n2">Repeat new password</label><input class="in" type="password" id="n2" autocomplete="new-password"></div>
      <div class="muted small">Other devices are signed out.</div><div class="row" style="justify-content:flex-end"><button class="btn p" id="go">Change password</button></div>`, {
      width: 460, onOpen: (box, close) => { box.querySelector('#go').onclick = (e) => U.busy(e.target, async () => {
        if (box.querySelector('#n1').value !== box.querySelector('#n2').value) throw new Error('The new passwords are not the same');
        await U.api('/api/settings/password', { body: { old: box.querySelector('#o').value, new: box.querySelector('#n1').value } });
        U.toast('Password changed'); close(); }); } });
    el.querySelector('#reset').onclick = async () => {
      if (!(await U.confirm('Reset the paper account?', `Paper trades, money and plans are cleared. The account restarts with ${U.usd(+el.querySelector('#pc').value, 0)} and each strategy gets ${U.usd(+el.querySelector('#ps').value, 0)}.`, { danger: true, word: 'RESET', ok: 'Reset paper' }))) return;
      await U.api('/api/reset-paper', { body: { confirm: 'RESET', start_cash: el.querySelector('#pc').value, strategy_cash: el.querySelector('#ps').value } });
      U.toast('Paper account reset'); App.refreshTop();
    };
    el.querySelector('#stopall').onclick = async () => {
      if (!(await U.confirm('Stop all strategies?', 'Every strategy sells everything with a split plan, in every mode that is on.', { danger: true, word: 'STOP', ok: 'Stop all' }))) return;
      await U.api('/api/stop-all', { body: { confirm: 'STOP' } }); U.toast('All strategies stopping');
    };
  };
})();
