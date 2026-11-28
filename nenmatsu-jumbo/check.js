/* 年末ジャンボ2026・ミニの当せん番号チェッカー（/nenmatsu-jumbo/ の「当せん番号を確かめる」）
 *
 * 抽せん（2026-12-31）のあと、下の RESULTS に宝くじ公式サイトの発表のとおり番号を入れる。
 * null のあいだは「抽せん前」として、番号の登録だけできる。
 *
 * 当たりの書き方（wins の1つ1つ）：
 *   k  … 組（"07" など）。全部の数字が合うとき
 *   k1 … 組の下1けた（"7"）。組下1ケタの当たり
 *   （k も k1 も無ければ「各組共通」）
 *   b  … 番号。6けたなら番号そのもの、それより短ければ下の何けたか（"734" なら下3けたが 734）
 * 特別な等級：
 *   zenko: true      … 1等の前後賞。1等の当たりの番号の1つ前と1つ後（組の条件は1等と同じ）
 *   kumichigai: true … 1等の組違い賞。番号が1等と同じで、組だけ違う
 */
"use strict";

const JUMBO_RESULTS = {
    /* 例：
    nenmatsu: [
        { name: "1等", prize: 700000000, wins: [{ k: "07", b: "103734" }] },
        { name: "1等の前後賞", prize: 150000000, zenko: true },
        { name: "1等の組違い賞", prize: 100000, kumichigai: true },
        { name: "2等", prize: 100000000, wins: [{ k: "123", b: "145678" }] },
        { name: "5等", prize: 10000, wins: [{ b: "123" }, { b: "456" }] },
        { name: "7等", prize: 300, wins: [{ b: "5" }] }
    ],
    */
    nenmatsu: null,
    mini: null
};

(function () {
    const KINDS = { nenmatsu: "年末ジャンボ", mini: "年末ジャンボミニ" };
    const STORE = "tooldock-jumbo-check-2026";
    const $ = (id) => document.getElementById(id);
    /* 7億5,000万3,000円 のように */
    const yen = (n) => {
        const oku = Math.floor(n / 1e8), man = Math.floor(n % 1e8 / 1e4), r = n % 1e4;
        const f = (x) => x.toLocaleString("ja-JP");
        const s = (oku ? f(oku) + "億" : "") + (man ? f(man) + "万" : "") + (r ? f(r) : "");
        return (s || "0") + "円";
    };

    let tickets = [];
    try { tickets = JSON.parse(localStorage.getItem(STORE) || "[]") || []; } catch (e) { tickets = []; }
    const save = () => { try { localStorage.setItem(STORE, JSON.stringify(tickets)); } catch (e) { } };

    /* 1つの当たり（w）に、組 kumi・番号 ban の券が合うか */
    function hit(w, kumi, ban) {
        if (w.k != null && Number(w.k) !== kumi) return false;
        if (w.k1 != null && kumi % 10 !== Number(w.k1)) return false;
        const b = String(w.b);
        if (b.length >= 6) return Number(b) === ban;
        return String(ban).slice(-b.length) === b;
    }

    /* 1枚の券のいちばん高い当たり。無ければ null */
    function judge(tiers, kumi, ban) {
        const first = (tiers.find((t) => t.name === "1等") || {}).wins || [];
        let best = null;
        for (const t of tiers) {
            let ok = false;
            if (t.zenko) {
                ok = first.some((w) => String(w.b).length >= 6 &&
                    (hit({ ...w, b: String(Number(w.b) - 1) }, kumi, ban) || hit({ ...w, b: String(Number(w.b) + 1) }, kumi, ban)));
            } else if (t.kumichigai) {
                ok = first.some((w) => Number(w.b) === ban && !hit(w, kumi, ban));
            } else {
                ok = (t.wins || []).some((w) => hit(w, kumi, ban));
            }
            if (ok && (!best || t.prize > best.prize)) best = t;
        }
        return best;
    }

    function render() {
        const body = $("chkRows");
        body.textContent = "";
        let total = 0, hits = 0, count = 0, anyResult = false;
        tickets.forEach((tk, i) => {
            const tiers = JUMBO_RESULTS[tk.kind];
            const li = document.createElement("li");
            const res = [];
            count += tk.n;
            if (tiers) {
                anyResult = true;
                for (let j = 0; j < tk.n; j++) {
                    const ban = tk.ban + j;
                    const t = judge(tiers, tk.kumi, ban);
                    if (t) { res.push(ban + "番：" + t.name + "（" + yen(t.prize) + "）"); total += t.prize; hits++; }
                }
            }
            const t = document.createElement("span");
            t.className = "t";
            t.textContent = KINDS[tk.kind] + "　" + String(tk.kumi).padStart(2, "0") + "組 " +
                (tk.n > 1 ? tk.ban + "〜" + (tk.ban + tk.n - 1) + "番（" + tk.n + "枚）" : tk.ban + "番");
            li.appendChild(t);
            const btn = document.createElement("button");
            btn.type = "button"; btn.className = "sub-btn"; btn.textContent = "消す";
            btn.addEventListener("click", () => { tickets.splice(i, 1); save(); render(); });
            li.appendChild(btn);
            const r = document.createElement("span");
            r.className = "r";
            if (!tiers) r.textContent = "抽せん前";
            else if (res.length) { r.innerHTML = res.map((x) => "<strong>" + x + "</strong>").join("<br>"); li.className = "win"; }
            else r.textContent = "はずれ";
            li.appendChild(r);
            body.appendChild(li);
        });
        const sum = $("chkSum");
        if (!tickets.length) sum.textContent = "";
        else if (!anyResult) sum.textContent = "登録した券：" + count + "枚。抽せんのあと、このページを開くと当たりが出ます。";
        else sum.textContent = "登録した券 " + count + "枚のうち、当たり " + hits + "枚・合計 " + yen(total) + "。";
    }

    function add() {
        const err = $("chkErr");
        err.textContent = "";
        const kind = $("chkKind").value;
        const kumi = Number($("chkKumi").value.trim());
        const banS = $("chkBan").value.trim();
        const n = Number($("chkN").value);
        if (!Number.isInteger(kumi) || kumi < 1 || kumi > 200) { err.textContent = "組は 01〜200 の数字で入れてください。"; return; }
        if (!/^1\d{5}$/.test(banS)) { err.textContent = "番号は 100000〜199999 の6けたで入れてください。"; return; }
        if (!Number.isInteger(n) || n < 1 || n > 1000) { err.textContent = "枚数は 1〜1000 の数字で入れてください。"; return; }
        const ban = Number(banS);
        if (ban + n - 1 > 199999) { err.textContent = "連番の最後が 199999 を超えます。最初の番号を確かめてください。"; return; }
        tickets.push({ kind, kumi, ban, n });
        save();
        $("chkBan").value = "";
        render();
    }

    $("chkAdd").addEventListener("click", add);
    ["chkKumi", "chkBan", "chkN"].forEach((id) => $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") add(); }));

    const ready = JUMBO_RESULTS.nenmatsu || JUMBO_RESULTS.mini;
    $("chkStatus").textContent = ready
        ? "2026年12月31日（木）の抽せんの当せん番号で確かめます。念のため、宝くじ公式サイトの発表とも見比べてください。"
        : "当せん番号は、12月31日（木）の抽せんのあとにここへ載せます。手元の券の組と番号を今のうちに入れておけば、抽せんのあとにこのページを開くだけで当たりが分かります。";
    render();
})();
