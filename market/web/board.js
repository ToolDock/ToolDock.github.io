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

  /* ── 5段目：メーター（Fear & Greed と VIX で共通） ────

     どちらも「0〜最大のどこにいるか」を示すだけなので、同じ形にする。
     片方が円弧、片方が縦棒だと、並べたときに不揃いに見える。

     Chart.js の doughnut を曲げて針を足すより、SVGを直接書くほうが短い。 */

  var GAUGE = {
    span: 120,        /* 開き角（度） */
    r: 96,            /* 円弧の半径 */
    width: 15,        /* 円弧の太さ */
    gap: 1.6,         /* バンドどうしの隙間（度） */
    needle: "#6b7280" /* 針。無彩色にして、色はバンドだけに持たせる */
  };

  function polar(deg, radius) {
    var t = deg * Math.PI / 180;
    return [
      (radius * Math.sin(t)).toFixed(2),
      (-radius * Math.cos(t)).toFixed(2)
    ];
  }

  /* 値を、メーターの中心からの角度（度）に直す */
  function gaugeAngle(value, min, max) {
    var v = Math.max(min, Math.min(max, value));
    return ((v - min) / (max - min) - 0.5) * GAUGE.span;
  }

  function bandArc(fromDeg, toDeg, color) {
    var a = polar(fromDeg, GAUGE.r), b = polar(toDeg, GAUGE.r);
    return '<path d="M' + a + 'A' + GAUGE.r + ',' + GAUGE.r + ' 0 0 1 ' + b +
           '" fill="none" stroke="' + color + '" stroke-width="' + GAUGE.width +
           '" stroke-linecap="round"/>';
  }

  /* bands は [{from, to, color}] に正規化してから渡す */
  function gauge(host, opts) {
    if (!host) { return; }

    var min = opts.min, max = opts.max;
    /* 目盛りの文字まで入る最小の箱にしてある。
       余白を広く取ると、下の数字との間が間延びする */
    var svg = ['<svg viewBox="-116 -124 232 132" role="img" aria-label="' +
               escapeText(opts.label) + '">'];

    opts.bands.forEach(function (band) {
      var a = gaugeAngle(band.from, min, max) + GAUGE.gap;
      var b = gaugeAngle(band.to, min, max) - GAUGE.gap;
      if (b > a) { svg.push(bandArc(a, b, band.color)); }
    });

    /* 針。細い二等辺三角形にして、根元に小さな軸を置く */
    var deg = gaugeAngle(opts.value, min, max);
    var tip = polar(deg, GAUGE.r - GAUGE.width / 2 - 10);
    var left = polar(deg - 90, 3);
    var right = polar(deg + 90, 3);
    svg.push('<polygon points="' + [tip, left, right].join(" ") +
             '" fill="' + GAUGE.needle + '"/>');
    svg.push('<circle cx="0" cy="0" r="6" fill="' + GAUGE.needle + '"/>');
    svg.push('<circle cx="0" cy="0" r="2.4" fill="#ffffff"/>');

    (opts.ticks || []).forEach(function (tick) {
      var p = polar(gaugeAngle(tick, min, max), GAUGE.r + 20);
      svg.push('<text x="' + p[0] + '" y="' + p[1] + '" text-anchor="middle" ' +
               'dominant-baseline="middle" font-size="11.5" fill="' + fontColor() +
               '" opacity="0.6">' + tick + '</text>');
    });

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

    gauge(document.getElementById("chart-fg"), {
      label: "Fear and Greed Index",
      value: fg.value, min: 0, max: 100, ticks: [0, 50, 100],
      bands: bands.map(function (b) {
        return { from: b[0], to: b[1], color: b[4] };
      })
    });

    bind(document, "fear_greed.value_text", fg.value_text);
    bind(document, "fear_greed.label", fg.label_ja + "（" + fg.label_en + "）");
    paint('[data-bind="fear_greed.label"]', fg.color);
  }

  function renderVix(vix, bands) {
    var card = document.querySelector(".meter--vix");
    if (!vix) { card.hidden = true; return; }
    bind(document, "vix.note", vix.note);
    gauge(document.getElementById("chart-vix"), {
      label: "VIX指数",
      value: vix.value, min: 0, max: 50, ticks: [0, 25, 50],
      bands: bands.map(function (b) {
        return { from: b[0], to: b[1], color: b[3] };
      })
    });

    bind(document, "vix.value_text", vix.value_text);
    bind(document, "vix.change_text", vix.change_text);
    bind(document, "vix.band_label", vix.band_label);
    paint('[data-bind="vix.band_label"]', vix.band_color);
    colorize(document.querySelector('[data-bind="vix.change_text"]'), vix.direction);
  }

  /* 区分のラベルに、そのバンドの色を付ける。

     ただしバンドの色は円弧に敷くためのもので、文字にすると薄い。
     たとえば中立の金色は白地でコントラストが2.5:1しかなく、
     文字として読めない（WCAG AA は 4.5:1）。
     円弧の色はそのままに、文字だけ読める濃さまで落とす */
  function paint(selector, color) {
    var el = document.querySelector(selector);
    if (el) { el.style.color = readableOnWhite(color); }
  }

  function luminance(rgb) {
    var a = rgb.map(function (v) {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  }

  function readableOnWhite(hex, target) {
    target = target || 4.5;
    var rgb = [1, 3, 5].map(function (i) { return parseInt(hex.substr(i, 2), 16); });
    for (var i = 0; i < 24; i++) {
      if (1.05 / (luminance(rgb) + 0.05) >= target) { break; }
      rgb = rgb.map(function (v) { return Math.round(v * 0.92); });
    }
    return "#" + rgb.map(function (v) {
      return ("0" + v.toString(16)).slice(-2);
    }).join("");
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
