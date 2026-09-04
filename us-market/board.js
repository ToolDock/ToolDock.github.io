/* 昨日の米国株 ── market.json を読んでページを組み立てる。
 *
 * チャートは Chart.js（/js/vendor/chart.umd.min.js）で描く。
 * market.json に入っているのは数値と系列だけで、図の定義は持たない。
 *
 * 折れ線3種（タイルの値動き・円建てS&P500・ドローダウン）は Chart.js。
 * Fear & Greed のメーターと VIX のメーターは図形なので、
 * Chart.js を曲げるより素のSVGで描くほうが短く正確になる。
 * 触るとしたら COLORS（色）と、各 render〜()（文言・並び）で足りるようにしてある。
 */
(function () {
  "use strict";

  var DATA_URL = "./market.json";

  var COLORS = {
    up: "#15803d",
    down: "#b91c1c",
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

  /* タイルのチャートだけは期間の切り替えで作り直すので、
     別に持っておいて古いものを破棄する。放っておくと Chart.js 側に残る */
  var tileCharts = [];

  function clearTileCharts() {
    tileCharts.forEach(function (chart) { chart.destroy(); });
    tileCharts = [];
  }

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

  /* ── 1・2段目：タイルの値動き ───────────────── */

  /* 表示期間。8枚まとめて切り替える。
     1日だけ5分足（times / values）、あとは日足（daily）と週足（weekly）を切って使う */
  var RANGES = [
    { key: "1d",  label: "1日",   series: null,     origin: "前日終値" },
    { key: "1m",  label: "1ヶ月", series: "daily",  origin: "1ヶ月前" },
    { key: "ytd", label: "年初来", series: "daily",  origin: "昨年末" },
    { key: "1y",  label: "1年",   series: "daily",  origin: "1年前" },
    { key: "5y",  label: "5年",   series: "weekly", origin: "5年前" }
  ];

  var range = "1d";

  function rangeDef(key) {
    for (var i = 0; i < RANGES.length; i++) {
      if (RANGES[i].key === key) { return RANGES[i]; }
    }
    return RANGES[0];
  }

  /* その期間の起点となる日付（これ以降を描く） */
  function cutoff(key, lastDate) {
    if (key === "ytd") { return lastDate.slice(0, 4) + "-01-01"; }
    if (key === "5y")  { return ""; }          /* 持っているぶん全部 */
    var d = new Date(lastDate + "T00:00:00Z");
    if (key === "1m") { d.setUTCMonth(d.getUTCMonth() - 1); }
    if (key === "1y") { d.setUTCFullYear(d.getUTCFullYear() - 1); }
    return d.toISOString().slice(0, 10);
  }

  /* 期間ぶんの系列と、比較の起点。
     起点は「期間に入る直前の終値」。無ければ期間の最初の値を使う */
  function viewOf(tile, key) {
    if (key === "1d") {
      return {
        labels: tile.times || [],
        values: tile.values || [],
        base: tile.prev_close,
        last: tile.price,
        span: tile.session + " のセッション"
      };
    }

    var series = tile[rangeDef(key).series];
    if (!series || !series.dates || series.dates.length < 2) { return null; }

    var dates = series.dates;
    var from = cutoff(key, dates[dates.length - 1]);
    var i = 0;
    while (i < dates.length && dates[i] < from) { i++; }
    if (dates.length - i < 2) { return null; }

    return {
      labels: dates.slice(i),
      values: series.values.slice(i),
      base: i > 0 ? series.values[i - 1] : series.values[i],
      last: series.values[series.values.length - 1],
      span: dates[i] + " 〜 " + dates[dates.length - 1]
    };
  }

  /* 騰落の文字列。期間で起点が変わるので、サーバー側の change_text は使えない */
  function changeOf(tile, view) {
    if (!view || view.base == null || view.last == null) {
      return { text: "—", direction: 0, arrow: "―" };
    }
    var diff = view.last - view.base;
    var pct = view.base ? diff / view.base * 100 : null;
    var dir = diff > 0 ? 1 : (diff < 0 ? -1 : 0);
    var text = tile.change_mode === "bp"
      ? signedFmt(diff * 100, 1) + "bp（" + signed(pct) + "%）"
      : signedFmt(diff, tile.digits) + "（" + signed(pct) + "%）";
    return { text: text, direction: dir, arrow: dir > 0 ? "▲" : (dir < 0 ? "▼" : "―") };
  }

  /* 横軸の目盛り。図が大きくなったぶん、どこがいつなのかが要る。

     Chart.js の autoSkip は「何点おき」で間引くので、日付を年や月に
     まるめると同じ文字が2つ並ぶ（5年で「2025 2025」など）。
     区切りが変わった最初の点にだけ文字を置き、あとは空にする。 */
  function axisTicks(labels, key) {
    var out = [];
    var seen = null;

    labels.forEach(function (label) {
      var unit = null;
      var text = null;

      if (typeof label === "string" && label.length === 10) {
        if (key === "5y") {
          unit = label.slice(0, 4);                       /* 年ごと */
          text = unit;
        } else if (key === "1m") {
          /* 週ごと。+3 は、エポックの起点が木曜なので月曜区切りに寄せるため */
          unit = Math.floor(Date.parse(label + "T00:00:00Z") / 86400000 / 7 + 3 / 7);
          text = Number(label.slice(5, 7)) + "/" + Number(label.slice(8, 10));
        } else {
          unit = label.slice(0, 7);                        /* 月ごと */
          text = Number(label.slice(5, 7)) + "月";
        }
      }

      if (unit !== null && unit !== seen) {
        seen = unit;
        out.push(text);
      } else {
        out.push("");
      }
    });

    return out;
  }

  function tileChart(host, tile, view) {
    var color = dirColor(view.direction);
    var base = view.base;
    var values = view.values || [];
    var datasets = [];

    /* 起点の基準線。塗りつぶしの相手にもなる */
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

    /* 1日は "HH:MM" で重複しないので、素直に間引かせる。
       日付の期間だけ、こちらで目盛りの位置を決める */
    var ticks = { color: fontColor(), font: { size: 10 }, maxRotation: 0 };
    if (range === "1d") {
      ticks.autoSkip = true;
      ticks.maxTicksLimit = 7;
    } else {
      var marks = axisTicks(view.labels || [], range);
      ticks.autoSkip = false;
      ticks.callback = function (value, index) { return marks[index] || ""; };
    }

    var chart = makeChart(host, {
      type: "line",
      data: { labels: view.labels || [], datasets: datasets },
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
          x: {
            display: true,
            grid: { display: false },
            border: { display: false },
            ticks: ticks
          },
          y: { display: false, min: low - pad, max: high + pad }
        }
      }
    });

    if (chart) { tileCharts.push(chart); }
  }

  /* ── 3段目：円建てS&P500の年初来（年初＝100） ── */
  function yenSpxChart(host, series) {
    /* 値は年初からの騰落率（%）。0が年初 */
    var values = series.values;
    var color = values[values.length - 1] >= 0 ? COLORS.up : COLORS.down;
    var low = Math.min.apply(null, values.concat([0]));
    var high = Math.max.apply(null, values.concat([0]));
    var pad = (high - low) * 0.12 || 1;

    /* 端をそのまま渡すと目盛りに「13.185%」と生の値が出るので、
       5%きざみまで外側に丸める */
    var step = 5;
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
          /* 0（年初）を境に塗る。上げている区間と下げている区間が分かれる */
          fill: { target: { value: 0 },
                  above: rgba(COLORS.up, 0.14), below: rgba(COLORS.down, 0.14) },
          backgroundColor: rgba(color, 0.12)
        }]
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (item) { return signed(item.parsed.y) + "%"; }
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
              /* 5%きざみなので小数は出さない */
              callback: function (v) { return (v > 0 ? "+" : "") + v + "%"; }
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

  /* ── Fear & Greed のメーター ──────────────────

     CNN の本家に寄せた作り。
     外側に5つの区分を扇形で並べ、いま該当する区分だけ色を敷く。
     内側に0〜100の目盛りを置き、中心から太い針を出す。

     Chart.js の doughnut では扇形ごとのラベルや目盛りが作れないので、
     SVGを直接書いている。 */

  var FG = {
    span: 200,      /* 開き角（度） */
    rOut: 118,      /* 区分の外側 */
    rIn: 84,        /* 区分の内側 */
    rNum: 72,       /* 目盛りの数字 */
    rTick: 62,      /* 目盛りの線 */
    gap: 1.2        /* 区分どうしの隙間（度） */
  };

  function polar(deg, radius) {
    var t = deg * Math.PI / 180;
    return [
      (radius * Math.sin(t)).toFixed(2),
      (-radius * Math.cos(t)).toFixed(2)
    ];
  }

  function fgAngle(value) {
    var v = Math.max(0, Math.min(100, value));
    return (v / 100 - 0.5) * FG.span;
  }

  /* 扇形（外周の円弧 → 内周の円弧 で閉じる） */
  function wedge(fromDeg, toDeg, rOut, rIn) {
    var large = (toDeg - fromDeg) > 180 ? 1 : 0;
    return "M" + polar(fromDeg, rOut) +
           "A" + rOut + "," + rOut + " 0 " + large + " 1 " + polar(toDeg, rOut) +
           "L" + polar(toDeg, rIn) +
           "A" + rIn + "," + rIn + " 0 " + large + " 0 " + polar(fromDeg, rIn) + "Z";
  }

  function fgMeter(host, fg, bands) {
    if (!host) { return; }

    /* 扇の外側までちょうど収まる箱。余白を取ると、
       器の幅いっぱいに広げてもメーターが小さく見える */
    var svg = ['<svg viewBox="-121 -123 242 149" role="img" ' +
               'aria-label="Fear and Greed Index ' + fg.value_text + ' ' + fg.label_ja + '">'];

    bands.forEach(function (band) {
      var from = fgAngle(band[0]) + FG.gap;
      var to = fgAngle(band[1]) - FG.gap;
      var active = fg.value >= band[0] && fg.value <= band[1];

      svg.push('<path d="' + wedge(from, to, FG.rOut, FG.rIn) + '" fill="' +
               (active ? tint(band[4], 0.22) : "#f1f3f5") + '" stroke="' +
               (active ? band[4] : "#e3e6ea") + '" stroke-width="' +
               (active ? 1.6 : 1) + '"/>');

      /* 区分の名前。扇の真ん中に、円弧に沿って寝かせる */
      var mid = (from + to) / 2;
      var p = polar(mid, (FG.rOut + FG.rIn) / 2);

      /* 「極度の恐怖」は寝かせると読みにくいので2行に折る */
      var text = band[3];
      var lines = text.length >= 5 ? [text.slice(0, 3), text.slice(3)] : [text];
      var spans = lines.map(function (line, i) {
        return '<tspan x="' + p[0] + '" dy="' +
               (i === 0 ? (lines.length > 1 ? -6 : 0) : 12) + '">' +
               escapeText(line) + '</tspan>';
      }).join("");

      svg.push('<text x="' + p[0] + '" y="' + p[1] + '" text-anchor="middle" ' +
               'dominant-baseline="central" font-size="10.5" font-weight="700" ' +
               'letter-spacing="0.04em" fill="' +
               (active ? readableOnWhite(band[4]) : "#8b9298") + '" ' +
               'transform="rotate(' + mid.toFixed(1) + ' ' + p[0] + ' ' + p[1] + ')">' +
               spans + '</text>');
    });

    /* 内側の目盛り */
    for (var v = 0; v <= 100; v += 25) {
      var t = polar(fgAngle(v), FG.rNum);
      svg.push('<text x="' + t[0] + '" y="' + t[1] + '" text-anchor="middle" ' +
               'dominant-baseline="central" font-size="11" fill="#8b9298">' + v + '</text>');
    }
    for (var d = 0; d <= 100; d += 5) {
      var a = polar(fgAngle(d), FG.rTick), b2 = polar(fgAngle(d), FG.rTick - (d % 25 === 0 ? 7 : 4));
      svg.push('<line x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b2[0] + '" y2="' + b2[1] +
               '" stroke="#c8ced5" stroke-width="' + (d % 25 === 0 ? 2 : 1) + '"/>');
    }

    /* 針。CNNと同じく黒く太い一本。目盛りの手前まで伸ばす */
    var deg = fgAngle(fg.value);
    var tip = polar(deg, FG.rTick - 10);
    svg.push('<line x1="0" y1="0" x2="' + tip[0] + '" y2="' + tip[1] +
             '" stroke="#1f2328" stroke-width="5.5" stroke-linecap="round"/>');
    svg.push('</svg>');

    host.innerHTML = svg.join("");
  }

  /* 帯の色を、白と混ぜて薄くする */
  function tint(hex, alpha) {
    var rgb = [1, 3, 5].map(function (i) {
      return Math.round(parseInt(hex.substr(i, 2), 16) * alpha + 255 * (1 - alpha));
    });
    return "rgb(" + rgb.join(",") + ")";
  }

  /* ── Fear & Greed の1年チャート ─────────────── */
  function fgYearChart(host, data) {
    if (!host || !data) { return; }
    makeChart(host, {
      type: "line",
      data: {
        labels: data.dates,
        datasets: [{
          data: data.values,
          borderColor: "#1d4ed8",
          borderWidth: 1.8,
          pointRadius: 0,
          pointHitRadius: 6,
          fill: false
        }]
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function (i) { return Math.round(i.parsed.y); } } }
        },
        scales: {
          x: monthAxis(data.dates),
          y: {
            min: 0, max: 100,
            grid: { color: COLORS.grid },
            border: { display: false },
            ticks: { color: fontColor(), stepSize: 25 }
          }
        }
      }
    });
  }

  /* ── VIX と S&P500 を重ねた1年チャート ────────── */
  function vixYearChart(host, data) {
    if (!host || !data) { return; }
    makeChart(host, {
      type: "line",
      data: {
        labels: data.dates,
        datasets: [
          { label: "VIX", data: data.vix, yAxisID: "y",
            borderColor: "#1f2328", borderWidth: 1.8, pointRadius: 0, pointHitRadius: 6,
            fill: false },
          { label: "S&P500", data: data.sp500, yAxisID: "y1",
            borderColor: "#c98a3a", borderWidth: 1.8, pointRadius: 0, pointHitRadius: 6,
            fill: false }
        ]
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, align: "end",
                    labels: { color: fontColor(), boxWidth: 18, usePointStyle: false } },
          tooltip: {
            callbacks: {
              label: function (i) {
                return i.dataset.label + " " + fmt(i.parsed.y, i.datasetIndex === 0 ? 2 : 0);
              }
            }
          }
        },
        scales: {
          x: monthAxis(data.dates),
          y: {
            position: "left",
            grid: { color: COLORS.grid },
            border: { display: false },
            ticks: { color: fontColor() },
            title: { display: true, text: "VIX", color: fontColor() }
          },
          y1: {
            position: "right",
            grid: { drawOnChartArea: false },
            border: { display: false },
            ticks: { color: fontColor(), callback: function (v) { return fmt(v, 0); } },
            title: { display: true, text: "S&P500", color: fontColor() }
          }
        }
      }
    });
  }

  /* 月が変わる最初の日だけ「◯月」と出す横軸 */
  function monthAxis(dates) {
    var seen = {};
    var labels = dates.map(function (d) {
      var m = Number(d.slice(5, 7));
      if (seen[m]) { return ""; }
      seen[m] = true;
      return m + "月";
    });

    /* 1年ぶんだと先頭の月が数日しかないことがあり、
       次の月のラベルと重なって潰れる。短すぎる先頭は出さない */
    var first = labels.findIndex(function (l) { return l; });
    var second = labels.findIndex(function (l, i) { return l && i > first; });
    if (first >= 0 && second > 0 && second - first < 8) { labels[first] = ""; }
    return {
      grid: { display: false },
      border: { color: COLORS.grid },
      ticks: {
        color: fontColor(), autoSkip: false, maxRotation: 0,
        callback: function (_v, i) { return labels[i]; }
      }
    };
  }

  /* ── ヒートマップ ────────────────────────────

     面積が時価総額の比、色がその日の騰落率。
     まずセクターを敷き詰め、その中で銘柄を敷き詰める2段構え。

     並べ方は squarified treemap。単純に横一列に切ると、
     ウェイトの小さい銘柄が細長い帯になって名前が読めなくなる。 */

  /* 与えられた矩形に、値の比で長方形を敷き詰める */
  function squarify(values, rect) {
    var total = values.reduce(function (a, b) { return a + b.value; }, 0);
    if (!total) { return []; }

    var items = values.slice();
    var out = [];
    var x = rect.x, y = rect.y, w = rect.w, h = rect.h;
    var scale = (w * h) / total;

    function worst(row, side) {
      var sum = row.reduce(function (a, b) { return a + b; }, 0);
      var max = Math.max.apply(null, row), min = Math.min.apply(null, row);
      var s2 = sum * sum, side2 = side * side;
      return Math.max(side2 * max / s2, s2 / (side2 * min));
    }

    while (items.length) {
      var side = Math.min(w, h);
      var row = [items[0]];
      var areas = [items[0].value * scale];

      while (items.length > row.length) {
        var next = items[row.length].value * scale;
        if (worst(areas.concat([next]), side) > worst(areas, side)) { break; }
        row.push(items[row.length]);
        areas.push(next);
      }

      var rowArea = areas.reduce(function (a, b) { return a + b; }, 0);
      var thick = rowArea / side;
      var pos = 0;

      row.forEach(function (item, i) {
        var len = areas[i] / thick;
        out.push(w >= h
          ? { item: item, x: x, y: y + pos, w: thick, h: len }
          : { item: item, x: x + pos, y: y, w: len, h: thick });
        pos += len;
      });

      if (w >= h) { x += thick; w -= thick; } else { y += thick; h -= thick; }
      items = items.slice(row.length);
    }
    return out;
  }

  /* 騰落率を色に直す。±3%で振り切る。
     中央は無彩色にして、白い文字が乗る濃さにそろえてある */
  var HEAT_LIMIT = 2.5;

  function heatColor(pct) {
    var t = Math.min(Math.abs(pct) / HEAT_LIMIT, 1);
    /* 中央は青みのない灰色。青が入ると赤の隣で紫に見える */
    var mid = [117, 120, 122];
    var end = pct >= 0 ? [21, 128, 61] : [185, 28, 28];
    return "rgb(" + mid.map(function (v, i) {
      return Math.round(v + (end[i] - v) * t);
    }).join(",") + ")";
  }

  function renderHeatmap(data) {
    var section = document.getElementById("heatmap");
    if (!data) { section.hidden = true; return; }

    bind(document, "heatmap.title", data.title);
    bind(document, "heatmap.note", data.note);

    var summary = document.getElementById("heat-summary");
    summary.textContent = data.session + " のセッション　" +
      data.count + "銘柄中 " + data.up + "銘柄が上げ、" + data.down + "銘柄が下げ";

    var host = document.getElementById("heat");
    host.innerHTML = "";

    /* 高さは幅から決める。横長すぎても縦長すぎても読みにくい */
    var width = host.clientWidth || 860;
    var height = Math.round(Math.max(400, Math.min(620, width * 0.70)));
    host.style.height = height + "px";

    var boxes = squarify(
      data.sectors.map(function (s) { return { value: s.weight, sector: s }; }),
      { x: 0, y: 0, w: width, h: height });

    boxes.forEach(function (box) {
      var sector = box.item.sector;
      var group = document.createElement("div");
      group.className = "heat__sector";
      group.style.cssText = "left:" + box.x + "px;top:" + box.y + "px;" +
                            "width:" + box.w + "px;height:" + box.h + "px;";

      /* 背の低いセクターに名前を載せると、タイルの取り分が無くなる */
      var showName = box.h >= 46;
      if (showName) {
        var head = document.createElement("div");
        head.className = "heat__sector-name";
        head.textContent = sector.name;
        group.appendChild(head);
      } else {
        group.title = sector.name;
      }

      var top = showName ? 16 : 0;
      var inner = { x: 0, y: top, w: box.w - 2, h: box.h - top - 2 };
      squarify(sector.items.map(function (it) {
        return { value: it.weight, stock: it };
      }), inner).forEach(function (cell) {
        var it = cell.item.stock;
        var tile = document.createElement("div");
        tile.className = "heat__tile";
        tile.style.cssText = "left:" + cell.x + "px;top:" + cell.y + "px;" +
          "width:" + cell.w + "px;height:" + cell.h + "px;" +
          "background:" + heatColor(it.change_pct) + ";";
        tile.title = (it.name_ja ? it.name_ja + " " : "") +
          it.name + "（" + it.symbol + "）" + it.change_text;

        /* 狭いタイルに文字を詰めると潰れるので、入る場合だけ出す。
           上から順に、日本語名 → ティッカー → 騰落率。
           日本語名はいちばん場所を取るので、大きいタイルにだけ出す。
           AMD や IBM のように日本語でもその表記のままのものは
           name_ja が空なので、ティッカーだけになる */
        if (it.name_ja && cell.w >= 84 && cell.h >= 62) {
          var ja = document.createElement("span");
          ja.className = "heat__ja";
          ja.textContent = it.name_ja;
          tile.appendChild(ja);
        }
        if (cell.w >= 46 && cell.h >= 30) {
          var sym = document.createElement("span");
          sym.className = "heat__symbol";
          sym.textContent = it.symbol;
          tile.appendChild(sym);
        }
        if (cell.w >= 56 && cell.h >= 44) {
          var chg = document.createElement("span");
          chg.className = "heat__change";
          chg.textContent = it.change_text;
          tile.appendChild(chg);
        }
        group.appendChild(tile);
      });

      host.appendChild(group);
    });
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

    /* 期間を切り替えるたびにここへ戻ってくる。前回のぶんを片づけてから組み直す */
    clearTileCharts();
    host.innerHTML = "";

    rows.forEach(function (row) {
      var section = rowTpl.content.cloneNode(true);
      setText(section, ".row__title", row.title);
      var tileHost = section.querySelector(".row__tiles");

      row.tiles.forEach(function (tile) {
        var view = viewOf(tile, range);
        var move = changeOf(tile, view);
        var node = tileTpl.content.cloneNode(true);
        var article = node.querySelector(".tile");

        article.dataset.symbol = tile.symbol;
        article.dataset.direction = String(move.direction);
        setText(node, ".tile__label", tile.label);
        setText(node, ".tile__price", tile.price_text);
        setText(node, ".tile__change", move.arrow + " " + move.text);
        setText(node, ".tile__session",
                view ? view.span : "この期間のデータは取得できていません");

        var chart = node.querySelector(".tile__chart");
        chart.id = "chart-tile-" + tile.slug;
        if (view) {
          view.direction = move.direction;
          pending.push([chart.id, tile, view]);
        } else {
          chart.hidden = true;
        }
        tileHost.appendChild(node);
      });

      host.appendChild(section);
    });

    pending.forEach(function (item) {
      tileChart(document.getElementById(item[0]), item[1], item[2]);
    });
  }

  /* 期間のボタン。データを持っていない期間は出さない
     （更新が一度も回っていないうちは daily / weekly がまだ無い） */
  function renderRanges(rows) {
    var host = document.getElementById("ranges");
    if (!host) { return; }

    var usable = RANGES.filter(function (def) {
      if (!def.series) { return true; }
      return rows.some(function (row) {
        return row.tiles.some(function (tile) { return tile[def.series]; });
      });
    });

    if (usable.length < 2) { host.hidden = true; return; }

    host.innerHTML = "";
    usable.forEach(function (def) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "range";
      button.dataset.range = def.key;
      button.textContent = def.label;
      button.setAttribute("aria-pressed", String(def.key === range));
      button.addEventListener("click", function () {
        if (range === def.key) { return; }
        range = def.key;
        [].forEach.call(host.querySelectorAll(".range"), function (other) {
          other.setAttribute("aria-pressed", String(other.dataset.range === range));
        });
        renderRows(rows);
      });
      host.appendChild(button);
    });
  }

  function renderYenSpx(data, series) {
    var section = document.getElementById("yenspx");
    if (!data) { section.hidden = true; return; }

    bind(section, "yenspx.date_text", data.date_text);
    bind(section, "yenspx.start_date_text", data.start_date_text);
    bind(section, "yenspx.ytd_text", data.ytd_text);
    bind(section, "yenspx.from_peak_text", data.from_peak_text);
    bind(section, "yenspx.parts_stock", data.parts ? data.parts.stock_text : "—");
    bind(section, "yenspx.parts_fx", data.parts ? data.parts.fx_text : "");
    bind(section, "yenspx.note", data.note);

    colorize(section.querySelector('[data-bind="yenspx.ytd_text"]'), sign(data.ytd_pct));

    if (series && series.values && series.values.length) {
      yenSpxChart(document.getElementById("chart-yenspx"), series);
    }
  }

  function sign(value) { return value > 0 ? 1 : (value < 0 ? -1 : 0); }

  function signed(value) {
    return (value > 0 ? "+" : "") + value.toFixed(2);
  }

  /* 符号つき・桁指定つき。Python側の f"{x:+,.{digits}f}" と同じ見た目にする */
  function signedFmt(value, digits) {
    return (value >= 0 ? "+" : "") + fmt(value, digits);
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

  /* ── S&P500の月ごとの騰落 ─────────────────── */
  function renderMonthly(data) {
    var section = document.getElementById("monthly");
    if (!data || !data.rows.length) { section.hidden = true; return; }

    bind(document, "sp500_monthly.title", data.title);
    bind(document, "sp500_monthly.note", data.note);
    bind(document, "sp500_monthly.summary", data.summary);

    var body = document.querySelector("#monthly-table tbody");
    body.innerHTML = "";
    var lastYear = null;

    data.rows.forEach(function (r) {
      var tr = document.createElement("tr");

      /* 年が変わるところだけ「2025年」と出す。毎行に年を書くと読みにくい */
      var label = (r.year !== lastYear ? r.year + "年 " : "") + r.label;
      lastYear = r.year;

      var cells = [
        { text: label + (r.partial ? "（途中）" : ""), cls: "monthly__label" },
        { text: r.close_text, cls: "monthly__num" },
        { text: r.diff_text, cls: "monthly__num " + directionClass(r.direction) },
        { text: r.pct_text, cls: "monthly__num " + directionClass(r.direction) }
      ];
      cells.forEach(function (c) {
        var td = document.createElement("td");
        td.className = c.cls;
        td.textContent = c.text;
        tr.appendChild(td);
      });
      tr.title = r.date + " の終値";
      body.appendChild(tr);
    });
  }

  function renderFearGreed(fg, bands, chart) {
    var section = document.getElementById("fear-greed");
    if (!fg) { section.hidden = true; return; }
    bind(document, "fear_greed.note", fg.note);
    bind(document, "fear_greed.value_text", fg.value_text);
    bind(document, "fear_greed.label", fg.label_ja + "（" + fg.label_en + "）");
    paint('[data-bind="fear_greed.label"]', fg.color);

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

    fgMeter(document.getElementById("chart-fg"), fg, bands);

    /* 1年ぶんの履歴がまだ無いときは、空の枠を残さない */
    var chartHost = document.getElementById("chart-fg-year");
    if (chart) {
      fgYearChart(chartHost, chart);
    } else {
      chartHost.hidden = true;
      section.querySelector(".fg").style.gridTemplateColumns = "1fr";
    }
  }

  function renderVix(vix, chart) {
    var section = document.getElementById("vix");
    if (!vix) { section.hidden = true; return; }
    bind(document, "vix.note", vix.note);
    bind(document, "vix.value_text", vix.value_text);
    bind(document, "vix.change_text", vix.change_text);
    bind(document, "vix.band_label", vix.band_label);
    paint('[data-bind="vix.band_label"]', vix.band_color);
    colorize(document.querySelector('[data-bind="vix.change_text"]'), vix.direction);

    /* 1年ぶんの日足がまだ無いときは、この節ごと出さない */
    if (!chart) { section.hidden = true; return; }
    vixYearChart(document.getElementById("chart-vix"), chart);
  }

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

  /* バンドの色は円弧や扇に敷くためのもので、文字にすると薄い。
     色みは保ったまま、白地で読める濃さ（4.5:1）まで落とす */
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
    bind(document, "session_text", data.session_text);
    bind(document, "generated_at_text", data.generated_at_text);
    bind(document, "yenspx_chart_title", data.yenspx_chart_title);

    var updated = document.querySelector('time[data-bind="generated_at_text"]');
    if (updated) { updated.dateTime = data.generated_at; }
    var session = document.querySelector('time[data-bind="session_text"]');
    if (session) { session.dateTime = data.session || ""; }
    /* 取引日が取れていないときは、行ごと出さない */
    var sessionLine = document.querySelector(".board__session");
    if (sessionLine) { sessionLine.hidden = !data.session_text; }

    var bands = data.bands || {};
    renderRanges(data.rows);
    renderRows(data.rows);
    renderHeatmap(data.heatmap);
    renderYenSpx(data.yenspx, data.yenspx_series);
    renderDrawdown(data.drawdown);
    renderMonthly(data.sp500_monthly);
    renderFearGreed(data.fear_greed, bands.fear_greed || [], data.fg_chart);
    renderVix(data.vix, data.vix_chart);
    renderFooter(data.sources, data.disclaimer);

    /* ヒートマップは器の幅から寸法を決めるので、幅が変わったら組み直す */
    if (window.ResizeObserver) {
      var host = document.getElementById("heat");
      var last = host ? host.clientWidth : 0;
      new ResizeObserver(function () {
        if (!host || Math.abs(host.clientWidth - last) < 8) { return; }
        last = host.clientWidth;
        renderHeatmap(data.heatmap);
      }).observe(document.body);
    }
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
