/* =========================
   関連商品（楽天アフィリエイト）

   方針
   - 本文の邪魔をしない。ページ末尾に1ブロックだけ
   - そのページの内容と実際に関係のある商品しか置かない
   - 広告であることを明示する（景品表示法のステマ規制への対応）

   使い方
   PRODUCTS に、ページのパスをキーとして商品を並べる。
   url には楽天アフィリエイトで生成したリンクをそのまま入れる。
   商品が登録されていないページには、何も表示されない。
========================= */

(() => {

  "use strict";

  const PRODUCTS = {

    /* 例）
    "/kintoku/": [
      {
        title: "eBASEBALLパワフルプロ野球2026-2027",
        note: "本記事で扱っているゲーム本体",
        url: "https://hb.afl.rakuten.co.jp/..."
      }
    ],
    */

  };

  const items = PRODUCTS[location.pathname];

  if (!items || items.length === 0) return;

  /* ---- スタイル ---- */

  function injectStyle() {
    const style = document.createElement("style");

    style.textContent = `
      .td-shop {
        max-width: 1000px;
        margin: 40px auto 0;
        padding: 20px 22px;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        background: #fbfcfe;
        box-sizing: border-box;
      }

      .td-shop-head {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 14px;
      }

      .td-shop-head h2 {
        margin: 0;
        padding: 0;
        border: 0;
        font-size: 1.05rem;
        color: #334155;
      }

      .td-shop-tag {
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        padding: 3px 9px;
        border-radius: 999px;
        background: #e2e8f0;
        color: #475569;
      }

      .td-shop-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 12px;
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .td-shop-list a {
        display: block;
        padding: 14px 16px;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: white;
        text-decoration: none;
        color: #1e293b;
        transition: 0.15s;
      }

      .td-shop-list a:hover {
        border-color: #bf0000;
        transform: translateY(-1px);
      }

      .td-shop-title {
        font-weight: bold;
        line-height: 1.5;
      }

      .td-shop-note {
        margin-top: 4px;
        font-size: 0.85rem;
        color: #64748b;
      }

      .td-shop-foot {
        margin: 14px 0 0;
        font-size: 0.78rem;
        color: #94a3b8;
        line-height: 1.6;
      }
    `;

    document.head.appendChild(style);
  }

  /* ---- 描画 ---- */

  function escape(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function mount() {
    const box = document.createElement("aside");

    box.className = "td-shop";

    box.innerHTML = `
      <div class="td-shop-head">
        <h2>このページに関連する商品</h2>
        <span class="td-shop-tag">PR</span>
      </div>

      <ul class="td-shop-list">
        ${items.map(item => `
          <li>
            <a href="${escape(item.url)}" target="_blank" rel="nofollow sponsored noopener">
              <div class="td-shop-title">${escape(item.title)}</div>
              ${item.note ? `<div class="td-shop-note">${escape(item.note)}</div>` : ""}
            </a>
          </li>
        `).join("")}
      </ul>

      <p class="td-shop-foot">
        楽天アフィリエイトを利用しています。リンクを経由して購入された場合、
        当サイトに紹介料が支払われることがあります。価格や在庫は変動するため、
        最新の情報は各商品ページでご確認ください。
      </p>
    `;

    const related = document.getElementById("related-tools");

    if (related && related.parentNode) {
      related.parentNode.insertBefore(box, related);
    } else {
      document.body.appendChild(box);
    }
  }

  function start() {
    injectStyle();
    mount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
