/* Order history: every order the bot has sent, newest first, with the ids to check it against Webull later.
   V.renderOrderHistory(el, {sid, limit, compact, filters}) — the Orders page (all strategies) and each strategy page (sid). */
(function () {
  const V = window.Views || (window.Views = {});
  const RES = {
    filled: ['ok', 'filled'], part: ['warn', 'part filled'], cancelled: ['', 'not filled'], refused: ['err', 'refused'],
    working: ['info', 'at Webull'], inside: ['info', 'inside'],
  };
  const when = (t) => (t ? `${U.day(t)}, ${U.time(t)}` : '—');
  const sideHtml = (s) => (s === 'BUY' ? '<b class="up" style="font-weight:500">▲ Buy</b>' : '<b class="dn" style="font-weight:500">▼ Sell</b>');

  function typeHtml(r) {
    if (r.cross_with) return `<span title="Settled inside the bot: no Webull order, no fee">Inside the bot<span class="muted tiny" style="display:block">${r.side === 'SELL' ? '→' : '←'} ${U.esc((r.cross_name || '').split(' · ')[0])}</span></span>`;
    const ses = r.session && r.session !== 'CORE' ? `${r.retry ? ' · ' : ''}${U.esc(r.session.toLowerCase())}` : '';
    return (r.limit_price ? `Limit ${U.usd(r.limit_price)}` : 'Market') + (r.retry || ses ? `<span class="muted tiny" style="display:block">${r.retry ? 'retry ' + r.retry : ''}${ses}</span>` : '');
  }

  function statusHtml(r) {
    const [k, l] = RES[r.result] || ['', r.status];
    return U.pill(k, r.retried && r.result !== 'filled' ? l + ' → retried' : l);
  }

  function checkHtml(c) {
    if (!c) return '';
    if (c.error) return `<span class="dn">Could not ask Webull: ${U.esc(c.error)}</span>`;
    if (c.note) return `<span class="muted">${U.esc(c.note)}</span>`;
    if (c.ok) return `<span class="up">✓ Matches Webull</span> <span class="muted">· ${U.esc(c.webull.status)} · ${U.qty(c.webull.filled_qty)} filled${c.webull.avg_price ? ' @ ' + U.usd(c.webull.avg_price) : ''} · fee ${U.usd(c.webull.fee)}</span>`;
    return `<span class="dn">✗ Differs from Webull:</span> ${c.diffs.map((d) => `${U.esc(d.field)} bot ${U.esc(String(d.bot))} vs Webull ${U.esc(String(d.webull))}`).join(' · ')}`;
  }

  function detailHtml(r, cols) {
    const kv = (k, v) => `<div><div class="muted tiny">${k}</div><div class="num small" style="word-break:break-all">${v}</div></div>`;
    return `<tr class="ohd" data-for="${r.id}"><td colspan="${cols}" style="white-space:normal;background:var(--panel2)">
      <div class="grid" style="--min:170px;gap:10px 18px">
        ${kv('Bot order no.', '#' + r.id)}${kv('Plan', '#' + r.plan_id + (r.reason ? ' · ' + U.esc(r.reason) : ''))}
        ${kv('Client order id (sent to Webull)', r.client_order_id ? U.esc(r.client_order_id) : '—')}${kv('Webull order no.', r.broker_order_id ? U.esc(r.broker_order_id) : '—')}
        ${kv('Sent', when(r.submitted_at))}${kv('Last update', when(r.updated_at))}
        ${kv('Lot', `${r.lot}/${r.lots}${r.retry ? ' · retry ' + r.retry : ''}`)}${kv('Fee', U.usd(r.fee || 0))}
      </div>
      ${r.error ? `<div class="small muted" style="margin-top:8px">Note: ${U.esc(r.error)}</div>` : ''}
      <div class="row" style="gap:10px;margin-top:10px;flex-wrap:wrap">${r.client_order_id && !r.cross_with ? `<button class="btn s" data-chk="${r.id}">Check with Webull</button>` : ''}
        <span class="small" data-chkout="${r.id}"></span></div></td></tr>`;
  }

  V.renderOrderHistory = async function (el, o) {
    if (!el) return;
    o = o || {};
    const mode = U.mode(), compact = !!o.compact, limit = o.limit || 50;
    const st = o.state || {};                       // kept by the caller so a page refresh keeps filters, open rows and checks
    const f = st.f || (st.f = Object.assign({ strategy: o.sid || '', side: '', result: '', days: 0, offset: 0 }, o.filters || {}));
    const checks = st.checks || (st.checks = {}), open = st.open || (st.open = new Set());
    let strats = [];
    if (!o.sid) { try { strats = (await U.api('/api/strategies?mode=' + mode)).strategies; } catch (e) { strats = []; } }

    function qs(extra) {
      const q = new URLSearchParams({ mode, ...extra });
      if (f.strategy) q.set('strategy', f.strategy);
      if (f.side) q.set('side', f.side);
      if (f.result) q.set('result', f.result);
      if (f.days) q.set('days', f.days);
      return q.toString();
    }

    async function load() {
      const d = await U.api('/api/orders/history?' + qs({ limit, offset: f.offset }));
      const s = d.stats, cols = 10;
      const seg = (id, items, cur) => `<div class="seg" id="${id}">${items.map(([k, l]) => `<button data-v="${k}" class="${String(cur) === String(k) ? 'on' : ''}">${l}</button>`).join('')}</div>`;
      const row = (r) => `<tr class="ohr" data-id="${r.id}" style="cursor:pointer" title="Click for the order ids and a check with Webull">
          <td class="num">${when(r.t)}</td>
          ${o.sid ? '' : `<td style="white-space:normal;min-width:170px;max-width:240px"><span class="row small" style="gap:8px;flex-wrap:nowrap;align-items:baseline">${U.dot(r.color)}<span>${U.esc(r.name)}
            <span class="muted tiny" style="display:block">#${r.plan_id}${r.reason ? ' · ' + U.esc(r.reason) : ''}</span></span></span></td>`}
          <td class="num"><b>${U.esc(r.symbol)}</b></td><td>${sideHtml(r.side)}</td><td class="num small">${typeHtml(r)}</td>
          <td class="r num"><span class="${r.filled_qty > 0 ? '' : 'muted'}">${U.qty(r.filled_qty || 0)}</span><span class="muted"> / ${U.qty(r.qty != null ? r.qty : r.plan_qty)}</span></td>
          <td class="r num">${r.filled_qty > 0 ? U.usd(r.avg_price) : '—'}</td><td class="r num">${r.filled_qty > 0 ? U.usd(r.value) : '—'}</td>
          <td>${statusHtml(r)}</td><td class="num muted small">${r.cross_with ? 'no Webull order' : U.esc(r.broker_order_id || '—')}</td>
          ${o.sid ? `<td class="muted small" style="white-space:normal;min-width:160px">#${r.plan_id}${r.reason ? ' · ' + U.esc(r.reason) : ''}</td>` : ''}</tr>
          ${open.has(r.id) ? detailHtml(r, cols) : ''}`;
      const tiles = compact
        ? `<div class="row small" style="gap:6px 22px;padding:0 18px 12px;flex-wrap:wrap">
            <span><span class="muted">Orders</span> <b class="num">${s.orders}</b></span><span><span class="muted">Filled</span> <b class="num">${s.filled}</b></span>
            ${s.not_filled ? `<span><span class="muted">Not filled</span> <b class="num">${s.not_filled}</b></span>` : ''}${s.working ? `<span><span class="muted">At Webull now</span> <b class="num">${s.working}</b></span>` : ''}
            <span><span class="muted">Bought</span> <b class="num">${U.usd(s.bought, 0)}</b></span><span><span class="muted">Sold</span> <b class="num">${U.usd(s.sold, 0)}</b></span>
            <span><span class="muted">Fees</span> <b class="num">${U.usd(s.fees)}</b></span></div>`
        : `<div class="grid" style="--min:150px;padding:0 18px 14px">
            ${[['Orders sent', s.orders, `${s.webull} to Webull${s.inside ? ` · ${s.inside} inside the bot` : ''}`],
               ['Filled', s.filled, s.orders ? Math.round(s.filled / s.orders * 100) + '%' : ''],
               ['Not filled', s.not_filled, `${s.retried} sent again${s.working ? ` · ${s.working} at Webull now` : ''}`],
               ['Bought', U.usd(s.bought, 0), ''], ['Sold', U.usd(s.sold, 0), ''], ['Fees', U.usd(s.fees), '']].map(([k, v, sub]) =>
              `<div class="card" style="padding:14px 16px"><div class="eyebrow">${k}</div><div class="num big" style="margin-top:4px">${v}</div>${sub ? `<div class="muted small">${sub}</div>` : ''}</div>`).join('')}</div>`;
      el.innerHTML = `<section class="card flush">
        <div class="row sb" style="padding:16px 18px 10px;gap:10px;flex-wrap:wrap;align-items:flex-start">
          <div><h2 class="h2">${o.sid ? 'Orders' : 'Order history'}</h2><div class="muted small">${o.sid ? 'Every order this strategy has sent' : 'Every order the bot has sent'} (and trades settled inside the bot), newest first. Click a row for its ids and a check with Webull.</div></div>
          <div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn s" id="ohchk" title="Asks Webull about each order on this page (read-only)">Check this page with Webull</button>
            <a class="btn s" href="/api/orders/history.csv?${qs({})}">Export CSV</a></div></div>
        <div class="row" style="gap:8px;padding:0 18px 12px;flex-wrap:wrap">
          ${o.sid ? '' : `<select id="ohst" class="in" style="height:34px;width:auto;max-width:280px"><option value="">All strategies</option>${strats.map((x) => `<option value="${U.esc(x.id)}" ${f.strategy === x.id ? 'selected' : ''}>${U.esc(x.name)}</option>`).join('')}</select>`}
          ${o.sid ? '' : seg('ohsd', [['', 'Buys + sells'], ['BUY', 'Buys'], ['SELL', 'Sells']], f.side)}
          ${seg('ohrs', [['', 'All'], ['filled', 'Filled'], ['none', 'Not filled'], ['working', 'At Webull now']], f.result)}
          ${seg('ohdy', [[7, '7 days'], [30, '30 days'], [0, 'All time']], f.days)}</div>
        ${tiles}
        <div id="ohchkout" class="small" style="padding:0 18px 10px"></div>
        <div class="tw"><table class="t"><thead><tr><th>Sent (BKK)</th>${o.sid ? '' : '<th>Strategy · plan</th>'}<th>Symbol</th><th>Side</th><th>Type</th><th class="r">Filled / qty</th>
          <th class="r">Fill price</th><th class="r">Value</th><th>Status</th><th>Webull order no.</th>${o.sid ? '<th>Plan · why</th>' : ''}</tr></thead>
          <tbody>${d.rows.map(row).join('') || `<tr><td colspan="${cols}" class="empty">No orders here yet</td></tr>`}</tbody></table></div>
        <div class="row sb" style="padding:12px 16px;gap:10px;flex-wrap:wrap"><span class="muted small">Showing ${d.rows.length ? f.offset + 1 : 0}–${f.offset + d.rows.length} of ${d.total}
            · “retry” = the same lot sent again at a better limit after the first one did not fill</span>
          <div class="row" style="gap:6px">${o.sid && d.total > limit ? `<a class="btn s" href="#/orders?tab=history&strategy=${encodeURIComponent(o.sid)}">See all in Orders →</a>` : ''}
            ${d.total > limit ? `<button class="btn s" id="ohprev" ${f.offset ? '' : 'disabled'}>Previous</button><button class="btn s" id="ohnext" ${f.offset + limit < d.total ? '' : 'disabled'}>Next</button>` : ''}</div></div>
      </section>`;
      el.querySelectorAll('[data-chkout]').forEach((x) => { x.innerHTML = checkHtml(checks[x.dataset.chkout]); });
      U.on(el, '#ohsd button', 'click', (e, b) => { f.side = b.dataset.v; f.offset = 0; load(); });
      U.on(el, '#ohrs button', 'click', (e, b) => { f.result = b.dataset.v; f.offset = 0; load(); });
      U.on(el, '#ohdy button', 'click', (e, b) => { f.days = +b.dataset.v; f.offset = 0; load(); });
      const sel = el.querySelector('#ohst'); if (sel) sel.onchange = () => { f.strategy = sel.value; f.offset = 0; load(); };
      const pv = el.querySelector('#ohprev'); if (pv) pv.onclick = () => { f.offset = Math.max(0, f.offset - limit); load(); };
      const nx = el.querySelector('#ohnext'); if (nx) nx.onclick = () => { f.offset += limit; load(); };
      U.on(el, 'tr.ohr', 'click', (e, tr) => { const id = +tr.dataset.id; open.has(id) ? open.delete(id) : open.add(id); load(); });
      U.on(el, '[data-chk]', 'click', (e, b) => { e.stopPropagation(); U.busy(b, async () => { checks[b.dataset.chk] = await U.api(`/api/orders/${b.dataset.chk}/check`); load(); }); });
      el.querySelector('#ohchk').onclick = (e) => U.busy(e.target, async () => {
        const todo = d.rows.filter((r) => r.client_order_id && !r.cross_with);
        const out = el.querySelector('#ohchkout');
        let ok = 0, bad = [], err = 0;
        for (let i = 0; i < todo.length; i++) {
          out.innerHTML = `<span class="muted">Asking Webull… ${i + 1}/${todo.length}</span>`;
          try {
            const c = await U.api(`/api/orders/${todo[i].id}/check`);
            checks[todo[i].id] = c;
            if (c.ok) ok++; else if (c.ok === false) bad.push(todo[i]); else err++;
          } catch (x) { err++; }
          await new Promise((r) => setTimeout(r, 250));
        }
        bad.forEach((r) => open.add(r.id));
        await load();
        el.querySelector('#ohchkout').innerHTML = `<div class="note ${bad.length ? 'err' : err ? 'warn' : 'ok'}" style="margin:0"><b>${ok} of ${todo.length} orders on this page match Webull.</b>
          <span>${bad.length ? `${bad.length} differ (opened below).` : ''}${err ? ` ${err} could not be checked.` : ''}${!bad.length && !err ? 'Bot books and Webull agree.' : ''}</span></div>`;
      });
    }
    await load();
    return { reload: load };
  };
})();
