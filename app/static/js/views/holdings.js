/* What each strategy holds now: cash (by reason) and shares.
   V.holdingsByStrategy(h)        Dashboard → What your money is in → By strategy (HTML; wire with V.bindHoldings)
   V.renderHoldingsTable(el, h)   Portfolio → Holdings by strategy (strategy × symbol table, Not the bot's, Webull check)
   h: /api/holdings (also dashboard.holdings). */
(function () {
  const V = window.Views || (window.Views = {});
  const pc = (x, d) => (x == null ? '—' : (x * 100).toFixed(d == null ? 0 : d) + '%');
  const sh = (q) => U.qty(q) + ' sh';
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private window: not remembered */ } },
  };
  const short = (label) => (label || '').split(' · ').filter((p) => !/waits for|wait for/.test(p)).slice(0, 2).join(' · ');
  const statePill = (r) => { const t = short(r.label) || (r.state ? String(r.state).toUpperCase() : ''); return t ? U.pill('', t) : ''; };
  const stripe = (c) => `repeating-linear-gradient(135deg,${c} 0 4px,transparent 4px 8px)`;
  const colorOf = (h) => { const m = {}; (h.symbols || []).forEach((t) => { m[t.symbol] = t.color; }); return m; };

  function bar(r, h, height) {
    const col = colorOf(h), t = r.total || 1, segs = [];
    Object.entries(r.positions).sort((a, b) => b[1].value - a[1].value).forEach(([s, p]) => {
      segs.push(`<i title="${U.esc(s)} ${U.usd(p.value, 0)}" style="display:block;width:${(p.value / t * 100).toFixed(2)}%;background:${col[s] || '#888'}"></i>`);
    });
    const plain = r.rule_cash + r.orders;
    if (plain >= 0.5) segs.push(`<i title="Cash ${U.usd(plain, 0)}" style="display:block;width:${(plain / t * 100).toFixed(2)}%;background:${h.cash_color}"></i>`);
    if (r.waits >= 0.5) segs.push(`<i title="Waits for a buy signal ${U.usd(r.waits, 0)}" style="display:block;width:${(r.waits / t * 100).toFixed(2)}%;background:${stripe(h.cash_color)};box-shadow:inset 0 0 0 1px ${h.cash_color}"></i>`);
    return `<div style="display:flex;height:${height || 12}px;border-radius:6px;overflow:hidden;gap:2px;background:var(--line2)">${segs.join('')}</div>`;
  }

  function cashWords(r) {
    const bits = [];
    if (r.waits >= 0.5) bits.push(`${U.usd(r.waits, 0)} waits for a buy signal`);
    if (r.orders >= 0.5) bits.push(`${U.usd(r.orders, 0)} for planned orders`);
    return `Cash ${U.usd(r.cash, 0)}${bits.length ? ` <span class="muted">(${bits.join(', ')})</span>` : ''}`;
  }

  function legend(h) {
    return `<div class="row small muted" style="gap:14px;flex-wrap:wrap">${(h.symbols || []).map((t) => `<span class="row" style="gap:6px">${U.dot(t.color)}${U.esc(t.symbol)}</span>`).join('')}
      <span class="row" style="gap:6px">${U.dot(h.cash_color)}Cash</span>
      ${h.waits >= 0.5 ? `<span class="row" style="gap:6px"><span style="width:14px;height:9px;border-radius:3px;background:${stripe(h.cash_color)};box-shadow:inset 0 0 0 1px ${h.cash_color}"></span>Cash waiting for a buy signal</span>` : ''}</div>`;
  }

  function checkLine(h) {
    const a = h.account;
    if (!a) return h.account_error ? `<span class="muted">Webull not checked: ${U.esc(h.account_error)}</span>` : '';
    const bad = a.check.filter((c) => c.status !== 'match');
    if (bad.length) return `<span class="dn">✗ Differs from Webull: ${bad.map((c) => `${U.esc(c.symbol)} bot ${U.qty(c.bot)} vs Webull ${U.qty(c.account)}`).join(' · ')}</span>`;
    return `<span class="up">✓ Matches Webull${a.check.length ? ': ' + a.check.map((c) => `${U.esc(c.symbol)} ${U.qty(c.account)}`).join(', ') : ' (no shares)'}</span>`;
  }

  function notBotLine(h) {
    const n = h.not_bot;
    if (!n) return '';
    const parts = n.items.map((o) => `${U.esc(o.symbol)} ${U.usd(o.value, 0)}`);
    if (n.cash != null && Math.abs(n.cash) >= 0.5) parts.push(`own cash ${U.usd(n.cash, 0)}`);
    if (n.hkd) parts.push(`HK$${Number(n.hkd).toLocaleString('en-US', { maximumFractionDigits: 0 })}`);
    return `<a href="#/portfolio" class="small" style="color:inherit"><span class="muted">Not the bot's</span> <b class="num">${U.usd(n.total, 0)}</b>${parts.length ? ` <span class="muted">· ${parts.join(' · ')}</span>` : ''} <span class="muted">→</span></a>`;
  }

  function emptyToggle(h, key) {
    const n = (h.empty || []).length;
    if (!n) return '';
    const on = store.get(key, '0') === '1';
    return `<div class="row small" style="gap:8px;flex-wrap:wrap;padding-top:8px"><button class="btn s" data-hempty="${key}">${on ? 'Hide' : 'Show'} ${n} strateg${n === 1 ? 'y' : 'ies'} with no money</button>
      ${on ? `<span class="muted">${h.empty.map((e) => U.esc(e.name) + (e.control && e.control !== 'active' ? ' (' + U.esc(e.control) + ')' : '')).join(' · ')}</span>` : ''}</div>`;
  }

  /* ---------------------------------------------------------------- Dashboard: By strategy */
  V.holdingsByStrategy = function (h) {
    if (!h || !h.rows) return '<div class="muted small">Holdings are not available right now.</div>';
    const T = h.total || 0;
    const chips = (h.symbols || []).map((t) => `<div class="card" style="padding:10px 14px;background:var(--panel2)"><div class="row small muted" style="gap:6px">${U.dot(t.color)}${U.esc(t.symbol)}</div>
        <div class="num" style="font-size:18px;font-weight:600">${U.usd(t.value, 0)}</div><div class="muted small">${pc(t.pct, 1)} · ${sh(t.qty)}${t.strategies > 1 ? ` · ${t.strategies} strategies` : ''}</div></div>`).join('')
      + `<div class="card" style="padding:10px 14px;background:var(--panel2)"><div class="row small muted" style="gap:6px">${U.dot(h.cash_color)}Cash</div>
        <div class="num" style="font-size:18px;font-weight:600">${U.usd(h.cash, 0)}</div><div class="muted small">${T > 0.5 ? pc(h.cash / T, 1) : '—'}${h.waits >= 0.5 ? ` · ${U.usd(h.waits, 0)} waits for a buy signal` : ''}${h.orders >= 0.5 ? ` · ${U.usd(h.orders, 0)} for planned orders` : ''}</div></div>`;
    const showEmpty = store.get('holdEmptyDash', '0') === '1';
    const row = (r) => {
      const parts = Object.entries(r.positions).sort((a, b) => b[1].value - a[1].value).map(([s, p]) => `${U.esc(s)} <b>${U.qty(p.qty)}</b> sh ${U.usd(p.value, 0)}`);
      return `<a class="hrow" href="#/strategies/${encodeURIComponent(r.id)}"><div class="col" style="gap:3px;min-width:0">
          <span class="row" style="gap:8px;flex-wrap:nowrap">${U.dot(r.color)}<b class="ell">${U.esc(r.name)}</b></span>
          <span>${statePill(r)}</span></div>
        <div class="col" style="gap:5px;min-width:0">${bar(r, h)}<span class="small num" style="color:var(--text2)">${parts.concat([cashWords(r)]).join(' · ')}</span></div>
        <div class="num" style="text-align:right;font-weight:600">${U.usd(r.total, 0)}</div></a>`;
    };
    const emptyRows = showEmpty ? (h.empty || []).map((e) => `<a class="hrow" href="#/strategies/${encodeURIComponent(e.id)}" style="opacity:.6"><div><span class="row" style="gap:8px;flex-wrap:nowrap">${U.dot(e.color)}<span class="ell">${U.esc(e.name)}</span></span></div>
        <div class="muted small">No money${e.control && e.control !== 'active' ? ' · ' + U.esc(e.control) : ''}</div><div class="num muted" style="text-align:right">$0</div></a>`).join('') : '';
    return `<div class="grid" style="--min:170px;gap:10px">${chips}</div>
      ${legend(h)}
      <div class="col" style="gap:0">${h.rows.map(row).join('') || '<div class="muted small" style="padding:10px 0">No strategy has money yet.</div>'}${emptyRows}</div>
      ${emptyToggle(h, 'holdEmptyDash')}
      <div class="row sb small" style="gap:6px 12px;flex-wrap:wrap;border-top:1px solid var(--line2);padding-top:10px">
        <span><b>Bot ${U.usd(T + (h.unassigned || 0), 0)}</b> <span class="muted">· ${h.rows.length} strateg${h.rows.length === 1 ? 'y' : 'ies'} with money${h.unassigned >= 0.5 ? ` · ${U.usd(h.unassigned, 0)} not given to a strategy` : ''}</span></span>
        ${checkLine(h)}</div>
      ${h.not_bot ? `<div>${notBotLine(h)}</div>` : ''}`;
  };

  V.bindHoldings = function (root, rerender) {
    U.on(root, '[data-hempty]', 'click', (e, b) => {
      e.preventDefault();
      const k = b.dataset.hempty;
      store.set(k, store.get(k, '0') === '1' ? '0' : '1');
      rerender();
    });
  };

  /* ---------------------------------------------------------------- Portfolio: the full table */
  V.renderHoldingsTable = function (el, h) {
    if (!el) return;
    if (!h || !h.rows) { el.innerHTML = ''; return; }
    const mode = U.mode();
    const view = store.get('holdView', 'usd');                   // usd | shares
    const showEmpty = store.get('holdEmptyPort', '0') === '1';
    const openOwn = store.get('holdOwnOpen', '1') === '1';
    const syms = h.symbols || [];
    const nb = h.not_bot;
    const hasOther = nb && nb.items.length;
    const T = h.total || 0;
    const cellOf = (v, q, t, color) => {
      if (!(v >= 0.5) && !(q > 0)) return '<td class="r muted">—</td>';
      const top = view === 'shares' && q != null ? sh(q) : U.usd(v, 0);
      const sub = view === 'shares' && q != null ? U.usd(v, 0) : (t > 0.5 ? pc(v / t) : '') + (q != null ? ' · ' + sh(q) : '');
      return `<td class="r num">${top}<div class="muted tiny">${sub}</div>${t > 0.5 ? `<div style="height:3px;border-radius:2px;background:${color};width:${Math.max(4, v / t * 100).toFixed(0)}%;margin:4px 0 0 auto"></div>` : ''}</td>`;
    };
    const tgt = (r) => {
      const e = Object.entries(r.target || {}).sort((a, b) => b[1] - a[1]);
      if (!e.length) return 'cash';
      const rest = 1 - e.reduce((a, [, w]) => a + w, 0);
      return e.map(([s, w]) => `${U.esc(s)} ${pc(w, w < 0.995 ? 1 : 0)}`).join(' · ') + (rest > 0.02 ? ' · cash' : '');
    };
    const row = (r) => {
      const cells = syms.map((t) => (r.positions[t.symbol] ? cellOf(r.positions[t.symbol].value, r.positions[t.symbol].qty, r.total, t.color) : '<td class="r muted">—</td>')).join('');
      const extra = [r.waits >= 0.5 ? `<div class="tiny" style="color:var(--warn-fg)">${U.usd(r.waits, 0)} waits</div>` : '', r.orders >= 0.5 ? `<div class="tiny" style="color:var(--info)">${U.usd(r.orders, 0)} for orders</div>` : ''].join('');
      const cash = cellOf(r.cash, null, r.total, '#8a9a8c').replace(/<\/td>$/, extra + '</td>');
      return `<tr><td style="white-space:normal;min-width:180px"><a href="#/strategies/${encodeURIComponent(r.id)}" class="row" style="gap:8px;flex-wrap:nowrap;color:inherit">${U.dot(r.color)}<span>${U.esc(r.name)}</span></a></td>
        <td>${statePill(r)}<div class="muted tiny" style="margin-top:3px">target: ${tgt(r)}</div></td>${cells}${cash}${hasOther ? '<td class="r muted">—</td>' : ''}<td class="r num"><b>${U.usd(r.total, 0)}</b></td></tr>`;
    };
    const dashes = (n) => '<td class="r muted">—</td>'.repeat(n);
    const emptyRows = showEmpty ? (h.empty || []).map((e) => `<tr style="opacity:.6"><td><a href="#/strategies/${encodeURIComponent(e.id)}" class="row" style="gap:8px;flex-wrap:nowrap;color:inherit">${U.dot(e.color)}<span>${U.esc(e.name)}</span></a></td>
        <td class="muted small">no money${e.control && e.control !== 'active' ? ' · ' + U.esc(e.control) : ''}</td>${dashes(syms.length + 1 + (hasOther ? 1 : 0))}<td class="r num muted">$0</td></tr>`).join('') : '';
    const totals = syms.map((t) => `<td class="r num"><b>${view === 'shares' ? sh(t.qty) : U.usd(t.value, 0)}</b><div class="muted tiny">${pc(t.pct, 1)} · ${view === 'shares' ? U.usd(t.value, 0) : sh(t.qty)}</div></td>`).join('')
      + `<td class="r num"><b>${U.usd(h.cash, 0)}</b><div class="muted tiny">${T > 0.5 ? pc(h.cash / T, 1) : ''}${h.waits >= 0.5 ? ' · ' + U.usd(h.waits, 0) + ' waits' : ''}</div></td>${hasOther ? '<td class="r muted">—</td>' : ''}<td class="r num"><b>${U.usd(T, 0)}</b></td>`;
    const pool = h.unassigned >= 0.5 ? `<tr><td class="muted">Bot · not given to a strategy</td><td></td>${dashes(syms.length)}<td class="r num">${U.usd(h.unassigned, 0)}</td>${hasOther ? '<td class="r muted">—</td>' : ''}<td class="r num">${U.usd(h.unassigned, 0)}</td></tr>` : '';
    let own = '';
    if (nb) {
      const otherV = nb.items.filter((o) => !syms.some((t) => t.symbol === o.symbol)).reduce((a, o) => a + o.value, 0);
      const inBotSym = (s) => nb.items.filter((o) => o.symbol === s).reduce((a, o) => a + o.value, 0);
      own = `<tr class="ownhead" style="cursor:pointer"><td style="white-space:normal"><span class="row" style="gap:6px">${openOwn ? '▾' : '▸'} <b>Not the bot's</b></span><div class="muted tiny">in your Webull account, outside the bot</div></td><td></td>
          ${syms.map((t) => (inBotSym(t.symbol) >= 0.5 ? `<td class="r num">${U.usd(inBotSym(t.symbol), 0)}</td>` : '<td class="r muted">—</td>')).join('')}
          <td class="r num">${nb.cash != null ? U.usd(nb.cash, 0) : '—'}</td>${hasOther ? `<td class="r num">${U.usd(otherV, 0)}</td>` : ''}<td class="r num">${U.usd(nb.total, 0)}</td></tr>`;
      if (openOwn) {
        const sub = (name, desc, note, noteCls, cols) => `<tr style="background:var(--panel2)"><td style="white-space:normal;padding-left:34px"><b class="num">${name}</b><div class="muted tiny">${desc}</div></td>
            <td class="tiny ${noteCls}">${note}</td>${cols}</tr>`;
        nb.items.forEach((o) => {
          const col = syms.findIndex((t) => t.symbol === o.symbol);
          const cells = syms.map((t, i) => (i === col ? `<td class="r num">${U.usd(o.value, 2)}</td>` : '<td class="r muted">—</td>')).join('')
            + '<td class="r muted">—</td>' + (hasOther ? (col < 0 ? `<td class="r num">${U.usd(o.value, 2)}</td>` : '<td class="r muted">—</td>') : '') + `<td class="r num muted">${U.usd(o.value, 2)}</td>`;
          const desc = `${U.qty(o.qty)} ${o.qty === 1 ? 'share' : 'shares'}${o.price ? ' @ ' + U.usd(o.price) : ''}${o.cost ? ' · bought @ ' + U.usd(o.cost) : ''}${o.part ? ' · Webull holds more than the bot owns' : ''}${!o.price ? ' · Webull prices it $0' : ''}`;
          own += sub(U.esc(o.symbol), desc, o.pnl != null ? `${U.sgnUsd(o.pnl)} (${o.pnl_pct >= 0 ? '+' : ''}${pc(o.pnl_pct)})` : '', o.pnl > 0 ? 'up' : o.pnl < 0 ? 'dn' : 'muted', cells);
        });
        if (nb.cash != null) own += sub('USD cash', 'Cash in Webull not given to the bot (Money → Allocate gives it to the bot)', '', '', dashes(syms.length) + `<td class="r num">${U.usd(nb.cash, 2)}</td>` + (hasOther ? '<td class="r muted">—</td>' : '') + `<td class="r num muted">${U.usd(nb.cash, 2)}</td>`);
        if (nb.hkd) own += sub('HKD cash', `HK$${Number(nb.hkd).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} · kept apart, not in the USD total`, '', '', dashes(syms.length + 1 + (hasOther ? 1 : 0)) + `<td class="r num muted">HK$${Number(nb.hkd).toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>`);
      }
    }
    const a = h.account;
    const acctRow = a ? `<tr><td><b>Webull account</b></td><td>${a.check.every((c) => c.status === 'match') && a.adds_up ? U.pill('ok', '✓ books match') : U.pill('err', '✗ check')}</td>
        ${a.check.map((c) => `<td class="r num ${c.status === 'match' ? 'up' : 'dn'}">${c.status === 'match' ? '✓' : '✗'} ${sh(c.account)}</td>`).join('')}
        <td class="r num">${U.usd(a.cash, 0)}</td>${hasOther ? `<td class="r num">${U.usd(nb.items.filter((o) => !syms.some((t) => t.symbol === o.symbol)).reduce((x, o) => x + o.value, 0), 0)}</td>` : ''}
        <td class="r num"><b>${a.total != null ? U.usd(a.total, 0) : '—'}</b>${a.adds_up ? '' : `<div class="tiny dn">gap ${U.sgnUsd(a.gap, 0)}</div>`}</td></tr>` : '';
    const head = syms.map((t) => `<th class="r"><span class="row" style="gap:6px;justify-content:flex-end;flex-wrap:nowrap">${U.dot(t.color)}${U.esc(t.symbol)}</span></th>`).join('')
      + `<th class="r"><span class="row" style="gap:6px;justify-content:flex-end">${U.dot(h.cash_color)}Cash</span></th>${hasOther ? '<th class="r">Other</th>' : ''}<th class="r">Total</th>`;
    el.innerHTML = `<section class="card flush">
      <div class="row sb" style="padding:16px 18px 10px;gap:10px;flex-wrap:wrap;align-items:flex-start"><div><h2 class="h2">Holdings by strategy</h2>
        <div class="muted small">Each strategy's cash and shares now, the totals, and a check against your Webull account${h.checked_at ? ' (checked ' + U.time(h.checked_at) + ')' : ''}</div></div>
        <div class="row" style="gap:8px;flex-wrap:wrap"><div class="seg" id="hview"><button data-v="usd" class="${view === 'usd' ? 'on' : ''}">$ and %</button><button data-v="shares" class="${view === 'shares' ? 'on' : ''}">Shares</button></div>
          <a class="btn s" href="/api/holdings.csv?mode=${encodeURIComponent(mode)}">Export CSV</a></div></div>
      <div class="tw"><table class="t"><thead><tr><th>Strategy</th><th>Now</th>${head}</tr></thead><tbody>
        ${h.rows.map(row).join('') || `<tr><td colspan="${syms.length + 4}" class="empty">No strategy has money yet</td></tr>`}${emptyRows}
        <tr style="border-top:2px solid var(--border)"><td><b>All strategies</b></td><td></td>${totals}</tr>
        ${pool}${own}${acctRow}</tbody></table></div>
      <div style="padding:0 18px">${emptyToggle(h, 'holdEmptyPort')}</div>
      <div class="muted small" style="padding:10px 18px 14px">Cash “waits” = money you added with “wait for the next buy signal”; “for orders” = set aside for buys planned for the next open;
        the rest of the cash is where the strategy's rule says to be now. The thin bar under an amount is its share of the strategy.</div></section>`;
    const rer = () => V.renderHoldingsTable(el, h);
    U.on(el, '#hview button', 'click', (e, b) => { store.set('holdView', b.dataset.v); rer(); });
    U.on(el, 'tr.ownhead', 'click', () => { store.set('holdOwnOpen', openOwn ? '0' : '1'); rer(); });
    V.bindHoldings(el, rer);
  };
})();
