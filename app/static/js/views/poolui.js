/* Strategy pool (Money page, strategy page): one shared pot of the bot's money per mode. Members get money when a trade
   starts (trade size % of the pool) and give it back when it ends. Rules: Docs → Money: the strategy pool. */
(function () {
  const V = window.Views || (window.Views = {});
  const usd0 = (x) => U.usd(x, 0);
  const whoText = (who) => {
    const stay = who.filter((w) => !w.endsWith('(leaving)')), go = who.length - stay.length;
    return [stay.join(', '), go ? `${go} leaving` : ''].filter(Boolean).join(' · ');
  };

  /* The pool card, Money by group, Members and Not in the pool (pool on) — or a small "set up" card (pool off). */
  V.poolSections = function (p, mode) {
    if (!p.on) {
      const n = p.members.length;
      return `<section class="card row sb" style="gap:14px;flex-wrap:wrap"><div><h2 class="h2">Strategy pool · off</h2>
        <div class="muted small" style="max-width:780px;margin-top:4px">One shared pot instead of fixed cash per strategy: a member gets ${p.slot_pct}% of the pool when its buy signal starts a trade and gives it back, with its profit or loss, when the trade ends. ${n ? `${n} member${n > 1 ? 's' : ''} chosen.` : 'Choose the members first.'} <a href="#/docs/pool">How it works →</a></div></div>
        <div class="row" style="gap:8px"><button class="btn" data-pool="members">Choose members</button><button class="btn p" data-pool="settings">Pool settings…</button></div></section>`;
    }
    const W = mode === 'paper' ? 'account' : 'Webull';
    const tile = (k, v, usd, txt) => `<div class="fl"><div class="eyebrow">${k}</div><div class="num big" style="font-size:26px;margin-top:4px">${v} <span class="muted small" style="font-weight:400">= ${usd0(usd)}</span></div><div class="muted small">${txt}</div></div>`;
    const waits = p.waiting.length ? `<div class="note warn"><b>${p.waiting.length} signal${p.waiting.length > 1 ? 's' : ''} waiting for money:</b> ${p.waiting.map((m) => U.esc(m.name)).join(', ')} — only ${usd0(p.free)} is free (the smallest trade is ${usd0(p.min_usd)}). ${p.waiting.length > 1 ? 'They buy' : 'It buys'} at the next check after a trade ends or you allocate more to the bot.</div>` : '';
    const groups = p.groups.filter((g) => g.value > 0.5 || g.who.length).map((g) => {
      const scale = Math.max(40, p.cap_pct * 1.6);
      return `<div class="row" style="display:grid;grid-template-columns:190px minmax(0,1fr) 150px;gap:12px;align-items:center;padding:6px 0">
        <div class="small"><b style="font-weight:500">${U.esc(g.label)}</b><div class="muted tiny">${U.esc(whoText(g.who))}</div></div>
        <div style="position:relative;height:10px;border-radius:5px;background:var(--line2);overflow:hidden"><i style="position:absolute;left:0;top:0;bottom:0;border-radius:5px;width:${Math.min(100, g.pct * 100 / scale * 100)}%;background:${g.color}"></i><span style="position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--text);left:${p.cap_pct / scale * 100}%"></span></div>
        <div class="num small" style="text-align:right">${(g.pct * 100).toFixed(1)}% ${g.pct * 100 >= p.cap_pct - 0.05 ? U.pill('warn', 'at cap') : `<span class="muted">of ${p.cap_pct}%</span>`}</div></div>`;
    }).join('') || '<div class="muted small">No member in a trade.</div>';
    const rows = p.members.map((m) => `<tr><td><a href="#/strategies/${m.id}" class="row" style="gap:10px;color:var(--text);flex-wrap:nowrap">${U.dot(m.color, 10)}<b style="font-weight:500">${U.esc(m.name)}</b></a></td>
      <td class="muted small">${U.esc(m.group_label)}</td><td>${U.pill(m.status[0], m.status[1] + (m.since ? ' since ' + U.day(m.since) : ''))}</td>
      <td class="r num" style="font-weight:600">${m.value > 0.5 ? U.usd(m.value) : '—'}</td><td class="r num muted">${m.value > 0.5 && m.pct != null ? (m.pct * 100).toFixed(1) + '%' : '—'}</td>
      <td class="r num ${U.cls(m.open_pnl)}">${m.open_pnl != null ? U.sgnUsd(m.open_pnl, 0) : '—'}</td><td class="r num ${U.cls(m.pnl_joined)}">${U.sgnUsd(m.pnl_joined, 0)}</td>
      <td class="r"><button class="btn s" data-pool-rm="${m.id}">Remove</button></td></tr>`).join('') || '<tr><td colspan="8" class="muted">No members yet: Choose members.</td></tr>';
    const out = p.outside.map((r) => `<tr><td><a href="#/strategies/${r.id}" class="row" style="gap:10px;color:var(--text);flex-wrap:nowrap">${U.dot(r.color, 10)}<span>${U.esc(r.name)}</span></a></td>
      <td class="muted small">${U.esc(r.group_label)}</td>
      <td>${r.leaving ? U.pill('err', (r.sell_now ? 'Selling at the next open' : 'Leaving after this trade') + ' · ' + usd0(r.value)) : U.pill(r.wants ? 'info' : '', 'signal: ' + (r.state || '—'))}</td>
      <td class="r"><button class="btn s" data-pool-add="${r.id}">${r.leaving ? 'Stay in pool' : '+ Add to pool'}</button></td></tr>`).join('');
    return `<section class="card col" style="gap:14px"><div class="row sb" style="flex-wrap:wrap;gap:8px"><h2 class="h2">Strategy pool · ${p.members.length} member${p.members.length === 1 ? '' : 's'}</h2>
        <span class="muted small">Trades are funded first come, first served; open trades are never cut to make room. <a href="#/docs/pool">How it works →</a></span></div>
      <div class="flow" style="grid-template-columns:repeat(3,minmax(0,1fr))">
        ${tile('Trade size', p.slot_pct + '%', p.slot_usd, `Each new trade gets ${p.slot_pct}% of the pool. ${p.slot_auto ? 'Suggested' : `Suggested for ${p.members.length} members: ${p.suggested_slot}%`} (150% ÷ members, 10–25%).`)}
        ${tile('Group cap', p.cap_pct + '%', p.cap_usd, 'Strategies on the same market (groups of What your money is in) hold at most this together.')}
        ${tile('Smallest trade', p.min_pct + '%', p.min_usd, 'With less free cash than this, a signal waits for money instead of buying a tiny amount.')}</div>
      ${waits}
      <div class="idlebox card" style="padding:14px 16px" id="pool-exp"><div class="muted small">Expected return of this mix: loading…</div></div></section>
    <section class="card"><div class="row sb" style="margin-bottom:8px"><h2 class="h2">Money by group</h2><span class="muted small">Black line = group cap ${p.cap_pct}%</span></div>${groups}</section>
    <section class="card flush"><div class="row sb" style="padding:16px 20px 4px"><h2 class="h2">Members</h2><span class="muted small">P&amp;L since joined is each strategy's own profit; it goes to the whole pool.</span></div>
      <div class="tw"><table class="t"><thead><tr><th>Strategy</th><th>Group</th><th>Now</th><th class="r">In its trade</th><th class="r">Of pool</th><th class="r">Open trade P&amp;L</th><th class="r">P&amp;L since joined</th><th class="r"></th></tr></thead><tbody>${rows}</tbody></table></div></section>
    <section class="card flush"><div class="row sb" style="padding:16px 20px 4px"><h2 class="h2">Not in the pool · signals only</h2><span class="muted small">They keep their signals, charts and backtests, but never buy.</span></div>
      <div class="tw"><table class="t"><thead><tr><th>Strategy</th><th>Group</th><th>Now</th><th class="r"></th></tr></thead><tbody>${out || '<tr><td colspan="4" class="muted">Every strategy is a member.</td></tr>'}</tbody></table></div></section>`;
  };

  /* Expected return of a mix (the pool backtest): fills box, polls while the members' backtests are built. */
  V.poolExpected = async function (box, body, small) {
    let stop = false;
    const me = (box._req = (box._req || 0) + 1);        // only the newest request may write the box
    const gone = () => stop || !box.isConnected || box._req !== me;
    const tick = async () => {
      if (gone()) return;
      let r;
      try { r = await U.api('/api/pool/backtest', { body }); } catch (e) { if (!gone()) box.innerHTML = `<div class="muted small">Expected return: ${U.esc(e.message)}</div>`; return; }
      if (gone()) return;
      if (r.empty) { box.innerHTML = '<div class="muted small">Tick members to see the expected return of the mix.</div>'; return; }
      if (!r.ready) { box.innerHTML = `<div class="muted small"><span class="spin"></span> Expected return of this mix: running the members' backtests (${r.done} of ${r.of})…</div>`; setTimeout(tick, 2500); return; }
      if (r.error) { box.innerHTML = `<div class="muted small">Expected return: ${U.esc(r.error)}</div>`; return; }
      const cell = (x) => x ? `<b class="num ${U.cls(x.cagr)}">${x.cagr > 0 ? '+' : ''}${x.cagr}%</b> <span class="num muted">/ ${x.maxdd}%</span>` : '—';
      const P = r.periods || {};
      box.innerHTML = `<div class="row sb" style="flex-wrap:wrap;gap:6px"><b>Expected return of this mix</b><span class="muted small">a year / worst fall · trade size ${r.slot_pct}% · group cap ${r.cap_pct}% · money idle ${r.idle}%</span></div>
        <div class="row" style="gap:18px;flex-wrap:wrap;margin-top:8px">${[['1Y', P['1Y']], ['3Y', P['3Y']], ['5Y', P['5Y']], ['10Y', P['10Y']], ['Since ' + ((r.all || {}).from || '').slice(0, 4), r.all]].map(([k, x]) => `<div><div class="eyebrow">${k}</div>${cell(x)}</div>`).join('')}
          <div style="border-left:1px solid var(--line);padding-left:18px"><div class="eyebrow">Same members, fixed money each · 10Y</div>${cell((r.fixed || {})['10Y'])}</div></div>
        ${small ? '' : `<div class="muted tiny" style="margin-top:8px">${U.esc(r.note)}</div>`}`;
    };
    tick();
    return () => { stop = true; };
  };

  V.poolBind = function (el, p, mode, load) {
    U.on(el, '[data-pool=members]', 'click', () => V.poolMembersDialog(p, mode, load));
    U.on(el, '[data-pool=settings]', 'click', () => V.poolSettingsDialog(p, mode, load));
    U.on(el, '[data-pool-rm]', 'click', (e, b) => V.poolRemoveDialog(p.members.find((m) => m.id === b.dataset.poolRm), mode, load));
    U.on(el, '[data-pool-add]', 'click', (e, b) => U.busy(b, async () => {
      await U.api('/api/pool/stay', { body: { mode, strategy: b.dataset.poolAdd } }); U.toast('Added to the pool'); load();
    }));
    const box = el.querySelector('#pool-exp');
    if (box && p.on) V.poolExpected(box, { mode });
  };

  V.poolMembersDialog = async function (p, mode, onDone) {
    let R = {};
    try { R = await U.api('/api/pool/ranks?mode=' + mode); } catch (e) { U.toast('Backtest figures not available: ' + e.message); }
    const all = [...p.members.map((m) => ({ ...m, on: true })), ...p.outside.map((r) => ({ ...r, on: false }))]
      .map((r) => ({ ...r, ...(R[r.id] || { etf: r.group_label, etf_label: '', cap_group: r.group_label }) }));
    let by = 'r10';
    const score = (r) => (r[by] == null || r.r10 == null ? -1e9 : r[by]);
    const GRID = 'display:grid;grid-template-columns:22px 30px minmax(0,1fr) 92px 78px 112px;gap:10px;align-items:center';
    const list = (ticked) => {
      const G = {};
      all.forEach((r) => { (G[r.etf] = G[r.etf] || []).push(r); });
      Object.values(G).forEach((g) => g.sort((a, b) => score(b) - score(a) || a.name.localeCompare(b.name)));
      const keys = Object.keys(G).sort((a, b) => score(G[b][0]) - score(G[a][0]) || a.localeCompare(b));
      const capN = {};
      all.forEach((r) => { if (ticked.has(r.id)) capN[r.cap_group] = (capN[r.cap_group] || 0) + 1; });
      return keys.map((k) => {
        const g = G[k], n = g.length, t = g.filter((r) => ticked.has(r.id)).length, c = g[0].cap_group;
        const share = capN[c] > 1 ? ` · <span style="color:var(--warn-fg)">${capN[c]} ticked share the ${U.esc(c)} cap</span>` : '';
        const head = `<div class="row sb" style="gap:10px;flex-wrap:wrap;align-items:baseline;padding:16px 6px 6px;border-bottom:1px solid var(--line);font-size:14px">
          <div><b>${U.esc(k)}</b>${g[0].etf_label ? ` <span class="muted">· ${U.esc(g[0].etf_label)}</span>` : ''}</div>
          <div class="muted small">${n} strateg${n === 1 ? 'y' : 'ies'}${t ? ` · ${t} ticked` : ''} · cap group: ${U.esc(c)}${share}</div></div>`;
        return head + g.map((r, i) => {
          const best = i === 0 && n > 1 && r.r10 != null;
          const r10 = r.r10 != null ? `<b class="num ${U.cls(r.r10)}">${r.r10 > 0 ? '+' : ''}${r.r10.toFixed(1)}%</b>`
            : `<span class="muted small">${r.years ? r.years + ' years only' : 'no backtest'}</span>`;
          return `<label style="${GRID};padding:8px 6px;border-bottom:1px solid var(--line2);font-size:13.5px;cursor:pointer">
            <input type="checkbox" data-m="${r.id}" ${ticked.has(r.id) ? 'checked' : ''} style="width:17px;height:17px;accent-color:var(--accent)">
            <span class="num muted small" style="text-align:center">${n > 1 ? '#' + (i + 1) : ''}</span>
            <span class="row" style="gap:8px;flex-wrap:nowrap;min-width:0">${U.dot(r.color, 9)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${U.esc(r.name)}">${U.esc(r.name)}</span>${best ? U.pill('ok', 'Best') : ''}</span>
            <span style="text-align:right">${r10}</span>
            <span class="num muted" style="text-align:right">${r.dd10 != null ? r.dd10.toFixed(1) + '%' : '—'}</span>
            <span style="text-align:right">${U.pill('', 'signal: ' + U.esc(r.state || '—'))}</span></label>`;
        }).join('');
      }).join('');
    };
    U.modal(`Choose pool members · ${U.modeLabel[mode]}`, `<div class="col" style="gap:12px">
      <div class="row sb" style="flex-wrap:wrap;gap:10px"><div class="muted small" style="max-width:520px">Grouped by the ETF each strategy trades; inside each group the best 10-year backtest comes first. Only members trade; the others show signals only.${mode === 'live' ? ' <b>Live:</b> a strategy can join only after the Webull test trade of its ETF passed (Go-live → Test trade).' : ''}</div>
        <div class="row" style="gap:8px"><span class="muted small">Rank by</span><div class="seg" id="pm-by"><button type="button" class="on" data-by="r10">A year (10Y)</button><button type="button" data-by="ret_dd">Return ÷ worst fall</button></div></div></div>
      <div style="${GRID};padding:0 6px;font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em"><span></span><span>Rank</span><span>Strategy</span><span style="text-align:right">A year 10Y</span><span style="text-align:right">Worst fall</span><span style="text-align:right">Now</span></div>
      <div style="max-height:50vh;overflow:auto;margin-top:-8px" id="pm-list"></div>
      <div class="note" id="pm-sum"></div>
      <div class="idlebox card" style="padding:12px 14px" id="pm-exp"></div>
      <div class="row" style="justify-content:flex-end;gap:8px"><button class="btn" id="pm-c">Cancel</button><button class="btn p" id="pm-go">Save members</button></div></div>`, {
      width: 880,
      onOpen: (box, close) => {
        let timer = null;
        const ticked = new Set(p.members.map((m) => m.id));
        const draw = () => {
          const el = box.querySelector('#pm-list'), top = el.scrollTop;
          el.innerHTML = list(ticked);
          el.scrollTop = top;
        };
        const upd = () => {
          const ids = [...ticked], n = ids.length;
          const sug = n ? Math.round(Math.min(25, Math.max(10, 150 / n)) * 2) / 2 : 15;
          const slot = p.slot_auto ? sug : p.slot_pct;
          box.querySelector('#pm-sum').innerHTML = `<b>${n} member${n === 1 ? '' : 's'} selected.</b> Suggested trade size: <b>${sug}%</b> (150% ÷ ${n || 1}, kept between 10% and 25%). ${p.slot_auto ? 'The pool uses the suggestion.' : `Your setting is ${p.slot_pct}% (Pool settings).`}`;
          clearTimeout(timer);
          timer = setTimeout(() => V.poolExpected(box.querySelector('#pm-exp'), { mode, members: ids, slot_pct: slot }, true), 400);
        };
        box.querySelector('#pm-list').addEventListener('change', (e) => {
          const id = e.target.dataset && e.target.dataset.m;
          if (!id) return;
          e.target.checked ? ticked.add(id) : ticked.delete(id);
          draw(); upd();
        });
        box.querySelectorAll('#pm-by [data-by]').forEach((b) => b.addEventListener('click', () => {
          by = b.dataset.by;
          box.querySelectorAll('#pm-by [data-by]').forEach((x) => x.classList.toggle('on', x === b));
          draw();
        }));
        draw(); upd();
        box.querySelector('#pm-c').onclick = close;
        box.querySelector('#pm-go').onclick = (ev) => U.busy(ev.target, async () => {
          await U.api('/api/pool/members', { body: { mode, members: [...ticked] } });
          U.toast('Pool members saved'); close(); onDone && onDone();
        });
      },
    });
  };

  V.poolSettingsDialog = function (p, mode, onDone) {
    const T = p.total || 0;
    const inp = (id, v) => `<input class="in num" id="${id}" value="${v}" style="width:90px;height:40px;font-size:16px">`;
    U.modal(`Pool settings · ${U.modeLabel[mode]}`, `<div class="col" style="gap:16px">
      <label class="row sb"><b>Pool on</b><button type="button" class="sw ${p.on ? 'on' : ''}" id="ps-on" aria-label="Pool on"></button></label>
      <div class="muted small" id="ps-on-t"></div>
      <div><div class="row sb"><b>Trade size per new trade</b><span class="row" style="gap:8px">${inp('ps-slot', p.slot_pct)}<span class="muted">% of the pool</span></span></div>
        <label class="row small" style="gap:8px;margin-top:6px"><input type="checkbox" id="ps-auto" ${p.slot_auto ? 'checked' : ''}> Use the suggestion for the number of members (now ${p.suggested_slot}%)</label>
        <div class="muted small" id="ps-slot-t" style="margin-top:4px"></div></div>
      <div><div class="row sb"><b>Group cap</b><span class="row" style="gap:8px">${inp('ps-cap', p.cap_pct)}<span class="muted">% of the pool</span></span></div>
        <div class="muted small" id="ps-cap-t" style="margin-top:4px"></div></div>
      <div><div class="row sb"><b>Smallest trade</b><span class="row" style="gap:8px">${inp('ps-min', p.min_pct)}<span class="muted">% of the pool</span></span></div>
        <div class="muted small" id="ps-min-t" style="margin-top:4px"></div></div>
      <div class="note"><b>How the money moves</b><br>• A new buy signal takes the trade size, or the free cash if less (never below the smallest trade; signals starting together share it).<br>• Open trades keep their money and their own profit or loss; nothing is cut to make room.<br>• When a trade ends, the money (with its profit or loss) goes back to the pool.<br>• New money you allocate goes to the pool: the next trades get the bigger size, and signals waiting for money buy at the next check.<br>• Members don't park in gold or T-bills while out: that money stays in the pool for other signals.<br>• Strategies not in the pool only sell; their money comes back when they hold nothing.</div>
      <div class="idlebox card" style="padding:12px 14px" id="ps-exp"></div>
      <div class="row" style="justify-content:flex-end;gap:8px"><button class="btn" id="ps-c">Cancel</button><button class="btn p" id="ps-go">Save</button></div></div>`, {
      width: 660,
      onOpen: (box, close) => {
        let on = p.on, timer = null;
        const q = (s) => box.querySelector(s);
        const upd = () => {
          const auto = q('#ps-auto').checked;
          if (auto) q('#ps-slot').value = p.suggested_slot;
          q('#ps-slot').disabled = auto;
          const slot = +q('#ps-slot').value || 0, cap = +q('#ps-cap').value || 0, mn = +q('#ps-min').value || 0;
          q('#ps-slot-t').innerHTML = `= <b class="num">${usd0(T * slot / 100)}</b> per new trade now.`;
          q('#ps-cap-t').innerHTML = `= <b class="num">${usd0(T * cap / 100)}</b> per group. 25% had the best return for its risk in the research.`;
          q('#ps-min-t').innerHTML = `= <b class="num">${usd0(T * mn / 100)}</b>.`;
          q('#ps-on').classList.toggle('on', on);
          q('#ps-on-t').innerHTML = on ? 'On: members get money when a trade starts; everything else is signals only. Turning it on sells nothing except gold or T-bills members hold while out; cash of non-members goes back to the pool, and their open trades finish first.'
            : 'Off: money per strategy as before (Add money / Withdraw). Turning it off keeps every open trade\'s money with its strategy; free pool cash stays bot unassigned.';
          clearTimeout(timer);
          timer = setTimeout(() => V.poolExpected(q('#ps-exp'), { mode, slot_pct: slot, cap_pct: cap, min_pct: mn }, true), 400);
        };
        q('#ps-on').onclick = () => { on = !on; upd(); };
        ['#ps-slot', '#ps-cap', '#ps-min'].forEach((s) => q(s).addEventListener('input', upd));
        q('#ps-auto').addEventListener('change', upd);
        upd();
        q('#ps-c').onclick = close;
        q('#ps-go').onclick = (ev) => U.busy(ev.target, async () => {
          const auto = q('#ps-auto').checked;
          await U.api('/api/pool/settings', { body: { mode, on, auto_slot: auto, slot_pct: auto ? null : +q('#ps-slot').value, cap_pct: +q('#ps-cap').value, min_pct: +q('#ps-min').value } });
          U.toast('Pool settings saved'); close(); onDone && onDone();
        });
      },
    });
  };

  V.poolRemoveDialog = function (m, mode, onDone) {
    if (!m) return;
    const holds = m.value > 0.5;
    U.modal(`Take ${m.name.split(' · ')[0]} out of the pool?`, `<div class="col" style="gap:14px">
      <div class="muted">${U.esc(m.name)} ${holds ? `holds <b class="num">${U.usd(m.value)}</b> now${m.open_pnl != null ? ` (open trade ${U.sgnUsd(m.open_pnl, 0)})` : ''}.` : 'holds no money now: it simply stops getting money.'}</div>
      ${holds ? `<label class="opt on"><input type="radio" name="rm" value="finish" checked><div><b>Finish the trade, then leave</b><div class="muted small">It sells on its own signal as usual, and the money goes back to the pool. After that it shows signals only.</div></div></label>
      <label class="opt"><input type="radio" name="rm" value="sell"><div><b>Sell at the next open</b><div class="muted small">The position is sold at the next market open and the money goes back to the pool.</div></div></label>` : ''}
      <div class="muted small">Its trades and P&amp;L history are kept. You can add it back any time.</div>
      <div class="row" style="justify-content:flex-end;gap:8px"><button class="btn" id="rm-c">Cancel</button><button class="btn d" id="rm-go">Take out of the pool</button></div></div>`, {
      width: 560,
      onOpen: (box, close) => {
        box.querySelectorAll('.opt').forEach((o) => o.addEventListener('click', () => box.querySelectorAll('.opt').forEach((x) => x.classList.toggle('on', x === o))));
        box.querySelector('#rm-c').onclick = close;
        box.querySelector('#rm-go').onclick = (ev) => U.busy(ev.target, async () => {
          const sell = (box.querySelector('input[name=rm]:checked') || {}).value === 'sell';
          await U.api('/api/pool/remove', { body: { mode, strategy: m.id, sell } });
          U.toast('Taken out of the pool'); close(); onDone && onDone();
        });
      },
    });
  };

  /* Strategy page: the pool tile (first KPI) and the header buttons. */
  V.poolTile = function (pi) {
    if (!pi || !pi.on) return '';
    if (pi.member) {
      return `<div class="card" style="border-left:3px solid var(--accent)"><div class="eyebrow">Pool · ${U.esc(pi.mode_label)}</div><div class="num big" style="margin-top:6px">Member</div>
        <div class="muted small">gets ${pi.slot_pct}% of the pool per new trade = ${usd0(pi.slot_usd)} · group ${U.esc(pi.group_label)} (cap ${pi.cap_pct}%)${pi.waiting ? ' · <b class="warn-t">signal waits for money</b>' : ''}</div></div>`;
    }
    return `<div class="card"><div class="eyebrow">Pool · ${U.esc(pi.mode_label)}</div><div class="num big" style="margin-top:6px">Not a member</div>
      <div class="muted small">${pi.leaving ? 'leaving: its open trade finishes, then its money goes back to the pool' : 'signals only · never buys'}</div></div>`;
  };
  V.poolButtons = function (pi, c) {
    const ctl = `<button class="btn" data-ctl="${c.control === 'paused' ? 'active' : 'paused'}">${c.control === 'paused' ? 'Resume buys' : 'Pause buys'}</button><button class="btn d" data-ctl="stopping">Stop &amp; sell</button>`;
    return pi.member ? `<button class="btn" data-pool-me="remove">Remove from pool</button>${ctl}` : `<button class="btn p" data-pool-me="add">+ Add to pool</button>${ctl}`;
  };
})();
