// 選手一覧の検索（npb/build_players.py が書き出す。/player/players.json を読む）
(function(){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var PAGE = 60;
  var SMALL = {"ぁ":"あ","ぃ":"い","ぅ":"う","ぇ":"え","ぉ":"お","ゃ":"や","ゅ":"ゆ","ょ":"よ","っ":"つ","ゎ":"わ","ゕ":"か","ゖ":"け"};
  var VOWEL = {};
  ["あかさたなはまやらわがざだばぱぁゃゎ", "いきしちにひみりぎじぢびぴぃ", "うくすつぬふむゆるぐずづぶぷぅゅっゔ",
   "えけせてねへめれげぜでべぺぇ", "おこそとのほもよろをごぞどぼぽぉょ"].forEach(function(row, i){
    for (var j = 0; j < row.length; j++) VOWEL[row[j]] = "あいうえお"[i];
  });
  function hira(s){ return String(s || "").replace(/[ァ-ヶ]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) - 0x60); }); }
  function plain(c){ return c.normalize("NFD").replace(/[゙゚]/g, "").normalize("NFC"); }
  function norm(s){ return hira(String(s || "").normalize("NFKC")).replace(/[\s・･.．]/g, "").toLowerCase(); }
  function kanaOnly(s){ return hira(s).replace(/[^ぁ-ゖー]/g, ""); }
  function big(c){ return SMALL[c] || c; }
  function head(s){ s = kanaOnly(s); return big(s.charAt(0)); }
  function tail(s){
    s = kanaOnly(s);
    var c = s.charAt(s.length - 1);
    if (c === "ー") c = VOWEL[s.charAt(s.length - 2)] || "";
    return big(c);
  }
  function letter(v, dak){ var c = big(kanaOnly(v).charAt(0)); return dak ? plain(c) : c; }

  var data = null, list = [], shown = PAGE;
  function reading(o, part){ return part === "sei" ? o.sei : part === "mei" ? o.mei : o.kana; }

  function run(){
    if (!data) return;
    var q = norm($("q").value), team = $("f-team").value, pos = $("f-pos").value,
        t = $("f-t").value, b = $("f-b").value, act = $("f-act").value,
        part = $("s-part").value, dak = $("s-dak").checked, non = $("s-non").checked,
        h = letter($("s-head").value, dak), tl = letter($("s-tail").value, dak);
    var fix = function(c){ return dak ? plain(c) : c; };
    list = data.filter(function(o){
      // 在籍を「現役」にしたときは、いまその球団にいる選手だけ（移籍・退団した選手は除く）
      if (team && (act === "1" ? o.cur !== team : o.teams.indexOf(team) < 0)) return false;
      if (pos && o.pos !== pos) return false;
      if (t && o.hand.indexOf(t) !== 0) return false;
      if (b && o.hand.indexOf(b) < 0) return false;
      if (act !== "" && String(o.active) !== act) return false;
      if (q && o.key.indexOf(q) < 0) return false;
      var r = reading(o, part);
      if ((h || tl || non) && !kanaOnly(r)) return false;
      if (h && fix(head(r)) !== h) return false;
      if (tl && fix(tail(r)) !== tl) return false;
      if (non && tail(r) === "ん") return false;
      return true;
    });
    shown = PAGE;
    render();
    save();
  }

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }

  // 「（いまDeNA・育成）」のような添え書き（所属が成績の最後の球団と違う、育成契約）
  function note(o){
    var xs = [];
    if (o.cur && o.cur !== o.teams[o.teams.length - 1]) xs.push("いま" + esc(o.cur));
    if (o.ik) xs.push("育成");
    return xs.length ? "（" + xs.join("・") + "）" : "";
  }

  function render(){
    var part = $("s-part").value, sh = $("s-head").value || $("s-tail").value;
    var act = list.filter(function(o){ return o.active; }).length;
    $("count").textContent = list.length + "人" + (list.length ? "（うち現役 " + act + "人）" : "") +
      (list.length > shown ? "　上から" + shown + "人を表示" : "");
    $("results").innerHTML = list.slice(0, shown).map(function(o){
      var r = reading(o, part), last = tail(r);
      var yrs = o.first === o.last ? o.first : o.first + "〜" + o.last;
      return '<li><a href="/player/' + o.id + '/">' + esc(o.name) + '</a>' +
        (o.names.length ? '<span class="al">（' + esc(o.names.join("／")) + '）</span>' : '') +
        '<span class="kn">' + esc(r || o.kana) + (sh && last ? ' <b>' + esc(last) + '</b>' : '') + '</span>' +
        '<span class="mt">' + esc(o.pos) + '・' + esc(o.teams.join("→")) + '・' + yrs + (o.active ? '・現役' + note(o) : '') + '</span>' +
        (last && last !== "ん" ? '<button type="button" class="next" data-c="' + esc(last) + '">「' + esc(last) + '」から続ける</button>' : '') +
        '</li>';
    }).join("");
    $("more").hidden = list.length <= shown;
  }

  function save(){
    var p = new URLSearchParams();
    [["q","q"],["team","f-team"],["pos","f-pos"],["t","f-t"],["b","f-b"],["act","f-act"],["part","s-part"],["head","s-head"],["tail","s-tail"]].forEach(function(x){
      var v = $(x[1]).value; if (v && !(x[0] === "part" && v === "full")) p.set(x[0], v);
    });
    if ($("s-dak").checked) p.set("dak", "1");
    if ($("s-non").checked) p.set("non", "1");
    var s = p.toString();
    try { history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + (s ? "#search" : "")); } catch (e) {}
  }

  function load(){
    var p = new URLSearchParams(location.search);
    [["q","q"],["team","f-team"],["pos","f-pos"],["t","f-t"],["b","f-b"],["act","f-act"],["part","s-part"],["head","s-head"],["tail","s-tail"]].forEach(function(x){
      if (p.get(x[0])) $(x[1]).value = p.get(x[0]);
    });
    $("s-dak").checked = p.get("dak") === "1";
    $("s-non").checked = p.get("non") === "1";
  }

  ["q","s-head","s-tail"].forEach(function(id){ $(id).addEventListener("input", run); });
  ["f-team","f-pos","f-t","f-b","f-act","s-part","s-dak","s-non"].forEach(function(id){ $(id).addEventListener("change", run); });
  $("more").addEventListener("click", function(){ shown += PAGE * 2; render(); });
  $("results").addEventListener("click", function(e){
    var btn = e.target.closest("button.next");
    if (!btn) return;
    $("s-head").value = btn.getAttribute("data-c");
    $("s-tail").value = "";
    run();
    $("search").scrollIntoView({behavior: "smooth", block: "start"});
  });

  fetch("/player/players.json").then(function(r){ return r.json(); }).then(function(d){
    var c = {}; d.cols.forEach(function(k, i){ c[k] = i; });
    data = d.rows.map(function(r){
      var o = {}; d.cols.forEach(function(k){ o[k] = r[c[k]]; });
      o.key = norm([o.name, o.kana, o.names.join(" "), o.school].join(" "));
      return o;
    });
    var teams = {};
    data.forEach(function(o){ o.teams.forEach(function(t){ teams[t] = 1; }); });
    var order = ["巨人","阪神","DeNA","横浜","広島","中日","ヤクルト","ソフトバンク","日本ハム","ロッテ","西武","楽天","オリックス"];
    Object.keys(teams).sort(function(a, b){ return (order.indexOf(a) + 99) % 99 - (order.indexOf(b) + 99) % 99; }).forEach(function(t){
      var op = document.createElement("option"); op.textContent = t; $("f-team").appendChild(op);
    });
    load();
    run();
  }).catch(function(){ $("count").textContent = "データを読み込めませんでした。"; });
})();
