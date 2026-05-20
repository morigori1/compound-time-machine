"""Phase 10: local-life layer — eateries, markets, lodging + daily-life snippets.

Two parts:
  1. local_spot — real named everyday places (restaurants / cafes / markets / hotels)
     around each compound, pulled fresh from OpenStreetMap via Overpass. No popularity
     ranking is invented; they are simply "the everyday places nearby".
  2. life_snippet — short reported observations of daily life / atmosphere, curated
     from public reporting and shown as social-post-style cards (NOT live SNS, which
     can't be verified or reliably embedded).

Idempotent.
"""
import sqlite3, os, sys, time, json, math
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')
UA = 'compounds-poc/0.10 (local OSINT research dashboard)'
OVERPASS = 'https://overpass-api.de/api/interpreter'

con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS local_spot (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    lat REAL, lon REAL,
    category TEXT,
    kind TEXT,
    name TEXT
);
CREATE INDEX IF NOT EXISTS idx_localspot_cand ON local_spot(candidate_id);
CREATE TABLE IF NOT EXISTS life_snippet (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    ord INTEGER,
    topic TEXT,
    text TEXT,
    source_label TEXT,
    source_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_lifesnip_cand ON life_snippet(candidate_id);
""")
cur.execute("DELETE FROM local_spot")
cur.execute("DELETE FROM life_snippet")
con.commit()

CAT = {}
for v in ('restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court'):
    CAT[v] = 'food'
for v in ('marketplace', 'supermarket', 'convenience', 'mall', 'bakery'):
    CAT[v] = 'market'
for v in ('hotel', 'guest_house', 'hostel'):
    CAT[v] = 'lodging'


def overpass(lat, lon):
    q = (f'[out:json][timeout:30];('
         f'nwr(around:900,{lat},{lon})[amenity~"^(restaurant|cafe|fast_food|bar|pub|food_court|marketplace)$"][name];'
         f'nwr(around:900,{lat},{lon})[shop~"^(supermarket|convenience|mall|bakery)$"][name];'
         f'nwr(around:900,{lat},{lon})[tourism~"^(hotel|guest_house|hostel)$"][name];'
         f');out center tags 500;')
    data = urllib.parse.urlencode({'data': q}).encode()
    req = urllib.request.Request(OVERPASS, data=data,
                                 headers={'User-Agent': UA, 'Accept': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=70).read())


# --- daily-life snippets (curated from public reporting; shown as social-post cards) ---
SNIPPETS = {
    'KK Park': [
        ('うたい文句', 'Shwe Kokko は当初「新都市」「スマートシティ」「観光リゾート」として喧伝された。'
         '看板やCGは未来都市を描いたが、実態はかけ離れていた。',
         'The People’s Map of Global China', 'https://thepeoplesmap.net/project/shwe-kokko-special-economic-zone-yatai-new-city/'),
        ('対岸から', 'モエイ川をはさんだタイ・メーソット側からは、対岸に立ち並ぶ高層棟がはっきり見える。'
         '行けない場所が、川一本越しに見えている。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Shwe_Kokko'),
        ('国境の街', '周辺のミャワディは武装勢力の影響下にある紛争地でもある。'
         'きらびやかな開発と、すぐ外側の不安定さが同居している。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/KK_Park'),
        ('遠景はリゾート', 'メーソットの丘から見ると、コンパウンドは畑に広がる高原の研究都市か、'
         'あるいはリゾートのように見える。',
         'Asia News Network', 'https://asianews.network/in-myanmar-and-thailand-river-divides-hotbed-of-scam-centres-on-one-side-safe-haven-from-military-oppression-on-the-other/'),
        ('塔の洗濯物', '10階建てもある635棟の集合住宅。その窓辺には、干された洗濯物が見える。',
         'Asia News Network', 'https://asianews.network/in-myanmar-and-thailand-river-divides-hotbed-of-scam-centres-on-one-side-safe-haven-from-military-oppression-on-the-other/'),
        ('場違いなラスベガス', 'タイ側のサトウキビ畑を車で過ぎると、新都市が突如として現れ、'
         '建物が場違いなラスベガスのように灯る。',
         'Inquirer', 'https://globalnation.inquirer.net/286431/lights-dimmed-at-south-east-asias-scam-hub-but-pig-butchering-goes-on'),
        ('自己完結した街', 'スーパー、病院、レストラン、ホテルを備え、労働者向けの閉じた共同体を形成している。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/KK_Park'),
        ('消えた灯り', 'タイが電力・通信・燃料を断って以来、夜空を染めていた派手なネオンは数か月見られない。',
         'Inquirer', 'https://globalnation.inquirer.net/286431/lights-dimmed-at-south-east-asias-scam-hub-but-pig-butchering-goes-on'),
    ],
    'Jin Bei': [
        ('街の変貌', 'シハヌークビルはかつてバックパッカーが集う静かなビーチの町だった。'
         '2010年代後半、中国資本の流入でカジノ都市へと一変した。',
         'Global China Pulse', 'https://globalchinapulse.net/sihanoukville-rise-and-fall-of-a-frontier-city/'),
        ('食と看板', '中心部は火鍋店・KTV・中国語の看板で埋まり、中国人観光客向けの歓楽街と化した。',
         'Global China Pulse', 'https://globalchinapulse.net/sihanoukville-rise-and-fall-of-a-frontier-city/'),
        ('ブームの跡', '2019年のオンライン賭博禁止後、建てかけのビルが大量に放置された。'
         '歓楽の街に、未完成の骨組みが残る。',
         'Asia Times', 'https://asiatimes.com/2019/11/boom-to-bust-for-cambodias-chinese-casino-town/'),
        ('貝殻のネオン入口', 'Jin Beiカジノは夜、色とりどりの照明に包まれる。'
         '入口の上には、貝殻に収まったトランプとサイコロの立体看板が光る。',
         'World Casino Directory', 'https://www.worldcasinodirectory.com/casino/jin-bei-casino-hotel'),
        ('煙草とバカラ台', '金属探知機を抜けると、明るい絨毯敷きのホール。'
         'チェーンスモークの中国人男性たちが、緑のバカラ台に賭ける。',
         'WORLD', 'https://wng.org/articles/cambodian-casinoville-1617298866'),
        ('中国そのものの通り', 'レストランの看板は簡体字が中心で、四川・山西・北京の料理を掲げる。',
         'WORLD', 'https://wng.org/articles/cambodian-casinoville-1617298866'),
        ('砂ぼこりと騒音', '高層ホテルの脇を大型セメント車が行き交い、海風は砂ぼこりを含み、'
         '建設音が昼夜を問わず続く。',
         'WORLD', 'https://wng.org/articles/cambodian-casinoville-1617298866'),
        ('配信のための賭場', 'WMなどのカジノでは、若い女性が世界の配信視聴者へ向けてカードを配り、'
         '実際の客の姿はまばらだ。',
         'Al Jazeera', 'https://interactive.aljazeera.com/aje/2019/cambodia-casino-gamble/index.html'),
    ],
    'Chinatown': [
        ('ビーチの隣', 'オトレス・ビーチは今も一部の旅行者を集める。'
         'その砂浜のすぐ背後に、閉じた「チャイナタウン」の区画がある。',
         'Global China Pulse', 'https://globalchinapulse.net/sihanoukville-rise-and-fall-of-a-frontier-city/'),
        ('内部の食堂', 'コンパウンドの多くは内部に独自の食堂を持ち、住民が外に出ることは少ない。'
         '出前が来ると中国人男性が受け取りに出てくる、と近隣の店主は語る。',
         'Korea Times', 'https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound'),
        ('観光と犯罪の同居', 'リゾート開発の外形をまといながら、人身売買の拠点として記録されてきた。',
         'France 24', 'https://www.france24.com/en/live-news/20221109-inside-the-living-hell-of-cambodia-s-scam-operations'),
        ('ビーチが引っ越し道に', '夕暮れ、何十人もがスーツケースや、家具・箱・洗濯機まで載せた手押し車を、'
         'ビーチ越しに運んでいく。',
         'Mekong Independent', 'https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/'),
        ('ガラス片を載せた壁', 'コンパウンドは高さ3〜4mのコンクリート壁に囲まれ、上部には有刺鉄線と割れたガラス片。'
         '集合住宅というより刑務所だ。',
         'South China Morning Post', 'https://www.scmp.com/news/asia/southeast-asia/article/3329341/abducted-trapped-forced-scam-inside-cambodias-chinese-run-sihanoukville-crime-hub'),
        ('客が消えた街', 'カジノ客と関連商売が消え、トゥクトゥク運転手の夜の稼ぎは約5万リエル(12.5ドル)に落ちた。',
         'Mekong Independent', 'https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/'),
        ('五つ星の予定地', 'オトレスの浜の露店はブルドーザーで撤去され、五つ星ホテルの予定地に。'
         '新しい道路の脇に、寂しい砂浜が残った。',
         'Southeast Asia Backpacker', 'https://southeastasiabackpacker.com/destinations/cambodia/sihanoukville/'),
        ('残る漁の名残', '川の南岸のレストランは、今も地元の沿岸漁船が水揚げした魚介を出す。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Sihanoukville'),
    ],
    'Dara Sakor': [
        ('ゴースト開発', '広大な区画に対して実際の建設はまばら。'
         '空き地と無人の区画が広がる「建たなかった都市」として観察できる。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Dara_Sakor'),
        ('ほぼ無人の空港', '計画規模に比して便数の極端に少ない巨大空港。滑走路が原生林を貫く。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Dara_Sakor_International_Airport'),
        ('原生林と海岸', 'コッコンのマングローブと海岸線。'
         '観光リゾートの触れ込みの裏で、長年の土地紛争が続いた。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Dara_Sakor'),
        ('一軒のカジノと空白', '訪れた活動家が見たのは、カジノ一軒と、そこへの道、そして巨大な空港だけ。'
         '客は年に数か月しか来ないという。',
         'Mongabay', 'https://news.mongabay.com/2021/05/casinos-condos-and-sugar-cane-how-a-cambodian-national-park-is-being-sold-down-the-river/'),
        ('眠そうな空港の検問', '空港予定地では、一人の眠そうな警備員が車を通す。'
         '訪問者は、できたばかりの滑走路を車で走ることができた。',
         'Bangkok Post', 'https://www.bangkokpost.com/world/1715883/chinese-mega-resort-in-cambodia-raises-red-flags'),
        ('象の糞の道', '深水港へ続く67kmのでこぼこ道には、象の糞の筋のほか、ほとんど生活の気配がない。',
         'Bangkok Post', 'https://www.bangkokpost.com/world/1715883/chinese-mega-resort-in-cambodia-raises-red-flags'),
        ('こっそり戻る漁師', '2009年に内陸へ移された漁師は、今も時々Dara Sakorに忍び込み、舟を出して漁をする。',
         'Mongabay', 'https://news.mongabay.com/2021/05/casinos-condos-and-sugar-cane-how-a-cambodian-national-park-is-being-sold-down-the-river/'),
        ('基本設備のない移転先', '立ち退かされた村人は、海岸から遠い質素な木造家屋へ移された。'
         'その移転先には、電気も水道も仕事もなかった。',
         'Dialogue Earth', 'https://dialogue.earth/en/justice/11735-cambodians-struggle-to-be-compensated-for-dara-sakor-megaproject-2/'),
    ],
    "O'Smach": [
        ('国境の市場', 'タイ側のChong Chom国境市場は越境買い物客でにぎわう。'
         '国境のこちら側は、カジノが集まる小さな町。',
         'CamboJA News', 'https://cambojanews.com/senators-casino-fleeing-compound-not-hit-in-growing-scam-raids/'),
        ('小さな町', 'O’Smachは畑と数本の道路からなる通関集落。'
         'その一角に、不釣り合いに大きなカジノ・リゾートが立つ。',
         'CamboJA News', 'https://cambojanews.com/senators-casino-fleeing-compound-not-hit-in-growing-scam-raids/'),
        ('国境の非対称', '国境線をはさみ、カンボジア側にだけカジノが密集する。'
         'その不均衡そのものが、規制の裏側を可視化している。',
         'CamboJA News', 'https://cambojanews.com/after-thai-strikes-hit-cambodian-elites-casinos-trafficked-workers-feared-inside/'),
        ('検問所の間のカジノ', 'カンボジアとタイの検問所の間にカジノホテル2軒と市場が並び、'
         'タイ人はカンボジアの入国審査を通らずに賭けられる。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/O_Smach'),
        ('中古自転車の交易', '日本から輸入された中古自転車がO’Smachに運ばれ、'
         'Chong Chom市場で国境越しにタイ人へ売られる。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/O_Smach'),
        ('リゾートの装飾', 'O’Smachリゾートの入口には、噴水の中に光る巨大な緑の蓮。'
         '敷地には、クリスマス電飾を巻かれた装甲車が2台置かれている。',
         'Tourism Cambodia', 'https://www.tourismcambodia.com/travelguides/provinces/oddor-meanchey/what-to-see/331_o-smach.htm'),
        ('Chong Chom市場の品', '国境のChong Chom市場は安物・古着・模造品が広がり、'
         'サトウキビジュースの売り子や托鉢僧が行き交う。',
         'Live Less Ordinary', 'https://live-less-ordinary.com/thailand-cambodia-border-crossing/'),
        ('辺境の静寂', '国境砲撃で住民が逃げた後、O’Smachには不気味な静けさが漂う。'
         '通りは空っぽで、建物は放棄された。',
         'Asia News Network', 'https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/'),
    ],
    'Poipet': [
        ('越境ギャンブラー', 'タイでは賭博が違法。だからタイ人客は毎日のように国境を越え、'
         'Poipetのカジノ街へ通ってくる。',
         'VICE', 'https://www.vice.com/en/article/cambodias-bordertown-sin-city-is-a-post-apocalyptic-gamblers-hell/'),
        ('国境の無人地帯', '出入国ゲートの間に広がるカジノ地帯は、'
         '荷運び人や砂ぼこりが行き交う一種の無人地帯になっている。',
         'VICE', 'https://www.vice.com/en/article/cambodias-bordertown-sin-city-is-a-post-apocalyptic-gamblers-hell/'),
        ('カジノ街', 'Star Vegas、旧 Grand Diamond City — 2000年代から続く大型カジノが国境沿いに並ぶ。',
         'Cyber Scam Monitor', 'https://cyberscammonitor.net/profile/grand-diamond-city-casino-poipet-resort/'),
        ('二つの顔の町', 'Poipetははっきり二分される—大通りの北はごく普通のカンボジアの町、'
         '南はより貧しいスラム地区。',
         'Wikivoyage', 'https://en.wikivoyage.org/wiki/Poipet'),
        ('二つの市場', '町には市場が二つ。一つは清潔で風通しよく、もう一つは雑然として臭う。'
         'だが市場の食堂が、最も雰囲気のある食事処だという。',
         'Wikivoyage', 'https://en.wikivoyage.org/wiki/Poipet'),
        ('カジノの無料麺台', 'カジノは無料の麺台を設け、客は数分で立ち食いする。'
         '丼を賭け台へ持ち帰る者もいる。',
         'Casino Urbanism', 'https://casinourbanism.wordpress.com/2015/10/10/poipet-a-casino-town-between-thailand-and-cambodia/'),
        ('歩廊の物乞い', 'カジノ回廊の砂ぼこりっぽい屋根付き歩廊には物乞いがうずくまり、'
         'その傍らでカフェや果物の屋台が営む。',
         'Casino Urbanism', 'https://casinourbanism.wordpress.com/2015/10/10/poipet-a-casino-town-between-thailand-and-cambodia/'),
        ('賭場の空気', 'Poipetの賭場は煙の充満したぼろぼろの部屋。'
         'スロットが漫画の効果音を鳴らし、難しい顔の客が並ぶ。',
         'VICE', 'https://www.vice.com/en/article/cambodias-bordertown-sin-city-is-a-post-apocalyptic-gamblers-hell/'),
    ],
    'Bavet': [
        ('越境日帰り客', 'ベトナム側のMoc Baiから日帰りでカジノに来る客が多い。'
         '国境ゲートの目の前がカジノ街になっている。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Scam_centers_in_Cambodia'),
        ('国境のカジノ列', '既存の国境カジノに、後からコンクリートの棟群が次々と増設されていった。',
         'Wikipedia', 'https://en.wikipedia.org/wiki/Scam_centers_in_Cambodia'),
        ('もう一方の回廊', 'タイ国境のPoipetと対をなす、ベトナム国境のカジノ回廊。',
         'Cyber Scam Monitor', 'https://cyberscammonitor.net/profile/grand-diamond-city-casino-poipet-resort/'),
        ('中国語の看板', 'かつてベトナム語が一般的だったBavetは、今や裏通りまで中国語の看板で埋まり、'
         '中国語しか通じないカフェもある。',
         'Nikkei Asia', 'https://asia.nikkei.com/economy/china-here-china-there-cambodian-city-reshaped-by-chinese-money'),
        ('一本のカジノ通り', '国境を抜けるとBavetのカジノ街。'
         'Le Macauなどの名を掲げたみすぼらしいカジノ建築が、一本の通りに並ぶ。',
         'Inside Asian Gaming', 'https://www.asgam.com/mags/201010/40/'),
        ('10ドルの割引券', 'カジノの客には、ベトナム語で印刷された約10ドル相当の「割引券」が手渡される。',
         'VietnamNet', 'https://vietnamnet.vn/en/cambodian-casinos-enclosure-vietnamese-border-E79144.html'),
        ('カジノ隣のあばら家', '一部のBavetのカジノのすぐ隣には、ぼろぼろのあばら家が建つ。'
         '賭博の富と根強い貧困が、肩を並べている。',
         'Where The Wars Were (現地ブログ)', 'https://wherethewarswere-vietnamlaoscambodia.blogspot.com/2015/02/border-battles-casinos-sean-flynn.html'),
        ('町の市場', 'Phsar Bavet市場は生鮮・安価な衣料・日用品を売る。'
         'カジノを離れた、人々の暮らしが見える場所。',
         'Take Your Backpack', 'https://www.takeyourbackpack.com/backpacking-in-cambodia/visit-bavet/'),
    ],
}

cands = cur.execute("SELECT id, label, rep_lat, rep_lon FROM compound_candidate ORDER BY id").fetchall()
spot_total = snip_total = 0
for cid, label, rlat, rlon in cands:
    # view center = building cluster centroid when available
    lat, lon = rlat, rlon
    cl = cur.execute("SELECT lat, lon FROM poi WHERE candidate_id=? AND name='中心建物群'", (cid,)).fetchone()
    if cl:
        lat, lon = cl

    try:
        data = overpass(lat, lon)
    except Exception as e:
        print(f"  [P10 ERR] overpass {label[:24]}: {e}", file=sys.stderr)
        data = {'elements': []}
    seen = set()
    kept = 0
    for el in data.get('elements', []):
        tags = el.get('tags', {})
        nm = tags.get('name:en') or tags.get('name')
        if not nm or nm.lower() in seen:
            continue
        kind = tags.get('amenity') or tags.get('shop') or tags.get('tourism')
        category = CAT.get(kind)
        if not category:
            continue
        c = el.get('center') or {}
        elat = c.get('lat') or el.get('lat')
        elon = c.get('lon') or el.get('lon')
        if elat is None or elon is None:
            continue
        cur.execute("""INSERT INTO local_spot(candidate_id, lat, lon, category, kind, name)
                       VALUES(?,?,?,?,?,?)""", (cid, elat, elon, category, kind, nm))
        seen.add(nm.lower())
        kept += 1
        spot_total += 1

    key = next((k for k in SNIPPETS if k in label), None)
    snips = 0
    if key:
        for ordi, (topic, text, slabel, surl) in enumerate(SNIPPETS[key]):
            cur.execute("""INSERT INTO life_snippet(candidate_id, ord, topic, text, source_label, source_url)
                           VALUES(?,?,?,?,?,?)""", (cid, ordi, topic, text, slabel, surl))
            snips += 1
            snip_total += 1
    con.commit()
    print(f"  [P10] {label[:32]:32s}: {kept:3d} local spots | {snips} life snippets")
    time.sleep(1.5)

print(f"[P10] done. {spot_total} local spots, {snip_total} life snippets.")
con.close()
