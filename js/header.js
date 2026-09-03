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

  /* ファビコンと同じ絵柄を切り出したもの */
  const MARK = "/img/mark.png";

  function injectStyle() {
    if (document.getElementById("td-header-style")) return;

    const style = document.createElement("style");
    style.id = "td-header-style";

    style.textContent = `
      /* ページ側が裸の header{} や a{} を書いていることがあり、
         そのままだと余白・寄せ・色をそこから拾ってしまう。
         見た目に関わるものは、ここで全部言い切っておく。
         この一括指定は下の個別指定より前に置くこと（同じ強さなので後勝ち） */
      .td-header,
      .td-header * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        border: 0;
        border-radius: 0;
        background: none;
        box-shadow: none;
        text-align: left;
        text-decoration: none;
        letter-spacing: normal;
        font-family: -apple-system, "Segoe UI", "Hiragino Sans",
                     "Noto Sans JP", Meiryo, sans-serif;
        font-style: normal;
      }

      .td-header {
        display: block;
        background: #ffffff;
        color: #1f2937;
        line-height: 1.2;
        /* フッターと同じ系統の青を、細く1本だけ。
           太い線や濃い色を敷くと本文より目立ってしまう */
        border-bottom: 2px solid #7dd3fc;
      }

      /* ロゴは画面の左端に寄せる。
         本文の幅にそろえて中央に寄せると、帯の中で宙に浮いて見える */
      .td-header-inner {
        padding: 6px 12px;
      }

      .td-header a {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        color: inherit;
      }

      /* ファビコンと同じマーク。
         元画像が48pxなので、それより小さく出して常に鮮明に保つ */
      .td-header img {
        display: block;
        width: 26px;
        height: 26px;
        max-width: none;
        min-width: 0;
      }

      .td-header-name {
        display: block;
        color: #1f2937;
        font-size: 16px;
        font-weight: 700;
        line-height: 1.15;
        letter-spacing: -0.2px;
      }

      .td-header-tag {
        display: block;
        margin-top: 1px;
        color: #7b8794;
        font-size: 10px;
        line-height: 1.2;
        letter-spacing: 0;
      }

      @media (max-width: 600px) {
        .td-header-inner { padding: 5px 10px; }
        .td-header img { width: 23px; height: 23px; }
        .td-header-name { font-size: 15px; }
      }

      /* カテゴリのメニュー。
         ロゴだけだと最上部から他のページへ行けないので、
         カテゴリへの入口をここに並べる */
      .td-header-inner {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px 16px;
      }

      .td-header-nav {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 2px 4px;
      }

      .td-header-nav a {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        color: #374151;
        font-size: 13px;
        font-weight: 700;
        white-space: nowrap;
      }

      .td-header-nav a:hover {
        background: #eef6fd;
        color: #0369a1;
      }

      /* いま見ているカテゴリを塗って示す */
      .td-header-nav a[aria-current="page"] {
        background: #e0f2fe;
        color: #0369a1;
      }

      @media (max-width: 600px) {
        .td-header-inner { gap: 2px 10px; }
        .td-header-nav a { padding: 3px 7px; font-size: 12px; }
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

  /* カテゴリの並びは tool-data を唯一の情報源にする。
     カテゴリを足したり名前を変えたりしても、ここは触らなくていい */
  function navLinks() {
    const names = window.CATEGORY_NAMES || {};
    const tools = (window.TOOLS || []).filter(t => !t.hidden);

    /* 中身のあるカテゴリだけ出す。空の入口を作らない */
    const cats = Object.keys(names).filter(
      c => tools.some(t => t.category === c));

    const current = typeof CURRENT_TOOL !== "undefined"
      ? (window.TOOLS || []).find(t => t.id === CURRENT_TOOL)
      : null;

    return cats.map(c => {
      const here = current && current.category === c;
      return `<a href="/category/?cat=${encodeURIComponent(c)}"${
        here ? ' aria-current="page"' : ""}>${names[c]}</a>`;
    }).join("");
  }

  function mount() {
    injectStyle();

    headerEl = document.createElement("header");
    headerEl.className = "td-header";
    headerEl.id = "td-header";

    headerEl.innerHTML = `
      <div class="td-header-inner">
        <a href="/">
          <img src="${MARK}"
               width="48" height="48"
               alt="ToolDock">
          <span>
            <span class="td-header-name">ToolDock</span>
            <span class="td-header-tag">無料Webツール集</span>
          </span>
        </a>
        <nav class="td-header-nav" aria-label="カテゴリ">${navLinks()}</nav>
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
