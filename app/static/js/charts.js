/* TradingView Lightweight Charts (v4) drawing of a strategy chart spec:
   { charts: [{ title, subtitle, candles, lines:[{name,color,width,data,legend}], markers, ribbon:[{time,color}],
                panes:[{title,height,lines:[...],hlines:[{value,label}],step}], tv, time_visible }] }
   Panes (ADX, volatility, weight) are separate charts kept in sync with the price chart. */
(function () {
  const C = (window.Charts = {});
  const TZ = 'Asia/Bangkok';
  const fmtTime = (daily) => new Intl.DateTimeFormat('en-GB', daily ? { timeZone: 'UTC', day: 'numeric', month: 'short', year: '2-digit' }
    : { timeZone: TZ, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });

  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }

  function base(el, opts) {
    const daily = !!opts.daily;
    const f = fmtTime(daily);
    const c = LightweightCharts.createChart(el, {
      autoSize: true,
      layout: { background: { type: 'solid', color: css('--chart-bg') }, textColor: css('--chart-text'), fontSize: 11,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif" },
      grid: { vertLines: { color: css('--chart-grid') }, horzLines: { color: css('--chart-grid') } },
      rightPriceScale: { borderColor: css('--line'), minimumWidth: 72 },
      timeScale: { borderColor: css('--line'), timeVisible: !daily, secondsVisible: false, visible: opts.timeVisible !== false,
        rightOffset: 4, tickMarkFormatter: (t) => {
          const d = new Date(t * 1000);
          return new Intl.DateTimeFormat('en-GB', daily ? { timeZone: 'UTC', day: 'numeric', month: 'short' } : { timeZone: TZ, day: 'numeric', month: 'short' }).format(d);
        } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      localization: { timeFormatter: (t) => f.format(new Date(t * 1000)), priceFormatter: (p) => p.toLocaleString('en-US', { maximumFractionDigits: p < 100 ? 3 : 2 }) },
      handleScale: { axisPressedMouseMove: true }, handleScroll: true,
    });
    if (opts.noLogo) { try { c.applyOptions({ layout: { attributionLogo: false } }); } catch (e) {} }
    return c;
  }

  function legendHtml(items) {
    return items.map((x) => `<span style="color:${x.color || 'inherit'}">${U.esc(x.label)}${x.value != null ? ' <b class="num" style="font-weight:500">' + U.esc(x.value) + '</b>' : ''}</span>`).join('');
  }

  const fmtV = (v) => v == null ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: Math.abs(v) < 100 ? 3 : 2 });

  C.base = base;

  C.render = function (host, spec, opts) {
    opts = opts || {};
    const charts = [];
    host.innerHTML = '';
    if (!spec || !spec.charts || !spec.charts.length) {
      host.innerHTML = `<div class="empty">${U.esc((spec && spec.error) || 'No chart data yet. The bot downloads prices on its first run.')}</div>`;
      return { destroy() {} };
    }
    spec.charts.forEach((c, ci) => {
      const daily = c.candles.length > 1 && (c.candles[1].time - c.candles[0].time) >= 86400;
      const wrap = document.createElement('div');
      wrap.className = 'col';
      wrap.style.gap = '8px';
      wrap.innerHTML = `${spec.charts.length > 1 || opts.titles ? `<div class="row sb"><div><div class="eyebrow">${U.esc(c.subtitle || '')}</div><div class="h2">${U.esc(c.title)}</div></div>
        ${c.tv ? `<a class="btn s" href="${U.esc(c.tv)}" target="_blank" rel="noopener">Open ${U.esc(c.tv_symbol || c.title)} in TradingView ↗</a>` : ''}</div>` : ''}
        <div class="tvwrap"><div class="tvmain" style="height:${opts.height || (c.panes && c.panes.length ? 340 : 420)}px;position:relative"><div class="tvlegend"></div></div></div>`;
      host.appendChild(wrap);
      const tvwrap = wrap.querySelector('.tvwrap');
      const mainEl = wrap.querySelector('.tvmain');
      const panes = (c.panes || []).filter((p) => !opts.hidePanes || !opts.hidePanes.includes(p.id));
      const chart = base(mainEl, { daily, timeVisible: panes.length === 0 });
      charts.push(chart);
      const candle = chart.addCandlestickSeries({ upColor: '#26A69A', downColor: '#EF5350', borderVisible: false, wickUpColor: '#26A69A', wickDownColor: '#EF5350' });
      candle.setData(c.candles);
      const lineSeries = [];
      (c.lines || []).forEach((l) => {
        if (opts.hideLines && opts.hideLines.includes(l.name)) return;
        const s = chart.addLineSeries({ color: l.color, lineWidth: l.width || 2, priceLineVisible: false, lastValueVisible: l.legend !== false,
          crosshairMarkerVisible: false });
        s.setData(l.data);
        lineSeries.push({ s, l });
      });
      if (c.ribbon && c.ribbon.length) {
        const r = chart.addHistogramSeries({ priceScaleId: 'ribbon', priceLineVisible: false, lastValueVisible: false, base: 0 });
        chart.priceScale('ribbon').applyOptions({ scaleMargins: { top: 0.965, bottom: 0 }, visible: false });
        r.setData(c.ribbon.map((x) => ({ time: x.time, value: 1, color: x.color })));
        chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.06 } });
      }
      if (!opts.hideMarkers && c.markers && c.markers.length) candle.setMarkers(c.markers.slice().sort((a, b) => a.time - b.time));
      const legend = mainEl.querySelector('.tvlegend');
      const lastBar = c.candles[c.candles.length - 1];
      const legendFor = (bar, t) => {
        const col = bar && bar.close >= bar.open ? '#26A69A' : '#EF5350';
        const items = [{ label: c.title }];
        if (bar) items.push({ label: 'O', value: fmtV(bar.open), color: col }, { label: 'H', value: fmtV(bar.high), color: col },
          { label: 'L', value: fmtV(bar.low), color: col }, { label: 'C', value: fmtV(bar.close), color: col });
        lineSeries.forEach(({ l }) => {
          if (l.legend === false) return;
          const pt = l.data.find((d) => d.time === t) || {};
          let v = pt.value;
          if (v == null) {
            const sib = lineSeries.find((x) => x.l !== l && x.l.legend === false && x.l.name.split(' (')[0] === l.name.split(' (')[0]);
            if (sib) v = (sib.l.data.find((d) => d.time === t) || {}).value;
          }
          items.push({ label: l.name.replace(' (up)', ''), value: fmtV(v), color: l.color });
        });
        legend.innerHTML = legendHtml(items);
      };
      legendFor(lastBar, lastBar && lastBar.time);
      const paneCharts = [];
      panes.forEach((p, pi) => {
        const pel = document.createElement('div');
        pel.className = 'tvpane';
        pel.style.height = (p.height || 110) + 'px';
        pel.innerHTML = '<div class="tvlegend"></div>';
        tvwrap.appendChild(pel);
        const pc = base(pel, { daily, timeVisible: pi === panes.length - 1, noLogo: true });
        charts.push(pc);
        const ps = [];
        p.lines.forEach((l, li) => {
          let s;
          if (l.area) {
            s = pc.addAreaSeries({ lineColor: l.color, topColor: l.color + '55', bottomColor: l.color + '08', lineWidth: l.width || 2,
              lineType: p.step ? 1 : 0, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false });
          } else {
            s = pc.addLineSeries({ color: l.color, lineWidth: l.width || 2, lineType: p.step ? 1 : 0, priceLineVisible: false,
              lastValueVisible: li === 0, crosshairMarkerVisible: false });
          }
          s.setData(l.data);
          ps.push({ s, l });
          if (li === 0) (p.hlines || []).forEach((h) => s.createPriceLine({ price: h.value, color: '#787B86', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: h.label || '' }));
        });
        const pl = pel.querySelector('.tvlegend');
        const pleg = (t) => {
          pl.innerHTML = legendHtml([{ label: p.title }].concat(ps.map(({ l }) => {
            const pt = l.data.find((d) => d.time === t) || l.data[l.data.length - 1] || {};
            return { label: l.name, value: fmtV(pt.value), color: l.color };
          })).concat((p.hlines || []).map((h) => ({ label: '— ' + (h.label || h.value), color: '#787B86' }))));
        };
        pleg(lastBar && lastBar.time);
        paneCharts.push({ pc, ps, pleg });
      });
      // keep the panes scrolled and zoomed with the price chart
      let syncing = false;
      const all = [chart].concat(paneCharts.map((x) => x.pc));
      all.forEach((src) => src.timeScale().subscribeVisibleLogicalRangeChange((r) => {
        if (syncing || !r) return;
        syncing = true;
        all.forEach((dst) => { if (dst !== src) dst.timeScale().setVisibleLogicalRange(r); });
        syncing = false;
      }));
      chart.subscribeCrosshairMove((param) => {
        const bar = param.time ? param.seriesData.get(candle) : null;
        legendFor(bar || lastBar, param.time || (lastBar && lastBar.time));
        paneCharts.forEach(({ pc, ps, pleg }) => {
          pleg(param.time || (lastBar && lastBar.time));
          if (param.time && ps[0] && pc.setCrosshairPosition) {
            const pt = ps[0].l.data.find((d) => d.time === param.time);
            if (pt && pt.value != null) pc.setCrosshairPosition(pt.value, param.time, ps[0].s);
          } else if (pc.clearCrosshairPosition) pc.clearCrosshairPosition();
        });
      });
      chart.timeScale().fitContent();
    });
    return { destroy() { charts.forEach((x) => { try { x.remove(); } catch (e) {} }); } };
  };
})();
