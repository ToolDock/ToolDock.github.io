// 順位推移グラフ（npb/build_standings.py が書き出す）。
// ページに埋め込んだ日ごとの試合結果から、球団ごとの貯金の線を描き、▶で開幕から動かす
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var data = JSON.parse(document.getElementById("standings-data").textContent);
  var days = data.days, D = days.length;

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  // 球団ごとに、日ごとの 勝・敗・分・連勝(+)/連敗(-) を積み上げる（引き分けは連勝・連敗を止めない）
  function walk(results) {
    var w = 0, l = 0, t = 0, s = 0, out = [];
    results.forEach(function (day) {
      for (var i = 0; i < day.length; i++) {
        var r = day[i];
        if (r === "W") { w++; s = s > 0 ? s + 1 : 1; }
        else if (r === "L") { l++; s = s < 0 ? s - 1 : -1; }
        else t++;
      }
      out.push([w, l, t, s]);
    });
    return out;
  }
  function pct(w, l) { return w + l ? w / (w + l) : 0; }
  function signed(n) { return n > 0 ? "+" + n : String(n); }
  function streakText(s) { return s >= 2 ? s + "連勝" : s <= -2 ? (-s) + "連敗" : ""; }
  function jdate(d) { var p = d.split("-"); return (+p[1]) + "月" + (+p[2]) + "日"; }

  // 描く大きさは、表示される幅に合わせる（1単位＝1px。スマホでも文字が小さくならない）。
  // 縦横の比は standings.css の .chart の aspect-ratio と同じにする
  var charts = [];
  var teamsByLg = {};
  Object.keys(data.lg).forEach(function (key) {
    teamsByLg[key] = data.lg[key].map(function (t) {
      var v = walk(t.r), first = 0;
      while (first < D - 1 && v[first][0] + v[first][1] + v[first][2] === 0) first++;
      // 線は開幕の前の日（貯金0）から引く。リーグによって開幕の日が違う年がある
      return { n: t.n, c: t.c, k: t.k, v: v, start: Math.max(0, first - 1) };
    });
  });

  function build() {
    charts = [];
    Object.keys(data.lg).forEach(function (key) {
      var fig = document.querySelector('.chart[data-lg="' + key + '"]');
      if (!fig) return;
      var board = fig.parentNode.querySelector("ol.board");
      var teams = teamsByLg[key];
      var W = Math.max(280, Math.round(fig.clientWidth || 720));
      var narrow = W < 560;
      var H = Math.round(W * (narrow ? 0.95 : 0.6));
      var fs = narrow ? 11 : 12;
      var L = 36, R = narrow ? 92 : 118, T = 12, B = 26;
      // 縦の目盛りは、その日までに出た貯金の幅に合わせて動かす（開幕のころは差が小さいので拡大して見せる）。
      // pmin・pmax は、その日までの全球団の貯金の最小・最大
      var pmin = [], pmax = [], mn = 0, mx = 0;
      for (var d = 0; d < D; d++) {
        teams.forEach(function (t) { if (d >= t.start) { var x = t.v[d][0] - t.v[d][1]; mn = Math.min(mn, x); mx = Math.max(mx, x); } });
        pmin.push(mn); pmax.push(mx);
      }
      var c = { lo: 0, hi: 1, xmax: D - 1, pmin: pmin, pmax: pmax, L: L, R: R, T: T, B: B, W: W, H: H, fs: fs, narrow: narrow };
      // 横は、開幕からその日までを枠いっぱいに使う（試合が進むほど、前の日は横に縮んでいく）
      function X(i) { return L + (c.xmax > 0 ? i / c.xmax : 0) * (W - L - R); }
      function Y(v) { return T + (c.hi - v) / (c.hi - c.lo) * (H - T - B); }

      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": fig.getAttribute("aria-label") });
      // 目盛り（貯金と月の頭）は、縦横の範囲が変わるので描くたびに作り直す
      c.grid = el("g", {});
      svg.appendChild(c.grid);
      c.months = [];
      days.forEach(function (d, i) { var m = d.slice(5, 7); if (!c.months.length || c.months[c.months.length - 1].m !== m) c.months.push({ m: m, i: i }); });
      // 線はグラフの枠の中だけに描く（名前は枠の右にはみ出してよい）
      var clipId = "clip-" + key;
      var defs = el("defs", {}), clip = el("clipPath", { id: clipId });
      clip.appendChild(el("rect", { x: L - 6, y: T - 6, width: W - L - R + 12, height: H - T - B + 12 }));
      defs.appendChild(clip); svg.appendChild(defs);
      var lines = el("g", { "clip-path": "url(#" + clipId + ")" }), labels = el("g", {});
      svg.appendChild(lines); svg.appendChild(labels);
      var parts = teams.map(function (t) {
        var p = { t: t };
        if (t.k) { p.casing = el("polyline", { fill: "none", stroke: t.k, "stroke-width": 4.6, "stroke-linejoin": "round", "stroke-linecap": "round" }); lines.appendChild(p.casing); }
        p.line = el("polyline", { fill: "none", stroke: t.c, "stroke-width": t.k ? 2.4 : 2.6, "stroke-linejoin": "round", "stroke-linecap": "round" });
        lines.appendChild(p.line);
        p.dot = el("circle", { r: 4, fill: t.c, stroke: t.k || "#fff", "stroke-width": 1.5 });
        p.label = el("text", { "font-size": fs, "font-weight": 700, fill: "#1c1d1f" });
        lines.appendChild(p.dot); labels.appendChild(p.label);
        return p;
      });
      fig.textContent = "";
      fig.appendChild(svg);
      c.parts = parts; c.teams = teams; c.board = board; c.X = X; c.Y = Y; c.gap = fs + 1;
      charts.push(c);
    });
  }

  // k（0〜D-1、小数もあり）の日までを描く
  // その日までの貯金の幅 → 見せる縦の範囲。0 は必ず入れ、上下に少し余白をとる。最低でも ±4 は見せる
  function target(c, i) {
    var lo = Math.min(0, c.pmin[i]), hi = Math.max(0, c.pmax[i]);
    var pad = Math.max(1, (hi - lo) * 0.08);
    lo -= pad; hi += pad;
    if (hi - lo < 8) { var mid = (hi + lo) / 2; lo = mid - 4; hi = mid + 4; }
    return [lo, hi];
  }

  function drawGrid(c) {
    c.grid.textContent = "";
    // 月の頭の線と名前。その日までに来た月だけ。名前は、次の月と近すぎるときは出さない
    var shown = c.months.filter(function (mo) { return mo.i <= c.xmax; });
    shown.forEach(function (mo, n) {
      var x = c.X(mo.i);
      c.grid.appendChild(el("line", { x1: x, x2: x, y1: c.T, y2: c.H - c.B, stroke: "#e6e4de" }));
      var next = shown[n + 1];
      var room = (next ? c.X(next.i) : c.W - c.R) - x;
      if (room < (c.narrow ? 26 : 30)) return;
      c.grid.appendChild(el("text", { x: x + 3, y: c.H - c.B + 16, "font-size": c.fs - 1, fill: "#1c1d1f" }, (+mo.m) + "月"));
    });
    var span = c.hi - c.lo, step = [1, 2, 5, 10, 20, 50].find(function (s) { return span / s <= 8; }) || 50;
    for (var v = Math.ceil(c.lo / step) * step; v <= c.hi; v += step) {
      var y = c.Y(v);
      c.grid.appendChild(el("line", { x1: c.L, x2: c.W - c.R, y1: y, y2: y, stroke: v === 0 ? "#1c1d1f" : "#e6e4de", "stroke-width": v === 0 ? 1.2 : 1 }));
      c.grid.appendChild(el("text", { x: c.L - 5, y: y + 4, "text-anchor": "end", "font-size": c.fs - 1, fill: "#1c1d1f" }, v > 0 ? "+" + v : String(v)));
    }
  }

  // dt（秒）があるときは、縦の範囲をなめらかに追いかける。無いとき（最初・つまみを動かしたとき）はすぐ合わせる
  var MIN_DAYS = 7;    // 開幕直後に1日が横いっぱいに広がりすぎないよう、横は最低でも1週間ぶん見せる

  function draw(k, dt) {
    var i = Math.floor(k), f = k - i;
    charts.forEach(function (c) {
      c.xmax = Math.min(D - 1, Math.max(k, MIN_DAYS));
      var tg = target(c, Math.min(D - 1, f > 0 ? i + 1 : i));
      if (dt) {
        var a = Math.min(1, dt * 5);
        c.lo += (tg[0] - c.lo) * a; c.hi += (tg[1] - c.hi) * a;
        // なめらかに追いかけても、描いた線がはみ出すことはないようにする
        var j = Math.min(D - 1, i + 1);
        var visLo = Math.min(0, c.pmin[i] + (c.pmin[j] - c.pmin[i]) * f), visHi = Math.max(0, c.pmax[i] + (c.pmax[j] - c.pmax[i]) * f);
        c.lo = Math.min(c.lo, visLo - 0.5); c.hi = Math.max(c.hi, visHi + 0.5);
      } else {
        c.lo = tg[0]; c.hi = tg[1];
      }
      drawGrid(c);
      var ends = [];
      c.parts.forEach(function (p) {
        var t = p.t, pts = [];
        var shown = i >= t.start;
        p.line.style.display = p.dot.style.display = p.label.style.display = shown ? "" : "none";
        if (p.casing) p.casing.style.display = shown ? "" : "none";
        for (var j = t.start; j <= i; j++) pts.push(c.X(j).toFixed(1) + "," + c.Y(t.v[j][0] - t.v[j][1]).toFixed(1));
        var ex = c.X(i), ey = c.Y(t.v[i][0] - t.v[i][1]);
        if (f > 0 && i + 1 < D) {
          var nv = t.v[i + 1][0] - t.v[i + 1][1], cv = t.v[i][0] - t.v[i][1];
          ex = c.X(i + f); ey = c.Y(cv + (nv - cv) * f);
          pts.push(ex.toFixed(1) + "," + ey.toFixed(1));
        }
        p.line.setAttribute("points", pts.join(" "));
        if (p.casing) p.casing.setAttribute("points", pts.join(" "));
        p.dot.setAttribute("cx", ex); p.dot.setAttribute("cy", ey);
        var cur = t.v[i];
        p.label.textContent = t.n + " " + signed(cur[0] - cur[1]);
        if (shown) ends.push({ p: p, x: ex, y: ey });
      });
      // 名前が重ならないよう、上から順に文字の高さぶんずつ離す
      ends.sort(function (a, b) { return a.y - b.y; });
      var prev = -1e9;
      ends.forEach(function (e) { var y = Math.max(e.y + 4, prev + c.gap); prev = y; e.p.label.setAttribute("x", e.x + 8); e.p.label.setAttribute("y", y); });
      drawBoard(c, i);
    });
    dayOut.textContent = jdate(days[i]);
    seek.value = i;
  }

  function drawBoard(c, i) {
    if (!c.board) return;
    var rows = c.teams.map(function (t) { var v = t.v[i]; return { t: t, w: v[0], l: v[1], d: v[2], s: v[3] }; });
    rows.sort(function (a, b) { return pct(b.w, b.l) - pct(a.w, a.l) || b.w - a.w; });
    c.board.textContent = "";
    rows.forEach(function (r, n) {
      var li = document.createElement("li");
      var st = streakText(r.s);
      li.innerHTML = '<span class="rk">' + (n + 1) + '</span><span class="nm"><i></i></span><span class="rec"></span>' +
        '<span class="sv"></span><span class="st"></span>';
      li.querySelector(".nm i").style.background = r.t.c;
      li.querySelector(".nm").appendChild(document.createTextNode(r.t.n));
      li.querySelector(".rec").textContent = r.w + "勝" + r.l + "敗" + r.d + "分";
      li.querySelector(".sv").textContent = signed(r.w - r.l);
      var stEl = li.querySelector(".st");
      stEl.textContent = st;
      // 5連勝・5連敗からは目立たせる
      if (Math.abs(r.s) >= 5) { stEl.classList.add("hot"); stEl.style.setProperty("--hot", r.s > 0 ? "#c62828" : "#1c1d1f"); }
      c.board.appendChild(li);
    });
  }

  // 再生
  var bar = document.querySelector(".player");
  var playBtn = bar.querySelector(".play"), dayOut = bar.querySelector(".day"), seek = bar.querySelector(".seek");
  var speed = 1, k = D - 1, playing = false, last = 0;
  var SECONDS = 120;    // ×1 で開幕から最終日まで2分（×4 で30秒）

  function tick(ts) {
    if (!playing) return;
    var dt = last ? (ts - last) / 1000 : 0;
    k = Math.min(D - 1, k + dt * (D - 1) / SECONDS * speed);
    last = ts;
    draw(k, dt || 0.016);
    if (k >= D - 1) { stop(); return; }
    requestAnimationFrame(tick);
  }
  function play() {
    if (k >= D - 1) { k = 0; draw(k); }   // 最初からのときは、縦の範囲も開幕の幅にすぐ戻す
    playing = true; last = 0;
    playBtn.textContent = "❚❚"; playBtn.setAttribute("aria-label", "一時停止");
    requestAnimationFrame(tick);
  }
  function stop() {
    playing = false;
    playBtn.textContent = "▶"; playBtn.setAttribute("aria-label", "開幕から再生");
  }
  playBtn.addEventListener("click", function () { playing ? stop() : play(); });
  seek.addEventListener("input", function () { stop(); k = +seek.value; draw(k); });
  bar.querySelectorAll(".speed button").forEach(function (b) {
    b.addEventListener("click", function () {
      speed = +b.dataset.speed;
      bar.querySelectorAll(".speed button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    });
  });

  build();
  draw(k);
  // 幅が変わったら描き直す（画面の回転など）
  var lastW = window.innerWidth, timer = null;
  window.addEventListener("resize", function () {
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(timer);
    timer = setTimeout(function () { build(); draw(k); }, 150);
  });
})();
