/* Profit & loss page (#/pnl): since start and month by month for the selected trading mode.
   Data: /api/pnl/report (app/pnlreport.py). Sections: summary, worth vs money put in, monthly returns grid, month statements,
   where it came from (by strategy), by strategy and month. A month button or a grid cell narrows the page to that month. */
(function () {
  const V = window.Views || (window.Views = {});
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const mName = (k, long) => { const [y, m] = k.split('-'); return (long ? new Date(Date.UTC(+y, +m - 1, 1)).toLocaleDateString('en-GB', { month: 'long', timeZone: 'UTC' }) : MON[+m - 1]) + ' ' + y; };
  const dTxt = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  const dShort = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  const pct = (v, dp) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(dp == null ? 1 : dp) + '%');
  const usd0 = (v) => U.usd(v, 0);
  const sg = (v) => U.sgnUsd(v, 0);
  const cl = (v) => (v > 0.004 ? 'up' : v < -0.004 ? 'dn' : '');
  const st = { per: 'all', unit: 'pct' };
  try { Object.assign(st, { unit: localStorage.getItem('plUnit') || 'pct' }); } catch (e) { /* private window */ }

  V.pnlReport = async function (el) {
    const mode = U.mode();
    let d;
    try { d = await U.api('/api/pnl/report?mode=' + mode); } catch (e) { U.error(el, e); return; }
    let resizeT = null;

    function render() {
      if (!d.since) {
        el.innerHTML = `<div class="col" style="gap:16px"><h1 class="h1">Profit &amp; loss · ${U.esc(U.modeLabel[mode])}</h1>
          <section class="card"><div class="empty small">No money in any strategy in ${U.esc(U.modeLabel[mode])} yet. The bot records the value every 30 minutes once a strategy has money; the first month appears after the first US close.</div></section></div>`;
        return;
      }
      const months = d.months, recent = months.slice(-3).reverse();
      if (st.per !== 'all' && !months.find((m) => m.m === st.per)) st.per = 'all';
      el.innerHTML = `<div class="col" style="gap:16px">
        <div class="row sb" style="gap:10px;flex-wrap:wrap;align-items:flex-end">
          <div><h1 class="h1">Profit &amp; loss · ${U.esc(U.modeLabel[mode])}</h1>
            <div class="muted small">Since you started and month by month, from the bot's own records. The total is the Dashboard's <i>Since start</i>.</div></div>
          <div class="row" style="gap:8px">
            <div class="seg" id="plper"><button data-p="all" class="${st.per === 'all' ? 'on' : ''}">Since start</button>${recent.map((m) => `<button data-p="${m.m}" class="${st.per === m.m ? 'on' : ''}">${mName(m.m)}</button>`).join('')}</div>
            <a class="btn s" href="/api/pnl/report.csv?mode=${mode}" download>Download CSV</a></div></div>
        ${hero()}
        <section class="card col" style="gap:8px"><div class="row sb" style="gap:8px;flex-wrap:wrap"><div><h2 class="h2">Worth vs money put in</h2>
            <div class="muted small">The gap between the two lines is your profit or loss. Green dots are money put in, red dots money taken out.</div></div>
            <div class="row small pl-legend" style="gap:14px"><span><i class="pl-sw" style="background:var(--text)"></i>Worth</span><span><i class="pl-sw pl-step"></i>Money put in</span>${d.since.held_pnl != null ? '<span><i class="pl-sw pl-held"></i>Bought and held</span>' : ''}</div></div>
          <div id="pleq" class="pl-plot"></div></section>
        <section class="card col" style="gap:10px"><div class="row sb" style="gap:8px"><div><h2 class="h2">Monthly returns</h2>
            <div class="muted small">Tap a month to see only that month on this page.</div></div>
            <div class="seg" id="plunit"><button data-u="pct" class="${st.unit === 'pct' ? 'on' : ''}">%</button><button data-u="usd" class="${st.unit === 'usd' ? 'on' : ''}">$</button></div></div>
          ${heat()}</section>
        <section class="card col" style="gap:8px"><h2 class="h2">Month statements</h2>${statements()}</section>
        <section class="card col" style="gap:8px"><div><h2 class="h2">Where it came from</h2>
            <div class="muted small">Each strategy's part of ${st.per === 'all' ? 'the profit or loss since start' : mName(st.per, true)}, worst to best. The rows add up to the total. Greyed: no money in it now.</div></div>
          <div id="plctr" class="pl-plot"></div></section>
        <section class="card col" style="gap:8px"><h2 class="h2">By strategy and month</h2>${grid()}</section>
      </div>`;
      U.on(el, '#plper button', 'click', (e, b) => { st.per = b.dataset.p; render(); });
      U.on(el, '#plunit button', 'click', (e, b) => { st.unit = b.dataset.u; try { localStorage.setItem('plUnit', st.unit); } catch (x) { /* ignore */ } render(); });
      U.on(el, '[data-pm]', 'click', (e, b) => { st.per = st.per === b.dataset.pm ? 'all' : b.dataset.pm; render(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
      drawEq();
      drawCtr();
    }

    function sel() {
      if (st.per === 'all') {
        const s = d.since;
        return { all: true, label: `Since start · ${dTxt(s.first)} → ${dTxt(s.last)} · ${s.days} trading day${s.days === 1 ? '' : 's'}`,
          pnl: s.pnl, ret: s.ret, put: s.put_in, worth: s.worth, start: 0, held_pnl: s.held_pnl, held_ret: s.held_ret, up: s.up, down: s.down, fees: d.fees_total,
          best: months.reduce((a, m) => (m.best && (!a || m.best.pnl > a.pnl) ? m.best : a), null), worst: months.reduce((a, m) => (m.worst && (!a || m.worst.pnl < a.pnl) ? m.worst : a), null) };
      }
      const m = months.find((x) => x.m === st.per);
      return { all: false, label: `${mName(m.m, true)}${m.to_date ? ' · to ' + dShort(m.last) : ''} · ${m.days} trading day${m.days === 1 ? '' : 's'}`,
        pnl: m.pnl, ret: m.ret, put: m.flow, worth: m.end, start: m.start, held_pnl: m.held_pnl, held_ret: m.held_ret, up: m.up, down: m.down, fees: m.fees, best: m.best, worst: m.worst };
    }
    const months = d.months;

    function hero() {
      const x = sel();
      const short = d.since.years < 1 && x.all;
      const inPlay = x.start + Math.max(x.put, 0), mx = Math.max(inPlay, x.worth, 1);
      const keep = Math.min(inPlay, x.worth);
      const diff = x.held_pnl == null ? null : x.pnl - x.held_pnl;
      return `<section class="card pl-hero">
        <div class="col" style="gap:4px;min-width:0">
          <div class="eyebrow">${U.esc(x.label)}</div>
          <div class="pl-big ${cl(x.pnl)}">${sg(x.pnl)}</div>
          <div class="small"><b class="${cl(x.ret)}">${pct(x.ret)}</b> <span class="muted">time-weighted</span> · <b class="${cl(x.pnl)}">${pct(inPlay > 0.5 ? x.pnl / inPlay : 0)}</b> <span class="muted">of the money in play${x.all ? ' (the Dashboard\'s %)' : ''}${short ? ' · not yearly rates (under a year of records)' : ''}</span></div>
          <div class="row small" style="gap:8px;margin-top:10px;flex-wrap:wrap">
            ${x.all ? `<span class="muted">Put in</span><b class="num">${usd0(x.put)}</b>` : `<span class="muted">Start</span><b class="num">${usd0(x.start)}</b><span class="muted">${x.put >= 0 ? '+ put in' : '− taken out'}</span><b class="num">${usd0(Math.abs(x.put))}</b>`}
            <span class="muted">→</span><span class="muted">${x.all ? 'Worth now' : 'End'}</span><b class="num">${usd0(x.worth)}</b></div>
          <div class="pl-bar" title="Green: what is left of the money in play · red: the loss (or green beyond: the gain)">
            <i style="width:${(keep / mx * 100).toFixed(1)}%;background:var(--up)"></i>
            <i style="left:${(keep / mx * 100).toFixed(1)}%;width:${(Math.abs(inPlay - x.worth) / mx * 100).toFixed(1)}%;background:${x.worth >= inPlay ? 'var(--up)' : 'var(--dn)'};opacity:${x.worth >= inPlay ? 0.45 : 0.85}"></i></div>
        </div>
        <div class="pl-side">
          ${x.held_pnl != null ? `<div class="muted small">Same money bought and held in the same ETFs</div>
            <div class="pl-mid ${cl(x.held_pnl)}">${sg(x.held_pnl)} <span class="small">${pct(x.held_ret)}</span></div>
            <div style="margin-top:6px">${U.pill(diff >= 0 ? 'ok' : 'err', (diff >= 0 ? 'Bot ' + sg(diff) + ' ahead' : 'Bot ' + sg(diff) + ' behind'))}</div>` : '<div class="muted small">No buy-and-hold record for this period.</div>'}
          <div class="pl-kv"><span class="muted">Days up / down</span><b>${x.up} / ${x.down}</b></div>
          ${x.best ? `<div class="pl-kv"><span class="muted">Best day</span><b class="${cl(x.best.pnl)}">${sg(x.best.pnl)} <span class="muted small">${dShort(x.best.d)}</span></b></div>` : ''}
          ${x.worst ? `<div class="pl-kv"><span class="muted">Worst day</span><b class="${cl(x.worst.pnl)}">${sg(x.worst.pnl)} <span class="muted small">${dShort(x.worst.d)}</span></b></div>` : ''}
          <div class="pl-kv"><span class="muted">Fees paid (already in the P&amp;L)</span><b>${U.usd(x.fees)}</b></div>
        </div></section>`;
    }

    function drawEq() {
      const host = el.querySelector('#pleq');
      if (!host) return;
      let pts = d.days;
      if (st.per !== 'all') {
        const i0 = pts.findIndex((p) => p.d.slice(0, 7) === st.per), i1 = pts.length - 1 - pts.slice().reverse().findIndex((p) => p.d.slice(0, 7) === st.per);
        pts = pts.slice(Math.max(0, i0 - 1), i1 + 1);
      }
      if (pts.length < 2) { host.innerHTML = '<div class="empty small">The chart starts after the second US close.</div>'; return; }
      const W = Math.max(320, host.clientWidth || 900), H = 230, L = 58, R = 74, T = 14, B = 26, n = pts.length;
      const vals = pts.flatMap((p) => [p.v, p.c, p.b].filter((x) => x != null));
      let lo = Math.min(...vals), hi = Math.max(...vals);
      const pad = (hi - lo) * 0.08 || hi * 0.1 || 1; lo = Math.max(0, lo - pad); hi += pad;
      const X = (i) => L + (i * (W - L - R)) / (n - 1), Y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
      const step = (hi - lo) / 4, mag = Math.pow(10, Math.floor(Math.log10(step))), nice = Math.ceil(step / mag) * mag;
      let h = '';
      for (let g = Math.ceil(lo / nice) * nice; g <= hi; g += nice) h += `<line x1="${L}" x2="${W - R}" y1="${Y(g)}" y2="${Y(g)}" class="pl-grid"/><text x="${L - 8}" y="${Y(g) + 4}" text-anchor="end" class="pl-ax">${g >= 1000 ? '$' + (g / 1000).toFixed(g % 1000 ? 1 : 0) + 'k' : '$' + Math.round(g)}</text>`;
      let area = pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.v).toFixed(1)}`).join('');
      for (let i = n - 1; i >= 0; i--) area += `L${X(i).toFixed(1)} ${Y(pts[i].c).toFixed(1)}`;
      const last = pts[n - 1], gain = last.v - last.c;
      h += `<path d="${area}Z" fill="${gain >= 0 ? 'var(--up)' : 'var(--dn)'}" opacity="0.13"/>`;
      h += `<path d="${pts.map((p, i) => (i ? `H${X(i).toFixed(1)}V` : `M${X(i).toFixed(1)} `) + Y(p.c).toFixed(1)).join('')}" fill="none" stroke="var(--muted)" stroke-width="1.6"/>`;
      if (pts.every((p) => p.b != null)) h += `<path d="${pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.b).toFixed(1)}`).join('')}" fill="none" stroke="#8E6BBF" stroke-width="1.6" stroke-dasharray="5 4"/>`;
      h += `<path d="${pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.v).toFixed(1)}`).join('')}" fill="none" stroke="var(--text)" stroke-width="2.2"/>`;
      const every = Math.max(1, Math.ceil(n / Math.max(4, Math.floor((W - L - R) / 84))));
      pts.forEach((p, i) => {
        const fl = i ? p.c - pts[i - 1].c : (p.d === d.days[0].d ? p.c : 0);
        if (Math.abs(fl) >= 1) h += `<circle cx="${X(i)}" cy="${Y(p.c)}" r="4" fill="${fl > 0 ? 'var(--up)' : 'var(--dn)'}"><title>${dShort(p.d)}: ${fl > 0 ? 'put in' : 'taken out'} ${usd0(Math.abs(fl))}</title></circle>`;
        if ((i % every === 0 && n - 1 - i >= every * 0.6) || i === n - 1) h += `<text x="${X(i)}" y="${H - 6}" text-anchor="middle" class="pl-ax">${dShort(p.d)}</text>`;
        h += `<rect x="${X(i) - (W - L - R) / n / 2}" y="${T}" width="${(W - L - R) / n}" height="${H - T - B}" fill="transparent"><title>${dTxt(p.d)}${p.live ? ' (now)' : ''}
Worth ${usd0(p.v)} · put in ${usd0(p.c)} · ${sg(p.v - p.c)}${p.b != null ? '\nBought and held ' + usd0(p.b) : ''}${Math.abs(p.pnl) >= 0.5 ? '\nThat day ' + sg(p.pnl) : ''}</title></rect>`;
      });
      h += `<text x="${X(n - 1) + 8}" y="${Y(last.v) + 4}" class="pl-end ${cl(gain)}">${sg(gain)}</text>`;
      host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="Worth against money put in">${h}</svg>`;
    }

    function heat() {
      const years = [...new Set(months.map((m) => m.m.slice(0, 4)))].sort().reverse();
      const by = {}; months.forEach((m) => { by[m.m] = m; });
      const mxp = Math.max(0.02, ...months.map((m) => Math.abs(m.ret)));
      const cell = (k) => {
        const m = by[k];
        if (!m) return '<td class="pl-hm-none">·</td>';
        const v = st.unit === 'pct' ? m.ret : m.pnl, a = 0.18 + 0.67 * Math.min(1, Math.abs(m.ret) / mxp);
        return `<td data-pm="${k}" class="pl-hm-cell ${st.per === k ? 'sel' : ''}" style="background:${m.ret >= 0 ? 'rgba(61,213,152,' : 'rgba(255,122,122,'}${a.toFixed(2)})${a > 0.5 ? ';color:#0A0F0C' : ''}" title="${mName(k, true)}${m.to_date ? ' (to date)' : ''}: ${sg(m.pnl)} · ${pct(m.ret)}">${st.unit === 'pct' ? pct(v) : sg(v)}${m.to_date ? '<sup>*</sup>' : ''}</td>`;
      };
      const yr = (y) => {
        const ms = months.filter((m) => m.m.startsWith(y));
        const r = ms.reduce((a, m) => a * (1 + m.ret), 1) - 1, p = ms.reduce((a, m) => a + m.pnl, 0);
        return `<td class="pl-hm-year ${cl(p)}">${st.unit === 'pct' ? pct(r) : sg(p)}</td>`;
      };
      const tiles = months.slice(-12).reverse().map((m) => `<button data-pm="${m.m}" class="pl-tile ${st.per === m.m ? 'sel' : ''}" style="background:${m.ret >= 0 ? 'rgba(61,213,152,' : 'rgba(255,122,122,'}${(0.18 + 0.67 * Math.min(1, Math.abs(m.ret) / mxp)).toFixed(2)})${Math.abs(m.ret) / mxp > 0.48 ? ';color:#0A0F0C' : ''}">
        <span class="small">${mName(m.m)}${m.to_date ? '*' : ''}</span><b>${st.unit === 'pct' ? pct(m.ret) : sg(m.pnl)}</b></button>`).join('');
      return `<div class="pl-tiles">${tiles}</div><div class="tw pl-hm-wrap"><table class="pl-hm"><thead><tr><th></th>${MON.map((m) => `<th>${m}</th>`).join('')}<th>Year</th></tr></thead><tbody>
        ${years.map((y) => `<tr><th>${y}</th>${MON.map((x, i) => cell(`${y}-${String(i + 1).padStart(2, '0')}`)).join('')}${yr(y)}</tr>`).join('')}</tbody></table></div>
        <div class="tiny muted">% = time-weighted return of the month (money put in during the month is not a gain); $ = profit or loss. * = month to date.</div>`;
    }

    function statements() {
      const rows = months.slice().reverse();
      const s = d.since;
      return `<div class="tw"><table class="t pl-st"><thead><tr><th>Month</th><th class="r">Start</th><th class="r">Put in / taken out</th><th class="r">Profit / loss</th><th class="r">Return</th>
          ${s.held_pnl != null ? '<th class="r">Held instead</th>' : ''}<th class="r">End</th><th class="r">Days up / down</th></tr></thead><tbody>
        ${rows.map((m) => `<tr data-pm="${m.m}" class="${st.per === m.m ? 'on' : ''}" style="cursor:pointer"><td>${mName(m.m, true)}${m.to_date ? ' <span class="muted small">to date</span>' : ''}${m.m === s.first.slice(0, 7) ? ` <span class="muted small">from ${dShort(s.first)}</span>` : ''}</td>
          <td class="r num">${usd0(m.start)}</td><td class="r num muted">${Math.abs(m.flow) >= 0.5 ? sg(m.flow) : '—'}</td>
          <td class="r num ${cl(m.pnl)}" style="font-weight:600">${sg(m.pnl)}</td><td class="r num ${cl(m.ret)}">${pct(m.ret)}</td>
          ${s.held_pnl != null ? `<td class="r num ${cl(m.held_ret)}">${pct(m.held_ret)}</td>` : ''}<td class="r num">${usd0(m.end)}</td><td class="r num muted">${m.up} / ${m.down}</td></tr>`).join('')}</tbody>
        <tfoot><tr><td><b>Since start</b></td><td class="r num">$0</td><td class="r num">${sg(s.put_in)}</td><td class="r num ${cl(s.pnl)}" style="font-weight:700">${sg(s.pnl)}</td>
          <td class="r num ${cl(s.ret)}"><b>${pct(s.ret)}</b></td>${s.held_pnl != null ? `<td class="r num ${cl(s.held_ret)}">${pct(s.held_ret)}</td>` : ''}<td class="r num"><b>${usd0(s.worth)}</b></td><td class="r num muted">${s.up} / ${s.down}</td></tr></tfoot></table></div>
        <div class="tiny muted">Start + put in + profit = end, like a bank statement. A month's end is the value at its last US close (the current month: now). Tap a row to see only that month above.</div>`;
    }

    function drawCtr() {
      const host = el.querySelector('#plctr');
      if (!host) return;
      const k = st.per;
      let rows = d.strategies.map((s) => ({ s, v: k === 'all' ? (s.pnl || 0) : (s.months[k] || 0) })).filter((r) => Math.abs(r.v) >= 0.5 || (!r.s.no_money && k === 'all'));
      if (k !== 'all' && d.timing && d.timing[k]) rows.push({ s: { name: 'Timing of the records', no_money: true }, v: d.timing[k] });
      rows.sort((a, b) => a.v - b.v);
      if (!rows.length) { host.innerHTML = '<div class="empty small">No profit or loss in this period.</div>'; return; }
      const W = Math.max(320, host.clientWidth || 900), narrow = W < 640, rh = narrow ? 40 : 26, L = narrow ? 8 : Math.min(300, W * 0.34), R = 80;
      const mn = Math.min(0, ...rows.map((r) => r.v)), mx = Math.max(0, ...rows.map((r) => r.v)), span = (mx - mn) || 1;
      const A = L + (mn < 0 ? 70 : 8), Z = A + (W - A - R) * (-mn / span), S = (W - A - R) / span;   // room for the labels on both sides
      let h = `<line x1="${Z}" x2="${Z}" y1="0" y2="${rows.length * rh}" class="pl-zero"/>`;
      const room = Math.floor(((narrow ? W - 16 : L - 14)) / 6.4);                  // ~6.4px per character at 12.5px
      const nm = (t) => (t.length > room ? t.slice(0, room - 1).trimEnd() + '…' : t);
      rows.forEach((r, i) => {
        const y = i * rh + (narrow ? 18 : 4), w = Math.abs(r.v) * S, x = r.v >= 0 ? Z : Z - w;
        h += narrow ? `<text x="${L}" y="${y - 4}" class="pl-name ${r.s.no_money ? 'off' : ''}">${U.esc(nm(r.s.name))}<title>${U.esc(r.s.name)}</title></text>`
          : `<text x="${L - 10}" y="${y + 13}" text-anchor="end" class="pl-name ${r.s.no_money ? 'off' : ''}">${U.esc(nm(r.s.name))}<title>${U.esc(r.s.name)}</title></text>`;
        h += `<rect x="${x}" y="${y + 2}" width="${Math.max(w, 1.5)}" height="15" rx="3" fill="${r.v >= 0 ? 'var(--up)' : 'var(--dn)'}" opacity="${r.s.no_money ? 0.38 : 0.9}"/>`;
        h += `<text x="${r.v >= 0 ? Z + w + 6 : Z - w - 6}" y="${y + 14}" text-anchor="${r.v >= 0 ? 'start' : 'end'}" class="pl-ax">${Math.abs(r.v) < 0.5 ? '$0' : sg(r.v)}</text>`;
      });
      host.innerHTML = `<svg viewBox="0 0 ${W} ${rows.length * rh + 8}" width="100%" height="${rows.length * rh + 8}" role="img" aria-label="Profit or loss by strategy">${h}</svg>`;
    }

    function grid() {
      const keys = months.map((m) => m.m).slice(-6);
      const rows = d.strategies.filter((s) => Math.abs(s.pnl || 0) >= 0.5 || !s.no_money).slice().sort((a, b) => (a.no_money - b.no_money) || ((b.value || 0) - (a.value || 0)));
      const mxv = Math.max(1, ...rows.flatMap((s) => keys.map((k) => Math.abs(s.months[k] || 0))));
      const cell = (v, strong) => {
        if (Math.abs(v) < 0.5) return '<td class="r num muted">—</td>';
        const a = 0.12 + 0.5 * Math.min(1, Math.abs(v) / mxv);
        return `<td class="r num" style="background:${v >= 0 ? 'rgba(61,213,152,' : 'rgba(255,122,122,'}${a.toFixed(2)})${strong ? ';font-weight:600' : ''}">${sg(v)}</td>`;
      };
      const tot = (k) => months.find((m) => m.m === k).pnl;
      return `<div class="tw"><table class="t pl-grid-t"><thead><tr><th>Strategy</th><th class="r">Money now</th>${keys.map((k) => `<th class="r">${mName(k)}</th>`).join('')}<th class="r">Since start</th></tr></thead><tbody>
        ${rows.map((s) => `<tr class="${s.no_money ? 'pl-off' : ''}"><td><a href="#/strategies/${U.esc(s.id)}?tab=pnl" class="row" style="gap:8px;flex-wrap:nowrap;color:inherit">${U.dot(s.color, 9)}<span class="ell">${U.esc(s.name)}</span></a></td>
          <td class="r num muted">${s.no_money ? '$0' : usd0(s.value)}</td>${keys.map((k) => cell(s.months[k] || 0)).join('')}${cell(s.pnl || 0, true)}</tr>`).join('')}
        ${keys.some((k) => d.timing && d.timing[k]) ? `<tr class="pl-off"><td class="muted">Timing of the records</td><td></td>${keys.map((k) => cell((d.timing || {})[k] || 0)).join('')}<td></td></tr>` : ''}</tbody>
        <tfoot><tr><td><b>All strategies</b></td><td class="r num"><b>${usd0(d.since.worth)}</b></td>${keys.map((k) => `<td class="r num ${cl(tot(k))}"><b>${sg(tot(k))}</b></td>`).join('')}<td class="r num ${cl(d.since.pnl)}"><b>${sg(d.since.pnl)}</b></td></tr></tfoot></table></div>
        <div class="tiny muted">Each strategy's months are its own Daily P&amp;L days (tap a name for them); the rows add up to the month totals${months.length > 6 ? '; the last 6 months shown, all in the CSV' : ''}.</div>`;
    }

    render();
    const onResize = () => { clearTimeout(resizeT); resizeT = setTimeout(() => { if (document.body.contains(el)) { drawEq(); drawCtr(); } }, 200); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  };
})();
