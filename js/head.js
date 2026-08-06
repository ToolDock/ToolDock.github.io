/* =========================
   共通<head>生成
   charset / viewport は各HTMLに静的記述、
   gtag は analytics.js が担当。ここは
   ページ固有のメタ情報だけを出力する。
========================= */

const SITE_NAME = "ToolDock";
const SITE_ORIGIN = "https://tooldock.github.io";

const tool = TOOLS.find(t => t.id === CURRENT_TOOL);

if (!tool) {
  console.error("Tool not found:", CURRENT_TOOL);
}

function escapeAttr(str){
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* =========================
   HEAD
========================= */

if (tool) {

  /* seoTitle / seoDesc があれば検索結果用にそちらを優先し、
     title / desc はパンくず・カード表示用の短い名前として使う */

  const metaTitle =
    `${tool.seoTitle || tool.title} | ${SITE_NAME}`;

  const metaDesc = tool.seoDesc || tool.desc;

  const pageUrl = SITE_ORIGIN + tool.url;

  /* title / description / canonical は各HTMLに静的記述してある。
     Googlebot が最初のクロール（JS実行前）で読めるようにするためで、
     ここでは既に無い場合だけ補う。この判定が成立するよう、
     静的タグは必ずこのスクリプトより前に置くこと。 */

  const hasTitle = !!document.querySelector("title");
  const hasDesc = !!document.querySelector('meta[name="description"]');
  const hasCanonical = !!document.querySelector('link[rel="canonical"]');

  /* OGP画像はツールごとに用意している（/ogp/<id>.png）。
     一覧などの内部ページはサイト共通の既定画像を使う */

  const ogImage = tool.hidden
    ? `${SITE_ORIGIN}/ogp.png`
    : `${SITE_ORIGIN}/ogp/${tool.id}.png`;

  document.write(`

    <link rel="icon"
          href="/favicon.ico">

    <link rel="stylesheet"
          href="/style.css">

    ${hasTitle ? "" : `<title>${escapeAttr(metaTitle)}</title>`}

    ${hasDesc ? "" : `<meta name="description"
          content="${escapeAttr(metaDesc)}">`}

    <meta property="og:type"
          content="website">

    <meta property="og:site_name"
          content="${SITE_NAME}">

    <meta property="og:title"
          content="${escapeAttr(metaTitle)}">

    <meta property="og:description"
          content="${escapeAttr(metaDesc)}">

    <meta property="og:url"
          content="${pageUrl}">

    <meta property="og:image"
          content="${ogImage}">

    <meta property="og:image:width"
          content="1200">

    <meta property="og:image:height"
          content="630">

    <meta property="og:locale"
          content="ja_JP">

    <meta name="twitter:card"
          content="summary_large_image">

    <meta name="theme-color"
          content="${tool.themeColor || "#ffffff"}">

    ${hasCanonical ? "" : `<link rel="canonical"
          href="${pageUrl}">`}

  `);
}

/* =========================
   共通CSS
========================= */

const style = document.createElement("style");

style.textContent = `

  .breadcrumb{
    font-size:14px;
    color:#666;
    padding:12px 20px;
    margin-bottom:10px;
    line-height:1.6;
    word-break:break-word;
  }

  .breadcrumb a{
    color:#2563eb;
    text-decoration:none;
  }

  .breadcrumb a:hover{
    text-decoration:underline;
  }

  .bc-sep{
    margin:0 6px;
    color:#999;
  }

`;

document.head.appendChild(style);

/* =========================
   DOM Ready
========================= */

document.addEventListener("DOMContentLoaded", () => {

  if (!tool) return;

  /* =========================
     カテゴリ名
     ※ category/index.html と同じ対応表
  ========================= */

  const categoryLabel =
    CATEGORY_NAMES[tool.category]
    || tool.category;

  /* =========================
     パンくず
     カテゴリを持たないページ（カテゴリ一覧など）では出さない
  ========================= */

  if (!tool.hidden) {

    const nav = document.createElement("nav");

    nav.className = "breadcrumb";

    nav.setAttribute(
      "aria-label",
      "パンくずリスト"
    );

    nav.innerHTML = `
      <a href="/">${SITE_NAME}</a>

      <span class="bc-sep">›</span>

      <a href="/category/?cat=${encodeURIComponent(tool.category)}">
        ${categoryLabel}
      </a>

      <span class="bc-sep">›</span>

      <span>${tool.title}</span>
    `;

    document.body.prepend(nav);

    /* =========================
       Breadcrumb JSON-LD
    ========================= */

    addJsonLd({
      "@context": "https://schema.org",

      "@type": "BreadcrumbList",

      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": SITE_NAME,
          "item": `${SITE_ORIGIN}/`
        },

        {
          "@type": "ListItem",
          "position": 2,
          "name": categoryLabel,
          "item":
            `${SITE_ORIGIN}/category/?cat=${encodeURIComponent(tool.category)}`
        },

        {
          "@type": "ListItem",
          "position": 3,
          "name": tool.title,
          "item": SITE_ORIGIN + tool.url
        }
      ]
    });
  }

  /* =========================
     WebSite JSON-LD
  ========================= */

  addJsonLd({
    "@context": "https://schema.org",

    "@type": "WebSite",

    "name": SITE_NAME,

    "url": `${SITE_ORIGIN}/`
  });

});

function addJsonLd(data){
  const script =
    document.createElement("script");

  script.type = "application/ld+json";

  script.textContent = JSON.stringify(data);

  document.head.appendChild(script);
}

/* =========================
   共通パーツの読み込み
   右レールと広告枠。各HTMLに書かず、ここから1回だけ読み込む
========================= */

for (const src of ["/js/sidebar.js", "/js/ads.js"]) {
  const partScript = document.createElement("script");

  partScript.src = src;

  /* 動的に足したスクリプトは既定で非同期になるため、
     順序を保つために明示的に切っておく */
  partScript.async = false;

  document.head.appendChild(partScript);
}
