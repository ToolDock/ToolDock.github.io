/* 今日の米国市場 ── market.json を読んでページを組み立てる。
 *
 * チャートは Chart.js（/js/vendor/chart.umd.min.js）で描く。
 * market.json に入っているのは数値と系列だけで、図の定義は持たない。
 *
 * 折れ線3種（タイルの日中足・基準価額・ドローダウン）は Chart.js。
 * Fear & Greed のメーターと VIX のメーターは図形なので、
 * Chart.js を曲げるより素のSVGで描くほうが短く正確になる。
 * 触るとしたら COLORS（色）と、各 render〜()（文言・並び）で足りるようにしてある。
 */
(function () {
  "use strict";

  var DATA_URL = "./market.json";

  var COLORS = {
    up: "#2e7d32",
    down: "#c62828",
    flat: "#78909c",
    grid: "rgba(128,128,128,0.22)"
  };

  var MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];

  function cssVar(name, fallback) {
    var value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (value || "").trim() || fallback;
  }

  function fontColor() { return cssVar("--chart-font-color", "#3d4348"); }

  function dirColor(direction) {
    return direction > 0 ? COLORS.up : (direction < 0 ? COLORS.down : COLORS.flat);
  }

  function rgba(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16),
        g = parseInt(hex.slice(3, 5), 16),
        b = parseInt(hex.slice(5, 7), 16);
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
  }

  function directionClass(direction) {
    return direction > 0 ? "up" : (direction < 0 ? "down" : "flat");
  }

  function setText(root, selector, text) {
    var el = root.querySelector(selector);
    if (el) { el.textContent = text == null ? "" : text; }
  }

  /* data-bind="a.b" の要素にまとめて値を入れる */
  function bind(scope, path, value) {
    var nodes = document.querySelectorAll('[data-bind="' + path + '"]');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = value == null ? "" : value;
    }
  }

  function fmt(value, digits) {
    return Number(value).toLocaleString("ja-JP", {
      minimumFractionDigits: digits, maximumFractionDigits: digits
    });
  }

  /* 器を <canvas> に差し替えて返す。高さはCSS側（.tile__chart など）が決める */
  function canvasIn(host) {
    if (!host) { return null; }
    host.innerHTML = "";
    var canvas = document.createElement("canvas");
    host.appendChild(canvas);
    return canvas;
  }

  var charts = [];

  function makeChart(host, config) {
    var canvas = canvasIn(host);
    if (!canvas) { return null; }
    config.options = config.options || {};
    config.options.responsive = true;
    config.options.maintainAspectRatio = false;
    config.options.animation = false;
    var chart = new Chart(canvas, config);
    charts.push(chart);
    return chart;
  }

  /* ── 1・2段目：タイルの日中足 ───────────────── */
  function tileChart(host, tile) {
    var color = dirColor(tile.direction);
    var base = tile.prev_close;
    var values = tile.values || [];
    var datasets = [];

    /* 前日終値の基準線。塗りつぶしの相手にもなる */
    if (base != null) {
      datasets.push({
        data: values.map(function () { return base; }),
        borderColor: COLORS.flat,
        borderWidth: 1,
        borderDash: [3, 3],
        pointRadius: 0,
        fill: false
      });
    }

    datasets.push({
      data: values,
      borderColor: color,
      borderWidth: 2,
      pointRadius: 0,
      pointHitRadius: 8,
      tension: 0,
      fill: base != null ? { target: 0, above: rgba(color, 0.16), below: rgba(color, 0.16) } : false,
      backgroundColor: rgba(color, 0.16)
    });

    /* 前日終値を含めた範囲に少し余白を足す。全体が横一線に見えないように */
    var span = values.filter(function (v) { return v != null; });
    if (base != null) { span = span.concat([base]); }
    var low = Math.min.apply(null, span);
    var high = Math.max.apply(null, span);
    var pad = (high - low) * 0.15 || (Math.abs(high) * 0.001 + 0.01);

    makeChart(host, {
      type: "line",
      data: { labels: tile.times || [], datasets: datasets },
      options: {
        layout: { padding: 0 },
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: function (item) { return item.datasetIndex === datasets.length - 1; },
            callbacks: {
              label: function (item) { return fmt(item.parsed.y, tile.digits); }
            }
          }
        },
        scales: {
          x: { display: false },
          y: { display: false, min: low - pad, max: high + pad }
        }
      }
    });
  }

  /* ── 3段目：基準価額の年初来 ────────────────── */
  function fundChart(host, series) {
    var values = series.values;
    var color = values[values.length - 1] >= values[0] ? COLORS.up : COLORS.down;
    var low = Math.min.apply(null, values);
    var high = Math.max.apply(null, values);
    var pad = (high - low) * 0.12;

    /* 端をそのまま渡すと目盛りに「46,752円」と生の値が出るので、
       きりのいい単位まで外側に丸める */
    var step = 1000;
    low = Math.floor((low - pad) / step) * step;
    high = Math.ceil((high + pad) / step) * step;

    /* 月が変わる最初の営業日だけ「◯月」と出す */
    var seen = {};
    var monthTick = series.dates.map(function (d) {
      var month = Number(d.slice(5, 7));
      if (seen[month]) { return ""; }
      seen[month] = true;
      return month + "月";
    });

    makeChart(host, {
      type: "line",
      data: {
        labels: series.dates,
        datasets: [{
          data: values,
          borderColor: color,
          borderWidth: 2.4,
          pointRadius: 0,
          pointHitRadius: 6,
          fill: "origin",
          backgroundColor: rgba(color, 0.12)
        }]
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (item) { return fmt(item.parsed.y, 0) + "円"; }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: COLORS.grid },
            ticks: {
              color: fontColor(), autoSkip: false, maxRotation: 0,
              callback: function (_v, i) { return monthTick[i]; }
            }
          },
          y: {
            min: low, max: high,
            grid: { color: COLORS.grid },
            border: { display: false },
            ticks: {
              color: fontColor(),
              callback: function (v) { return fmt(v, 0) + "円"; }
            }
          }
        }
      }
    });
  }

  /* ── 4段目：年初来ドローダウン ──────────────── */
  function drawdownChart(host, drawdown) {
    var years = Object.keys(drawdown.years).sort();
    if (!years.length) { return; }

    var lowest = 0;
    var datasets = years.map(function (year, index) {
      var y = drawdown.years[year];
      var latest = index === years.length - 1;
      var color = latest ? COLORS.down : COLORS.flat;
      y.values.forEach(function (v) { lowest = Math.min(lowest, v); });
      return {
        label: year + "年",
        /* 年をまたいで重ねるので、横軸は日付ではなく「年の何日目か」にそろえる */
        data: y.dates.map(function (d, i) {
          return { x: dayOfYear(d), y: y.values[i] };
        }),
        borderColor: color,
        borderWidth: latest ? 2.6 : 2.0,
        borderDash: latest ? [] : [6, 4],
        pointRadius: 0,
        pointHitRadius: 6,
        fill: latest ? "origin" : false,
        backgroundColor: rgba(color, 0.10)
      };
    });

    makeChart(host, {
      type: "line",
      data: { datasets: datasets },
      options: {
        interaction: { mode: "nearest", axis: "x", intersect: false },
        plugins: {
          legend: {
            display: true, align: "end",
            labels: { color: fontColor(), boxWidth: 18, usePointStyle: false }
          },
          tooltip: {
            callbacks: {
              title: function (items) { return monthDayLabel(items[0].parsed.x); },
              label: function (item) {
                return item.dataset.label + " " + item.parsed.y.toFixed(2) + "%";
              }
            }
          }
        },
        scales: {
          x: {
            type: "linear", min: 1, max: 366,
            grid: { color: COLORS.grid },
            border: { display: false },
            ticks: {
              color: fontColor(), autoSkip: false, maxRotation: 0,
              stepSize: 1,
              callback: function (v) {
                var i = MONTH_TICKS.indexOf(v);
                return i === -1 ? "" : (i + 1) + "月";
              }
            },
            afterBuildTicks: function (axis) {
              axis.ticks = MONTH_TICKS.map(function (v) { return { value: v }; });
            }
          },
          y: {
            /* 下端も5%刻みに丸める。生の値が目盛りに出ないように */
            min: Math.floor(Math.min(lowest * 1.15, -2) / 5) * 5, max: 2.5,
            grid: { color: COLORS.grid },
            border: { display: false },
            ticks: {
              color: fontColor(),
              callback: function (v) { return v + "%"; }
            }
          }
        }
      }
    });

    /* 各年の最大下落を、値だけ添えておく */
    var host2 = document.getElementById("drawdown-max");
    if (host2) {
      host2.innerHTML = "";
      years.slice().reverse().forEach(function (year) {
        var y = drawdown.years[year];
        if (y.max == null) { return; }
        var item = document.createElement("span");
        item.className = "dd-max";
        item.textContent = year + "年 最大 " + y.max.toFixed(1) + "%（" + y.max_date + "）";
        host2.appendChild(item);
      });
    }
  }

  function dayOfYear(iso) {
    var d = new Date(iso + "T00:00:00");
    return Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 86400000);
  }

  function monthDayLabel(day) {
    for (var i = MONTH_TICKS.length - 1; i >= 0; i--) {
      if (day >= MONTH_TICKS[i]) {
        return (i + 1) + "月" + (day - MONTH_TICKS[i] + 1) + "日ごろ";
      }
    }
    return day + "日目";
  }

  /* ── 5段目：Fear & Greed のメーター ──────────── */
  var FG_SPAN = 120;                  /* メーターの開き角（度） */
  var FG_R_OUT = 100, FG_R_IN = 78;

  function fgAngle(value) {
    var v = Math.max(0, Math.min(100, value));
    return (v / 100 - 0.5) * FG_SPAN * Math.PI / 180;
  }

  function fgPoint(theta, radius) {
    return [radius * Math.sin(theta), -radius * Math.cos(theta)];
  }

  function arcPath(low, high, rOut, rIn) {
    var a1 = fgAngle(low), a2 = fgAngle(high);
    var o1 = fgPoint(a1, rOut), o2 = fgPoint(a2, rOut);
    var i2 = fgPoint(a2, rIn), i1 = fgPoint(a1, rIn);
    return "M" + o1 + "A" + rOut + "," + rOut + " 0 0 1 " + o2 +
           "L" + i2 + "A" + rIn + "," + rIn + " 0 0 0 " + i1 + "Z";
  }

  function fgGauge(host, fg, bands) {
    if (!host) { return; }
    var svg = ['<svg viewBox="-135 -125 270 150" role="img" aria-label="Fear and Greed Index">'];

    bands.forEach(function (band) {
      svg.push('<path d="' + arcPath(band[0], band[1], FG_R_OUT, FG_R_IN) +
               '" fill="' + band[4] + '"/>');
    });

    /* 針 */
    var theta = fgAngle(fg.value);
    var tip = fgPoint(theta, FG_R_IN - 6);
    var left = fgPoint(theta - Math.PI / 2, 4.5);
    var right = fgPoint(theta + Math.PI / 2, 4.5);
    var tail = fgPoint(theta + Math.PI, 10);
    svg.push('<polygon points="' + [tip, left, tail, right].join(" ") +
             '" fill="rgba(120,144,156,0.95)"/>');
    svg.push('<circle cx="0" cy="0" r="7" fill="#78909c"/>');

    [0, 50, 100].forEach(function (tick) {
      var p = fgPoint(fgAngle(tick), FG_R_OUT + 13);
      svg.push('<text x="' + p[0] + '" y="' + p[1] + '" text-anchor="middle" ' +
               'dominant-baseline="middle" font-size="12" fill="' + fontColor() +
               '" opacity="0.65">' + tick + '</text>');
    });
    svg.push('</svg>');

    host.innerHTML = svg.join("");

    bind(document, "fear_greed.value_text", fg.value_text);
    bind(document, "fear_greed.label", fg.label_ja + "（" + fg.label_en + "）");
    var label = document.querySelector('[data-bind="fear_greed.label"]');
    if (label) { label.style.color = fg.color; }
  }

  /* ── 5段目：VIX のメーター ─────────────────── */
  function vixMeter(host, vix, bands) {
    if (!host) { return; }
    var MAX = 50, H = 210, W = 46, X = 34, TOP = 14;
    var y = function (v) { return TOP + H - (Math.max(0, Math.min(MAX, v)) / MAX) * H; };

    var svg = ['<svg viewBox="0 0 260 250" role="img" aria-label="VIX指数">'];

    bands.forEach(function (band) {
      var top = y(Math.min(band[1], MAX)), bottom = y(band[0]);
      svg.push('<rect x="' + X + '" y="' + top + '" width="' + W +
               '" height="' + (bottom - top) + '" fill="' + band[3] + '" opacity="0.85"/>');
    });
    svg.push('<rect x="' + X + '" y="' + TOP + '" width="' + W + '" height="' + H +
             '" fill="none" stroke="' + COLORS.flat + '" stroke-width="1"/>');

    for (var v = 0; v <= MAX; v += 10) {
      svg.push('<text x="' + (X - 8) + '" y="' + y(v) + '" text-anchor="end" ' +
               'dominant-baseline="middle" font-size="11" fill="' + fontColor() +
               '" opacity="0.7">' + v + '</text>');
    }

    var mark = y(vix.value);
    svg.push('<line x1="' + (X - 6) + '" y1="' + mark + '" x2="' + (X + W + 18) +
             '" y2="' + mark + '" stroke="' + COLORS.flat + '" stroke-width="3"/>');
    svg.push('<polygon points="' + (X + W + 18) + "," + (mark - 6) + " " +
             (X + W + 28) + "," + mark + " " + (X + W + 18) + "," + (mark + 6) +
             '" fill="' + COLORS.flat + '"/>');

    svg.push('<text x="' + (X + W + 34) + '" y="' + (mark - 4) + '" font-size="30" ' +
             'font-weight="700" fill="' + fontColor() + '">' + vix.value_text + '</text>');
    svg.push('<text x="' + (X + W + 34) + '" y="' + (mark + 16) + '" font-size="13" fill="' +
             dirColor(vix.direction) + '">' + escapeText(vix.change_text) + '</text>');
    svg.push('<text x="' + (X + W + 34) + '" y="' + (TOP + H - 2) + '" font-size="15" ' +
             'font-weight="700" fill="' + vix.band_color + '">' +
             escapeText(vix.band_label) + '</text>');
    /* 左の目盛りと重なるので、値と同じ右の列に置く */
    svg.push('<text x="' + (X + W + 34) + '" y="' + (TOP + 10) + '" ' +
             'font-size="12" fill="' + fontColor() + '" opacity="0.6">上ほど警戒</text>');
    svg.push('</svg>');

    host.innerHTML = svg.join("");
  }

  function escapeText(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* ── 各段の組み立て ─────────────────────── */
  function renderRows(rows) {
    var host = document.getElementById("rows");
    var rowTpl = document.getElementById("tpl-row");
    var tileTpl = document.getElementById("tpl-tile");
    var pending = [];

    rows.forEach(function (row) {
      var section = rowTpl.content.cloneNode(true);
      setText(section, ".row__title", row.title);
      var tileHost = section.querySelector(".row__tiles");

      row.tiles.forEach(function (tile) {
        var node = tileTpl.content.cloneNode(true);
        var article = node.querySelector(".tile");
        article.dataset.symbol = tile.symbol;
        article.dataset.direction = String(tile.direction);
        setText(node, ".tile__label", tile.label);
        setText(node, ".tile__price", tile.price_text);
        setText(node, ".tile__change", tile.arrow + " " + tile.change_text);
        setText(node, ".tile__session", tile.session + " のセッション");

        var chart = node.querySelector(".tile__chart");
        chart.id = "chart-tile-" + tile.slug;
        pending.push([chart.id, tile]);
        tileHost.appendChild(node);
      });

      host.appendChild(section);
    });

    pending.forEach(function (item) {
      tileChart(document.getElementById(item[0]), item[1]);
    });
  }

  function renderFund(fund, series) {
    var section = document.getElementById("fund");
    if (!fund) { section.hidden = true; return; }

    bind(section, "fund.nav_text", fund.nav_text);
    bind(section, "fund.date_text", fund.date_text);
    bind(section, "fund.start_date_text", fund.start_date_text);
    bind(section, "fund.change_line", fund.arrow + " " + fund.change_text);
    bind(section, "fund.ytd_text", signed(fund.ytd_pct) + "%");
    bind(section, "fund.from_peak_text", signed(fund.from_peak_pct) + "%");
    bind(section, "fund.peak_text", Math.round(fund.peak).toLocaleString("ja-JP"));

    colorize(section.querySelector('[data-bind="fund.change_line"]'), fund.direction);
    colorize(section.querySelector('[data-bind="fund.ytd_text"]'), sign(fund.ytd_pct));

    if (series && series.values && series.values.length) {
      fundChart(document.getElementById("chart-nav"), series);
    }
  }

  function sign(value) { return value > 0 ? 1 : (value < 0 ? -1 : 0); }

  function signed(value) {
    return (value > 0 ? "+" : "") + value.toFixed(2);
  }

  function colorize(el, direction) {
    if (!el) { return; }
    el.classList.remove("up", "down", "flat");
    el.classList.add(directionClass(direction));
  }

  function renderDrawdown(drawdown) {
    bind(document, "drawdown.title", drawdown.title);
    bind(document, "drawdown.note", drawdown.note);
    drawdownChart(document.getElementById("chart-drawdown"), drawdown);
  }

  function renderFearGreed(fg, bands) {
    var card = document.querySelector(".meter--fg");
    if (!fg) { card.hidden = true; return; }
    bind(document, "fear_greed.note", fg.note);

    var host = document.getElementById("fg-history");
    host.innerHTML = "";
    fg.history.forEach(function (item) {
      var wrap = document.createElement("div");
      wrap.className = "meter__history-item";
      var label = document.createElement("span");
      label.className = "meter__history-label";
      label.textContent = item.label;
      var value = document.createElement("span");
      value.className = "meter__history-value";
      value.textContent = item.value == null ? "—" : Math.round(item.value);
      wrap.appendChild(label);
      wrap.appendChild(value);
      host.appendChild(wrap);
    });

    fgGauge(document.getElementById("chart-fg"), fg, bands);
  }

  function renderVix(vix, bands) {
    var card = document.querySelector(".meter--vix");
    if (!vix) { card.hidden = true; return; }
    bind(document, "vix.note", vix.note);
    vixMeter(document.getElementById("chart-vix"), vix, bands);
  }

  function renderFooter(sources, disclaimer) {
    var host = document.getElementById("sources");
    host.innerHTML = "";
    sources.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      host.appendChild(li);
    });
    bind(document, "disclaimer", disclaimer);
  }

  /* ── 起動 ───────────────────────────────── */
  var payload = null;

  function render(data) {
    payload = data;
    bind(document, "title", data.title);
    bind(document, "generated_at_text", data.generated_at_text);
    bind(document, "fund_chart_title", data.fund_chart_title);
    var time = document.querySelector("time[data-bind]");
    if (time) { time.dateTime = data.generated_at; }

    var bands = data.bands || {};
    renderRows(data.rows);
    renderFund(data.fund, data.fund_series);
    renderDrawdown(data.drawdown);
    renderFearGreed(data.fear_greed, bands.fear_greed || []);
    renderVix(data.vix, bands.vix || []);
    renderFooter(data.sources, data.disclaimer);
  }

  function fail(message) {
    var el = document.getElementById("error");
    el.hidden = false;
    el.textContent = "データを読み込めませんでした: " + message;
  }

  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (res) {
      if (!res.ok) { throw new Error(res.status + " " + res.statusText); }
      return res.json();
    })
    .then(render)
    .catch(function (e) { fail(e.message); });

})();
