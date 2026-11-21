/* 保存する画像の右下に、小さいロゴとURLを入れる（共有されたときの名札）。
   わざと小さく薄くしているので、画像編集で消せる程度。
   使い方：TDMark.draw(ctx, 幅, 高さ) … canvas の右下に描く
           TDMark.copy(canvas) … ロゴ入りの複製 canvas を返す（画面の canvas は汚さない） */
(function () {
    var URL_TEXT = "tooldock.github.io";
    var logo = new Image();
    logo.src = "/img/mark.png";

    function draw(ctx, w, h) {
        /* 文字の大きさは画像の大きさに合わせる（短い辺の2.2%、9〜22px） */
        var fs = Math.max(9, Math.min(22, Math.round(Math.min(w, h) * 0.022)));
        var pad = Math.round(fs * 0.45);
        var icon = logo.complete && logo.naturalWidth ? Math.round(fs * 1.15) : 0;
        var gap = icon ? Math.round(fs * 0.35) : 0;

        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.font = "bold " + fs + "px system-ui, -apple-system, 'Hiragino Sans', 'Noto Sans JP', sans-serif";
        var tw = Math.ceil(ctx.measureText(URL_TEXT).width);
        var bw = pad * 2 + icon + gap + tw;
        var bh = Math.max(icon, fs) + pad * 2 - Math.round(fs * 0.2);
        var m = Math.round(fs * 0.5);
        var x = w - bw - m, y = h - bh - m;

        /* うすい黒の札（どんな背景でも読める） */
        ctx.globalAlpha = 0.42;
        ctx.fillStyle = "#000";
        var r = Math.round(bh / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + bw, y, x + bw, y + bh, r);
        ctx.arcTo(x + bw, y + bh, x, y + bh, r);
        ctx.arcTo(x, y + bh, x, y, r);
        ctx.arcTo(x, y, x + bw, y, r);
        ctx.closePath();
        ctx.fill();

        ctx.globalAlpha = 0.9;
        if (icon) ctx.drawImage(logo, x + pad, y + (bh - icon) / 2, icon, icon);
        ctx.fillStyle = "#fff";
        ctx.textBaseline = "middle";
        ctx.fillText(URL_TEXT, x + pad + icon + gap, y + bh / 2 + 0.5);
        ctx.restore();
    }

    function copy(src) {
        var cv = document.createElement("canvas");
        cv.width = src.width; cv.height = src.height;
        var ctx = cv.getContext("2d");
        ctx.drawImage(src, 0, 0);
        draw(ctx, cv.width, cv.height);
        return cv;
    }

    window.TDMark = { draw: draw, copy: copy };
})();
