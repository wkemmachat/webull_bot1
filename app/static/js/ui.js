/* Shared helpers: API calls, formatting, small UI pieces (toast, modal, confirm). Global namespace: U. */
(function () {
  const TZ = 'Asia/Bangkok';
  const U = (window.U = {});

  U.api = async function (path, opts) {
    opts = opts || {};
    const init = { method: opts.method || (opts.body ? 'POST' : 'GET'), headers: {} };
    if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
    const r = await fetch(path, init);
    if (r.status === 401) { location.href = '/login'; throw new Error('Please sign in'); }
    const ct = r.headers.get('content-type') || '';
    const j = ct.includes('json') ? await r.json() : await r.text();
    if (!r.ok) throw new Error((j && j.detail) || ('Error ' + r.status));
    return j;
  };

  U.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  };
  U.mode = function () { try { return localStorage.getItem('mode') || 'paper'; } catch (e) { return 'paper'; } };
  U.setMode = function (m) { try { localStorage.setItem('mode', m); } catch (e) {} };
  U.modeLabel = { paper: 'Paper', test: 'Webull test', live: 'Live' };

  U.usd = function (v, dp) {
    if (v == null || isNaN(v)) return '—';
    dp = dp == null ? 2 : dp;
    const s = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return (v < 0 ? '−$' : '$') + s;
  };
  U.sgnUsd = function (v, dp) { if (v == null || isNaN(v)) return '—'; return (v >= 0 ? '+' : '') + U.usd(v, dp); };
  U.pct = function (v, dp) {
    if (v == null || isNaN(v)) return '—';
    dp = dp == null ? 1 : dp;
    const s = (Math.abs(v) * 100).toFixed(dp) + '%';
    return v > 0 ? '+' + s : v < 0 ? '−' + s : s;
  };
  U.n = function (v, dp) {
    if (v == null || isNaN(v)) return '—';
    return Number(v).toLocaleString('en-US', { minimumFractionDigits: dp || 0, maximumFractionDigits: dp == null ? 2 : dp });
  };
  U.cls = function (v) { return v > 0 ? 'up' : v < 0 ? 'dn' : ''; };
  const fmt = (o) => new Intl.DateTimeFormat('en-GB', Object.assign({ timeZone: TZ }, o));
  U.time = function (t) { return t ? fmt({ hour: '2-digit', minute: '2-digit', hour12: false }).format(t * 1000) : '—'; };
  U.day = function (t) { return t ? fmt({ day: 'numeric', month: 'short' }).format(t * 1000) : '—'; };
  U.dt = function (t) {
    if (!t) return '—';
    const d = new Date(t * 1000), now = new Date();
    const same = fmt({ year: 'numeric', month: 'numeric', day: 'numeric' }).format(d) === fmt({ year: 'numeric', month: 'numeric', day: 'numeric' }).format(now);
    return same ? 'Today ' + U.time(t) : U.day(t) + ' ' + U.time(t);
  };
  U.dtLong = function (t) { return t ? fmt({ weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).format(t * 1000) : '—'; };
  U.ago = function (t) {
    if (!t) return 'never';
    const s = Date.now() / 1000 - t;
    if (s < 90) return 'just now';
    if (s < 3600) return Math.round(s / 60) + ' min ago';
    if (s < 86400 * 2) return Math.round(s / 3600) + ' h ago';
    return Math.round(s / 86400) + ' days ago';
  };
  U.pill = function (cls, text) { return `<span class="pill ${cls || ''}">${U.esc(text)}</span>`; };
  /* A strategy's state: the signal (pill in the signal's colour) and, on its own line, what the bot is doing about it. */
  U.stateBlock = function (s, extra) {
    const a = s.activity;
    const icon = { queued: '◷', running: '●', waiting: '○' };
    return `<div class="col" style="gap:5px;align-items:flex-start;min-width:0">
      <span class="pill wrap ${s.state_cls || ''}">${U.esc(s.state_label || s.label || '—')}</span>
      ${a ? `<span class="act ${a.kind}"><i aria-hidden="true">${icon[a.kind] || '•'}</i>${U.esc(a.text)}</span>` : ''}
      ${extra || ''}</div>`;
  };
  U.dur = function (days) {
    if (days == null) return '—';
    if (days < 60) return days + ' day' + (days === 1 ? '' : 's');
    if (days < 730) return (days / 30.44).toFixed(days < 300 ? 1 : 0) + ' months';
    return (days / 365.25).toFixed(1) + ' years';
  };
  U.durShort = function (days) {
    if (days == null) return '—';
    if (days < 60) return days + ' d';
    if (days < 730) return Math.round(days / 30.44) + ' mo';
    return (days / 365.25).toFixed(1) + ' yr';
  };
  /* "Today +$120 (+0.8%)" and "worst fall −37% · underwater up to 14 mo" for a strategy card */
  U.todayLine = function (s) {
    if (!s.today) return '';
    const lab = s.today.live ? 'Today' : new Date(s.today.day + 'T00:00:00Z').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
    return `<span class="num small ${U.cls(s.today.pnl)}" title="${s.today.live ? 'This US session so far' : 'Last completed US session'} (money moved that day left out)">${lab} ${U.sgnUsd(s.today.pnl, 0)}${s.today.pct != null ? ' (' + U.pct(s.today.pct, 2) + ')' : ''}</span>`;
  };
  /* Stopped strategies with no money in this mode are hidden on Home and Strategies unless the viewer shows them */
  U.showIdle = function (v) {
    try {
      if (v === undefined) return localStorage.getItem('showIdle') === '1';
      localStorage.setItem('showIdle', v ? '1' : '0');
    } catch (e) { U._showIdle = !!v; }
    return v === undefined ? !!U._showIdle : v;
  };
  U.idleToggle = function (n, on) {
    if (!n) return '';
    return `<span class="muted">${on ? '' : `${n} stopped with no money hidden`}</span><button class="btn s" data-idle="1">${on ? 'Hide stopped (' + n + ')' : 'Show stopped (' + n + ')'}</button>`;
  };
  /* Buy zone of a strategy (its underwater percentile): 70–80 "Buy zone" (green), 80–100 "Strong buy zone" (solid dark green) */
  U.dipCls = function (d) { return d && d.zone === 'deep' ? 'dipz2' : d && d.zone === 'dip' ? 'dipz1' : ''; };
  U.ordinal = function (n) { n = Math.round(n); const t = n % 100, e = n % 10; return n + (t >= 11 && t <= 13 ? 'th' : e === 1 ? 'st' : e === 2 ? 'nd' : e === 3 ? 'rd' : 'th'); };
  U.dipPill = function (d) {
    if (!d || !d.zone) return '';
    const deep = d.zone === 'deep';
    const tip = `${d.depth}% below its backtest high: deeper than ${d.pct}% of its days in the last ${d.years} years (70th = ${d.p70}%, 80th = ${d.p80}%, 90th = ${d.p90}%). As of ${d.day}. In the backtests, money added in this zone was more often up a year later — a statistic, not a promise.`;
    return `<span class="pill ${deep ? 'dip2' : 'dip1'}" title="${U.esc(tip)}">${deep ? '▲▲ Strong buy zone' : '▲ Buy zone'} · ${U.ordinal(d.pct)} pct · ${d.depth.toFixed(0)}%</span>`;
  };
  U.ddLine = function (s) {
    if (!s.dd) return '';
    return `<span class="muted small" title="From the backtest since ${U.esc(s.dd.from || '')}: the deepest fall below a previous high, and the longest time before a new high">Worst fall <b class="dn">${s.dd.worst.toFixed(0)}%</b>${s.dd.longest_days != null ? ' · underwater up to ' + U.durShort(s.dd.longest_days) : ''}</span>`;
  };
  U.dot = function (color, size) { return `<span class="dot" style="background:${U.esc(color)};${size ? `width:${size}px;height:${size}px` : ''}"></span>`; };
  U.spark = function (vals, color) {
    if (!vals || vals.length < 2) return '<svg viewBox="0 0 120 36" style="width:120px;height:36px" aria-hidden="true"></svg>';
    const mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), r = mx - mn || 1;
    const pts = vals.map((v, i) => (i * 120 / (vals.length - 1)).toFixed(1) + ',' + (33 - (v - mn) / r * 30).toFixed(1)).join(' ');
    return `<svg viewBox="0 0 120 36" style="width:120px;height:36px" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${U.esc(color)}" stroke-width="2"/></svg>`;
  };
  U.loading = function (el) { el.innerHTML = '<div class="empty"><span class="spin"></span></div>'; };
  U.error = function (el, e) { el.innerHTML = `<div class="note err">${U.esc(e.message || e)}</div>`; };

  U.toast = function (msg, kind) {
    const box = document.getElementById('toast');
    const d = document.createElement('div');
    if (kind === 'err') d.className = 'err';
    d.textContent = msg;
    box.appendChild(d);
    setTimeout(() => d.remove(), kind === 'err' ? 7000 : 3500);
  };

  /* modal(title, html, {onOpen(el, close)}) → returns close() */
  U.modal = function (title, html, opts) {
    opts = opts || {};
    const bg = document.createElement('div');
    bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${U.esc(title)}" style="max-width:${opts.width || 600}px">
      <div class="modal-h"><h2 style="font-size:19px;font-weight:600">${U.esc(title)}</h2><button class="x" type="button" aria-label="Close">×</button></div>
      <div class="modal-b">${html}</div></div>`;
    document.body.appendChild(bg);
    const close = () => { bg.remove(); document.removeEventListener('keydown', esc); if (opts.onClose) opts.onClose(); };
    const esc = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', esc);
    bg.querySelector('.x').onclick = close;
    bg.addEventListener('mousedown', (e) => { if (e.target === bg) close(); });
    if (opts.onOpen) opts.onOpen(bg.querySelector('.modal-b'), close);
    const first = bg.querySelector('input,select,textarea');
    if (first) setTimeout(() => first.focus(), 30);
    return close;
  };

  /* confirm with optional typed word. resolves true/false */
  U.confirm = function (title, text, opts) {
    opts = opts || {};
    return new Promise((res) => {
      let done = false;
      U.modal(title, `<div class="muted">${text}</div>
        ${opts.word ? `<div class="f"><label for="cw">Type <b class="mono">${U.esc(opts.word)}</b> to confirm</label><input class="in mono" id="cw" autocomplete="off"></div>` : ''}
        <div class="row" style="justify-content:flex-end"><button class="btn" type="button" data-a="no">Cancel</button>
        <button class="btn ${opts.danger ? 'd' : 'p'}" type="button" data-a="yes">${U.esc(opts.ok || 'Confirm')}</button></div>`, {
        width: 480,
        onOpen: (el, close) => {
          el.querySelector('[data-a=no]').onclick = () => close();
          el.querySelector('[data-a=yes]').onclick = () => {
            if (opts.word && el.querySelector('#cw').value.trim() !== opts.word) { U.toast('Type ' + opts.word + ' to confirm', 'err'); return; }
            done = true; close(); res(opts.word ? el.querySelector('#cw').value.trim() : true);
          };
        },
        onClose: () => { if (!done) res(false); },
      });
    });
  };

  U.on = function (root, sel, ev, fn) {
    root.querySelectorAll(sel).forEach((x) => x.addEventListener(ev, (e) => fn(e, x)));
  };
  U.busy = async function (btn, fn) {
    const t = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span>';
    try { return await fn(); } catch (e) { U.toast(e.message, 'err'); } finally { btn.disabled = false; btn.innerHTML = t; }
  };
  U.stateCls = function (c) { return c || ''; };
})();
