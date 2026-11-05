/* =========================
   広告枠

   方針
   - 本文を覆う大きな広告は置かない
   - 下から小さく出るバー（閉じられる）と、ページ末尾の1枠だけ

   AdSense 本体のスクリプトは、各HTMLの <head> に静的に記述してある。
   所有権の確認クローラは JavaScript を実行する前のソースを見るため、
   ここから動的に差し込む方式では検出されない。
   このファイルが受け持つのは広告枠の描画だけ。

   AdSense で作成した広告ユニットのスロットIDを SLOT_STICKY / SLOT_END に入れる。
   直したら js/head.js の PARTS_VERSION を1つ上げる。
========================= */

(() => {

  "use strict";

  /* 各HTMLに書いてある番号と揃えること */
  const CLIENT = "ca-pub-8349615939902537";

  /* 広告の枠を出すかどうか（2026-11-05 承認） */
  const UNITS_ENABLED = true;

  /* 番号が空の枠は出さない */
  const SLOT_STICKY = "2304525201";   /* 「下のバー」ユニット（固定 320×50） */
  const SLOT_END = "8286258434";      /* 「ページ末尾」ユニット */
  const SLOT_RAIL = "3354505118";     /* 「右の列」ユニット（レスポンシブ）。右レールの先頭 */

  /* 右レールが出る幅（js/sidebar.js の WIDE と揃える） */
  const RAIL_WIDE = "(min-width: 1200px)";

  /* 下のバーを出し始めるスクロール量 */
  const STICKY_AFTER = 600;

  const DISMISS_KEY = "tooldock-ad-sticky-closed";

  if (!CLIENT) return;

  /* 本文の無い案内のページ（運営者情報・お問い合わせ・プライバシーポリシー・カテゴリ一覧）には広告を置かない */
  const NO_AD_PATHS = ["/about/", "/contact/", "/privacy/", "/category/"];
  if (NO_AD_PATHS.indexOf(location.pathname) >= 0) return;

  function pushAd() {
    (window.adsbygoogle = window.adsbygoogle || []).push({});
  }

  /* ---- スタイル ---- */

  function injectStyle() {
    const style = document.createElement("style");

    style.textContent = `
      /* 右レールの先頭の枠。レールの中身は幅260pxほど */
      /* 300×250 を入れるため、レールの左右の余白（20px）まで広げて幅300pxにする */
      .td-ad-rail {
        margin: 0 -20px 22px;
        text-align: center;
      }

      /* 広告が来なかった枠は、見出しごと隠す */
      .td-ad-end:has(ins[data-ad-status="unfilled"]),
      .td-ad-rail:has(ins[data-ad-status="unfilled"]) {
        display: none;
      }

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

      /* 下のバーが出ている間は、右下の「Top」ボタンをバーの上に逃がす（バーの × が隠れないように） */
      .td-pagetop {
        transition: opacity 0.2s, visibility 0.2s, bottom 0.25s ease-out;
      }

      @media (max-width: 1199px) {
        body.td-adbar-on .td-pagetop {
          bottom: 82px;
        }
      }

      /* 右レールが出ている画面では、レールの下に潜り込ませない */
      @media (min-width: 1200px) {
        .td-ad-sticky {
          right: 300px;
        }
      }
    `;

    document.head.appendChild(style);
  }

  /* ---- ページ末尾の枠 ---- */

  /* ---- 右レールの先頭の枠 ----
     大きさは 300×250 に決める（AdSense のユニットも固定 300×250）。data-ad-format="auto" に任せると、
     縦に長い広告（幅240×高さ900ほど）が来て、レールが広告で埋まった（2026-11-05）。
     レスポンシブのユニットは、ins に幅と高さを書き data-ad-format を外すと、その大きさに収まる広告になる。
     レールは js/sidebar.js が作る。狭い画面ではレールが隠れ、中身は本文の下に移るが、
     そこにはページ末尾の枠があるので、この枠はレールが出ているときだけ置く。
     隠れた場所で push すると幅0で失敗するので、狭い画面で開いたときは、広げたときに初めて置く */

  function mountRailSlot() {
    const rail = document.querySelector(".td-rail");
    if (!rail) return;

    const mq = window.matchMedia(RAIL_WIDE);

    const mount = () => {
      if (rail.querySelector(".td-ad-rail")) return;

      const box = document.createElement("div");

      box.className = "td-ad-rail";

      box.innerHTML = `
        <div class="td-ad-label">スポンサーリンク</div>
        <ins class="adsbygoogle"
             style="display:inline-block;width:300px;height:250px"
             data-ad-client="${CLIENT}"
             data-ad-slot="${SLOT_RAIL}"></ins>
      `;

      rail.insertBefore(box, rail.firstChild);

      pushAd();
    };

    if (mq.matches) {
      mount();
    } else {
      const onChange = () => {
        if (!mq.matches) return;
        mq.removeEventListener("change", onChange);
        mount();
      };
      mq.addEventListener("change", onChange);
    }
  }

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
      document.body.classList.remove("td-adbar-on");

      try { sessionStorage.setItem(DISMISS_KEY, "1"); } catch (e) { /* 保存できなくても動作に影響はない */ }

      setTimeout(() => bar.remove(), 300);
    });

    /* 広告が入ったときだけ出す。AdSense は枠に data-ad-status="filled" / "unfilled" を書く。
       入る前から出していると、中が空の白い帯が本文を隠していた（2026-11-05） */
    const ins = bar.querySelector("ins");
    let filled = false;
    let scrolled = false;

    const show = () => {
      if (!filled || !scrolled || !bar.isConnected) return;
      bar.classList.add("shown");
      document.body.classList.add("td-adbar-on");
    };

    const onStatus = () => {
      const status = ins.getAttribute("data-ad-status");
      if (status === "filled") {
        filled = true;
        show();
      } else if (status === "unfilled") {
        bar.remove();                 /* 広告が来なかったときは、帯ごと片付ける */
        document.body.classList.remove("td-adbar-on");
      }
    };

    new MutationObserver(onStatus).observe(ins, { attributes: true, attributeFilter: ["data-ad-status"] });
    onStatus();

    /* ある程度読み進めてから出す */
    const onScroll = () => {
      if (window.scrollY > STICKY_AFTER) {
        scrolled = true;
        window.removeEventListener("scroll", onScroll);
        show();
      }
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---- 起動 ---- */

  function start() {
    /* 枠を出すのは承認後だけ。それまでは何もしない */
    if (!UNITS_ENABLED) return;

    injectStyle();
    if (SLOT_END) mountEndSlot();
    if (SLOT_STICKY) mountStickySlot();
    if (SLOT_RAIL) mountRailSlot();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
