/* =========================
   共通フッター

   全ページの末尾に、サイト内リンク・表示切り替え・著作権表記を出す。
   各HTMLには書かず、head.js から1回だけ読み込む。

   リンク先は実在するページのみ。存在しないページへ誘導すると
   利用者にとっても検索エンジンにとっても不利益になる。
========================= */

(() => {

  "use strict";

  const SITE_NAME = "ToolDock";
  const START_YEAR = 2026;

  /* 表示モードの保存先。PC表示を選んだ端末だけ記憶する */
  const VIEW_KEY = "tooldock-view";

  const LINKS = [
    { href: "/", label: "ホーム" },
    { href: "/category/", label: "ツール一覧" },
    { href: "/about/", label: "このサイトについて" },
    { href: "/contact/", label: "お問い合わせ" },
    { href: "/privacy/", label: "プライバシーポリシー" },
    { href: "/privacy/#ads", label: "広告について" }
  ];

  /* =========================
     表示モード（PC / モバイル）

     viewport の指定を差し替えることで、狭い画面でも
     PC と同じ横幅で表示できるようにする。
     画面が広い端末では viewport が効かず切り替えても何も
     起きないため、その場合はボタン自体を出さない。
  ========================= */

  function viewportTag() {
    let meta = document.querySelector('meta[name="viewport"]');

    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "viewport";
      document.head.appendChild(meta);
    }

    return meta;
  }

  function applyView(mode) {
    const meta = viewportTag();

    /* content を書き換えるだけでは反映されない環境があるため、
       いったん外してから入れ直す */
    const next = mode === "pc"
      ? "width=1100"
      : "width=device-width, initial-scale=1.0";

    if (meta.getAttribute("content") === next) return;

    meta.remove();

    const fresh = document.createElement("meta");
    fresh.name = "viewport";
    fresh.content = next;

    document.head.appendChild(fresh);
  }

  function currentView() {
    try {
      return localStorage.getItem(VIEW_KEY) === "pc" ? "pc" : "mobile";
    } catch (e) {
      return "mobile";
    }
  }

  function setView(mode) {
    try {
      if (mode === "pc") localStorage.setItem(VIEW_KEY, "pc");
      else localStorage.removeItem(VIEW_KEY);
    } catch (e) {
      /* 保存できなくても、そのページ内では切り替わる */
    }

    applyView(mode);
    render();
  }

  /* 切り替えが意味を持つのは、viewport が効く狭い画面だけ */
  function switchable() {
    return window.screen.width <= 900 || currentView() === "pc";
  }

  /* =========================
     スタイル
  ========================= */

  function injectStyle() {
    if (document.getElementById("td-footer-style")) return;

    const style = document.createElement("style");
    style.id = "td-footer-style";

    style.textContent = `
      .td-footer {
        margin-top: 60px;
        padding: 0;
        background:
          repeating-linear-gradient(
            -45deg,
            rgba(255, 255, 255, 0.06) 0 6px,
            rgba(255, 255, 255, 0) 6px 12px
          ),
          linear-gradient(180deg, #0ea5e9 0%, #0284c7 100%);
        color: #ffffff;
        font-size: 15px;
        line-height: 1.9;
        box-sizing: border-box;
      }

      .td-footer * {
        box-sizing: border-box;
      }

      .td-view {
        padding: 12px 20px;
        background: #ffffff;
        color: #334155;
        text-align: center;
        font-size: 15px;
      }

      .td-view button {
        width: auto;
        margin: 0 4px;
        padding: 2px 8px;
        border: 0;
        border-radius: 6px;
        background: none;
        color: #0284c7;
        font-size: 15px;
        font-family: inherit;
        cursor: pointer;
        text-decoration: underline;
      }

      .td-view button:hover {
        background: #e0f2fe;
      }

      .td-view button[aria-current="true"] {
        color: #0f172a;
        font-weight: bold;
        text-decoration: none;
        cursor: default;
      }

      .td-view .td-view-sep {
        color: #cbd5e1;
      }

      .td-footer-inner {
        max-width: 1000px;
        margin: 0 auto;
        padding: 26px 20px 18px;
      }

      .td-footer-links {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 6px 20px;
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .td-footer-links a {
        color: #ffffff;
        text-decoration: none;
      }

      .td-footer-links a:hover {
        text-decoration: underline;
      }

      .td-copyright {
        margin: 22px 0 0;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.3);
        text-align: center;
        font-size: 13px;
        color: rgba(255, 255, 255, 0.9);
      }

      /* ページ先頭へ戻る */
      .td-pagetop {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 9999;

        width: 56px;
        height: 56px;
        padding: 0;

        border: 0;
        border-radius: 50%;

        background: #0284c7;
        color: #ffffff;

        font-size: 11px;
        font-family: inherit;
        line-height: 1.2;

        cursor: pointer;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);

        opacity: 0;
        visibility: hidden;
        transition: opacity 0.2s, visibility 0.2s;
      }

      .td-pagetop.is-shown {
        opacity: 1;
        visibility: visible;
      }

      .td-pagetop:hover {
        background: #0369a1;
      }

      .td-pagetop span {
        display: block;
        font-size: 15px;
      }

      @media print {
        .td-footer,
        .td-pagetop {
          display: none !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  /* =========================
     描画
  ========================= */

  let footerEl = null;

  function render() {
    if (!footerEl) return;

    const view = currentView();

    const viewRow = switchable()
      ? `
        <div class="td-view">
          表示：
          <button type="button" data-view="pc"
                  aria-current="${view === "pc"}">PC</button>
          <span class="td-view-sep">|</span>
          <button type="button" data-view="mobile"
                  aria-current="${view === "mobile"}">モバイル</button>
        </div>
      `
      : "";

    const year = new Date().getFullYear();
    const years = year > START_YEAR ? `${START_YEAR}-${year}` : `${START_YEAR}`;

    footerEl.innerHTML = `
      ${viewRow}

      <div class="td-footer-inner">
        <ul class="td-footer-links">
          ${LINKS.map(l => `<li><a href="${l.href}">${l.label}</a></li>`).join("")}
        </ul>

        <p class="td-copyright">© ${years} ${SITE_NAME}</p>
      </div>
    `;

    for (const btn of footerEl.querySelectorAll("[data-view]")) {
      btn.addEventListener("click", () => setView(btn.dataset.view));
    }
  }

  /* =========================
     画面の端から端まで伸ばす

     style.css が body に max-width:900px を掛けているため、
     そのままでは本文と同じ幅で止まってしまう。
     body の位置を実測して、左端をビューポートの左端に合わせる。

     右レールは position:fixed で全高を覆うので、
     表示されているときはその幅だけ手前で止める。
  ========================= */

  let topBtn = null;

  function fullBleed() {
    if (!footerEl) return;

    const cs = getComputedStyle(document.body);
    const bodyRect = document.body.getBoundingClientRect();

    const padLeft = parseFloat(cs.paddingLeft) || 0;
    const borderLeft = parseFloat(cs.borderLeftWidth) || 0;

    const rail = document.querySelector(".td-rail");

    const railWidth = rail && getComputedStyle(rail).display !== "none"
      ? rail.getBoundingClientRect().width
      : 0;

    /* clientWidth はスクロールバーを含まないため、
       これを使うと横スクロールが発生しない */
    const viewport = document.documentElement.clientWidth;

    footerEl.style.marginLeft =
      -(bodyRect.left + borderLeft + padLeft) + "px";

    footerEl.style.width = (viewport - railWidth) + "px";

    if (topBtn) {
      topBtn.style.right = (railWidth + 18) + "px";
    }
  }

  function mount() {
    injectStyle();

    footerEl = document.createElement("footer");
    footerEl.className = "td-footer";

    document.body.appendChild(footerEl);

    render();

    /* ページ先頭へ戻るボタン */
    const top = document.createElement("button");

    top.type = "button";
    top.className = "td-pagetop";
    top.setAttribute("aria-label", "ページの先頭へ戻る");
    top.innerHTML = `<span aria-hidden="true">▲</span>Top`;

    top.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    document.body.appendChild(top);
    topBtn = top;

    const onScroll = () => {
      top.classList.toggle("is-shown", window.scrollY > 400);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    fullBleed();

    /* レールの表示切り替えや画面の回転に追従させる */
    let resizeTimer = null;

    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(fullBleed, 120);
    });

    /* 右レールは footer.js より後に読み込まれることがあるため、
       描画が落ち着いた時点でもう一度測り直す */
    window.addEventListener("load", fullBleed);
    setTimeout(fullBleed, 300);
  }

  /* 保存された表示モードは、描画前に当てておく */
  if (currentView() === "pc") applyView("pc");

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }

})();
