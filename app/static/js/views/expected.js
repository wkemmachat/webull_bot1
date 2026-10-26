/* Expected return of the money in the strategies, split like the pie (unassigned money not counted).
   V.renderExpected(el) — data from /api/expected: per strategy the research return minus the planning haircut, the
   weak/typical/good range from the bot backtest's volatility, the mix's range from the correlations, and real vs expected.
   "Plan a ratio" opens the ratio planner: set a % per strategy (slider or number) and a total, see 1/2/3 years at once,
   save the ratio, then give bot-unassigned money by it (the Money dialog opens prefilled; nothing trades before that). */
(function () {
  const V = window.Views || (window.Views = {});
  const cache = {};          // mode → {d, at}
  const planner = {};        // mode → {total, pct: {sid: percent}} while the ratio planner is open
  const HAIRCUTS = [0, 15, 30, 50];
  const N = [1, 2, 3];
  const TRACK = { early: ['', 'Too early'], ahead: ['ok', 'Ahead'], behind: ['warn', 'Behind'], below: ['err', 'Below weak case'] };

  const day = (iso) => { if (!iso) return '—'; const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }); };
  const mon = (iso) => { if (!iso) return '—'; const d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }); };
  const pct0 = (v) => U.pct(v, Math.abs(v) >= 1 ? 0 : 1);
  // table sort: the most profitable first by default (Plan a year, high → low); a click on a header sorts by it
  const SORT_KEY = 'expSort';
  let sort = { k: 'plan', dir: -1 };
  try { const x = JSON.parse(localStorage.getItem(SORT_KEY) || 'null'); if (x && x.k) sort = x; } catch (e) {}
  const COLS = [['name', 'Strategy', ''], ['money', 'Money', 'r'], ['plan', 'Plan a year', 'r'], ['y1', '1 year', 'r'], ['y3', '3 years', 'r'],
    ['real', 'Real vs expected', ''], ['bt', 'Bot backtest now', 'r']];

  function ranges(mu, sig, z) {
    const out = {};
    N.forEach((n) => {
      const lg = n * Math.log1p(mu), r = { typical: Math.exp(lg) - 1 };
      if (sig != null) { r.weak = Math.exp(lg - z * sig * Math.sqrt(n)) - 1; r.good = Math.exp(lg + z * sig * Math.sqrt(n)) - 1; }
      out[n] = r;
    });
    return out;
  }

  // the same maths as app/expected.py portfolio(): each strategy's money grows on its own; range from the mix's volatility
  function portfolio(items, corr, z) {
    const its = items.filter((x) => x.amount > 0.005 && x.mu != null);
    const tot = its.reduce((a, x) => a + x.amount, 0);
    if (tot <= 0) return null;
    const ids = (corr && corr.ids) || [], M = (corr && corr.m) || [];
    const w = {}; its.forEach((x) => { w[x.id] = x.amount / tot; });
    let sp = null;
    if (its.every((x) => x.sig != null)) {
      let v = 0;
      its.forEach((a) => its.forEach((b) => {
        const rho = a.id === b.id ? 1 : (ids.includes(a.id) && ids.includes(b.id) ? M[ids.indexOf(a.id)][ids.indexOf(b.id)] : 0.5);
        v += w[a.id] * w[b.id] * a.sig * b.sig * rho;
      }));
      sp = Math.sqrt(Math.max(v, 0));
    }
    const out = { amount: tot, vol: sp, periods: {}, a_year: its.reduce((a, x) => a + w[x.id] * x.mu, 0) };
    N.forEach((n) => {
      const g = its.reduce((a, x) => a + w[x.id] * Math.pow(1 + x.mu, n), 0);
      const r = { typical: g - 1, usd: tot * g };
      if (sp != null) { r.weak = g * Math.exp(-z * sp * Math.sqrt(n)) - 1; r.good = g * Math.exp(z * sp * Math.sqrt(n)) - 1; }
      out.periods[n] = r;
    });
    return out;
  }

  // worst fall of this split in the backtest, weekly closes over the weeks every funded strategy has data
  function mixFall(items, weekly) {
    const its = items.filter((x) => x.amount > 0.005);
    if (!its.length || its.some((x) => !weekly[x.id])) return null;
    const WK = 7 * 86400000, t0 = (x) => Date.parse(weekly[x.id].w0 + 'T00:00:00Z');
    const start = Math.max(...its.map(t0)), end = Math.min(...its.map((x) => t0(x) + (weekly[x.id].wv.length - 1) * WK));
    const weeks = Math.round((end - start) / WK) + 1;
    if (weeks < 26) return null;
    const tot = its.reduce((a, x) => a + x.amount, 0);
    let peak = -Infinity, worst = 0, at = start;
    for (let k = 0; k < weeks; k++) {
      let v = 0;
      its.forEach((x) => { const a = weekly[x.id].wv, o = Math.round((start - t0(x)) / WK); v += a[o + k] / a[o] * x.amount / tot; });
      peak = Math.max(peak, v);
      if (v / peak - 1 < worst) { worst = v / peak - 1; at = start + k * WK; }
    }
    const each = its.reduce((a, x) => a + (weekly[x.id].maxdd || 0) * x.amount / tot, 0);
    const iso = (t) => new Date(t).toISOString().slice(0, 10);
    return { maxdd: worst * 100, from: iso(start), at: iso(at), all_at_once: each };
  }

  function rangeBar(r) {
    if (r.weak == null) return '';
    const lo = r.weak, hi = r.good, span = hi - lo || 1, x = (v) => Math.max(0, Math.min(100, (v - lo) / span * 100));
    const zero = lo < 0 && hi > 0 ? `<span style="position:absolute;left:${x(0)}%;top:-3px;bottom:-3px;width:1px;background:var(--dim)" title="0%"></span>` : '';
    return `<div style="position:relative;height:6px;border-radius:3px;background:linear-gradient(90deg,var(--err-bg),var(--ok-bg));margin:10px 0 6px">${zero}
      <span style="position:absolute;left:calc(${x(r.typical)}% - 6px);top:-3px;width:12px;height:12px;border-radius:50%;background:var(--accent);border:2px solid var(--panel)"></span></div>
      <div class="row sb tiny num"><span class="dn">weak ${pct0(r.weak)}</span><span class="up">good ${pct0(r.good)}</span></div>`;
  }

  V.renderExpected = function (el) {
    const mode = U.mode();
    let d = cache[mode] && cache[mode].d, poll = null;

    async function fetchData(force) {
      if (!force && cache[mode] && Date.now() - cache[mode].at < 120000) return cache[mode].d;
      const x = await U.api('/api/expected?mode=' + mode);
      cache[mode] = { d: x, at: Date.now() };
      return x;
    }

    function items() {
      const pl = planner[mode];
      return d.strategies.map((s) => ({ id: s.id, mu: s.mu, sig: s.vol,
        amount: Math.max(0, pl ? (pl.total || 0) * (Number(pl.pct[s.id]) || 0) / 100 : s.value) }));
    }
    const sumPct = () => Object.values(planner[mode].pct).reduce((a, v) => a + (Number(v) || 0), 0);
    const curTotal = () => d.strategies.reduce((a, s) => a + Math.max(0, s.value), 0);
    function ratioFrom(kind) {
      const out = {}, live = d.strategies.filter((s) => s.mu != null);
      if (kind === 'now') { const t = curTotal(); d.strategies.forEach((s) => { out[s.id] = t > 0 ? Math.round(Math.max(0, s.value) / t * 1000) / 10 : 0; }); }
      else if (kind === 'saved' && d.plan) d.strategies.forEach((s) => { out[s.id] = d.plan.pct[s.id] || 0; });
      else if (kind === 'eq') { const e = Math.floor(1000 / live.length) / 10; d.strategies.forEach((s) => { out[s.id] = s.mu != null ? e : 0; }); }
      else d.strategies.forEach((s) => { out[s.id] = 0; });
      return out;
    }

    function tilesHtml() {
      const its = items(), p = portfolio(its, d.corr, d.z);
      if (!p) return `<div class="empty small" style="padding:16px">${planner[mode] ? 'Give some strategies a ratio and a total to see' : 'No money in any strategy yet. Press <b>Plan a ratio</b> to see'} what a split could return.</div>`;
      const f = mixFall(its, d.weekly || {});
      return `<div class="grid" style="--min:190px">${N.map((n) => {
        const r = p.periods[n];
        return `<div style="border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0">
          <div class="eyebrow">${n} year${n > 1 ? 's' : ''} · typical</div>
          <div class="num big ${U.cls(r.typical)}" style="margin-top:4px">${pct0(r.typical)}</div>
          <div class="muted small num">${U.usd(p.amount, 0)} → <b style="color:var(--text)">${U.usd(r.usd, 0)}</b></div>
          ${r.weak != null ? rangeBar(r) + `<div class="tiny muted num" style="margin-top:2px">${U.usd(p.amount * (1 + r.weak), 0)} … ${U.usd(p.amount * (1 + r.good), 0)}</div>`
            : '<div class="tiny muted" style="margin-top:10px">Weak / good range after the first backtest check</div>'}</div>`;
      }).join('')}</div>
      <div class="muted small" style="line-height:1.5">About <b>${U.pct(p.a_year)}</b> a year on average${p.vol != null ? `, mix volatility ${(p.vol * 100).toFixed(0)}% a year` : ''}.
        ${f ? `Worst fall of this split in the backtest: <b class="dn">${f.maxdd.toFixed(1)}%</b> (weekly closes since ${mon(f.from)}, the weeks every funded strategy has data; worst at ${day(f.at)}).
        If every strategy had its own worst fall at the same time: <b class="dn">${f.all_at_once.toFixed(1)}%</b>.` : ''}</div>`;
    }

    function totalTrackHtml() {
      const t = d.track;
      if (!t || planner[mode]) return '';
      const [cls, lab] = TRACK[t.status];
      return `<div class="note ${cls === 'err' ? 'err' : cls === 'warn' ? 'warn' : cls === 'ok' ? 'ok' : 'info'} small" style="margin:0;display:block">
        <b>Real vs expected, all strategies:</b> worth ${U.usd(t.value, 0)} now; at the plan it would be ${U.usd(t.expected, 0)}
        (${U.pct(t.real_ret)} real vs ${U.pct(t.exp_ret)} expected on ${U.usd(t.net_in, 0)} put in). ${U.esc(lab)}${t.status === 'early' ? ' — the first 3 months say little.' : '.'}</div>`;
    }

    function sortValue(s, i, its) {
      const c = s.check || {}, tr = s.track;
      switch (sort.k) {
        case 'name': return s.name.toLowerCase();
        case 'money': return its[i].amount;
        case 'plan': return s.mu;
        case 'y1': return s.mu == null ? null : Math.pow(1 + s.mu, 1) - 1;
        case 'y3': return s.mu == null ? null : Math.pow(1 + s.mu, 3) - 1;
        case 'real': return tr && tr.real_ret != null ? tr.real_ret - (tr.exp_ret || 0) : null;
        case 'bt': return c.ok && c.cagr != null ? c.cagr : null;
        default: return null;
      }
    }

    function order(its) {
      const idx = d.strategies.map((s, i) => i);
      return idx.sort((a, b) => {
        const va = sortValue(d.strategies[a], a, its), vb = sortValue(d.strategies[b], b, its);
        if (va == null && vb == null) return a - b;
        if (va == null) return 1;                           // no number: always last
        if (vb == null) return -1;
        if (va < vb) return -sort.dir;
        if (va > vb) return sort.dir;
        return a - b;
      });
    }

    function headHtml() {
      const ck = d.check || {};
      return COLS.map(([k, label, cls]) => {
        const on = sort.k === k, arrow = on ? (sort.dir < 0 ? '▼' : '▲') : '';
        const sub = k === 'bt' ? `<div class="tiny muted" style="font-weight:400">${ck.running ? 'updating…' : ck.stale ? 'out of date' : ck.cost_pct != null ? 'fee ' + ck.cost_pct + '% a trade' : ''}</div>` : '';
        return `<th class="${cls}" aria-sort="${on ? (sort.dir < 0 ? 'descending' : 'ascending') : 'none'}"><button type="button" data-sort="${k}" class="th-sort${on ? ' on' : ''}" title="Sort by ${label}">${label}<span class="arr">${arrow}</span></button>${sub}</th>`;
      }).join('');
    }

    function bindSort() {
      U.on(el, '[data-sort]', 'click', (e, btn) => {
        const k = btn.dataset.sort;
        sort = sort.k === k ? { k, dir: -sort.dir } : { k, dir: k === 'name' ? 1 : -1 };   // numbers: high → low first
        try { localStorage.setItem(SORT_KEY, JSON.stringify(sort)); } catch (x) {}
        const box = el.querySelector('[data-rows]');
        if (box) { box.innerHTML = rowsHtml(); bindSort(); }
      });
    }

    function rowsHtml() {
      const its = items(), tot = its.reduce((a, x) => a + x.amount, 0), plan = d.plan;
      const p = portfolio(its, d.corr, d.z);
      const body = order(its).map((i) => {
        const s = d.strategies[i];
        const amt = its[i].amount, b = s.basis, rg = s.mu != null ? ranges(s.mu, s.vol, d.z) : null, c = s.check || {};
        const cell = (n) => rg ? `<td class="r num"><div class="${U.cls(rg[n].typical)}">${pct0(rg[n].typical)}</div>${rg[n].weak != null ? `<div class="tiny muted">${pct0(rg[n].weak)} … ${pct0(rg[n].good)}</div>` : ''}</td>` : '<td class="r muted">—</td>';
        const tr = s.track;
        const trk = tr ? `${U.pill(TRACK[tr.status][0], TRACK[tr.status][1])}<div class="tiny muted num" style="margin-top:3px">${U.pct(tr.real_ret)} vs ${U.pct(tr.exp_ret)}</div>` : '<span class="muted">—</span>';
        const chk = c.ok ? `<div class="num ${s.mu != null && c.cagr < s.mu * 100 ? 'dn' : ''}">${c.cagr != null ? c.cagr.toFixed(1) + '% a yr' : '—'}</div>
            <div class="tiny muted num">worst 12 m ${c.worst12 != null ? c.worst12.toFixed(0) + '%' : '—'}</div>`
          : c.error ? `<span class="tiny dn">${U.esc(String(c.error).slice(0, 60))}</span>` : '<span class="muted">—</span>';
        const share = tot ? (amt / tot * 100).toFixed(1) + '%' : '';
        const pp = plan ? (plan.pct[s.id] || 0) : null;
        return `<tr><td><a href="#/strategies/${U.esc(s.id)}" class="row" style="gap:8px;flex-wrap:nowrap;color:var(--text)">${U.dot(s.color, 10)}<span>${U.esc(s.name)}</span></a></td>
          <td class="r num">${U.usd(amt, 0)}<div class="tiny muted">${share}${pp != null ? ` · <span title="Your saved ratio">ratio ${pp.toFixed(1)}%</span>` : ''}</div></td>
          <td class="r num">${s.mu != null ? `<b>${U.pct(s.mu)}</b><div class="tiny muted">${U.esc(b.basis)} ${b.cagr.toFixed(1)}%</div>` : '<span class="muted">—</span>'}</td>
          ${cell(1)}${cell(3)}<td>${trk}</td><td class="r">${chk}</td></tr>`;
      }).join('');
      const foot = p ? `<tfoot><tr><td>All</td><td class="r num">${U.usd(p.amount, 0)}</td><td class="r num">${U.pct(p.a_year)}</td>
        ${[1, 3].map((n) => `<td class="r num"><div class="${U.cls(p.periods[n].typical)}">${pct0(p.periods[n].typical)}</div>${p.periods[n].weak != null ? `<div class="tiny muted" style="font-weight:400">${pct0(p.periods[n].weak)} … ${pct0(p.periods[n].good)}</div>` : ''}</td>`).join('')}
        <td></td><td></td></tr></tfoot>` : '';
      return `<div class="tw"><table class="t t-sort"><thead><tr>${headHtml()}</tr></thead><tbody>${body}</tbody>${foot}</table></div>`;
    }

    /* ---------------- ratio planner */
    function sumHtml() {
      const pl = planner[mode], t = sumPct(), left = 100 - t;
      const bar = d.strategies.filter((s) => (pl.pct[s.id] || 0) > 0)
        .map((s) => `<div style="flex:${pl.pct[s.id]};background:${U.esc(s.color)}" title="${U.esc(s.name)} ${pl.pct[s.id]}%"></div>`).join('');
      const msg = Math.abs(left) < 0.05 ? `<span class="pill ok">Ratio total 100%</span>`
        : left > 0 ? `<span class="pill warn">Ratio total ${t.toFixed(1)}% · ${left.toFixed(1)}% not placed</span> <button class="btn s" data-fill>Fill to 100%</button>`
          : `<span class="pill err">Ratio total ${t.toFixed(1)}% · ${(-left).toFixed(1)}% too much</span> <button class="btn s" data-fill>Scale to 100%</button>`;
      return `<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;gap:2px;background:var(--line2)">${bar}${left > 0.05 ? `<div style="flex:${left}"></div>` : ''}</div>
        <div class="row" style="gap:8px;flex-wrap:wrap;align-items:center">${msg}</div>`;
    }

    function prowInfo(s) {
      const pl = planner[mode], pc = Number(pl.pct[s.id]) || 0, amt = (pl.total || 0) * pc / 100, diff = amt - Math.max(0, s.value);
      const rg = s.mu != null ? ranges(s.mu, s.vol, d.z)[1] : null;
      return `<span>${U.usd(amt, 0)} <span class="muted">· now ${U.usd(s.value, 0)}${Math.abs(diff) >= 1 ? ` · <span class="${diff > 0 ? 'up' : 'dn'}">${diff > 0 ? '+' : '−'}${U.usd(Math.abs(diff), 0).replace('−', '')}</span>` : ''}</span></span>
        <span class="muted">${s.mu != null ? `plan ${U.pct(s.mu)} a yr${rg && rg.weak != null ? ` · 1 y ${pct0(rg.weak)} … ${pct0(rg.good)}` : ''}` : 'no expected return yet'}</span>`;
    }

    function plannerHtml() {
      const pl = planner[mode];
      return `<div class="col" style="gap:12px" data-planner>
        <div class="row sb" style="gap:12px;flex-wrap:wrap;align-items:flex-end">
          <div class="f" style="margin:0"><label for="ptot">Plan for (USD)</label><input class="in num" id="ptot" inputmode="decimal" style="width:160px" value="${Math.round(pl.total || 0)}"></div>
          <div class="row" style="gap:6px;flex-wrap:wrap"><span class="muted tiny">Start from</span>
            <button class="btn s" data-pre="now">My current split</button>${d.plan ? '<button class="btn s" data-pre="saved">Saved ratio</button>' : ''}
            <button class="btn s" data-pre="eq">Equal</button><button class="btn s" data-pre="clr">All 0%</button></div></div>
        <div class="col" style="gap:8px" data-sum>${sumHtml()}</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(440px,100%),1fr));column-gap:28px">${d.strategies.map((s) => {
          const pc = Number(pl.pct[s.id]) || 0;
          return `<div data-prow="${U.esc(s.id)}" style="padding:10px 2px;border-bottom:1px solid var(--line2)">
            <div class="row sb" style="gap:10px;flex-wrap:nowrap">
              <a href="#/strategies/${U.esc(s.id)}" class="row" style="gap:8px;min-width:0;flex-wrap:nowrap;color:var(--text)">${U.dot(s.color, 10)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(s.name)}</span></a>
              <span class="row" style="gap:4px;flex-wrap:nowrap"><input class="in num" data-pct="${U.esc(s.id)}" inputmode="decimal" aria-label="Ratio for ${U.esc(s.name)} in %"
                style="width:76px;height:32px;text-align:right" value="${pc ? +pc.toFixed(1) : 0}"><span class="muted">%</span></span></div>
            <input type="range" min="0" max="100" step="0.5" value="${pc}" data-rng="${U.esc(s.id)}" aria-label="Ratio for ${U.esc(s.name)}"
              style="width:100%;margin:8px 0 4px;accent-color:${U.esc(s.color)}">
            <div class="row sb tiny num" style="gap:8px;flex-wrap:wrap" data-pinfo>${prowInfo(s)}</div></div>`;
        }).join('')}</div>
        <div class="tiny muted">The ratio is of the money in strategies only (keep any cash you want aside in bot unassigned or Webull).
          <b>Give unassigned money by this ratio</b> opens the Give-to-strategies dialog with the amounts that move your split toward the ratio; nothing trades until you confirm there.</div>
      </div>`;
    }

    function refreshPlanner(skipRow) {
      el.querySelector('[data-tiles]').innerHTML = tilesHtml();
      el.querySelector('[data-sum]').innerHTML = sumHtml();
      bindFill();
      d.strategies.forEach((s) => {
        const row = el.querySelector(`[data-prow="${s.id}"]`);
        if (!row) return;
        row.querySelector('[data-pinfo]').innerHTML = prowInfo(s);
        if (s.id !== skipRow) {
          const pc = Number(planner[mode].pct[s.id]) || 0;
          row.querySelector('[data-pct]').value = +pc.toFixed(1);
          row.querySelector('[data-rng]').value = pc;
        }
      });
    }

    function bindFill() {
      const f = el.querySelector('[data-fill]');
      if (!f) return;
      f.onclick = () => {
        const pl = planner[mode], t = sumPct();
        if (t <= 0) { pl.pct = ratioFrom('eq'); } else {
          Object.keys(pl.pct).forEach((k) => { pl.pct[k] = Math.round((Number(pl.pct[k]) || 0) / t * 1000) / 10; });
          const diff = Math.round((100 - sumPct()) * 10) / 10;           // rounding leftover to the biggest ratio
          if (diff) { const big = Object.keys(pl.pct).sort((a, b) => pl.pct[b] - pl.pct[a])[0]; pl.pct[big] = Math.round((pl.pct[big] + diff) * 10) / 10; }
        }
        refreshPlanner();
      };
    }

    async function giveByRatio() {
      const pl = planner[mode];
      if (Math.abs(sumPct() - 100) > 0.05) { U.toast('Make the ratios add up to 100% first', 'err'); return; }
      const m = await U.api('/api/money?mode=' + mode);
      const pool = Math.max(0, (m.fund || {}).pool || 0);
      if (pool < 1) { U.toast('Bot unassigned is $0. Allocate money to the bot first (Money → Allocate to bot), then come back.', 'err'); return; }
      const val = {}; (m.rows || []).forEach((r) => { val[r.id] = Math.max(0, r.value || 0); });
      const base = Object.values(val).reduce((a, v) => a + v, 0) + pool;
      const need = {}, over = [];
      d.strategies.forEach((s) => {
        const tgt = base * (Number(pl.pct[s.id]) || 0) / 100, have = val[s.id] || 0;
        if (tgt > have + 0.5) need[s.id] = tgt - have; else if (have > tgt + 50) over.push([s, have - tgt]);
      });
      const tn = Object.values(need).reduce((a, v) => a + v, 0), k = tn > pool ? pool / tn : 1;
      const prefill = {}; Object.keys(need).forEach((id) => { prefill[id] = Math.floor(need[id] * k * 100) / 100; });
      const note = `Prefilled from your ratio: with ${U.usd(base, 0)} (money in strategies + ${U.usd(pool, 0)} unassigned) these amounts bring each strategy
        ${k < 1 ? 'as close to its ratio as the unassigned money allows' : 'to its ratio'}.${over.length ? ` ${over.length <= 3 ? 'Above their ratio: ' + over.map(([s, x]) => `${U.esc(s.name)} by ${U.usd(x, 0)}`).join(', ') : `${over.length} strategies hold more than their ratio (the − amounts in the planner)`} — withdraw or move that money on the Money page for an exact match.` : ''}
        Change any amount before you confirm.`;
      V.splitDialog(() => { cache[mode] = null; fetchData(true).then((x) => { d = x; draw(); }); }, { prefill, note });
    }

    function draw() {
      const pl = planner[mode], rv = d.review, ck = d.check || {};
      const hc = HAIRCUTS.includes(d.haircut_pct) ? HAIRCUTS : HAIRCUTS.concat([d.haircut_pct]).sort((a, b) => a - b);
      let savedLine = '';
      if (!pl && d.plan) {
        const sp = portfolio(d.strategies.map((s) => ({ id: s.id, mu: s.mu, sig: s.vol, amount: d.plan.pct[s.id] || 0 })), d.corr, d.z);
        if (sp) savedLine = `<div class="row sb small" style="gap:10px;flex-wrap:wrap;border:1px dashed var(--line);border-radius:10px;padding:10px 14px">
          <span><b>Your saved ratio</b> <span class="muted">(${U.day(d.plan.saved_at)})</span>: typical ${N.map((n) => `${n} y <b class="${U.cls(sp.periods[n].typical)}">${pct0(sp.periods[n].typical)}</b>`).join(' · ')}</span>
          <button class="btn s" data-open-saved>Open it in the planner</button></div>`;
      }
      el.innerHTML = `<section class="card col" style="gap:14px" id="expected">
        <div class="row sb" style="gap:10px;flex-wrap:wrap;align-items:flex-start"><div style="min-width:0;flex:1 1 300px"><h2 class="h2">${pl ? 'Ratio planner' : 'Expected return'}</h2>
          <div class="muted small">${pl ? 'Set a ratio per strategy and see 1, 2 and 3 years at once — nothing is traded until you give money' : 'If the money stays split like the pie (value now, unassigned not counted)'}
          · research return − ${d.haircut_pct}% planning haircut</div></div>
          <div class="col" style="gap:6px;align-items:flex-end">
            <div class="row" style="gap:6px;flex-wrap:nowrap"><span class="muted tiny">Haircut</span><div class="seg" data-hc>${hc.map((h) => `<button data-h="${h}" class="${h === d.haircut_pct ? 'on' : ''}">${h}%</button>`).join('')}</div></div>
            ${rv.due ? U.pill('warn', 'Yearly review due') : `<span class="tiny muted">Research reviewed ${day(rv.reviewed)} · next ${mon(rv.next)}</span>`}</div></div>
        <div data-tiles class="col" style="gap:12px">${tilesHtml()}</div>
        ${pl ? plannerHtml() : totalTrackHtml() + savedLine + `<div data-rows>${rowsHtml()}</div>`}
        <div class="row sb" style="gap:10px;flex-wrap:wrap">
          <div class="row" style="gap:8px;flex-wrap:wrap">
            ${pl ? `<button class="btn p s" data-give>Give unassigned money by this ratio</button><button class="btn s" data-save>Save this ratio</button>
              ${d.plan ? '<button class="btn s" data-unsave>Delete saved ratio</button>' : ''}<button class="btn s" data-close>Close planner</button>`
            : `<button class="btn s" data-try>Plan a ratio</button><button class="btn s" data-check ${ck.running ? 'disabled' : ''}>${ck.running ? '<span class="spin"></span> Checking the backtests…' : 'Re-run the check'}</button>`}</div>
          <div class="muted tiny" style="text-align:right">${ck.at ? `Backtest check ${U.dt(ck.at)} (${U.esc(ck.by || '')})` : 'Backtest check not run yet — it gives the weak / good range'}
            · <a href="#/docs/expected-returns">How it is worked out →</a></div></div>
        <div class="tiny muted">Typical = the middle case; about 1 period in 10 ends below the weak case and 1 in 10 above the good case. Backtests, not a promise: real results are usually lower.</div>
      </section>`;
      bindSort();
      U.on(el, '[data-hc] button', 'click', async (e, b) => {
        await U.api('/api/expected/haircut', { body: { pct: Number(b.dataset.h) } });
        d = await fetchData(true); draw();
      });
      const btn = (sel, fn) => { const x = el.querySelector(sel); if (x) x.onclick = fn; };
      const open = (kind) => {
        const t = curTotal() + (d.unassigned || 0);
        planner[mode] = { total: kind === 'saved' && d.plan.total ? d.plan.total : (t >= 100 ? Math.round(t) : 100000),
          pct: ratioFrom(kind === 'saved' ? 'saved' : (curTotal() > 0 ? 'now' : 'eq')) };
        draw();
        el.scrollIntoView({ block: 'start', behavior: 'smooth' });
      };
      btn('[data-try]', () => open(d.plan ? 'saved' : 'now'));
      btn('[data-open-saved]', () => open('saved'));
      btn('[data-close]', () => { delete planner[mode]; draw(); });
      btn('[data-give]', () => giveByRatio().catch((e) => U.toast(e.message || String(e), 'err')));
      btn('[data-save]', async () => {
        const r = await U.api('/api/expected/plan', { body: { pct: planner[mode].pct, total: planner[mode].total } }).catch((e) => { U.toast(e.message, 'err'); return null; });
        if (!r) return;
        d.plan = r.plan; U.toast('Ratio saved — it shows on the Dashboard and Strategies, on every device'); draw();
      });
      btn('[data-unsave]', async () => {
        if (!(await U.confirm('Delete the saved ratio?', 'Only the saved plan is deleted; no money moves.', { ok: 'Delete' }))) return;
        await U.api('/api/expected/plan', { body: { pct: {} } }); d.plan = null; draw();
      });
      btn('[data-check]', async () => {
        const st = await U.api('/api/expected/check', { body: {} });
        d.check = st; draw(); U.toast('Checking every strategy\'s backtest (about a minute)');
        watch();
      });
      if (!pl) return;
      bindFill();
      U.on(el, '[data-pre]', 'click', (e, b) => { planner[mode].pct = ratioFrom(b.dataset.pre); refreshPlanner(); });
      const tot = el.querySelector('#ptot');
      tot.addEventListener('input', () => { planner[mode].total = Number(String(tot.value).replace(/[^0-9.]/g, '')) || 0; refreshPlanner(); });
      el.querySelectorAll('[data-rng]').forEach((r) => r.addEventListener('input', () => {
        planner[mode].pct[r.dataset.rng] = Number(r.value);
        el.querySelector(`[data-pct="${r.dataset.rng}"]`).value = +Number(r.value).toFixed(1);
        refreshPlanner(r.dataset.rng);
      }));
      el.querySelectorAll('[data-pct]').forEach((i) => i.addEventListener('input', () => {
        const v = Math.min(100, Math.max(0, Number(String(i.value).replace(/[^0-9.]/g, '')) || 0));
        planner[mode].pct[i.dataset.pct] = v;
        el.querySelector(`[data-rng="${i.dataset.pct}"]`).value = v;
        refreshPlanner(i.dataset.pct);
      }));
    }

    function watch() {
      if (poll) return;
      poll = setInterval(async () => {
        if (!document.body.contains(el)) { clearInterval(poll); poll = null; return; }
        try {
          const x = await fetchData(true);
          if (!x.check.running) { clearInterval(poll); poll = null; d = x; draw(); }
        } catch (e) { clearInterval(poll); poll = null; }
      }, 5000);
    }

    // the page's own refresh keeps this panel; it reloads quietly every 2 minutes unless a split is being tried
    el._expRefresh = () => {
      if (planner[mode] || el.contains(document.activeElement)) return;
      fetchData(false).then((x) => { if (x !== d) { d = x; draw(); } }).catch(() => {});
    };
    if (d) draw(); else U.loading(el);
    fetchData(false).then((x) => { d = x; draw(); if (x.check && x.check.running) watch(); }).catch((e) => U.error(el, e));
  };
})();
