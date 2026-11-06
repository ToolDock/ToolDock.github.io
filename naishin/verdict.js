/* 内申点ツール共通：目標に届くか（余裕・不足）を分かりやすく出す */
(function () {
    "use strict";
    var css = ".td-vd{margin:10px 0 4px;padding:12px 14px;border-radius:8px;font-size:.95rem;line-height:1.6}" +
        ".td-vd .big{font-size:1.25rem;font-weight:800;margin-bottom:2px}" +
        ".td-vd .big b{font-size:1.6rem;font-variant-numeric:tabular-nums;white-space:nowrap}" +
        ".td-vd ul{margin:4px 0 0;padding-left:1.2em}.td-vd li{margin:2px 0}" +
        ".td-vd.ok{background:#ecfdf3;color:#05603a;border:1px solid #abefc6}" +
        ".td-vd.ng{background:#fef3f2;color:#912018;border:1px solid #fecdca}" +
        ".td-vd.hint{background:var(--surface-2,#f4f4f2);color:#3a3d42;font-size:.9rem}";
    var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

    function fmt(x, dec) { var p = Math.pow(10, dec); return (Math.round(x * p + 1e-9) / p).toFixed(dec); }
    function up(x) { return Math.ceil(x - 1e-9); }

    /*
     * o.score 今の値 / o.goal 目標（空なら案内）/ o.dec 表示の小数桁 / o.unit "S1値" など
     * o.exam = { per: 当日点1点で増える値, left: 当日点であと取れる点（満点まで）, n: 教科数, word: "当日点" }
     * o.naishin = [{ label: "中3の評定", per: 1つ上げて増える値, left: あと上げられる数 }]
     */
    window.tdVerdict = function (el, o) {
        if (o.goal === "" || o.goal == null || isNaN(Number(o.goal))) {
            el.className = "td-vd hint";
            el.innerHTML = "志望校の目標（模試や塾の資料にある合格の目安）を入れると、届いているか、あと何点かを表示します。";
            return;
        }
        var diff = o.score - Number(o.goal), ex = o.exam, word = ex.word || "当日点";
        if (diff >= -1e-9) {
            el.className = "td-vd ok";
            var down = Math.floor(diff / ex.per + 1e-9);
            el.innerHTML = '<div class="big">届いています　目標より <b>＋' + fmt(diff, o.dec) + "</b> の余裕</div>" +
                (down >= 1 ? word + "が合計 約" + down + "点（1教科 約" + fmt(down / ex.n, 1) + "点）下がっても届く計算です。" : "ほぼちょうどです。当日点が1点下がると届かなくなります。");
            return;
        }
        var lack = -diff, items = [];
        var needEx = up(lack / ex.per);
        items.push(needEx <= ex.left
            ? word + "なら：あと合計 約" + needEx + "点（1教科 約" + fmt(needEx / ex.n, 1) + "点）"
            : word + "だけでは届きません（満点でもあと " + fmt(lack - ex.left * ex.per, o.dec) + "）");
        /* 内申：効きの大きい順（渡した順）に上げていく */
        var rest = lack, parts = [];
        (o.naishin || []).forEach(function (n) {
            if (rest <= 1e-9 || n.left <= 0) return;
            var k = Math.min(n.left, up(rest / n.per));
            rest -= k * n.per; parts.push(n.label + "をあと合計 " + k);
        });
        if (o.naishin && o.naishin.length) {
            items.push(rest <= 1e-9
                ? "内申なら：" + parts.join("、") + " 上げる"
                : "内申だけでは届きません（全部5にしても不足）");
        }
        el.className = "td-vd ng";
        el.innerHTML = '<div class="big">目標まで あと <b>' + fmt(lack, o.dec) + "</b></div><ul><li>" + items.join("</li><li>") + "</li></ul>";
    };
})();
