/*
 * 「初期値に戻す」「消す」など、押すと入力が消えるボタンを、2回押しで動かす。
 *
 * confirm() の確認は、XやLINEなどのアプリの中のブラウザでは出ないことがあり、
 * そのときは押しても何も起きない（取り消し扱いになる）。そこで確認はボタン自身で行う。
 * 1回目でボタンの文字が赤い「もう一度押すと…」に変わり、数秒以内にもう一度押すと実行する。
 * 時間が過ぎると元の表示に戻る。
 *
 *   twoStepButton(document.getElementById("btnReset"), function () { ... }, "もう一度押すと、初期値に戻します");
 */
(function () {
  "use strict";
  window.twoStepButton = function (btn, action, armedText, ms) {
    if (!btn) return;
    var original = btn.textContent;
    var timer = null;
    var saved = null;
    function disarm() {
      clearTimeout(timer);
      timer = null;
      btn.textContent = original;
      if (saved) {
        btn.style.color = saved.color;
        btn.style.borderColor = saved.borderColor;
        btn.style.fontWeight = saved.fontWeight;
      }
    }
    btn.addEventListener("click", function () {
      if (!timer) {
        saved = { color: btn.style.color, borderColor: btn.style.borderColor, fontWeight: btn.style.fontWeight };
        btn.textContent = armedText || "もう一度押すと実行します";
        btn.style.color = "#dc2626";
        btn.style.borderColor = "#dc2626";
        btn.style.fontWeight = "700";
        timer = setTimeout(disarm, ms || 4000);
        return;
      }
      disarm();
      action();
    });
  };
})();
