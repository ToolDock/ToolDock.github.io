/* =========================
   共通ヘッダー

   全ページの先頭に、ロゴだけの細い帯を出す。
   各HTMLには書かず、head.js から1回だけ読み込む
   （head.js を読まないトップページは、そのHTMLから直接読む）。

   狙いは2つ。
   1. 下のフッターと上下で挟んで、サイトとしての体裁を整える
   2. どのページにも実在する画像を1枚置く。
      og:image はSNSのカード用で、Googleが検索結果や
      コレクションのサムネイルに使うのはページ内の画像なので、
      画像がまったく無いページは代表画像を持てない

   本文の邪魔をしないよう、高さは抑えて色も敷かない。
========================= */

(() => {

  "use strict";

  /* すでに置かれていれば何もしない（二重読み込み対策） */
  if (document.getElementById("td-header")) return;

  const LOGO = "/img/logo.png";

  function injectStyle() {
    if (document.getElementById("td-header-style")) return;

    const style = document.createElement("style");
    style.id = "td-header-style";

    style.textContent = `
      .td-header {
        box-sizing: border-box;
        background: #ffffff;
        /* フッターと同じ青で下端に細い線を引き、上下で挟む */
        border-bottom: 3px solid;
        border-image: linear-gradient(90deg, #0ea5e9 0%, #0284c7 100%) 1;
      }

      /* ロゴは画面の左上に置く。
         本文の幅にそろえて中央に寄せると、帯の中で宙に浮いて見える */
      .td-header-inner {
        padding: 8px 18px;
      }

      .td-header a {
        display: inline-block;
        line-height: 0;
        text-decoration: none;
      }

      .td-header img {
        display: block;
        width: auto;
        height: 44px;
      }

      @media (max-width: 600px) {
        .td-header img { height: 36px; }
        .td-header-inner { padding: 7px 14px; }
      }

      @media print {
        .td-header { display: none !important; }
      }
    `;

    document.head.appendChild(style);
  }

  /* =========================
     画面の端から端まで伸ばす

     style.css が body に max-width:900px を掛けているため、
     そのままでは本文と同じ幅で止まる。
     footer.js と同じ考え方で、body の位置を実測して左端に合わせる。
  ========================= */

  let headerEl = null;

  function fullBleed() {
    if (!headerEl) return;

    const cs = getComputedStyle(document.body);
    const bodyRect = document.body.getBoundingClientRect();

    const padLeft = parseFloat(cs.paddingLeft) || 0;
    const borderLeft = parseFloat(cs.borderLeftWidth) || 0;

    const rail = document.querySelector(".td-rail");

    const railWidth = rail && getComputedStyle(rail).display !== "none"
      ? rail.getBoundingClientRect().width
      : 0;

    /* clientWidth はスクロールバーを含まないので横スクロールが出ない */
    const viewport = document.documentElement.clientWidth;

    /* body の上余白ぶんだけ、帯が下がって見えてしまうのを打ち消す */
    const padTop = parseFloat(cs.paddingTop) || 0;

    headerEl.style.marginLeft =
      -(bodyRect.left + borderLeft + padLeft) + "px";

    headerEl.style.marginTop = -padTop + "px";
    headerEl.style.width = (viewport - railWidth) + "px";
  }

  function mount() {
    injectStyle();

    headerEl = document.createElement("header");
    headerEl.className = "td-header";
    headerEl.id = "td-header";

    /* 幅と高さを属性で持たせて、読み込み中に本文が飛び跳ねないようにする */
    headerEl.innerHTML = `
      <div class="td-header-inner">
        <a href="/" aria-label="ToolDock ホーム">
          <img src="${LOGO}"
               width="1068" height="332"
               alt="ToolDock 無料Webツール集">
        </a>
      </div>
    `;

    /* パンくずより前に出す。head.js が body の先頭に差し込むため、
       ここでも先頭に入れて順序を保つ */
    document.body.insertBefore(headerEl, document.body.firstChild);

    fullBleed();

    let resizeTimer = null;

    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(fullBleed, 120);
    });

    /* 右レールは後から読み込まれることがあるので測り直す。
       あわせて、あとから body の先頭に差し込まれた要素
       （パンくずなど）に追い越されていないか見て、先頭に戻す */
    const settle = () => {
      if (headerEl.parentNode && document.body.firstChild !== headerEl) {
        document.body.insertBefore(headerEl, document.body.firstChild);
      }
      fullBleed();
    };

    window.addEventListener("load", settle);
    setTimeout(settle, 300);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }

})();
