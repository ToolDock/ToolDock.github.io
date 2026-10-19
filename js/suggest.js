/* =========================
   検索欄の入力候補

   入力した文字で始まる候補（選手名・金特・特殊能力など）を、検索欄の下に出す。
   各HTMLには書かず、head.js から1回だけ読み込む。

   ページ側の使い方（head.js があとから読み込むので、読み込み前でも呼べる形にしてある）:

     (window.tdSuggest = window.tdSuggest || []).push(function (S) {
       S.attach(document.getElementById("q"), {
         items: function () { return [{ label: "坂本 勇人", keys: ["さかもと・はやと"], sub: "巨人" }]; },
         pick: function (item, input) { ... }   // 省略時は、検索欄に label を入れて input イベントを出す
       });
     });

   - items は、文字を打つたびに呼ぶ（データをあとから読み込むページでも、読み込めた時点から候補が出る）
   - 候補は「入力で始まるもの」を先に、そのあとに「入力を含むもの」を並べる。並びは items の順
   - ひらがな・カタカナ、全角・半角、大文字・小文字、空白と「・」の違いは無視する
========================= */

(() => {

  "use strict";

  if (window.TDSuggest) return;

  const LIMIT = 8;

  /* パワプロの特殊能力・金特のうち、漢字を含む名前の読み（ひらがなで打っても候補に出すため）。
     読みが2通りあり得るものは「|」で並べる */
  const READINGS = {
    "いぶし銀": "いぶしぎん",
    "お祭り男": "おまつりおとこ",
    "かく乱": "かくらん",
    "ささやき戦術": "ささやきせんじゅつ",
    "ささやき破り": "ささやきやぶり",
    "カット打ち": "かっとうち",
    "サヨナラ男": "さよならおとこ",
    "ストライク先行": "すとらいくせんこう",
    "ストライク送球": "すとらいくそうきゅう",
    "ダメ押し": "だめおし",
    "ド根性": "どこんじょう",
    "ノミの心臓": "のみのしんぞう",
    "バズーカ送球": "ばずーかそうきゅう",
    "バント職人": "ばんとしょくにん",
    "フル出場": "ふるしゅつじょう",
    "ホーム死守": "ほーむししゅ",
    "ホーム突入": "ほーむとつにゅう",
    "マルチ弾": "まるちだん",
    "ミート多用": "みーとたよう",
    "メッタ打ち": "めったうち",
    "一球入魂": "いっきゅうにゅうこん",
    "一発": "いっぱつ",
    "三振": "さんしん",
    "不屈の魂": "ふくつのたましい",
    "主砲キラー": "しゅほうきらー",
    "乱調": "らんちょう",
    "人気者": "にんきもの",
    "代打〇": "だいだ",
    "代打の神様": "だいだのかみさま",
    "伝説のサヨナラ男": "でんせつのさよならおとこ",
    "低め〇": "ひくめ",
    "低球必打": "ていきゅうひつだ",
    "併殺": "へいさつ",
    "全開": "ぜんかい",
    "内角必打": "ないかくひつだ",
    "内角攻め": "ないかくぜめ|ないかくせめ",
    "内角無双": "ないかくむそう",
    "内野安打〇": "ないやあんだ",
    "切り込み隊長": "きりこみたいちょう",
    "初球〇": "しょきゅう",
    "力配分": "ちからはいぶん",
    "勝ち運": "かちうん",
    "勝利の星": "しょうりのほし",
    "勝負師": "しょうぶし",
    "四球": "しきゅう|ふぉあぼーる",
    "回またぎ〇": "かいまたぎ",
    "固め打ち": "かためうち",
    "国際大会✕": "こくさいたいかい",
    "国際大会〇": "こくさいたいかい",
    "変化球中心": "へんかきゅうちゅうしん",
    "変幻自在": "へんげんじざい",
    "夏男": "なつおとこ",
    "外角必打": "がいかくひつだ",
    "大番狂わせ": "おおばんくるわせ",
    "奪三振": "だつさんしん",
    "威圧感": "いあつかん",
    "存在感": "そんざいかん",
    "守備職人": "しゅびしょくにん",
    "安全圏〇": "あんぜんけん",
    "安打製造機": "あんだせいぞうき",
    "完全燃焼": "かんぜんねんしょう",
    "寸前": "すんぜん",
    "対エース〇": "たいえーす",
    "対ストレート〇": "たいすとれーと",
    "対ランナー〇": "たいらんなー",
    "対変化球〇": "たいへんかきゅう",
    "対強打者〇": "たいきょうだしゃ",
    "尻上がり": "しりあがり",
    "左キラー": "ひだりきらー",
    "左腕キラー": "さわんきらー",
    "帳尻合わせ": "ちょうじりあわせ",
    "広角打法": "こうかくだほう",
    "広角砲": "こうかくほう",
    "引っ張り屋": "ひっぱりや",
    "強心臓": "きょうしんぞう",
    "強振多用": "きょうしんたよう",
    "怪物球威": "かいぶつきゅうい",
    "怪童": "かいどう",
    "恐怖の満塁男": "きょうふのまんるいおとこ",
    "悪球打ち": "あっきゅううち|あくきゅううち",
    "意外性": "いがいせい",
    "慎重打法": "しんちょうだほう",
    "慎重盗塁": "しんちょうとうるい",
    "扇風機": "せんぷうき",
    "打球反応〇": "だきゅうはんのう",
    "投手位置右": "とうしゅいちみぎ",
    "投手位置左": "とうしゅいちひだり",
    "投打躍動": "とうだやくどう",
    "抜け球": "ぬけだま|ぬけきゅう",
    "春男": "はるおとこ",
    "暴れ球": "あばれだま|あばれきゅう",
    "本塁打厳禁": "ほんるいだげんきん",
    "根性〇": "こんじょう",
    "死球集中": "しきゅうしゅうちゅう",
    "気迫ヘッド": "きはくへっど",
    "決勝打": "けっしょうだ",
    "流し打ち": "ながしうち",
    "渾身の決勝打": "こんしんのけっしょうだ",
    "満塁男": "まんるいおとこ",
    "火事場の馬鹿力": "かじばのばかぢから|かじばのばかちから",
    "火消し": "ひけし",
    "牽制〇": "けんせい",
    "球持ち〇": "たまもち",
    "球界の頭脳": "きゅうかいのずのう",
    "球速安定": "きゅうそくあんてい",
    "真っスラ": "まっすら",
    "短気": "たんき",
    "秋男": "あきおとこ",
    "積極守備": "せっきょくしゅび",
    "積極打法": "せっきょくだほう",
    "積極盗塁": "せっきょくとうるい",
    "積極走塁": "せっきょくそうるい",
    "窮地○": "きゅうち",
    "立ち上がり〇": "たちあがり",
    "粘り打ち": "ねばりうち",
    "精密機械": "せいみつきかい",
    "精神的支柱": "せいしんてきしちゅう",
    "終盤力": "しゅうばんりょく",
    "緊急登板〇": "きんきゅうとうばん",
    "緩急〇": "かんきゅう",
    "芸術的流し打ち": "げいじゅつてきながしうち",
    "荒れ球": "あれだま|あれきゅう",
    "要所〇": "ようしょ",
    "調子安定": "ちょうしあんてい",
    "調子極端": "ちょうしきょくたん",
    "負け運": "まけうん",
    "走者釘付": "そうしゃくぎづけ",
    "超投打躍動": "ちょうとうだやくどう",
    "軽い球": "かるいたま",
    "逃げ球": "にげだま|にげきゅう",
    "逆境〇": "ぎゃっきょう",
    "逆襲": "ぎゃくしゅう",
    "速球中心": "そっきゅうちゅうしん",
    "選球眼": "せんきゅうがん",
    "重い球": "おもいたま",
    "重戦車": "じゅうせんしゃ",
    "鉄の壁": "てつのかべ",
    "鉄人": "てつじん",
    "鉄腕": "てつわん",
    "闘志": "とうし",
    "闘魂": "とうこん",
    "電光石火": "でんこうせっか",
    "驚異の切れ味": "きょういのきれあじ",
    "高球必打": "こうきゅうひつだ",
    "高速チャージ": "こうそくちゃーじ",
    "高速ベースラン": "こうそくべーすらん",
    "高速レーザー": "こうそくれーざー",
    "魔術師": "まじゅつし"
  };

  function norm(s) {
    return String(s || "")
      .normalize("NFKC")
      .replace(/[ァ-ヶ]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60))
      .replace(/[\s・･.．]/g, "")
      .toLowerCase();
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function injectStyle() {
    if (document.getElementById("td-suggest-style")) return;
    const style = document.createElement("style");
    style.id = "td-suggest-style";
    style.textContent = `
      .td-suggest {
        position: fixed;
        z-index: 10000;
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        list-style: none;
        max-height: 320px;
        overflow-y: auto;
        background: #fff;
        border: 1px solid #bcbab2;
        border-top: 0;
        font-family: "Noto Sans JP","Hiragino Kaku Gothic ProN","Hiragino Sans",Meiryo,sans-serif;
        text-align: left;
      }
      .td-suggest[hidden] { display: none; }
      .td-suggest li {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin: 0;
        padding: 8px 12px;
        border-top: 1px solid #e6e4de;
        color: #1c1d1f;
        font-size: 15px;
        line-height: 1.4;
        cursor: pointer;
      }
      .td-suggest li:first-child { border-top: 0; }
      .td-suggest li[aria-selected="true"],
      .td-suggest li:hover { background: #f4f3ef; }
      .td-suggest b { font-weight: 700; }
      .td-suggest small {
        margin-left: auto;
        padding-left: 8px;
        font-size: 12px;
        color: #1c1d1f;
        white-space: nowrap;
      }
    `;
    document.head.appendChild(style);
  }

  let uid = 0;

  function attach(input, opts) {
    if (!input || input.dataset.tdSuggest) return;
    input.dataset.tdSuggest = "1";
    injectStyle();

    const list = document.createElement("ul");
    list.className = "td-suggest";
    list.id = "td-suggest-" + (++uid);
    list.setAttribute("role", "listbox");
    list.hidden = true;
    document.body.appendChild(list);

    input.setAttribute("autocomplete", "off");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id);
    input.setAttribute("aria-expanded", "false");

    const limit = opts.limit || LIMIT;
    let shown = [], active = -1, cache = null, cacheSrc = null;

    /* items の結果ごとに、比べる文字列を1回だけ作っておく */
    function prepared() {
      const src = opts.items() || [];
      if (src !== cacheSrc) {
        cacheSrc = src;
        cache = src.map(it => ({
          it,
          keys: [it.label].concat(it.keys || [], (READINGS[it.label] || "").split("|")).map(norm).filter(Boolean)
        }));
      }
      return cache;
    }

    function place() {
      const r = input.getBoundingClientRect();
      list.style.left = r.left + "px";
      list.style.top = r.bottom + "px";
      list.style.width = Math.max(r.width, 220) + "px";
    }

    function close() {
      list.hidden = true;
      active = -1;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    function open() {
      const q = norm(input.value);
      if (!q) return close();
      const head = [], part = [];
      for (const p of prepared()) {
        if (p.keys.some(k => k.startsWith(q))) head.push(p.it);
        else if (part.length < limit && p.keys.some(k => k.includes(q))) part.push(p.it);
        if (head.length >= limit) break;
      }
      shown = head.concat(part).slice(0, limit);
      // 入力がそのまま候補1つと同じなら、もう出さない
      if (!shown.length || (shown.length === 1 && norm(shown[0].label) === q)) return close();
      active = -1;
      list.innerHTML = shown.map((it, i) =>
        `<li role="option" id="${list.id}-${i}" data-i="${i}" aria-selected="false"><b>${esc(it.label)}</b>` +
        (it.sub ? `<small>${esc(it.sub)}</small>` : "") + "</li>").join("");
      place();
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    function highlight(i) {
      active = i;
      list.querySelectorAll("li").forEach((li, n) => li.setAttribute("aria-selected", n === i ? "true" : "false"));
      const li = list.children[i];
      if (li) {
        li.scrollIntoView({ block: "nearest" });
        input.setAttribute("aria-activedescendant", li.id);
      }
    }

    function choose(i) {
      const it = shown[i];
      if (!it) return;
      close();
      if (opts.pick) {
        opts.pick(it, input);
      } else {
        input.value = it.value != null ? it.value : it.label;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    input.addEventListener("input", open);
    input.addEventListener("focus", () => { if (input.value) open(); });
    input.addEventListener("blur", () => setTimeout(close, 150));

    input.addEventListener("keydown", e => {
      if (list.hidden || e.isComposing) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        highlight((active + 1) % shown.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        highlight(active <= 0 ? shown.length - 1 : active - 1);
      } else if (e.key === "Enter" && active >= 0) {
        e.preventDefault();
        choose(active);
      } else if (e.key === "Escape") {
        close();
      }
    });

    // 押した瞬間に検索欄からフォーカスが外れて閉じないよう、mousedown で止める
    list.addEventListener("mousedown", e => e.preventDefault());
    list.addEventListener("click", e => {
      const li = e.target.closest("li");
      if (li) choose(+li.dataset.i);
    });

    window.addEventListener("scroll", () => { if (!list.hidden) place(); }, { passive: true, capture: true });
    window.addEventListener("resize", () => { if (!list.hidden) place(); });
  }

  const api = { attach, norm };
  window.TDSuggest = api;

  // 読み込みより前にページが頼んでおいた分を実行し、以後はすぐ実行する
  const queued = Array.isArray(window.tdSuggest) ? window.tdSuggest : [];
  window.tdSuggest = { push: fn => fn(api) };
  queued.forEach(fn => fn(api));

})();
