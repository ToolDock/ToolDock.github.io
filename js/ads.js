/* =========================
   広告枠

   方針
   - 本文を覆う大きな広告は置かない
   - 下から小さく出るバー（閉じられる）と、ページ末尾の1枠だけ
   - 審査に通るまでは ENABLED を false にしておき、
     AdSense のコードを一切読み込まない

   設定は2段階に分かれている

   【審査に出すとき】
     CLIENT に、AdSense が発行した「ca-pub-」で始まる番号を入れる。
     これだけで審査用のスクリプトが読み込まれる。
     広告の枠はまだ出ない（審査中に空枠を出しても意味がないため）。

   【承認されたあと】
     UNITS_ENABLED を true にし、AdSense で作成した広告ユニットの
     スロットIDを SLOT_STICKY / SLOT_END に入れる。
========================= */

(() => {

  "use strict";

  /* 「ca-pub-」で始まる番号。空のあいだは何も読み込まない */
  const CLIENT = "ca-pub-8349615939902537";

  /* 広告の枠を出すかどうか。承認後に true にする */
  const UNITS_ENABLED = false;

  const SLOT_STICKY = "";
  const SLOT_END = "";

  /* 下のバーを出し始めるスクロール量 */
  const STICKY_AFTER = 600;

  const DISMISS_KEY = "tooldock-ad-sticky-closed";

  /* 番号が未設定のうちは、審査用スクリプトも枠も出さない */
  if (!CLIENT) return;

  /* ---- AdSense 本体を1回だけ読み込む ---- */

  function loadAdSense() {
    if (document.querySelector('script[src*="adsbygoogle"]')) return;

    const s = document.createElement("script");

    s.async = true;
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + CLIENT;
    s.crossOrigin = "anonymous";

    document.head.appendChild(s);
  }

  function pushAd() {
    (window.adsbygoogle = window.adsbygoogle || []).push({});
  }

  /* ---- スタイル ---- */

  function injectStyle() {
    const style = document.createElement("style");

    style.textContent = `
      .td-ad-end {
        max-width: 1000px;
        margin: 32px auto 0;
        text-align: center;
      }

      .td-ad-label {
        font-size: 0.72rem;
        color: #94a3b8;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
      }

      .td-ad-sticky {
        position: fixed;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 20;

        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;

        padding: 6px 10px;
        box-sizing: border-box;

        background: rgba(255, 255, 255, 0.94);
        border-top: 1px solid #e2e8f0;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.08);

        transform: translateY(110%);
        transition: transform 0.25s ease-out;
      }

      .td-ad-sticky.shown {
        transform: translateY(0);
      }

      .td-ad-sticky .td-ad-close {
        flex-shrink: 0;
        width: 28px;
        height: 28px;
        border: none;
        border-radius: 50%;
        background: #e2e8f0;
        color: #475569;
        font-size: 1rem;
        line-height: 1;
        cursor: pointer;
      }

      .td-ad-sticky .td-ad-close:hover {
        background: #cbd5e1;
      }

      /* 右レールが出ている画面では、レールの下に潜り込ませない */
      @media (min-width: 1300px) {
        .td-ad-sticky {
          right: 300px;
        }
      }
    `;

    document.head.appendChild(style);
  }

  /* ---- ページ末尾の枠 ---- */

  function mountEndSlot() {
    const box = document.createElement("div");

    box.className = "td-ad-end";

    box.innerHTML = `
      <div class="td-ad-label">スポンサーリンク</div>
      <ins class="adsbygoogle"
           style="display:block"
           data-ad-client="${CLIENT}"
           data-ad-slot="${SLOT_END}"
           data-ad-format="auto"
           data-full-width-responsive="true"></ins>
    `;

    const related = document.getElementById("related-tools");

    if (related && related.parentNode) {
      related.parentNode.insertBefore(box, related.nextSibling);
    } else {
      document.body.appendChild(box);
    }

    pushAd();
  }

  /* ---- 下から出るバー ---- */

  function mountStickySlot() {
    if (sessionStorage.getItem(DISMISS_KEY) === "1") return;

    const bar = document.createElement("div");

    bar.className = "td-ad-sticky";

    bar.innerHTML = `
      <ins class="adsbygoogle"
           style="display:inline-block;width:320px;height:50px"
           data-ad-client="${CLIENT}"
           data-ad-slot="${SLOT_STICKY}"></ins>
      <button type="button" class="td-ad-close" aria-label="広告を閉じる">×</button>
    `;

    document.body.appendChild(bar);

    pushAd();

    bar.querySelector(".td-ad-close").addEventListener("click", () => {
      bar.classList.remove("shown");

      try { sessionStorage.setItem(DISMISS_KEY, "1"); } catch (e) { /* 保存できなくても動作に影響はない */ }

      setTimeout(() => bar.remove(), 300);
    });

    /* ある程度読み進めてから出す */
    const onScroll = () => {
      if (window.scrollY > STICKY_AFTER) {
        bar.classList.add("shown");
        window.removeEventListener("scroll", onScroll);
      }
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---- 起動 ---- */

  function start() {
    /* 審査用のスクリプトは、番号さえ入っていれば読み込む */
    loadAdSense();

    /* 枠を出すのは承認後だけ */
    if (!UNITS_ENABLED) return;

    injectStyle();
    mountEndSlot();
    mountStickySlot();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
