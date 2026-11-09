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

  /* 番号が空の枠は出さない。
     AdSense のユニットはどれもレスポンシブ型（2026-11-09）。ins に幅と高さを書き、data-ad-format を
     付けないので、実際の大きさはここで決めた大きさになる */
  const SLOT_STICKY = "2304525201";   /* 「下のバー」ユニット。狭い画面で 320×50 */
  const SLOT_STICKY_BIG = "9370755728"; /* 「下のバー（大）」ユニット。広い画面（iPad・PC）で 728×90 にする */
  const SLOT_END = "8286258434";      /* 「ページ末尾」ユニット */
  const SLOT_RAIL = "3354505118";     /* 「右の列」ユニット（レスポンシブ）。右レールの先頭 */
  const SLOT_TOP = "7810262044";      /* 「上の帯」ユニット。パンくずのすぐ下、本文の上の横長の枠 */
  const SLOT_RELATED = "8162823719";  /* 「同じカテゴリのツール」の上の細い枠。いまは「共有の上」と同じユニットを使う */
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
  const LAZY_PX = 400;

  /* 注意：adsbygoogle.push({}) は「どの枠を埋めるか」を指定できず、ページの中でまだ埋まっていない
     最初の ins から順に埋める。遅らせる枠の ins を先に置いておくと、ほかの枠（下のバーなど）の push が
     その枠を先に埋めてしまい、下のバーがページの最後まで来ないと出なかった（2026-11-09）。
     遅らせる枠は、近づくまで同じ大きさの空の箱（.td-ad-ph）だけを置き、近づいたら ins に差し替えて push する */
  function placeholder(w, h) {
    return `<div class="td-ad-ph" data-w="${w}" data-h="${h}" style="display:inline-block;width:${w}px;height:${h}px"></div>`;
  }

  function fillPlaceholders(box, slot) {
    const phs = box.querySelectorAll(".td-ad-ph");
    phs.forEach(ph => {
      const ins = document.createElement("ins");
      ins.className = "adsbygoogle";
      ins.style.cssText = `display:inline-block;width:${ph.dataset.w}px;height:${ph.dataset.h}px`;
      ins.setAttribute("data-ad-client", CLIENT);
      ins.setAttribute("data-ad-slot", slot);
      ph.replaceWith(ins);
    });
    phs.forEach(() => pushAd());
  }

  function whenNear(el, fn) {
    /* IntersectionObserver は「交わる／交わらない」が切り替わったときしか知らせないので、
       一気に下まで飛ぶと（画面の下→画面の上へ）、一度も知らせが来ない。スクロールのたびに位置を見る */
    let done = false;
    const check = () => {
      if (done || !el.isConnected) return;
      if (el.getBoundingClientRect().top < window.innerHeight + LAZY_PX) {
        done = true;
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
        fn();
      }
    };
    let queued = false;
    const onScroll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; check(); });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    check();
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

      .td-ad-end:not(:has(ins:not([data-ad-status="unfilled"]), .td-ad-ph)),
      .td-ad-rail:has(ins[data-ad-status="unfilled"]),
      .td-ad-share:has(ins[data-ad-status="unfilled"]),
      .td-ad-related:has(ins[data-ad-status="unfilled"]),
      .td-ad-top:has(ins[data-ad-status="unfilled"]) {
        display: none;
      }

      /* ページ上の横長の枠。中央にそろえる */
      .td-ad-top {
        margin: 0 auto 14px;
        text-align: center;
        line-height: 0;
      }

      .td-ad-top .td-ad-label {
        line-height: 1.4;
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

      /* 「同じカテゴリのツール」の上の細い枠。共有の上と同じ形 */
      .td-ad-related {
        clear: both;
        margin: 32px 0 0;
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
     大きさは 300×250 に決める。data-ad-format="auto" に任せると、
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
     よくある質問の下、共有のボタンの上。細い横長のバナーだけにする。
     PC・iPad（幅740px以上）では 728×90（2026-11-09、468×60 から大きくした）、
     その間は 468×60、スマホ（ボタンが2段になる）では 320×50。
     共有の欄は js/share.js が作り、このファイルより後に動くので、ひと呼吸おいてから置く */

  function mountShareSlot() {
    const share = document.querySelector(".td-share");
    if (!share || document.querySelector(".td-ad-share")) return;

    const box = document.createElement("div");
    box.className = "td-ad-share";
    share.parentNode.insertBefore(box, share);

    fillBanner(box, SLOT_SHARE);
  }

  /* 細い横長の枠の中身。幅に応じて 728×90（PC・iPad）／468×60／320×50（スマホ）。
     近づいてから読み込む */
  function fillBanner(box, slot) {
    const cw = box.clientWidth;
    const [w, h] = cw >= 740 ? [728, 90] : cw >= 480 ? [468, 60] : [320, 50];

    box.innerHTML = `
      <div class="td-ad-label">スポンサーリンク</div>
      ${placeholder(w, h)}
    `;

    whenNear(box, () => fillPlaceholders(box, slot));
  }

  /* ---- 「同じカテゴリのツール」の上の細い枠 ----
     共有の上と同じ形。「同じカテゴリのツール」の欄が無いページには置かない */
  function mountRelatedSlot() {
    const related = document.getElementById("related-tools");
    if (!related || !related.parentNode || document.querySelector(".td-ad-related")) return;

    const box = document.createElement("div");
    box.className = "td-ad-related";
    related.parentNode.insertBefore(box, related);

    fillBanner(box, SLOT_RELATED);
  }

  /* ---- ページ上の帯 ----
     パンくずのすぐ下（ツールの見出しの上）。開いた瞬間に見える場所なので、すぐ読み込む。
     広い画面では 728×90、狭い画面では 320×50。枠の高さは先に取っておくので、
     広告が入ったときにツールの位置がずれることはない（来なかったときは枠ごと隠す）。
     パンくずの無いページ（トップ・カテゴリ一覧・お問い合わせなど）には置かない */

  function mountTopSlot() {
    const crumb = document.querySelector("nav.breadcrumb");
    if (!crumb || document.querySelector(".td-ad-top")) return;

    const box = document.createElement("div");
    box.className = "td-ad-top";
    crumb.parentNode.insertBefore(box, crumb.nextSibling);

    const wide = box.clientWidth >= 740;
    const w = wide ? 728 : 320, h = wide ? 90 : 50;

    box.innerHTML = `
      <div class="td-ad-label">スポンサーリンク</div>
      <ins class="adsbygoogle"
           style="display:inline-block;width:${w}px;height:${h}px"
           data-ad-client="${CLIENT}"
           data-ad-slot="${SLOT_TOP}"></ins>
    `;

    pushAd();
  }

  function mountEndSlot() {
    const box = document.createElement("div");

    box.className = "td-ad-end";

    /* 300×250。横いっぱいのレスポンシブだと、PCで横1400×縦500pxほどの大きな枠になり、
       文字だけの広告で埋まりがちだった（2026-11-06）。並べて入る幅（640px）があれば2つ並べる */
    const unit = () => placeholder(300, 250);

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

    whenNear(box, () => fillPlaceholders(box, SLOT_END));
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
    if (SLOT_TOP) mountTopSlot();
    if (SLOT_END) mountEndSlot();
    if (SLOT_STICKY) mountStickySlot();
    if (SLOT_RAIL) mountRailSlot();
    if (SLOT_SHARE) setTimeout(mountShareSlot, 0);
    if (SLOT_RELATED) setTimeout(mountRelatedSlot, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

})();
