/* =========================
   Google Analytics (gtag.js)
   全ページ共通。各HTMLへの直書きはここに集約。
========================= */

const GA_ID = "G-CZ668PDGPM";

const gaScript = document.createElement("script");

gaScript.async = true;
gaScript.src =
  "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;

document.head.appendChild(gaScript);

window.dataLayer = window.dataLayer || [];

function gtag(){
  dataLayer.push(arguments);
}

gtag('js', new Date());

gtag('config', GA_ID);
