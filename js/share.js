/* =========================
   共有ボタン

   全ページの本文の終わりに「このページを共有」を出す。
   各HTMLには書かず、head.js から1回だけ読み込む
   （head.js を読まないトップページは、そのHTMLから直接読む）。

   ツールの結果を共有したいページ（ルーレットなど）は、
   TDShare.attach(要素, () => 共有する文章) で、結果の下に
   「コピー・X・LINE」のボタンを付けられる。
========================= */

(() => {

  "use strict";

  if (window.TDShare) return;

  const SITE_NAME = "ToolDock";

  function pageUrl() {
    const c = document.querySelector('link[rel="canonical"]');
    return c ? c.href : location.origin + location.pathname;
  }

  /* 共有の文章に使うページ名。「 | ToolDock」は付けない（URLで分かる） */
  function pageTitle() {
    return document.title.replace(/\s*[|｜]\s*ToolDock\s*$/, "").trim();
  }

  function intents(text, url) {
    const t = encodeURIComponent(text);
    const u = encodeURIComponent(url);
    return {
      x: `https://x.com/intent/post?text=${t}&url=${u}`,
      line: `https://social-plugins.line.me/lineit/share?url=${u}&text=${t}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
      hatena: `https://b.hatena.ne.jp/entry/panel/?url=${u}`
    };
  }

  /* クリップボードへ。使えない環境では、選択してコピーする昔の方法に切り替える */
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise((resolve, reject) => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy") ? resolve() : reject(new Error("copy"));
      } catch (e) {
        reject(e);
      } finally {
        ta.remove();
      }
    });
  }

  /* ボタンを押した直後に「コピーしました」と出して、少ししたら戻す */
  function flash(btn, label) {
    const original = btn.dataset.label || btn.textContent;
    btn.dataset.label = original;
    btn.textContent = label;
    btn.classList.add("is-done");
    clearTimeout(btn._timer);
    btn._timer = setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove("is-done");
    }, 1800);
  }

  function injectStyle() {
    if (document.getElementById("td-share-style")) return;

    const style = document.createElement("style");
    style.id = "td-share-style";

    /* ページ側のCSSに左右されないよう、見た目に関わるものはここで言い切る */
    style.textContent = `
      .td-share {
        box-sizing: border-box;
        clear: both;
        margin: 36px 0 0;
        padding: 16px 0 0;
        border-top: 1px solid var(--line, #d8d6cf);
        text-align: left;
        font-family: "Noto Sans JP","Hiragino Kaku Gothic ProN","Hiragino Sans",Meiryo,sans-serif;
      }

      .td-share-title {
        margin: 0 0 10px;
        padding: 0;
        border: 0;
        background: none;
        font-size: 14px;
        font-weight: 700;
        line-height: 1.5;
        color: inherit;
        text-align: left;
      }

      .td-share-buttons {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 0;
        padding: 0;
      }

      .td-share-buttons a,
      .td-share-buttons button {
        box-sizing: border-box;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: auto;
        min-width: 0;
        min-height: 36px;
        margin: 0;
        padding: 6px 14px;
        border: 1px solid transparent;
        border-radius: 3px;
        box-shadow: none;
        font: inherit;
        font-size: 13.5px;
        font-weight: 700;
        line-height: 1.2;
        letter-spacing: 0;
        text-decoration: none;
        cursor: pointer;
        color: #fff;
        transform: none;
      }

      .td-share-buttons a:hover,
      .td-share-buttons button:hover {
        filter: brightness(0.9);
        transform: none;
      }

      .td-share-x { background: #000; }
      .td-share-line { background: #06c755; }
      .td-share-facebook { background: #1877f2; }
      .td-share-hatena { background: #00a4de; }

      .td-share-copy,
      .td-share-more {
        background: #fff !important;
        color: #1c1d1f !important;
        border-color: #bcbab2 !important;
      }

      .td-share-buttons .is-done {
        background: #1c1d1f !important;
        color: #fff !important;
        border-color: #1c1d1f !important;
      }

      /* ツールの結果の共有（ルーレットなど） */
      .td-share-result {
        box-sizing: border-box;
        max-width: 440px;
        margin: 16px auto 18px;
        text-align: left;
      }

      .td-share-result[hidden] { display: none; }

      .td-share-result textarea {
        box-sizing: border-box;
        display: block;
        width: 100%;
        margin: 0 0 8px;
        padding: 10px 12px;
        border: 1px solid #bcbab2;
        border-radius: 3px;
        background: #fff;
        color: #1c1d1f;
        font: inherit;
        font-size: 14px;
        line-height: 1.7;
        resize: none;
      }

      .td-share-result .td-share-buttons { justify-content: center; }
    `;

    document.head.appendChild(style);
  }

  /* ボタンの並び。text はクリックしたときに読む（結果が変わっても最新を共有する） */
  function buttons(getText, opts = {}) {
    const row = document.createElement("div");
    row.className = "td-share-buttons";

    const url = () => opts.url || pageUrl();

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "td-share-copy";
    copyBtn.textContent = opts.copyLabel || "リンクをコピー";
    copyBtn.addEventListener("click", () => {
      const body = opts.copyText ? opts.copyText() : url();
      copy(body).then(() => flash(copyBtn, "コピーしました"), () => flash(copyBtn, "コピーできませんでした"));
    });

    const links = [
      ["x", "Xでポスト"],
      ["line", "LINEで送る"]
    ];
    if (!opts.compact) {
      links.push(["facebook", "Facebook"], ["hatena", "はてブ"]);
    }

    for (const [key, label] of links) {
      const a = document.createElement("a");
      a.className = `td-share-${key}`;
      a.textContent = label;
      a.href = "#";
      a.target = "_blank";
      a.rel = "noopener";
      /* 押した時点の文章とURLで開く */
      a.addEventListener("click", () => {
        a.href = intents(getText(), url())[key];
      });
      row.appendChild(a);
    }

    row.insertBefore(copyBtn, opts.copyFirst ? row.firstChild : null);

    /* スマホでは、端末の共有メニュー（ほかのアプリ）も出せる */
    if (navigator.share) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "td-share-more";
      more.textContent = "ほかのアプリ";
      more.addEventListener("click", () => {
        navigator.share({ title: pageTitle(), text: getText(), url: url() }).catch(() => {});
      });
      row.appendChild(more);
    }

    return row;
  }

  /* ---- ページの共有 ---- */

  function mountPageShare() {
    if (document.querySelector(".td-share")) return;

    const section = document.createElement("section");
    section.className = "td-share";
    section.setAttribute("aria-label", "このページを共有");

    const title = document.createElement("p");
    title.className = "td-share-title";
    title.textContent = "このページを共有";
    section.appendChild(title);

    section.appendChild(buttons(() => pageTitle()));

    /* 本文の終わりに置く。
       1. 解説の記事（.tool-article / article）があれば、その最後のものの直後
       2. なければ、見出しの帯と同じ入れ物（後ろに同じ種類の入れ物が続けば、その最後のもの）のいちばん最後
       3. 入れ物が body のときや帯の無いページは、人気のページ・関連ツール・フッターの手前 */
    const outside = (el) => el.closest(".td-rail, .td-rail-inline, #related-tools, .td-footer, .td-share");
    const articles = [...document.querySelectorAll(".tool-article, article")].filter((a) => !outside(a));
    const lastArticle = articles[articles.length - 1];

    if (lastArticle) {
      lastArticle.insertAdjacentElement("afterend", section);
      return;
    }

    const banner = document.querySelector(".td-banner");
    let box = banner && banner.parentElement;

    if (box && box !== document.body) {
      /* ツールの箱のあとに、同じ種類の箱で使い方が続くページは、その最後の箱に置く */
      const kind = box.classList[0];
      let next = box.nextElementSibling;
      while (kind && next) {
        if (next.tagName === box.tagName && next.classList.contains(kind)) box = next;
        next = next.nextElementSibling;
      }
      box.appendChild(section);
      return;
    }

    const before = document.querySelector(".td-rail-inline")
      || document.getElementById("related-tools")
      || document.querySelector(".td-footer");

    if (before) before.parentNode.insertBefore(section, before);
    else document.body.appendChild(section);
  }

  /* ---- ツールの結果の共有 ----
     after の直後に、共有する文章（コピー用）とボタンを置く。
     getText() はその時点の結果の文章（URLは含めない。共有のときに付ける） */
  function attach(after, getText) {
    injectStyle();

    const box = document.createElement("div");
    box.className = "td-share-result";
    box.hidden = true;

    const ta = document.createElement("textarea");
    ta.readOnly = true;
    ta.rows = 4;
    ta.setAttribute("aria-label", "共有する文章");
    box.appendChild(ta);

    const full = () => `${getText()}\n${pageUrl()}`;

    box.appendChild(buttons(getText, {
      compact: true,
      copyFirst: true,
      copyLabel: "結果をコピー",
      copyText: full
    }));

    after.insertAdjacentElement("afterend", box);

    return {
      /* 結果が出たら呼ぶ。文章を作り直して表示する */
      update() {
        ta.value = full();
        ta.rows = Math.min(8, ta.value.split("\n").length);
        box.hidden = false;
      }
    };
  }

  window.TDShare = { attach, copy, pageUrl, pageTitle };

  function start() {
    injectStyle();
    mountPageShare();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
