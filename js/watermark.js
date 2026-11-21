/* 保存する画像の下に余白を足し、その右端に小さいロゴとページのURLを入れる（共有されたときの名札）。
   画像そのもの（枠など）には重ねない。わざと小さく薄くしているので、画像編集で切り取れる程度。
   使い方：TDMark.extend(canvas) … 下に余白とURLを足した、新しい canvas を返す（元の canvas はそのまま） */
(function () {
    var logo = new Image();
    logo.src = "/img/mark.png";

    function pageUrl() {
        var path = location.pathname.replace(/index\.html$/, "");
        return "tooldock.github.io" + path;
    }

    function extend(src) {
        var w = src.width, h = src.height;
        /* 文字の大きさは画像の大きさに合わせる（短い辺の2%、9〜20px） */
        var fs = Math.max(9, Math.min(20, Math.round(Math.min(w, h) * 0.02)));
        var strip = Math.round(fs * 1.9);

        var cv = document.createElement("canvas");
        cv.width = w; cv.height = h + strip;
        var ctx = cv.getContext("2d");
        ctx.drawImage(src, 0, 0);

        /* 余白の色は、元の画像のいちばん下の色に合わせる（透明なら透明のまま） */
        var px = [0, 0, 0, 0];
        try { px = src.getContext("2d").getImageData(Math.floor(w / 2), h - 1, 1, 1).data; } catch (e) {}
        var ink = "rgba(128,134,144,0.95)";
        if (px[3] > 128) {
            ctx.fillStyle = "rgb(" + px[0] + "," + px[1] + "," + px[2] + ")";
            ctx.fillRect(0, h, w, strip);
            var lum = 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2];
            ink = lum > 140 ? "rgba(0,0,0,0.42)" : "rgba(255,255,255,0.6)";
        }

        var text = pageUrl();
        ctx.font = fs + "px system-ui, -apple-system, 'Hiragino Sans', 'Noto Sans JP', sans-serif";
        var tw = Math.ceil(ctx.measureText(text).width);
        var icon = logo.complete && logo.naturalWidth ? Math.round(fs * 1.1) : 0;
        var gap = icon ? Math.round(fs * 0.3) : 0;
        var right = w - Math.round(fs * 0.7);
        var cy = h + strip / 2;

        ctx.globalAlpha = 0.75;
        if (icon) ctx.drawImage(logo, right - tw - gap - icon, cy - icon / 2, icon, icon);
        ctx.globalAlpha = 1;
        ctx.fillStyle = ink;
        ctx.textBaseline = "middle";
        ctx.fillText(text, right - tw, cy + 0.5);
        return cv;
    }

    window.TDMark = { extend: extend };
})();
