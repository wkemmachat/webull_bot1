/* Donut of how the money in the strategies is split (unassigned bot money not counted).
   V.renderAlloc(el, strategies) — strategies: [{id, name, color, value, net_in}] from the strategy cards. */
(function () {
  const V = window.Views || (window.Views = {});
  const KEY = 'tsb.alloc.basis';
  const BASIS = { value: 'Value now', net_in: 'Money put in' };
  const getBasis = () => { try { return localStorage.getItem(KEY) === 'net_in' ? 'net_in' : 'value'; } catch (e) { return 'value'; } };
  const setBasis = (b) => { try { localStorage.setItem(KEY, b); } catch (e) {} };

  function arc(cx, cy, r0, r1, a0, a1) {
    const p = (r, a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
    const big = a1 - a0 > Math.PI ? 1 : 0;
    const [x0, y0] = p(r1, a0), [x1, y1] = p(r1, a1), [x2, y2] = p(r0, a1), [x3, y3] = p(r0, a0);
    return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r1} ${r1} 0 ${big} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}L${x2.toFixed(2)} ${y2.toFixed(2)}A${r0} ${r0} 0 ${big} 0 ${x3.toFixed(2)} ${y3.toFixed(2)}Z`;
  }

  V.renderAlloc = function (el, strategies, opts) {
    opts = opts || {};
    let basis = getBasis();

    function draw() {
      const all = strategies.map((s) => ({ id: s.id, name: s.name, color: s.color, v: Math.max(0, Number(s[basis]) || 0), value: s.value, net_in: s.net_in }));
      const rows = all.filter((s) => s.v > 0.005).sort((a, b) => b.v - a.v);
      const empty = all.filter((s) => s.v <= 0.005);
      const tot = rows.reduce((x, s) => x + s.v, 0);
      const S = 220, cx = S / 2, cy = S / 2, r1 = 104, r0 = 70;
      let a = 0;
      const segs = rows.map((s, i) => {
        const span = (s.v / tot) * Math.PI * 2;
        const d = rows.length === 1
          ? `M${cx} ${cy - r1}A${r1} ${r1} 0 1 1 ${cx - 0.01} ${cy - r1}ZM${cx} ${cy - r0}A${r0} ${r0} 0 1 0 ${cx + 0.01} ${cy - r0}Z`
          : arc(cx, cy, r0, r1, a, a + span);
        a += span;
        return `<path d="${d}" fill="${U.esc(s.color)}" fill-rule="evenodd" stroke="var(--panel)" stroke-width="2" stroke-linejoin="round" data-i="${i}" tabindex="0"
          role="img" aria-label="${U.esc(s.name)}: ${U.usd(s.v, 0)}, ${(s.v / tot * 100).toFixed(1)}%"><title>${U.esc(s.name)} · ${U.usd(s.v, 0)} · ${(s.v / tot * 100).toFixed(1)}%</title></path>`;
      }).join('');
      const center = (title, amount, sub) => `<div class="muted small" style="max-width:120px;line-height:1.25;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">${U.esc(title)}</div>
        <div class="num" style="font-size:20px;font-weight:600;margin-top:2px">${amount}</div><div class="muted small num">${sub}</div>`;
      el.innerHTML = `<section class="card col" style="gap:14px">
        <div class="row sb" style="gap:10px;flex-wrap:wrap"><div><h2 class="h2">${U.esc(opts.title || 'Money in strategies')}</h2>
          <div class="muted small">Split of the ${U.usd(tot, 0)} in ${rows.length} strateg${rows.length === 1 ? 'y' : 'ies'} · unassigned money not counted</div></div>
          <div class="seg" data-alloc-basis>${Object.entries(BASIS).map(([k, l]) => `<button data-b="${k}" class="${basis === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>
        ${rows.length ? `<div class="row" style="gap:24px;align-items:center;flex-wrap:wrap">
          <div style="position:relative;width:${S}px;height:${S}px;flex:0 0 auto;margin:0 auto">
            <svg viewBox="0 0 ${S} ${S}" width="${S}" height="${S}" style="display:block;overflow:visible">${segs}</svg>
            <div data-alloc-center style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;pointer-events:none">
              ${center('Total · ' + BASIS[basis].toLowerCase(), U.usd(tot, 0), rows.length + ' strategies')}</div></div>
          <div class="col" style="flex:1 1 260px;min-width:0;gap:0">
            ${rows.map((s, i) => `<a href="#/strategies/${U.esc(s.id)}" class="kv" data-li="${i}" style="padding:7px 6px;border-radius:6px;color:var(--text)">
              <span class="row" style="gap:10px;flex-wrap:nowrap;min-width:0">${U.dot(s.color, 10)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${U.esc(s.name)}</span></span>
              <span class="row" style="gap:12px;flex-wrap:nowrap"><span class="num">${U.usd(s.v, 0)}</span><span class="num" style="width:52px;text-align:right;font-weight:600">${(s.v / tot * 100).toFixed(1)}%</span></span></a>`).join('')}
            ${empty.length ? `<div class="muted small" style="padding:8px 6px 0">No money: ${empty.map((s) => U.esc(s.name)).join(', ')}</div>` : ''}
          </div></div>`
        : `<div class="empty small">No money in any strategy yet${basis === 'net_in' ? ' (money put in)' : ''}. Give a strategy money on the Money page.</div>`}
      </section>`;
      U.on(el, '[data-alloc-basis] button', 'click', (e, b) => { basis = b.dataset.b; setBasis(basis); draw(); });
      if (!rows.length) return;
      const cEl = el.querySelector('[data-alloc-center]');
      const paths = el.querySelectorAll('path[data-i]'), items = el.querySelectorAll('[data-li]');
      let cur = null;
      const focus = (i) => {
        cur = i;
        paths.forEach((p) => { p.style.opacity = i == null || +p.dataset.i === i ? '1' : '.35'; });
        items.forEach((x) => { x.style.background = +x.dataset.li === i ? 'var(--hover)' : ''; });
        if (i == null) cEl.innerHTML = center('Total · ' + BASIS[basis].toLowerCase(), U.usd(tot, 0), rows.length + ' strategies');
        else {
          const s = rows[i], other = basis === 'value' ? s.net_in : s.value;
          cEl.innerHTML = center(s.name, (s.v / tot * 100).toFixed(1) + '%', U.usd(s.v, 0) + (other != null ? '<br>' + (basis === 'value' ? 'put in ' : 'now ') + U.usd(other, 0) : ''));
        }
      };
      paths.forEach((p) => {
        p.style.cursor = 'pointer'; p.style.transition = 'opacity .12s';
        p.addEventListener('pointerenter', () => focus(+p.dataset.i));
        p.addEventListener('pointerleave', (e) => { if (e.pointerType !== 'touch') focus(null); });
        p.addEventListener('focus', () => focus(+p.dataset.i));
        p.addEventListener('blur', () => focus(null));
        p.addEventListener('click', () => { const i = +p.dataset.i; if (cur === i) location.hash = '#/strategies/' + rows[i].id; else focus(i); });
      });
      items.forEach((x) => { x.addEventListener('pointerenter', () => focus(+x.dataset.li)); x.addEventListener('pointerleave', () => focus(null)); });
    }
    draw();
  };
})();
