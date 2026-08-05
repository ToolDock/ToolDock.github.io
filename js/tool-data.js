/* =========================
   サイト全体のツール定義
   title / desc  … パンくず・カード・一覧用の短い表記
   seoTitle / seoDesc … <title>・meta description 用（省略時は title / desc）
   themeColor    … 省略時は #ffffff
========================= */

window.CATEGORY_NAMES = {
  life: "生活",
  work: "業務",
  math: "数学",
  game: "ゲーム"
};

window.TOOLS = [
  {
    id: "roulette",
    title: "Webルーレット",
    desc: "抽選やランダム選択ができる無料ルーレットツール。",
    category: "life",
    url: "/roulette/"
  },

  {
    id: "i_roulette",
    title: "イカサマルーレット",
    desc: "指定した回に思い通りの確率で、思い通りの選択肢を当選させられる、無料イカサマルーレットツール。",
    category: "life",
    url: "/i_roulette/"
  },

  {
    id: "h_roulette",
    title: "ギリギリまで結果が分からないヒリつくルーレット",
    desc: "急加速、急停止、跳ね返り、逆回転、停止時の揺れ...とにかく最後まで読めない無料の激アツルーレットツール。",
    category: "life",
    url: "/h_roulette/"
  },

  {
    id: "fukuri",
    title: "複利計算・積立シミュレーター",
    desc: "細かな設定が豊富な複利計算・投資信託などの積立をシミュレーションするツール。",
    seoTitle: "複利計算・積立シミュレーター",
    seoDesc: "初期投資・積立・リスクを設定し、モンテカルロ法で将来資産をシミュレーションできる複利計算ツールです。設定はブラウザに自動保存されます。",
    category: "life",
    url: "/fukuri/"
  },

  {
    id: "seiza",
    title: "星座占い｜12星座の運勢チェック",
    desc: "簡潔で前向きな星座占い。毎日4時更新です。",
    seoTitle: "今日の星座占い｜12星座ランキング",
    seoDesc: "毎日朝4時更新。12星座の今日の運勢ランキング、ラッキーアイテム、アドバイスをチェック。",
    themeColor: "#111827",
    category: "life",
    url: "/seiza/"
  },

  {
    id: "omikuji",
    title: "おみくじ",
    desc: "大凶から大吉、0.1%の超大吉まで引ける無料おみくじ。結果は紙の画像で保存・共有できます。",
    seoTitle: "おみくじ｜大凶から超大吉まで引ける無料オンラインおみくじ",
    seoDesc: "大凶から大吉に加え、0.1%でしか出ない超大吉が入った無料おみくじ。結果はおみくじ風の紙の画像として保存・共有できます。",
    category: "life",
    url: "/omikuji/"
  },

  {
    id: "todolist",
    title: "Todoリスト",
    desc: "課題や業務の期限を管理できるシンプルなTodoリスト。",
    category: "work",
    url: "/todolist/"
  },

  {
    id: "genkoyosi",
    title: "Web原稿用紙エディタ",
    desc: "字下げ・句読点の扱いなど、原稿用紙の書式で文章を書けるエディタ。",
    category: "work",
    url: "/genkoyosi/"
  },

  {
    id: "timer",
    title: "Webタイマー・ストップウォッチ",
    desc: "シンプルなタイマー・ストップウォッチ。",
    category: "work",
    url: "/timer/"
  },

  {
    id: "makejson",
    title: "JSON成形・圧縮ツール",
    desc: "JSONを成形したり、圧縮したりなど編集をすることができるツール。",
    category: "work",
    url: "/makejson/"
  },

  {
    id: "mojibake",
    title: "文字化け生成・復元ツール",
    desc: "テキスト列を文字化けさせるツール。復元も同じサイトで可能。",
    category: "life",
    url: "/mojibake/"
  },

  {
    id: "seiki",
    title: "regex正規化ツール",
    desc: "regexを正規化するツール。",
    category: "work",
    url: "/seiki/"
  },

  {
    id: "qr",
    title: "QRコード作成ツール",
    desc: "URLやWi-fiをQRコードに変換するツール。",
    category: "work",
    url: "/qr/"
  },

  {
    id: "whichcheap",
    title: "どっちが安い？コスパ計算ツール",
    desc: "複数の容量が異なる商品の、どちらがコスパが良いか、安いかを計算するツール。",
    category: "life",
    url: "/whichcheap/"
  },

  {
    id: "hakohige",
    title: "きれいな箱ひげ図を描写するツール",
    desc: "最小値・第一四分位数・中央値・第三四分位数・最大値を入力し、きれいに箱ひげ図を描くツールです。",
    seoTitle: "箱ひげ図 作成ツール｜五数要約から画像出力",
    seoDesc: "最大値・第三四分位数・中央値・第一四分位数・最小値・平均値から、きれいな箱ひげ図を作成できる無料ツールです。PNG画像として保存可能。",
    category: "math",
    url: "/hakohige/"
  },

  {
    id: "matrix",
    title: "行列計算ツール",
    desc: "行列の計算（逆行列・正規化・固有値など）を行うツール。",
    category: "math",
    url: "/matrix/"
  },

  {
    id: "hakidasi",
    title: "途中式付き・掃き出し法ツール",
    desc: "途中式を付けて、線形代数の行列における掃き出し法（ガウス・ジョルダン法）を行うツール。",
    seoTitle: "掃き出し法ツール｜途中式つき・分数表示対応",
    seoDesc: "行基本変形の途中式を分数のまま表示する無料の掃き出し法（ガウス・ジョルダン法）ツール。行列のランクも判定できます。",
    category: "math",
    url: "/hakidasi/"
  },

  {
    id: "ode",
    title: "途中式付き・微分方程式ツール",
    desc: "途中式を付けて、微分方程式の計算を行うツール。",
    category: "math",
    url: "/ode/"
  },

  {
    id: "radix",
    title: "n進数変換ツール",
    desc: "2進数・8進数・10進数・16進数など、2〜36進法の相互変換を行うツール。小数にも対応。",
    seoTitle: "n進数変換ツール｜2進数・8進数・10進数・16進数をまとめて変換",
    seoDesc: "入力した数値を2進数・8進数・10進数・16進数へ同時に変換できる無料の基数変換ツール。2〜36進法、小数、マイナス、巨大な桁数にも対応しています。",
    category: "math",
    url: "/radix/"
  },

  {
    id: "typing-game",
    title: "横文字ばっかりのタイピングゲーム",
    desc: "やたら横文字しか出てこない、無料のタイピングゲームです。",
    seoTitle: "横文字ばっかりのタイピングゲーム｜無料英語タイピング練習ゲーム",
    seoDesc: "横文字ばっかりの単語を高速入力する無料タイピングゲーム。IT・ビジネス・SNS用語などのカタカナ語をローマ字で入力してスコアを競おう。",
    themeColor: "#00e5ff",
    category: "game",
    url: "/typing-game/"
  },

  {
    id: "kintoku",
    title: "パワプロ2026-2027 金特研究所一覧と獲得できる金特まとめ",
    desc: "パワプロ2026-2027の、マイライフの金特研究所一覧と獲得できる金特まとめです。",
    category: "game",
    url: "/kintoku/"
  },

  {
    id: "counter",
    title: "文字数カウント",
    desc: "原稿用紙換算・全角半角の内訳・X(Twitter)の文字数まで数えられる文字数カウンター。",
    seoTitle: "文字数カウント｜原稿用紙換算・全角半角・X(Twitter)対応の無料文字数カウンター",
    seoDesc: "入力した文章の文字数をリアルタイムで数える無料ツール。改行やスペースを含めるかを設定でき、原稿用紙の枚数、全角・半角の内訳、バイト数、行数、単語数、X(Twitter)の文字数、目標文字数までの残りも同時に確認できます。",
    category: "work",
    url: "/counter/"
  },

  /* 一覧・関連ツールには出さない内部ページ */
  {
    id: "category",
    title: "カテゴリ",
    desc: "カテゴリ別のツール一覧です。",
    category: "",
    url: "/category/",
    hidden: true
  }
];
