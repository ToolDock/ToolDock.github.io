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
  const SLOT_STICKY = "2304525201";   /* 「下のバー」ユニット（固定 320×50）。狭い画面用 */
  const SLOT_STICKY_BIG = "9370755728"; /* 「下のバー（大）」ユニット。広い画面（iPad・PC）で 728×90 にする */
  const SLOT_END = "8286258434";      /* 「ページ末尾」ユニット */
  const SLOT_RAIL = "3354505118";     /* 「右の列」ユニット（レスポンシブ）。右レールの先頭 */
  const SLOT_SHARE = "8162823719";    /* 「共有の上」ユニット（レスポンシブ）。「このページを共有」の直前の細い枠 */

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

  /* 画面の下端からこの距離まで近づいたら、広告を取りに行く。
     ページ末尾・共有の上は、開いた時点で読み込むと9割以上が見られないまま終わり、
     視認可能率が1割を切っていた（2026-11-08）。見られない表示は単価を下げるので、
     近づいてから読み込む（枠の場所と大きさは先に取っておくので、表示がずれることはない） */
  const LAZY_MARGIN = "0px 0px 400px 0px";

  function whenNear(el, fn) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    const io = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { io.disconnect(); fn(); }
    }, { rootMargin: LAZY_MARGIN });
    io.observe(el);
  }

  function injectStyle() {
    const style = document.createElement("style");

    style.textContent = `
      /* 右レールの先頭の枠。レールの中身は幅260pxほど */
      /* 300×250 を入れるため、レールの左右の余白（20px）まで広げて幅300pxにする */
      .td-ad-rail {
        margin: 0 -20px 22px;
        text-align: center;
      }

      /* レールの一番下の枠。レールは最後まで見えたら止まるので、そこからページの最後まで映り続ける */
      .td-ad-rail.td-ad-rail-end {
        margin: 22px -20px 0;
      }

      /* 広告が来なかった枠は隠し、1つも来なければ見出しごと隠す */
      .td-ad-end ins[data-ad-status="unfilled"] {
        display: none !important;
      }

      .td-ad-end:not(:has(ins:not([data-ad-status="unfilled"]))),
      .td-ad-rail:has(ins[data-ad-status="unfilled"]),
      .td-ad-share:has(ins[data-ad-status="unfilled"]) {
        display: none;
      }

      .td-ad-end {
        max-width: 1000px;
        margin: 32px auto 0;
        text-align: center;
      }

      /* 300×250 を、広い画面では2つ横に、狭い画面では1つ */
      .td-ad-end .td-ad-pair {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 20px;
      }

      /* 「このページを共有」の上の細い枠。共有のボタンと同じく左にそろえる */
      .td-ad-share {
        clear: both;
        margin: 32px 0 0;
        text-align: left;
      }

      .td-ad-share .td-ad-label {
        text-align: left;
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

      /* 大きいバー（728×90）は高さがあるので、どの幅でもその上に逃がす */
      body.td-adbar-on:has(.td-ad-sticky.big) .td-pagetop {
        bottom: 122px;
      }

      /* 右レールが出ている画面では、レールの下に潜り込ませない。
         レールの無いページ（トップなど）では、画面の右端まで伸ばす */
      @media (min-width: 1200px) {
        body:has(.td-rail) .td-ad-sticky {
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

    /* 先頭と一番下の2か所。同じユニットを2回使う（一番下は、レールが止まってから映り続ける） */
    const make = (extra) => {
      const box = document.createElement("div");

      box.className = "td-ad-rail" + (extra ? " " + extra : "");

      box.innerHTML = `
        <div class="td-ad-label">スポンサーリンク</div>
        <ins class="adsbygoogle"
             style="display:inline-block;width:300px;height:250px"
             data-ad-client="${CLIENT}"
             data-ad-slot="${SLOT_RAIL}"></ins>
      `;

      return box;
    };

    const mount = () => {
      if (rail.querySelector(".td-ad-rail")) return;

      rail.insertBefore(make(""), rail.firstChild);
      rail.appendChild(make("td-ad-rail-end"));   /* js/sidebar.js は、レールの中身をこの枠の手前に入れる */

      pushAd();
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

  /* ---- 「このページを共有」の上の細い枠 ----
     よくある質問の下、共有のボタンの上。大きさは共有のボタンの並び（幅506pxほど）に合わせて 468×60、
     狭い画面（ボタンが2段になる）では 320×50。目立たせないよう、細いバナーだけにする。
     共有の欄は js/share.js が作り、このファイルより後に動くので、ひと呼吸おいてから置く */

  function mountShareSlot() {
    const share = document.querySelector(".td-share");
    if (!share || document.querySelector(".td-ad-share")) return;

    const box = document.createElement("div");
    box.className = "td-ad-share";
    share.parentNode.insertBefore(box, share);

    const wide = box.clientWidth >= 480;
    const w = wide ? 468 : 320, h = wide ? 60 : 50;

    box.innerHTML = `
      <div class="td-ad-label">スポンサーリンク</div>
      <ins class="adsbygoogle"
           style="display:inline-block;width:${w}px;height:${h}px"
           data-ad-client="${CLIENT}"
           data-ad-slot="${SLOT_SHARE}"></ins>
    `;

    whenNear(box, pushAd);
  }

  function mountEndSlot() {
    const box = document.createElement("div");

    box.className = "td-ad-end";

    /* 300×250。横いっぱいのレスポンシブだと、PCで横1400×縦500pxほどの大きな枠になり、
       文字だけの広告で埋まりがちだった（2026-11-06）。並べて入る幅（640px）があれば2つ並べる */
    const unit = () => `
      <ins class="adsbygoogle"
           style="display:inline-block;width:300px;height:250px"
           data-ad-client="${CLIENT}"
           data-ad-slot="${SLOT_END}"></ins>`;

    box.innerHTML = `
      <div class="td-ad-label">スポンサーリンク</div>
      <div class="td-ad-pair">${unit()}</div>
    `;

    const related = document.getElementById("related-tools");

    if (related && related.parentNode) {
      related.parentNode.insertBefore(box, related.nextSibling);
    } else {
      document.body.appendChild(box);
    }

    /* 幅は置いてから測る（ページごとに本文の幅が違うため） */
    const pair = box.querySelector(".td-ad-pair");
    const count = pair.clientWidth >= 640 ? 2 : 1;
    if (count === 2) pair.insertAdjacentHTML("beforeend", unit());

    whenNear(box, () => { for (let n = 0; n < count; n++) pushAd(); });
  }

  /* ---- 下から出るバー ---- */

  function mountStickySlot() {
    if (sessionStorage.getItem(DISMISS_KEY) === "1") return;

    const bar = document.createElement("div");

    bar.className = "td-ad-sticky";

    /* 横に 728×90 と × ボタンが収まる画面では大きい枠にする。
       右レールが出る幅（1200px以上）では、バーはレールの左までなので、その分を引いて測る */
    const avail = window.innerWidth >= 1200 ? window.innerWidth - 300 : window.innerWidth;
    const big = SLOT_STICKY_BIG && avail >= 790;
    const [w, h, slot] = big ? [728, 90, SLOT_STICKY_BIG] : [320, 50, SLOT_STICKY];
    if (big) bar.classList.add("big");

    bar.innerHTML = `
      <ins class="adsbygoogle"
           style="display:inline-block;width:${w}px;height:${h}px"
           data-ad-client="${CLIENT}"
           data-ad-slot="${slot}"></ins>
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
    if (SLOT_SHARE) setTimeout(mountShareSlot, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
