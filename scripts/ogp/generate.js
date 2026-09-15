#!/usr/bin/env node
/*
 * OGP画像（1200x630のPNG、ogp/<id>.png）を生成する。
 *
 * scripts/ogp/template.html をヘッドレスブラウザで開き、指定した
 * タイトル・説明文を差し込んでスクリーンショットするだけ。
 * 色・配置は既存のOGP画像から実測してテンプレート側にそろえてある。
 *
 * 使い方:
 *   node scripts/ogp/generate.js <tool-id> [<tool-id> ...]
 *   node scripts/ogp/generate.js --all-missing   # ogp/<id>.png が無いツールだけ生成
 *
 * タイトル・説明文は js/tool-data.js の該当ツール（seoTitle||title,
 * seoDesc||desc）からそのまま読む。
 *
 * Node に playwright-core が必要。Claude Codeのサンドボックス環境では
 * グローバルにインストール済みのplaywrightパッケージの中に入っているが、
 * 素のnodeからは見えないことがあるため、その場合はNODE_PATHを通して
 * 実行すること（インストール場所は環境による）:
 *   NODE_PATH=$(npm root -g)/playwright/node_modules \
 *     node scripts/ogp/generate.js <tool-id>
 * ローカルで動かす場合は `npm i playwright-core` とChromiumの用意が
 * 別途必要。
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const TEMPLATE = path.join(__dirname, "template.html");
const OGP_DIR = path.join(ROOT, "ogp");

function parseTools() {
  const js = fs.readFileSync(path.join(ROOT, "js", "tool-data.js"), "utf8");
  const body = js.slice(js.indexOf("window.TOOLS"));
  const blocks = body.match(/\{[^{}]*?id:\s*"[^"]+"[\s\S]*?\n {2}\}/g) || [];
  const tools = [];
  for (const block of blocks) {
    if (/hidden:\s*true/.test(block)) continue;
    const get = (key) => {
      const m = block.match(new RegExp(key + ':\\s*"([^"]*)"'));
      return m ? m[1] : null;
    };
    const id = get("id");
    if (!id) continue;
    tools.push({
      id,
      title: get("seoTitle") || get("title"),
      desc: get("seoDesc") || get("desc")
    });
  }
  return tools;
}

async function renderOne(chromium, tool) {
  const url =
    "file://" + TEMPLATE +
    "?title=" + encodeURIComponent(tool.title) +
    "&desc=" + encodeURIComponent(tool.desc);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
  await page.goto(url);
  await page.waitForTimeout(100);
  const out = path.join(OGP_DIR, tool.id + ".png");
  await page.screenshot({ path: out });
  await browser.close();
  console.log("wrote", path.relative(ROOT, out));
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("使い方: node scripts/ogp/generate.js <tool-id> [...] | --all-missing");
    process.exit(1);
  }
  const tools = parseTools();
  let targets;
  if (args[0] === "--all-missing") {
    targets = tools.filter((t) => !fs.existsSync(path.join(OGP_DIR, t.id + ".png")));
  } else {
    targets = args.map((id) => {
      const t = tools.find((x) => x.id === id);
      if (!t) throw new Error("tool-data.js に見つからないid: " + id);
      return t;
    });
  }
  if (targets.length === 0) {
    console.log("対象なし");
    return;
  }
  let chromium;
  try {
    chromium = require("playwright-core").chromium;
  } catch (e) {
    console.error(
      "playwright-core が見つからない。NODE_PATHを通して実行すること（このファイル冒頭のコメント参照）。"
    );
    throw e;
  }
  for (const tool of targets) {
    await renderOne(chromium, tool);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
