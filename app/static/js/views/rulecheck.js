/* Check the rule: on a strategy's Overview, for each leg, small charts of exactly the numbers the rule compares, one lane
   per condition, the rule's answer next to the bot's, and a day check with that day's numbers.
   V.ruleCheck(host, sid) — data from /api/strategies/{sid}/rulecheck (app/rulecheck.py). */
(function () {
  const V = window.Views || (window.Views = {});
  const RTYPES = ['trend_gate', 'ibd_gate', 'trend_split', 'split_mix'];
  V.ruleCheckTypes = RTYPES;

  function fmt(v, d) {
    if (v == null) return '—';
    return Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  V.ruleCheck = async function (host, sid) {
    if (!host) return;
    const st = { range: '8M', view: null, day: null, pinned: false, data: null };
    let resizeT = null;

    async function load() {
      host.innerHTML = '<section class="card"><div class="empty"><span class="spin"></span></div></section>';
      try { st.data = await U.api(`/api/strategies/${sid}/rulecheck?range=${st.range}`); } catch (e) { st.data = { views: [], error: e.message }; }
      const v = st.data.views || [];
      if (!v.length) { host.innerHTML = st.data.error ? `<section class="card"><div class="note err small">Check the rule: ${U.esc(st.data.error)}</div></section>` : ''; return; }
      if (!v.find((x) => x.id === st.view)) st.view = v[0].id;
      st.day = st.data.t.length - 1;
      st.pinned = false;
      render();
    }

    const view = () => st.data.views.find((x) => x.id === st.view);
    const S = (k) => (st.data.series[k] || { v: [], d: 2 });

    function render() {
      const d = st.data, v = view(), n = d.t.length;
      const mm = v.mismatch;
      host.innerHTML = `<section class="card col rc" style="gap:12px">
        <div class="row sb" style="gap:10px;flex-wrap:wrap">
          <div><h2 class="h2">Check the rule</h2>
            <div class="muted small">The numbers the rule compares, one lane per condition. Hover a day to read it; click to keep it.</div></div>
          <div class="seg" id="rcr">${['3M', '8M', '1Y', '2Y'].map((r) => `<button data-r="${r}" class="${st.range === r ? 'on' : ''}">${r}</button>`).join('')}</div>
        </div>
        ${d.views.length > 1 ? `<div class="seg rc-views" id="rcv">${d.views.map((x) => `<button data-v="${U.esc(x.id)}" class="${x.id === st.view ? 'on' : ''}">${U.esc(x.label)}${x.mismatch ? ' ⚠' : ''}</button>`).join('')}</div>` : ''}
        <div class="rc-rule">${U.esc(v.rule)}</div>
        ${mm == null ? '' : mm === 0
          ? `<div class="small">${U.pill('ok', '✓ matches')} The rule's answer (worked out from these charts) and the bot's decision agree on all ${n} days.</div>`
          : `<div class="small">${U.pill('err', mm + ' days differ')} Days where the rule's answer and the bot's decision differ are marked red in the last two lanes.</div>`}
        <div class="rc-plot"><svg id="rcsvg" width="100%"></svg></div>
        <div class="rc-cards">
          <div class="rc-day" id="rcday"></div>
          <div class="rc-tv"><div class="eyebrow" style="margin-bottom:6px">Same check in TradingView</div>
            ${(v.tv || []).map((x) => `<div class="small" style="margin-bottom:4px">${U.esc(x)}</div>`).join('')}</div>
        </div></section>`;
      U.on(host, '#rcr button', 'click', (e, b) => { st.range = b.dataset.r; load(); });
      U.on(host, '#rcv button', 'click', (e, b) => { st.view = b.dataset.v; render(); });
      draw();
    }

    function draw() {
      const svg = host.querySelector('#rcsvg');
      if (!svg) return;
      const d = st.data, v = view(), n = d.t.length;
      const W = Math.max(320, svg.clientWidth || host.clientWidth || 900);
      const LW = W < 640 ? 118 : 190, RW = 62, X0 = LW, X1 = W - RW;
      const col = (cc) => (cc === 'text' ? 'var(--text2)' : cc);
      const X = (i) => X0 + (n <= 1 ? 0 : (i * (X1 - X0)) / (n - 1));
      const bw = Math.max(1, (X1 - X0) / Math.max(n, 1));
      let y = 4, h = '';
      const esc = U.esc;
      const txt = (x, yy, s, cls, anchor) => `<text x="${x}" y="${yy}" class="${cls || 'rc-t'}"${anchor ? ` text-anchor="${anchor}"` : ''}>${esc(s)}</text>`;
      v.charts.forEach((c) => {
        y += 16;
        h += txt(X0, y - 4, c.title, 'rc-title');
        const top = y, H = c.height;
        let lo = Infinity, hi = -Infinity;
        c.lines.forEach((l) => S(l.key).v.forEach((x) => { if (x != null) { lo = Math.min(lo, x); hi = Math.max(hi, x); } }));
        (c.hlines || []).forEach((l) => { lo = Math.min(lo, l.value); hi = Math.max(hi, l.value); });
        if (!isFinite(lo)) { lo = 0; hi = 1; }
        if (hi === lo) { hi += 1; lo -= 1; }
        const pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
        const Y = (val) => top + H - ((val - lo) / (hi - lo)) * H;
        h += `<rect x="${X0}" y="${top}" width="${X1 - X0}" height="${H}" class="rc-bg"/>`;
        if (c.shade && c.shade.key === 'cloud') {
          const a = S(c.shade.a).v, b = S(c.shade.b).v;
          for (let i = 0; i < n; i++) if (a[i] != null && b[i] != null) {
            const y1 = Y(Math.max(a[i], b[i])), y2 = Y(Math.min(a[i], b[i]));
            h += `<rect x="${X(i) - bw / 2}" y="${y1}" width="${bw + 0.5}" height="${Math.max(0.5, y2 - y1)}" fill="${a[i] >= b[i] ? '#26A69A' : '#EF5350'}" opacity="0.16"/>`;
          }
        } else if (c.shade && c.shade.key) {
          const sv = S(c.shade.key).v;
          for (let i = 0; i < n; i++) if (sv[i] === c.shade.when) h += `<rect x="${X(i) - bw / 2}" y="${top}" width="${bw + 0.5}" height="${H}" fill="${c.shade.color}" opacity="0.18"/>`;
        }
        const dec = Math.max(0, ...c.lines.map((l) => S(l.key).d));
        const hy = (c.hlines || []).map((l) => Y(l.value));
        [0, 0.5, 1].forEach((f) => {
          const val = lo + pad + (hi - lo - 2 * pad) * f;
          if (hy.some((q) => Math.abs(q - Y(val)) < 11)) return;
          h += txt(X1 + 6, Y(val) + 4, fmt(val, Math.abs(val) >= 100 ? 0 : Math.min(dec, 2)), 'rc-ax');
        });
        (c.hlines || []).forEach((l) => { h += `<line x1="${X0}" x2="${X1}" y1="${Y(l.value)}" y2="${Y(l.value)}" class="rc-hl"/>` + txt(X1 + 6, Y(l.value) + 4, fmt(l.value, l.value % 1 ? 2 : 0), 'rc-hlt'); });
        c.lines.forEach((l) => {
          const vals = S(l.key).v;
          let p = '', prev = null;
          for (let i = 0; i < n; i++) {
            const val = vals[i];
            if (val == null) { prev = null; continue; }
            const xx = X(i).toFixed(1), yy = Y(val).toFixed(1);
            if (prev == null) p += `M${xx} ${yy}`;
            else p += l.step ? `H${xx}V${yy}` : `L${xx} ${yy}`;
            prev = val;
          }
          h += `<path d="${p}" fill="none" style="stroke:${col(l.color)}" stroke-width="${l.width || 1.5}"${l.dash ? ' stroke-dasharray="5 4"' : ''}/>`;
        });
        let ly = top + 12;
        c.lines.forEach((l) => { h += `<rect x="4" y="${ly - 8}" width="10" height="3" style="fill:${col(l.color)}"/>` + txt(18, ly - 3, l.name, 'rc-leg'); ly += 15; });
        (c.hlines || []).forEach((l) => { h += `<line x1="4" x2="14" y1="${ly - 7}" y2="${ly - 7}" class="rc-hl"/>` + txt(18, ly - 3, 'level ' + fmt(l.value, l.value % 1 ? 2 : 0), 'rc-leg'); ly += 15; });
        if (c.shade && c.shade.label) h += `<rect x="4" y="${ly - 10}" width="10" height="8" fill="${c.shade.color}" opacity="0.35"/>` + txt(18, ly - 3, c.shade.label, 'rc-leg');
        y = top + H + 6;
        if (c.note) { h += txt(X0, y + 8, c.note, 'rc-note'); y += 12; }
      });
      y += 12;
      h += txt(4, y, 'Conditions', 'rc-title');
      y += 6;
      const rk = (v.lanes.find((l) => l.kind === 'rule') || {}).key, bk = (v.lanes.find((l) => l.kind === 'bot') || {}).key;
      const rv = rk ? S(rk).v : null, bv = bk ? S(bk).v : null;
      v.lanes.forEach((l) => {
        if (l.kind === 'rule') { y += 6; h += `<line x1="4" x2="${X1}" y1="${y}" y2="${y}" class="rc-sep"/>`; y += 6; }
        const vals = S(l.key).v;
        h += txt(4, y + 11, l.label, l.kind === 'cond' ? 'rc-lane' : 'rc-lane rc-strong');
        for (let i = 0; i < n; i++) {
          const on = vals[i] === 1, bad = l.kind !== 'cond' && rv && bv && rv[i] !== bv[i];
          h += `<rect x="${X(i) - bw / 2}" y="${y}" width="${bw + 0.5}" height="14" class="${bad ? 'rc-bad' : on ? (l.kind === 'cond' ? 'rc-on' : 'rc-in') : 'rc-off'}"/>`;
        }
        y += 18;
      });
      y += 6;
      let lastM = -1;
      for (let i = 0; i < n; i++) {
        const dt = new Date(d.t[i] * 1000), m = dt.getUTCMonth();
        if (m !== lastM) { if (lastM !== -1 || i === 0) h += txt(X(i), y + 10, dt.toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' }) + (m === 0 ? ' ' + dt.getUTCFullYear() : ''), 'rc-ax'); lastM = m; }
      }
      y += 16;
      h += `<line id="rcx" x1="0" x2="0" y1="4" y2="${y - 18}" class="rc-x"/><rect id="rchit" x="${X0}" y="0" width="${X1 - X0}" height="${y}" fill="transparent"/>`;
      svg.setAttribute('height', y);
      svg.setAttribute('viewBox', `0 0 ${W} ${y}`);
      svg.innerHTML = h;
      const hit = svg.querySelector('#rchit');
      const at = (ev) => { const r = svg.getBoundingClientRect(); const px = ((ev.clientX - r.left) / r.width) * W; return Math.max(0, Math.min(n - 1, Math.round(((px - X0) / (X1 - X0)) * (n - 1)))); };
      hit.addEventListener('mousemove', (ev) => { if (!st.pinned) { st.day = at(ev); mark(); } });
      hit.addEventListener('click', (ev) => { const i = at(ev); st.pinned = !(st.pinned && i === st.day); st.day = i; mark(); });
      st.X = X;
      mark();
    }

    function mark() {
      const v = view(), d = st.data, i = st.day;
      const line = host.querySelector('#rcx');
      if (line && st.X) { line.setAttribute('x1', st.X(i)); line.setAttribute('x2', st.X(i)); }
      const fill = (t) => t.replace(/\{([^}]+)\}/g, (m, k) => { const s = S(k); return fmt(s.v[i], s.d); });
      const yes = (k) => S(k).v[i] === 1;
      const rk = (v.lanes.find((l) => l.kind === 'rule') || {}).key, bk = (v.lanes.find((l) => l.kind === 'bot') || {}).key;
      const date = new Date(d.t[i] * 1000).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
      let res = '';
      if (rk && bk) {
        const a = yes(rk), b = yes(bk);
        res = `<div class="row" style="gap:8px;flex-wrap:wrap;margin-top:8px">
          <span class="small">Rule says <b>${a ? 'IN' : 'OUT'}</b></span><span class="small">· Bot was <b>${b ? 'IN' : 'OUT'}</b></span>
          ${a === b ? U.pill('ok', '✓ same') : U.pill('err', '✗ different')}</div>`;
      }
      const box = host.querySelector('#rcday');
      if (!box) return;
      box.innerHTML = `<div class="row sb" style="margin-bottom:6px"><div class="eyebrow">Day check · ${U.esc(date)} close</div>
          <span class="muted small">${st.pinned ? 'kept · click again to release' : 'hover the charts'}</span></div>
        <table class="t rc-ck"><colgroup><col style="width:50%"><col style="width:36%"><col style="width:14%"></colgroup><thead><tr><th>Condition</th><th>That day</th><th class="r">Met</th></tr></thead><tbody>${v.checks.map((c) => `<tr>
          <td><b>${U.esc(c.k)}</b>${c.need ? `<div class="muted small">${U.esc(c.need)}</div>` : ''}</td><td class="rc-num">${U.esc(fill(c.t))}</td>
          <td class="r">${c.ok == null ? '' : yes(c.ok) ? U.pill('ok', 'yes') : U.pill('', 'no')}</td></tr>`).join('')}</tbody></table>${res}
        <div class="muted small" style="margin-top:6px">Decided after this close; orders go at the next open.</div>`;
    }

    window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(() => { if (document.body.contains(host) && st.data && st.data.views.length) draw(); }, 200); });
    await load();
  };
})();
