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
      var lo = 0, hi = 0;
      teams.forEach(function (t) { t.v.forEach(function (x) { lo = Math.min(lo, x[0] - x[1]); hi = Math.max(hi, x[0] - x[1]); }); });
      var step = (hi - lo) > 40 ? 10 : 5;
      lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
      if (hi === lo) hi = lo + step;
      function X(i) { return L + (D > 1 ? i / (D - 1) : 0) * (W - L - R); }
      function Y(v) { return T + (hi - v) / (hi - lo) * (H - T - B); }

      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": fig.getAttribute("aria-label") });
      // 目盛り：貯金と、月の頭（月の名前は、次の月と近すぎるときは出さない）
      for (var v = lo; v <= hi; v += step) {
        svg.appendChild(el("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: v === 0 ? "#1c1d1f" : "#e6e4de", "stroke-width": v === 0 ? 1.2 : 1 }));
        svg.appendChild(el("text", { x: L - 5, y: Y(v) + 4, "text-anchor": "end", "font-size": fs - 1, fill: "#1c1d1f" }, v > 0 ? "+" + v : String(v)));
      }
      var months = [];
      days.forEach(function (d, i) { var m = d.slice(5, 7); if (!months.length || months[months.length - 1].m !== m) months.push({ m: m, i: i }); });
      months.forEach(function (mo, n) {
        svg.appendChild(el("line", { x1: X(mo.i), x2: X(mo.i), y1: T, y2: H - B, stroke: "#e6e4de" }));
        var next = months[n + 1];
        if (next && X(next.i) - X(mo.i) < (narrow ? 26 : 30)) return;
        svg.appendChild(el("text", { x: X(mo.i) + 3, y: H - B + 16, "font-size": fs - 1, fill: "#1c1d1f" }, (+mo.m) + "月"));
      });
      var lines = el("g", {}), labels = el("g", {});
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
      charts.push({ parts: parts, teams: teams, board: board, X: X, Y: Y, gap: fs + 1 });
    });
  }

  // k（0〜D-1、小数もあり）の日までを描く
  function draw(k) {
    var i = Math.floor(k), f = k - i;
    charts.forEach(function (c) {
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
  var SECONDS = 30;     // ×1 で開幕から最終日まで30秒

  function tick(ts) {
    if (!playing) return;
    if (last) k = Math.min(D - 1, k + (ts - last) / 1000 * (D - 1) / SECONDS * speed);
    last = ts;
    draw(k);
    if (k >= D - 1) { stop(); return; }
    requestAnimationFrame(tick);
  }
  function play() {
    if (k >= D - 1) k = 0;
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
