/*
 * タイピング練習（/typing-game/）の問題とローマ字の判定、結果の計算。
 * ページとランキングのサーバー（Google Apps Script。scripts/gas/typing-ranking.gs）で同じものを使う。
 *
 * ■ 問題を足したり判定を変えたりしたら VERSION を1つ上げ、
 *   このファイルを Apps Script の「engine.gs」に貼り直して、デプロイを更新すること。
 *   （サーバーと版が違うと、ランキングの登録を受け付けない）
 */
var TDT = (function () {
"use strict";
const VERSION = 1;

/* =========================================================
   問題（表示|よみ）
========================================================= */
const SENT = `今日はいい天気ですね|きょうはいいてんきですね
明日の朝は早めに起きます|あしたのあさははやめにおきます
駅の近くに新しいパン屋ができた|えきのちかくにあたらしいぱんやができた
冷蔵庫のプリンを食べたのは誰だ|れいぞうこのぷりんをたべたのはだれだ
週末は家でゆっくり映画を見たい|しゅうまつはいえでゆっくりえいがをみたい
傘を持っていけばよかった|かさをもっていけばよかった
締め切りは来週の金曜日です|しめきりはらいしゅうのきんようびです
電車が遅れているらしい|でんしゃがおくれているらしい
猫が日なたで丸くなっている|ねこがひなたでまるくなっている
夏休みの宿題がまだ終わらない|なつやすみのしゅくだいがまだおわらない
一度決めたことは最後までやり通す|いちどきめたことはさいごまでやりとおす
失敗は成功のもと|しっぱいはせいこうのもと
急がば回れ|いそがばまわれ
石の上にも三年|いしのうえにもさんねん
早起きは三文の徳|はやおきはさんもんのとく
好きこそものの上手なれ|すきこそもののじょうずなれ
塵も積もれば山となる|ちりもつもればやまとなる
百聞は一見にしかず|ひゃくぶんはいっけんにしかず
七転び八起き|ななころびやおき
雨降って地固まる|あめふってじかたまる
備えあれば憂いなし|そなえあればうれいなし
習うより慣れろ|ならうよりなれろ
能ある鷹は爪を隠す|のうあるたかはつめをかくす
犬も歩けば棒に当たる|いぬもあるけばぼうにあたる
花より団子|はなよりだんご
九回裏ツーアウト満塁のチャンス|きゅうかいうらつーあうとまんるいのちゃんす
コンビニでおにぎりを二つ買った|こんびにでおにぎりをふたつかった
スマートフォンの充電が切れそうだ|すまーとふぉんのじゅうでんがきれそうだ
来月から新しいプロジェクトが始まる|らいげつからあたらしいぷろじぇくとがはじまる
会議の資料を印刷しておいてください|かいぎのしりょうをいんさつしておいてください
お先に失礼します|おさきにしつれいします
よろしくお願いいたします|よろしくおねがいいたします
少々お待ちください|しょうしょうおまちください
図書館で静かに本を読む|としょかんでしずかにほんをよむ
自転車で海沿いの道を走る|じてんしゃでうみぞいのみちをはしる
晩ごはんはカレーライスにしよう|ばんごはんはかれーらいすにしよう
窓を開けると涼しい風が入ってきた|まどをあけるとすずしいかぜがはいってきた
指を正しい位置に置いてから打ち始めよう|ゆびをただしいいちにおいてからうちはじめよう
手元を見ないで打てるようになりたい|てもとをみないでうてるようになりたい
正確に打つことが速さへの近道|せいかくにうつことがはやさへのちかみち
春になると桜の花が咲きます|はるになるとさくらのはながさきます
秋は食欲の季節だ|あきはしょくよくのきせつだ
冬の夜空に星がきらめく|ふゆのよぞらにほしがきらめく
夕焼けで空がオレンジ色に染まる|ゆうやけでそらがおれんじいろにそまる
引っ越しの荷物がようやく片付いた|ひっこしのにもつがようやくかたづいた
新幹線の切符を予約した|しんかんせんのきっぷをよやくした
熱いお茶をいれて一休みしよう|あついおちゃをいれてひとやすみしよう
ファミリーレストランで待ち合わせ|ふぁみりーれすとらんでまちあわせ
パーティーの準備はもう済んだ|ぱーてぃーのじゅんびはもうすんだ
ヴァイオリンの音色が美しい|ゔぁいおりんのねいろがうつくしい
待ちに待った週末がやってきた|まちにまったしゅうまつがやってきた
思い立ったが吉日|おもいたったがきちじつ
宝くじが当たったら何をしよう|たからくじがあたったらなにをしよう
打ち間違えても落ち着いて続けよう|うちまちがえてもおちついてつづけよう
地図アプリを見ながら歩く|ちずあぷりをみながらあるく
洗濯物を取り込むのを忘れていた|せんたくものをとりこむのをわすれていた
机の上を片付けると集中できる|つくえのうえをかたづけるとしゅうちゅうできる
朝の満員電車はとても疲れる|あさのまんいんでんしゃはとてもつかれる
野菜もしっかり食べましょう|やさいもしっかりたべましょう
目覚まし時計が鳴る前に起きた|めざましどけいがなるまえにおきた
旅行の写真を整理する|りょこうのしゃしんをせいりする
雪が降ったら雪だるまを作ろう|ゆきがふったらゆきだるまをつくろう
夜更かしは体によくない|よふかしはからだによくない
昨日より今日、今日より明日|きのうよりきょうきょうよりあした
一歩ずつ前に進もう|いっぽずつまえにすすもう
お気に入りの喫茶店で読書する|おきにいりのきっさてんでどくしょする
次の駅で乗り換えてください|つぎのえきでのりかえてください
ご注文はお決まりですか|ごちゅうもんはおきまりですか
領収書をいただけますか|りょうしゅうしょをいただけますか
鉛筆を削ってから試験に臨む|えんぴつをけずってからしけんにのぞむ
本日は晴天なり|ほんじつはせいてんなり
月がとてもきれいですね|つきがとてもきれいですね
打鍵の音が心地よい|だけんのおとがここちよい
キーボードを新しくしたら速くなった|きーぼーどをあたらしくしたらはやくなった
練習は裏切らない|れんしゅうはうらぎらない
迷ったら楽しいほうを選ぶ|まよったらたのしいほうをえらぶ
東京駅から新大阪駅まで|とうきょうえきからしんおおさかえきまで
北海道でおいしい海鮮丼を食べた|ほっかいどうでおいしいかいせんどんをたべた
沖縄の海は透き通っている|おきなわのうみはすきとおっている
富士山の頂上で日の出を見る|ふじさんのちょうじょうでひのでをみる
締めの一杯はラーメンに限る|しめのいっぱいはらーめんにかぎる
ちょっとそこまで散歩してくる|ちょっとそこまでさんぽしてくる
雨の日は家でのんびり過ごす|あめのひはいえでのんびりすごす
年末は大掃除で忙しい|ねんまつはおおそうじでいそがしい
新しい靴で出かけよう|あたらしいくつででかけよう
温泉に入って疲れを取る|おんせんにはいってつかれをとる
誕生日おめでとうございます|たんじょうびおめでとうございます
最後まで諦めない|さいごまであきらめない
継続は力なり|けいぞくはちからなり
案ずるより産むが易し|あんずるよりうむがやすし
笑う門には福来る|わらうかどにはふくきたる
千里の道も一歩から|せんりのみちもいっぽから
チームワークで勝利をつかむ|ちーむわーくでしょうりをつかむ
ウェブサイトを毎日更新する|うぇぶさいとをまいにちこうしんする
ティッシュを箱ごと持ってきて|てぃっしゅをはこごともってきて
フォークとナイフを並べる|ふぉーくとないふをならべる
ジェットコースターに乗りたい|じぇっとこーすたーにのりたい
金曜日の夜は気分が軽い|きんようびのよるはきぶんがかるい
ペンギンがよちよち歩いている|ぺんぎんがよちよちあるいている
入場券は窓口で買えます|にゅうじょうけんはまどぐちでかえます
六時に駅の改札で会おう|ろくじにえきのかいさつであおう
隣の家から焼き魚のにおいがする|となりのいえからやきざかなのにおいがする`;

const WORDS = `猫|ねこ
桜|さくら
新幹線|しんかんせん
図書館|としょかん
自転車|じてんしゃ
冷蔵庫|れいぞうこ
洗濯機|せんたくき
扇風機|せんぷうき
加湿器|かしつき
電子レンジ|でんしれんじ
天気予報|てんきよほう
誕生日|たんじょうび
夏休み|なつやすみ
運動会|うんどうかい
修学旅行|しゅうがくりょこう
卒業式|そつぎょうしき
入学式|にゅうがくしき
遊園地|ゆうえんち
水族館|すいぞくかん
動物園|どうぶつえん
美術館|びじゅつかん
映画館|えいがかん
喫茶店|きっさてん
郵便局|ゆうびんきょく
交差点|こうさてん
横断歩道|おうだんほどう
駐車場|ちゅうしゃじょう
北海道|ほっかいどう
沖縄|おきなわ
名古屋|なごや
富士山|ふじさん
太平洋|たいへいよう
地球儀|ちきゅうぎ
望遠鏡|ぼうえんきょう
顕微鏡|けんびきょう
時刻表|じこくひょう
目覚まし時計|めざましどけい
鉛筆|えんぴつ
消しゴム|けしごむ
教科書|きょうかしょ
黒板|こくばん
給食|きゅうしょく
体育館|たいいくかん
満塁ホームラン|まんるいほーむらん
卓球|たっきゅう
陸上競技|りくじょうきょうぎ
将棋|しょうぎ
切手|きって
小包|こづつみ
新聞|しんぶん
辞書|じしょ
百科事典|ひゃっかじてん
炊飯器|すいはんき
味噌汁|みそしる
卵焼き|たまごやき
唐揚げ|からあげ
茶碗蒸し|ちゃわんむし
肉じゃが|にくじゃが
お好み焼き|おこのみやき
回転寿司|かいてんずし
抹茶|まっちゃ
金平糖|こんぺいとう
天ぷら|てんぷら
牛丼|ぎゅうどん
親子丼|おやこどん
紅茶|こうちゃ
牛乳|ぎゅうにゅう
一石二鳥|いっせきにちょう
十人十色|じゅうにんといろ
一期一会|いちごいちえ
試行錯誤|しこうさくご
臨機応変|りんきおうへん
起承転結|きしょうてんけつ
以心伝心|いしんでんしん
自画自賛|じがじさん
半信半疑|はんしんはんぎ
前代未聞|ぜんだいみもん
温故知新|おんこちしん
一生懸命|いっしょうけんめい
有言実行|ゆうげんじっこう
電光石火|でんこうせっか
春夏秋冬|しゅんかしゅうとう
花鳥風月|かちょうふうげつ
七転八倒|しちてんばっとう
紆余曲折|うよきょくせつ
単刀直入|たんとうちょくにゅう
優柔不断|ゆうじゅうふだん
正々堂々|せいせいどうどう
一心不乱|いっしんふらん
冒険|ぼうけん
宇宙|うちゅう
銀河|ぎんが
流れ星|ながれぼし
台風|たいふう
紅葉|こうよう
雪だるま|ゆきだるま
風鈴|ふうりん
花火|はなび
盆踊り|ぼんおどり
年賀状|ねんがじょう
お年玉|おとしだま
鏡餅|かがみもち
節分|せつぶん
雛祭り|ひなまつり
七夕|たなばた
大晦日|おおみそか
キーボード|きーぼーど
ショートカット|しょーとかっと
フォルダ|ふぉるだ
チョコレート|ちょこれーと
シュークリーム|しゅーくりーむ
ヴィンテージ|ゔぃんてーじ
ディナー|でぃなー
ジェラート|じぇらーと
ウォーターサーバー|うぉーたーさーばー
チャンピオン|ちゃんぴおん
ファインプレー|ふぁいんぷれー
ティーカップ|てぃーかっぷ
しゃっくり|しゃっくり
ぎっくり腰|ぎっくりごし
きゅうり|きゅうり
ちょうちょ|ちょうちょ`;

const EN = `apple|りんご
banana|バナナ
keyboard|キーボード
practice|練習
accuracy|正確さ
rhythm|リズム
finger|指
morning|朝
evening|夕方
weather|天気
umbrella|傘
station|駅
library|図書館
bicycle|自転車
mountain|山
river|川
ocean|海
island|島
forest|森
window|窓
kitchen|台所
breakfast|朝ごはん
dinner|夕ごはん
coffee|コーヒー
chocolate|チョコレート
birthday|誕生日
holiday|休日
weekend|週末
journey|旅
adventure|冒険
history|歴史
science|科学
language|言語
question|質問
answer|答え
problem|問題
solution|解決策
important|大切な
beautiful|美しい
different|ちがう
possible|できる
necessary|必要な
quickly|速く
slowly|ゆっくり
carefully|注意深く
together|いっしょに
tomorrow|明日
yesterday|昨日
tonight|今夜
already|もう
almost|ほとんど
always|いつも
sometimes|ときどき
between|あいだに
through|通りぬけて
without|なしで
because|なぜなら
although|けれども
knowledge|知識
experience|経験
challenge|挑戦
victory|勝利
champion|王者
baseball|野球
stadium|球場
pitcher|投手
catcher|捕手
computer|コンピューター
internet|インターネット
password|パスワード
software|ソフトウェア
message|伝言
picture|写真
music|音楽
guitar|ギター
piano|ピアノ
festival|祭り
fireworks|花火
summer|夏
winter|冬
spring|春
autumn|秋
rainbow|虹
thunder|雷
sunshine|日光
moonlight|月明かり
universe|宇宙
galaxy|銀河
planet|惑星
energy|エネルギー
quality|品質
quantity|量
journal|日誌
puzzle|パズル
quiz|クイズ
zebra|シマウマ
jazz|ジャズ
oxygen|酸素
yellow|黄色
purple|紫
crystal|水晶
freedom|自由
friendship|友情
patience|忍耐
courage|勇気
wisdom|知恵
strength|強さ
mystery|なぞ
treasure|宝物
whisper|ささやき
squirrel|リス
jungle|ジャングル
volcano|火山
earthquake|地震
environment|環境
university|大学
restaurant|レストラン
vegetable|野菜
strawberry|いちご
watermelon|スイカ
pineapple|パイナップル
sandwich|サンドイッチ
elephant|ゾウ
giraffe|キリン
penguin|ペンギン
dolphin|イルカ
butterfly|チョウ`;

const parse = s => s.trim().split("\n").map(l => { const [a, b] = l.split("|"); return { d: a, r: b }; });
const POOL = { sent: parse(SENT), word: parse(WORDS), en: parse(EN) };

/* =========================================================
   ローマ字（かな → 打ち方の候補）
========================================================= */
const K1 = {
  "あ":["a"],"い":["i","yi"],"う":["u","wu","whu"],"え":["e"],"お":["o"],
  "か":["ka","ca"],"き":["ki"],"く":["ku","cu","qu"],"け":["ke"],"こ":["ko","co"],
  "さ":["sa"],"し":["si","shi","ci"],"す":["su"],"せ":["se","ce"],"そ":["so"],
  "た":["ta"],"ち":["ti","chi"],"つ":["tu","tsu"],"て":["te"],"と":["to"],
  "な":["na"],"に":["ni"],"ぬ":["nu"],"ね":["ne"],"の":["no"],
  "は":["ha"],"ひ":["hi"],"ふ":["fu","hu"],"へ":["he"],"ほ":["ho"],
  "ま":["ma"],"み":["mi"],"む":["mu"],"め":["me"],"も":["mo"],
  "や":["ya"],"ゆ":["yu"],"よ":["yo"],
  "ら":["ra"],"り":["ri"],"る":["ru"],"れ":["re"],"ろ":["ro"],
  "わ":["wa"],"を":["wo"],
  "が":["ga"],"ぎ":["gi"],"ぐ":["gu"],"げ":["ge"],"ご":["go"],
  "ざ":["za"],"じ":["ji","zi"],"ず":["zu"],"ぜ":["ze"],"ぞ":["zo"],
  "だ":["da"],"ぢ":["di"],"づ":["du"],"で":["de"],"ど":["do"],
  "ば":["ba"],"び":["bi"],"ぶ":["bu"],"べ":["be"],"ぼ":["bo"],
  "ぱ":["pa"],"ぴ":["pi"],"ぷ":["pu"],"ぺ":["pe"],"ぽ":["po"],
  "ぁ":["xa","la"],"ぃ":["xi","li"],"ぅ":["xu","lu"],"ぇ":["xe","le"],"ぉ":["xo","lo"],
  "ゃ":["xya","lya"],"ゅ":["xyu","lyu"],"ょ":["xyo","lyo"],"ゎ":["xwa","lwa"],
  "ゔ":["vu"],"ー":["-"],"、":[","],"。":["."]
};
const TSU = ["xtu","ltu","xtsu","ltsu"];
const COMP = {};
const SM = { "ゃ":"a","ぃ":"i","ゅ":"u","ぇ":"e","ょ":"o" };
for (const [k, p] of Object.entries({ "き":"ky","ぎ":"gy","に":"ny","ひ":"hy","び":"by","ぴ":"py","み":"my","り":"ry","ぢ":"dy" }))
  for (const [s, v] of Object.entries(SM)) COMP[k + s] = [p + v];
const add = (k, ...v) => { COMP[k] = v; };
add("しゃ","sha","sya"); add("しぃ","syi"); add("しゅ","shu","syu"); add("しぇ","she","sye"); add("しょ","sho","syo");
add("ちゃ","cha","tya","cya"); add("ちぃ","tyi","cyi"); add("ちゅ","chu","tyu","cyu"); add("ちぇ","che","tye","cye"); add("ちょ","cho","tyo","cyo");
add("じゃ","ja","jya","zya"); add("じぃ","jyi","zyi"); add("じゅ","ju","jyu","zyu"); add("じぇ","je","jye","zye"); add("じょ","jo","jyo","zyo");
add("ふぁ","fa"); add("ふぃ","fi","fyi"); add("ふぇ","fe","fye"); add("ふぉ","fo"); add("ふゃ","fya"); add("ふゅ","fyu"); add("ふょ","fyo");
add("てぃ","thi"); add("てゃ","tha"); add("てゅ","thu"); add("てぇ","the"); add("てょ","tho");
add("でぃ","dhi"); add("でゃ","dha"); add("でゅ","dhu"); add("でぇ","dhe"); add("でょ","dho");
add("とぅ","twu"); add("どぅ","dwu");
add("うぃ","wi","whi"); add("うぇ","we","whe"); add("うぉ","who");
add("ゔぁ","va"); add("ゔぃ","vi"); add("ゔぇ","ve"); add("ゔぉ","vo"); add("ゔゅ","vyu");
add("つぁ","tsa"); add("つぃ","tsi"); add("つぇ","tse"); add("つぉ","tso");
add("くぁ","kwa","qa"); add("くぃ","qi"); add("くぇ","qe"); add("くぉ","qo"); add("ぐぁ","gwa");
add("いぇ","ye"); add("すぃ","swi");
const uniq = a => [...new Set(a)];
for (const k of Object.keys(COMP)) {
  const a = K1[k[0]] || [], b = K1[k[1]] || [];
  const cross = []; for (const x of a) for (const y of b) cross.push(x + y);
  COMP[k] = uniq([...COMP[k], ...cross]);
}
const CONS = /^[bcdfghjklmpqrstvwxyz]/;
const CONS_N = /^[bcdfghjklmpqrstvwxz]/;   // ん を n 1回で打てる次の頭文字（y・n・母音以外）

function tokenize(read, en) {
  if (en) return [...read].map(ch => ({ k: ch, c: [ch] }));
  let u = [];
  for (let i = 0; i < read.length; ) {
    const two = read.slice(i, i + 2);
    if (two.length === 2 && COMP[two]) { u.push({ k: two, c: COMP[two].slice() }); i += 2; continue; }
    const ch = read[i];
    u.push({ k: ch, c: (K1[ch] || [ch]).slice() }); i++;
  }
  // っ は次の音と1まとまりにする（子音を重ねる / xtu・ltu ＋ 次）
  const out = [];
  for (let i = 0; i < u.length; i++) {
    const x = u[i], nx = u[i + 1];
    if (x.k === "っ" && nx && nx.k !== "っ" && nx.k !== "ん") {
      const dbl = nx.c.filter(c => CONS.test(c)).map(c => c[0] + c);
      const sm = []; for (const t of TSU) for (const c of nx.c) sm.push(t + c);
      if (dbl.length) { out.push({ k: "っ" + nx.k, c: uniq([...dbl, ...sm]), sok: true, inner: nx.k }); i++; continue; }
    }
    if (x.k === "っ") { out.push({ k: "っ", c: TSU.slice() }); continue; }
    out.push(x);
  }
  // ん：次が子音（y・n 以外）なら n 1回でもよい
  for (let i = 0; i < out.length; i++) {
    if (out[i].k !== "ん") continue;
    const nx = out[i + 1];
    const single = !!nx && nx.c.every(c => CONS_N.test(c));
    out[i].c = single ? ["n", "nn", "xn"] : ["nn", "xn"];
    out[i].nOk = single;
  }
  return out;
}
function splitSok(c) {
  for (const t of ["xtsu","ltsu","xtu","ltu"]) if (c.startsWith(t)) return [t, c.slice(t.length)];
  return ["重ねる", c.slice(1)];
}


/* =========================================================
   1問ぶんの判定
========================================================= */
function Matcher(units, onCommit) { this.units = units; this.u = 0; this.b = ""; this.onCommit = onCommit || null; }
Matcher.prototype.done = function () { return this.u >= this.units.length; };
Matcher.prototype.commit = function (used) {
  const u = this.units[this.u];
  u._used = used;
  if (this.onCommit) this.onCommit(u, used);
  this.u++; this.b = "";
};
Matcher.prototype.feed = function (k) {
  const u = this.units[this.u];
  if (!u) return false;
  const nb = this.b + k;
  const m = u.c.filter(x => x.startsWith(nb));
  if (m.length) {
    this.b = nb;
    if (m.includes(nb) && (m.every(x => x === nb) || this.u === this.units.length - 1)) this.commit(nb);
    return true;
  }
  if (this.b && u.c.includes(this.b)) {        // 「n」のように、打ち切ったかどうか次の1打で決まるもの
    const nu = this.units[this.u + 1];
    if (nu && nu.c.some(x => x.startsWith(k))) { this.commit(this.b); return this.feed(k); }
  }
  return false;
};

function problem(mode, idx) {
  const p = POOL[mode][idx];
  if (!p) return null;
  return mode === "en" ? { idx, disp: p.d, kana: p.r, read: p.d, en: true } : { idx, disp: p.d, kana: p.r, read: p.r, en: false };
}
function unitsOf(pr) { return tokenize(pr.read.toLowerCase(), pr.en); }

/* =========================================================
   ランキング用の問題の順番（サーバーが渡す seed から決まる）
========================================================= */
function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const RECENT = mode => Math.min(30, Math.floor(POOL[mode].length / 2));
function sequence(mode, seed, n) {
  const r = rng(seed), len = POOL[mode].length, recent = [], out = [];
  for (let i = 0; i < (n || 400); i++) {
    let cand = [];
    for (let j = 0; j < len; j++) if (!recent.includes(j)) cand.push(j);
    const x = cand[Math.floor(r() * cand.length)];
    out.push(x); recent.push(x); if (recent.length > RECENT(mode)) recent.shift();
  }
  return out;
}

/* =========================================================
   結果の計算（ページとサーバーで同じ式）
   keys：打ったキーを並べた文字列、times：それぞれの時刻（開始からのms、整数）
========================================================= */
function evaluate(mode, sec, probs, keys, times) {
  const dur = sec * 1000;
  if (!POOL[mode] || ![30, 60, 120].includes(sec)) return { err: "設定が正しくありません" };
  if (typeof keys !== "string" || !Array.isArray(times) || keys.length !== times.length) return { err: "記録が壊れています" };
  let pi = 0, pr = problem(mode, probs[0]);
  if (!pr) return { err: "問題が見つかりません" };
  let m = new Matcher(unitsOf(pr)), shown = 0, started = false;
  let ok = 0, miss = 0, firstOk = 0, sumLat = 0, nLat = 0, done = 0, lastT = 0;
  for (let i = 0; i < keys.length; i++) {
    const t = times[i], k = keys[i];
    if (!Number.isInteger(t) || t < lastT || t > dur) return { err: "時刻が正しくありません" };
    lastT = t;
    const first = !started;
    if (first) { started = true; sumLat += t - shown; nLat++; }
    if (m.feed(k)) {
      ok++; if (first) firstOk++;
      if (m.done()) {
        done++; pi++;
        pr = problem(mode, probs[pi]);
        if (!pr) return { err: "問題が足りません" };
        m = new Matcher(unitsOf(pr)); shown = t; started = false;
      }
    } else miss++;
  }
  const waitTail = started ? 0 : dur - shown;
  const rDur = dur - sumLat - waitTail;
  const kpm = ok / dur * 60000;
  const rkpm = rDur > 0 ? (ok - firstOk) / rDur * 60000 : 0;
  const acc = ok + miss ? ok / (ok + miss) : 0;
  return {
    ok, miss, done, kpm, rkpm, acc,
    score: Math.round(kpm * acc * acc),
    lat: nLat ? sumLat / nLat : 0,
  };
}

const RANKS = [[0,"10級"],[50,"9級"],[75,"8級"],[90,"7級"],[100,"6級"],[130,"5級"],[160,"4級"],[190,"3級"],[220,"2級"],[235,"1級"],
  [250,"初段"],[300,"二段"],[350,"三段"],[400,"四段"],[450,"五段"],[500,"六段"],[550,"七段"],[600,"八段"],[650,"九段"],[750,"十段"],[900,"名人"]];
function rankOf(s) { let r = RANKS[0][1]; for (const [t, n] of RANKS) if (s >= t) r = n; return r; }

return { VERSION, POOL, K1, COMP, tokenize, splitSok, Matcher, problem, unitsOf, sequence, evaluate, rankOf, RANKS };
})();
if (typeof window !== "undefined") window.TDT = TDT;
