/* =========================
   右レール（サイドバー）

   画面が広いときは右端に固定表示し、body に右余白を入れて
   本文と重ならないようにする。狭いときは本文の最後に流し込む。

   背景色の明るさを見て、暗いページでは配色を反転させる。
========================= */

(() => {

  "use strict";

  const ORIGIN = "https://tooldock.github.io";

  /* 表示に使う閾値。この幅未満では本文の下に置く */
  const WIDE = "(min-width: 1300px)";

  /* よく見られているページ（実際のクリック数の多い順に手で並べている） */
  const POPULAR = [
    "kintoku",
    "hakidasi",
    "counter",
    "koyuchi",
    "renritsu",
    "circuit"
  ];

  const CATEGORY_ORDER = ["math", "work", "life", "game"];

  /* ---- 背景の明るさから配色を決める ---- */

  /* 単色の明るさ。透明・解釈不能なら null を返す */
  function luminanceOf(color) {
    const m = String(color).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;

    const parts = m[1].split(",").map(v => parseFloat(v));
    const alpha = parts.length > 3 ? parts[3] : 1;

    if (!alpha) return null;

    return (parts[0] * 299 + parts[1] * 587 + parts[2] * 114) / 1000;
  }

  /* グラデーション指定から色を拾って平均を取る */
  function luminanceOfImage(image) {
    const found = String(image).match(/rgba?\([^)]+\)/g);
    if (!found) return null;

    const values = found.map(luminanceOf).filter(v => v !== null);
    if (!values.length) return null;

    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  /*
     背景の明るさを、確度の高い順に見ていく。
     グラデーションだけを指定したページ（seiza など）は
     background-color が透明になるため、画像側も見る必要がある。
     どこからも決まらない場合は、既定の白地とみなす。
  */
  function isDarkBackground() {
    const bodyStyle = getComputedStyle(document.body);

    const candidates = [
      luminanceOf(bodyStyle.backgroundColor),
      luminanceOfImage(bodyStyle.backgroundImage),
      luminanceOf(getComputedStyle(document.documentElement).backgroundColor)
    ];

    for (const lum of candidates) {
      if (lum !== null) return lum < 128;
    }

    return false;
  }

  /* ---- スタイル ---- */

  function injectStyle(dark) {
    const style = document.createElement("style");

    style.id = "td-rail-style";

    /* 各ページの body 指定より後に差し込まれるが、
       ページ側の padding 指定に確実に勝つ必要があるため !important を使う */

    style.textContent = `

      .td-rail {
        display: none;
        position: fixed;
        top: 0;
        right: 0;
        bottom: 0;
        width: 300px;
        box-sizing: border-box;
        padding: 24px 20px 40px;
        overflow-y: auto;
        border-left: 1px solid ${dark ? "rgba(255,255,255,0.14)" : "#e2e8f0"};
        background: ${dark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.75)"};
        backdrop-filter: blur(6px);
        z-index: 5;
      }

      .td-rail-inline {
        max-width: 1000px;
        margin: 40px auto 0;
      }

      .td-box {
        margin-bottom: 22px;
      }

      .td-box h2 {
        margin: 0 0 10px;
        padding: 0 0 6px;
        font-size: 0.95rem;
        font-weight: bold;
        border: 0;
        border-bottom: 2px solid ${dark ? "rgba(255,255,255,0.2)" : "#e2e8f0"};
        color: ${dark ? "#e2e8f0" : "#334155"};
        letter-spacing: 0.02em;
      }

      .td-box ol,
      .td-box ul {
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .td-box li {
        margin: 0 0 2px;
      }

      .td-box a {
        display: block;
        padding: 8px 10px;
        border-radius: 8px;
        text-decoration: none;
        font-size: 0.9rem;
        line-height: 1.5;
        color: ${dark ? "#cbd5e1" : "#334155"};
      }

      .td-box a:hover {
        background: ${dark ? "rgba(255,255,255,0.08)" : "#eff6ff"};
        color: ${dark ? "#ffffff" : "#1d4ed8"};
      }

      .td-box a.current {
        background: ${dark ? "rgba(255,255,255,0.1)" : "#eff6ff"};
        color: ${dark ? "#ffffff" : "#1d4ed8"};
        font-weight: bold;
      }

      .td-rank {
        display: inline-block;
        width: 1.4em;
        color: ${dark ? "#94a3b8" : "#94a3b8"};
        font-size: 0.85em;
      }

      .td-cats {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .td-cats a {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid ${dark ? "rgba(255,255,255,0.2)" : "#cbd5e1"};
        font-size: 0.85rem;
      }

      /* 広い画面では右端に固定し、本文側に余白を作って重なりを防ぐ。
         基本ルールより後に置くことで確実に上書きする */
      @media ${WIDE} {
        body {
          padding-right: 300px !important;
        }

        .td-rail {
          display: block;
        }

        .td-rail-inline {
          display: none;
        }
      }

      /* 狭い画面では横に並べて場所を取りすぎないようにする */
      @media (max-width: 1299px) {
        .td-rail-inline .td-box ul,
        .td-rail-inline .td-box ol {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          gap: 2px 10px;
        }
      }
    `;

    document.head.appendChild(style);
  }

  /* ---- 中身を組み立てる ---- */

  function escape(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function linkList(items, ordered) {
    const tag = ordered ? "ol" : "ul";

    const rows = items.map((t, i) => `
      <li>
        <a href="${t.url}"${t.url === location.pathname ? ' class="current"' : ""}>
          ${ordered ? `<span class="td-rank">${i + 1}</span>` : ""}${escape(t.title)}
        </a>
      </li>
    `).join("");

    return `<${tag}>${rows}</${tag}>`;
  }

  function buildContent() {
    const tools = (window.TOOLS || []).filter(t => !t.hidden);

    if (tools.length === 0) return null;

    const current = tools.find(t => t.url === location.pathname);

    const wrap = document.createElement("div");

    let html = "";

    /* 人気のページ */
    const popular = POPULAR
      .map(id => tools.find(t => t.id === id))
      .filter(Boolean);

    if (popular.length) {
      html += `
        <div class="td-box">
          <h2>人気のページ</h2>
          ${linkList(popular, true)}
        </div>
      `;
    }

    /* 同じカテゴリ */
    if (current && current.category) {
      const same = tools.filter(
        t => t.category === current.category && t.id !== current.id
      );

      if (same.length) {
        html += `
          <div class="td-box">
            <h2>${(window.CATEGORY_NAMES || {})[current.category] || current.category}のツール</h2>
            ${linkList(same, false)}
          </div>
        `;
      }
    }

    /* カテゴリから探す */
    const cats = CATEGORY_ORDER.filter(c => tools.some(t => t.category === c));

    html += `
      <div class="td-box">
        <h2>カテゴリから探す</h2>
        <div class="td-cats">
          ${cats.map(c => `
            <a href="/category/?cat=${encodeURIComponent(c)}">${(window.CATEGORY_NAMES || {})[c] || c}</a>
          `).join("")}
          <a href="/">すべて</a>
        </div>
      </div>
    `;

    wrap.innerHTML = html;

    return wrap;
  }

  /* ---- 配置の切り替え ---- */

  function mount() {
    const content = buildContent();
    if (!content) return;

    const rail = document.createElement("aside");
    rail.className = "td-rail";
    rail.setAttribute("aria-label", "サイト内の他のページ");

    const inline = document.createElement("aside");
    inline.className = "td-rail-inline";
    inline.setAttribute("aria-label", "サイト内の他のページ");

    /* 同じ中身を2か所に持たせず、幅に応じて移し替える */
    const mq = window.matchMedia(WIDE);

    const place = () => {
      if (mq.matches) rail.appendChild(content);
      else inline.appendChild(content);
    };

    place();

    mq.addEventListener("change", place);

    document.body.appendChild(rail);

    /* 関連ツールの直前に置く。無ければ末尾 */
    const related = document.getElementById("related-tools");

    if (related) related.parentNode.insertBefore(inline, related);
    else document.body.appendChild(inline);
  }

  /* ---- 起動 ---- */

  function start() {
    if (!window.TOOLS) return;

    injectStyle(isDarkBackground());
    mount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
