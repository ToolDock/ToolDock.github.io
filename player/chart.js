// 選手ページの「年度別の推移」（npb/build_players.py が書き出す）。
// .trend の data-rows に [年, WAR, OPSか防御率] が並んでいる。null は出場なし・対象外
(function () {
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function nice(lo, hi, n) {
    var span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; }).find(function (s) { return s >= raw; });
    return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step: step };
  }
  function fmt(v, series, kind) {
    if (series === "war") return v.toFixed(1);
    return kind === "p" ? v.toFixed(2) : v.toFixed(3).replace(/^0/, "");
  }
  function draw(fig, rows, series, kind) {
    var idx = series === "war" ? 1 : 2;
    var pts = rows.filter(function (r) { return r[idx] != null; });
    if (!pts.length) {
      var p = document.createElement("p");
      p.className = "none";
      p.textContent = "対象の年がありません";
      fig.appendChild(p);
      return;
    }
    // 画面の幅のまま描く（縮小すると、スマホで目盛りの文字が小さくなりすぎる）
    var W = Math.max(280, Math.round(fig.clientWidth - 24)), H = 190, L = 40, R = 8, T = 12, B = 26;
    var y0 = rows[0][0], y1 = rows[rows.length - 1][0], n = y1 - y0 + 1;
    var vals = pts.map(function (r) { return r[idx]; });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if (series === "war") { lo = Math.min(lo, 0); hi = Math.max(hi, 1); }
    else if (kind === "p") { lo = Math.min(lo, 2); hi = Math.max(hi, 4); }
    else { lo = Math.min(lo, .6); hi = Math.max(hi, .8); }
    var sc = nice(lo, hi, 4);
    var cw = (W - L - R) / n;
    function X(y) { return L + (y - y0 + .5) * cw; }
    function Y(v) { return T + (sc.hi - v) / (sc.hi - sc.lo) * (H - T - B); }
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img" });
    for (var v = sc.lo; v <= sc.hi + 1e-9; v += sc.step) {
      var yy = Y(v), zero = series === "war" && Math.abs(v) < 1e-9;
      svg.appendChild(el("line", { x1: L, x2: W - R, y1: yy, y2: yy, stroke: zero ? "#9ca3af" : "#e5e7eb", "stroke-width": zero ? 1.2 : 1 }));
      svg.appendChild(el("text", { x: L - 6, y: yy + 3.5, "text-anchor": "end", "font-size": 10, fill: "#6b7280" }, fmt(v, series, kind)));
    }
    // 年のラベル。多いときは間引く
    var fit = Math.max(1, Math.floor((W - L - R) / 34));   // 年のラベルが入る数
    var every = n <= fit ? 1 : n <= fit * 2 ? 2 : n <= fit * 3 ? 3 : 5;
    for (var y = y0; y <= y1; y++) {
      if ((y - y0) % every && y !== y1) continue;
      if (y !== y1 && y1 - y < every && (y - y0) % every === 0 && y !== y0) continue;
      svg.appendChild(el("text", { x: X(y), y: H - 8, "text-anchor": "middle", "font-size": 10, fill: "#6b7280" },
        n > fit / 1.6 ? "'" + String(y).slice(2) : String(y)));
    }
    var best = pts.reduce(function (a, r) {
      if (!a) return r;
      return (series === "val" && kind === "p") ? (r[idx] < a[idx] ? r : a) : (r[idx] > a[idx] ? r : a);
    }, null);
    if (series === "war") {
      var bw = Math.max(2, Math.min(22, cw * .64));
      pts.forEach(function (r) {
        var v = r[1], top = Y(Math.max(v, 0)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
        var b = el("rect", { x: X(r[0]) - bw / 2, y: top, width: bw, height: h, rx: 2,
          fill: v < 0 ? "#dc2626" : (r === best ? "#1d4ed8" : "#60a5fa") });
        b.appendChild(el("title", {}, r[0] + "年 WAR " + v.toFixed(1)));
        svg.appendChild(b);
      });
    } else {
      // 出場のない年・対象外の年で線を切る
      // （MLB 在籍などで年が飛んでいるところも切る）
      var seg = [], segs = [];
      rows.forEach(function (r) {
        var gap = seg.length && r[0] - seg[seg.length - 1][0] > 1;
        if (r[2] == null || gap) { if (seg.length) segs.push(seg); seg = []; }
        if (r[2] != null) seg.push(r);
      });
      if (seg.length) segs.push(seg);
      segs.forEach(function (s) {
        if (s.length < 2) return;
        svg.appendChild(el("polyline", { points: s.map(function (r) { return X(r[0]) + "," + Y(r[2]); }).join(" "),
          fill: "none", stroke: "#0f766e", "stroke-width": 2, "stroke-linejoin": "round" }));
      });
      pts.forEach(function (r) {
        var c = el("circle", { cx: X(r[0]), cy: Y(r[2]), r: r === best ? 4 : 3,
          fill: r === best ? "#0f766e" : "#fff", stroke: "#0f766e", "stroke-width": 2 });
        c.appendChild(el("title", {}, r[0] + "年 " + (kind === "p" ? "防御率 " : "OPS ") + fmt(r[2], "val", kind)));
        svg.appendChild(c);
      });
    }
    var cap = fig.querySelector("figcaption");
    var b = document.createElement("b");
    b.textContent = (series === "war" ? "最高 " : "ベスト ") + best[0] + "年 " + fmt(best[idx], series, kind);
    cap.appendChild(b);
    fig.appendChild(svg);
  }
  document.querySelectorAll(".trend").forEach(function (box) {
    var rows = JSON.parse(box.dataset.rows);
    var kind = box.dataset.kind;
    box.querySelectorAll(".tchart").forEach(function (fig) { draw(fig, rows, fig.dataset.series, kind); });
  });
})();
