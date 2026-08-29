/* =========================
   関連商品（楽天アフィリエイト）

   方針
   - 本文の邪魔をしない。ページ末尾に1ブロックだけ
   - そのページの内容と実際に関係のある商品しか置かない
   - 広告であることを明示する（景品表示法のステマ規制への対応）

   使い方
   PRODUCTS に、ページのパスをキーとして商品を並べる。
   url と image には、楽天アフィリエイトが生成したHTMLに含まれる
   リンクと画像のURLをそのまま入れる。
   画像は楽天が配信するもの（hbb.afl.rakuten.co.jp）を使うこと。
   自前で保存した画像を使うのは楽天の規約で認められていない。
   商品が登録されていないページには、何も表示されない。
========================= */

(() => {

  "use strict";

  /* マイライフ関連の各ページで共有する商品 */
  const PAWAPURO_2026 =
    {
      title: "実況パワフルプロ野球2026-2027（Nintendo Switch）",
      note: "このページで扱っているマイライフを収録したゲーム本体",
      url: "https://hb.afl.rakuten.co.jp/ichiba/5680a356.7b82b269.5680a357.a3a58194/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fyamada-denki%2F2821431018%2F&link_type=picttext&ut=eyJwYWdlIjoiaXRlbSIsInR5cGUiOiJwaWN0dGV4dCIsInNpemUiOiIyNDB4MjQwIiwibmFtIjoxLCJuYW1wIjoicmlnaHQiLCJjb20iOjEsImNvbXAiOiJkb3duIiwicHJpY2UiOjEsImJvciI6MSwiY29sIjoxLCJiYnRuIjoxLCJwcm9kIjowLCJhbXAiOmZhbHNlfQ%3D%3D",
      image: "https://hbb.afl.rakuten.co.jp/hgb/5680a356.7b82b269.5680a357.a3a58194/?me_id=1357621&item_id=10680956&pc=https%3A%2F%2Fthumbnail.image.rakuten.co.jp%2F%400_mall%2Fyamada-denki%2Fcabinet%2Fa07000513%2F2821431018.jpg%3F_ex%3D240x240&s=240x240&t=picttext"
    };

  const PRODUCTS = {

    /* パワプロ2026-2027を扱うページは、どれも同じ本体の話。
       同じ商品を何回も書くと、片方だけ直して食い違うので1つにまとめる */
    "/kintoku/":       [PAWAPURO_2026],
    "/crystal/":       [PAWAPURO_2026],
    "/crystal-banno/": [PAWAPURO_2026],
    "/shippo/":        [PAWAPURO_2026],
    "/eikan-kintoku/": [PAWAPURO_2026],

    "/hakidasi/": [
      {
        title: "チャート式シリーズ 大学教養 線形代数（加藤文元）",
        note: "運営者が実際に使っていた線形代数の演習書です",
        url: "https://hb.afl.rakuten.co.jp/ichiba/56810aaa.3e1f3e18.56810aab.82f597d8/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fbook%2F16269109%2F&link_type=picttext&ut=eyJwYWdlIjoiaXRlbSIsInR5cGUiOiJwaWN0dGV4dCIsInNpemUiOiIyNDB4MjQwIiwibmFtIjoxLCJuYW1wIjoicmlnaHQiLCJjb20iOjEsImNvbXAiOiJkb3duIiwicHJpY2UiOjEsImJvciI6MSwiY29sIjoxLCJiYnRuIjoxLCJwcm9kIjowLCJhbXAiOmZhbHNlfQ%3D%3D",
        image: "https://hbb.afl.rakuten.co.jp/hgb/56810aaa.3e1f3e18.56810aab.82f597d8/?me_id=1213310&item_id=19967706&pc=https%3A%2F%2Fthumbnail.image.rakuten.co.jp%2F%400_mall%2Fbook%2Fcabinet%2F4638%2F9784410154638.jpg%3F_ex%3D240x240&s=240x240&t=picttext"
      }
    ]

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
        border: 1px solid #e7d3cd;
        border-top: 3px solid #bf0000;
        border-radius: 14px;
        background: #fffaf8;
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
        color: #7c2d12;
      }

      .td-shop-tag {
        font-size: 0.72rem;
        font-weight: bold;
        letter-spacing: 0.08em;
        padding: 3px 10px;
        border-radius: 999px;
        background: #bf0000;
        color: #ffffff;
      }

      .td-shop-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 12px;
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .td-shop-list a {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 14px 16px;
        border: 1px solid #ecdcd7;
        border-radius: 12px;
        background: white;
        text-decoration: none;
        color: #1e293b;
        transition: 0.15s;
      }

      .td-shop-list a:hover {
        border-color: #bf0000;
        box-shadow: 0 3px 10px rgba(191, 0, 0, 0.12);
        transform: translateY(-1px);
      }

      .td-shop-img {
        flex-shrink: 0;
        width: 96px;
        height: 96px;
        object-fit: contain;
        border-radius: 8px;
        background: #fafafa;
      }

      .td-shop-body {
        flex: 1;
        min-width: 0;
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

      .td-shop-btn {
        display: inline-block;
        margin-top: 10px;
        padding: 6px 16px;
        border-radius: 999px;
        background: #bf0000;
        color: #ffffff;
        font-size: 0.85rem;
        font-weight: bold;
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
              ${item.image ? `
                <img class="td-shop-img"
                     src="${escape(item.image)}"
                     alt="${escape(item.title)}"
                     width="96" height="96"
                     onerror="this.remove()">
              ` : ""}

              <div class="td-shop-body">
                <div class="td-shop-title">${escape(item.title)}</div>
                ${item.note ? `<div class="td-shop-note">${escape(item.note)}</div>` : ""}
                <span class="td-shop-btn">楽天市場で見る</span>
              </div>
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

    /* 本文（よくある質問）の直後、「人気のページ」より前に置く。

       sidebar.js のほうが先に読み込まれ、
       「人気のページ」を #related-tools の前に差し込む。
       こちらも #related-tools だけを見て入れると、
       そのうしろに回り込んでしまう。
       まず人気のページを探し、無ければ #related-tools を使う */

    const anchor =
      document.querySelector(".td-rail-inline") ||
      document.getElementById("related-tools");

    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(box, anchor);
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
