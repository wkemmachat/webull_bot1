(function () {
  const V = window.Views || (window.Views = {});

  /* tiny markdown: headings, lists, code blocks, tables, quotes, bold, italic, code, links */
  function md(src) {
    const lines = src.replace(/\r/g, '').split('\n');
    const item = (re) => {                      // a list item and its indented continuation lines
      let t = lines[i++].replace(re, '');
      while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) t += ' ' + lines[i++].trim();
      return t;
    };
    let out = '', i = 0;
    const inline = (s) => U.esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/(^|[\s(])\*([^*]+)\*/g, '$1<i>$2</i>').replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, u) => `<a href="${u}"${/^https?:/.test(u) ? ' target="_blank" rel="noopener"' : ''}>${t}</a>`);
    while (i < lines.length) {
      const l = lines[i];
      if (/^```/.test(l)) { let b = ''; i++; while (i < lines.length && !/^```/.test(lines[i])) b += lines[i++] + '\n'; i++; out += `<pre><code>${U.esc(b.replace(/\n$/, ''))}</code></pre>`; continue; }
      const h = l.match(/^(#{1,3})\s+(.*)/);
      if (h) { const id = h[2].toLowerCase().replace(/[^a-z0-9]+/g, '-'); out += `<h${h[1].length} id="${id}">${inline(h[2])}</h${h[1].length}>`; i++; continue; }
      if (/^\s*[-*]\s+/.test(l)) { out += '<ul>'; while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) out += `<li>${inline(item(/^\s*[-*]\s+/))}</li>`; out += '</ul>'; continue; }
      if (/^\s*\d+\.\s+/.test(l)) { out += '<ol>'; while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) out += `<li>${inline(item(/^\s*\d+\.\s+/))}</li>`; out += '</ol>'; continue; }
      if (/^>\s?/.test(l)) { let b = ''; while (i < lines.length && /^>\s?/.test(lines[i])) b += lines[i++].replace(/^>\s?/, '') + ' '; out += `<blockquote>${inline(b)}</blockquote>`; continue; }
      if (/^\|/.test(l)) {
        const rows = []; while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
        const cells = (r) => r.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
        out += '<div class="tw"><table><thead><tr>' + cells(rows[0]).map((c) => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>' +
          rows.slice(2).map((r) => '<tr>' + cells(r).map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>';
        continue;
      }
      if (!l.trim()) { i++; continue; }
      let p = ''; while (i < lines.length && lines[i].trim() && !/^(#|```|\s*[-*]\s|\s*\d+\.\s|>|\|)/.test(lines[i])) p += lines[i++] + ' ';
      out += `<p>${inline(p.trim())}</p>`;
    }
    return out;
  }

  V.docs = async function (el, params) {
    const idx = (await U.api('/api/docs')).docs;
    const name = params[0] || 'overview';
    const doc = await U.api('/api/docs/' + (idx.find((d) => d.name === name) ? name : idx[0].name));
    const groups = {};
    idx.forEach((d) => (groups[d.group] = groups[d.group] || []).push(d));
    const pos = idx.findIndex((d) => d.name === doc.name);
    const heads = [...doc.markdown.matchAll(/^##\s+(.*)$/gm)].map((m) => m[1]);
    el.innerHTML = `<div class="row" style="gap:28px;align-items:flex-start;flex-wrap:wrap">
      <nav class="toc" style="flex:1 1 220px;max-width:250px">
        <input class="in" id="ds" placeholder="Search the manual…" aria-label="Search the manual">
        ${Object.entries(groups).map(([g, ds]) => `<div class="g">${U.esc(g)}</div>${ds.map((d) => `<a href="#/docs/${d.name}" class="${d.name === doc.name ? 'on' : ''}">${U.esc(d.title)}</a>`).join('')}`).join('')}
      </nav>
      <article class="doc" style="flex:999 1 520px;min-width:0" id="art">
        <div class="muted small" style="margin-bottom:8px">${U.esc(doc.meta.group || '')} · updated ${U.day(doc.updated)}</div>${md(doc.markdown)}
        <div class="row sb" style="border-top:1px solid var(--line);padding-top:18px;margin-top:24px">
          ${pos > 0 ? `<a href="#/docs/${idx[pos - 1].name}">← ${U.esc(idx[pos - 1].title)}</a>` : '<span></span>'}
          ${pos < idx.length - 1 ? `<a href="#/docs/${idx[pos + 1].name}">${U.esc(idx[pos + 1].title)} →</a>` : ''}</div></article>
      <aside style="flex:1 1 170px;max-width:200px" class="col"><div class="eyebrow">On this page</div>
        ${heads.map((h) => `<a class="small" href="#/docs/${doc.name}" data-h="${U.esc(h.toLowerCase().replace(/[^a-z0-9]+/g, '-'))}" style="color:var(--muted)">${U.esc(h)}</a>`).join('')}
        <button class="btn s" onclick="window.print()" style="margin-top:12px">Print / save PDF</button></aside></div>`;
    U.on(el, '[data-h]', 'click', (e, a) => { e.preventDefault(); const t = el.querySelector('#' + CSS.escape(a.dataset.h)); if (t) t.scrollIntoView({ behavior: 'smooth' }); });
    el.querySelector('#ds').addEventListener('keydown', async (e) => {
      if (e.key !== 'Enter') return;
      const q = e.target.value.trim().toLowerCase();
      if (!q) return;
      const hits = [];
      for (const d of idx) { const x = await U.api('/api/docs/' + d.name); const i = x.markdown.toLowerCase().indexOf(q); if (i >= 0) hits.push({ d, snip: x.markdown.slice(Math.max(0, i - 60), i + 100) }); }
      el.querySelector('#art').innerHTML = `<h1>Search: ${U.esc(q)}</h1>${hits.map((h) => `<p><a href="#/docs/${h.d.name}"><b>${U.esc(h.d.title)}</b></a><br><span class="muted small">…${U.esc(h.snip)}…</span></p>`).join('') || '<p>Nothing found.</p>'}`;
    });
  };
})();
