"""Phase 11: granular "lawlessness texture" — short, concrete details from public reporting.

Each row is a single specific fragment (e.g. "1日20時間労働", "壁にガラス片", "$3,000で売買")
sourced from a real article. The dashboard displays them as small colored pills in the
testimony panel, giving a quick-scan feel of how pervasive the everyday violence is —
without burying it in long paragraphs.

Categories: violence / control / trafficking / conditions / complicity. Idempotent.
"""
import sqlite3, os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')

con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS danger_detail (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    category TEXT,
    text TEXT,
    source_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_danger_cand ON danger_detail(candidate_id);
""")
cur.execute("DELETE FROM danger_detail")
con.commit()

AMNESTY = 'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'

# (candidate_substring, category, short_text_jp, source_url)
DETAILS = [
    # ===== KK Park =====
    ('KK Park', 'conditions', '1日20時間労働', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'conditions', 'コンクリート床で就寝', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'violence', '鉄棒で殴打', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'violence', '電気警棒で感電', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'trafficking', '空港で拉致', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'control', '帰国後も脅迫電話', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'control', '携帯を頻繁に検閲', 'https://www.techpolicy.press/as-authorities-crack-down-on-scam-compounds-victims-are-getting-left-behind/'),
    ('KK Park', 'conditions', '1日18時間労働(別証言)', 'https://www.techpolicy.press/as-authorities-crack-down-on-scam-compounds-victims-are-getting-left-behind/'),
    ('KK Park', 'control', '内部完結都市(店・病院・食堂)', 'https://en.wikipedia.org/wiki/KK_Park'),
    ('KK Park', 'conditions', '635棟・最大10階建て', 'https://asianews.network/in-myanmar-and-thailand-river-divides-hotbed-of-scam-centres-on-one-side-safe-haven-from-military-oppression-on-the-other/'),
    ('KK Park', 'conditions', '米人投資家を演じ詐欺', 'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'conditions', '帰国者にパニック発作', 'https://www.techpolicy.press/as-authorities-crack-down-on-scam-compounds-victims-are-getting-left-behind/'),

    # ===== Jin Bei =====
    ('Jin Bei', 'conditions', '1日14〜15時間労働', 'https://vodenglish.news/woman-pleads-in-khmer-for-scam-rescue/'),
    ('Jin Bei', 'control', '3か月後に退所拒否', 'https://vodenglish.news/woman-pleads-in-khmer-for-scam-rescue/'),
    ('Jin Bei', 'control', '6か月延長を強要', 'https://vodenglish.news/woman-pleads-in-khmer-for-scam-rescue/'),
    ('Jin Bei', 'violence', '中国人男性をスーツケース遺体で発見', 'https://cambojanews.com/dead-chinese-man-linked-to-alleged-scam-operation-sihanoukville-compound/'),
    ('Jin Bei', 'control', '深夜1〜2時の突然移送', 'https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/'),
    ('Jin Bei', 'trafficking', '到着で初めて売られたと知る', 'https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/'),
    ('Jin Bei', 'conditions', 'インド人150人がコート上で蜂起', 'https://www.business-standard.com/india-news/cambodia-job-scam-60-rescued-2-days-after-stranded-indians-stage-revolt-124052200564_1.html'),
    ('Jin Bei', 'control', 'パスポートを没収', 'https://www.business-standard.com/india-news/cambodia-job-scam-60-rescued-2-days-after-stranded-indians-stage-revolt-124052200564_1.html'),

    # ===== Chinatown =====
    ('Chinatown', 'conditions', '一棟に最大800人収容', 'https://www.voanews.com/a/scam-victims-say-human-trafficking-still-a-problem-in-cambodia/7520511.html'),
    ('Chinatown', 'conditions', '1社に400〜500人', 'https://www.voanews.com/a/scam-victims-say-human-trafficking-still-a-problem-in-cambodia/7520511.html'),
    ('Chinatown', 'violence', '暗闇に隔離+電気警棒で1年', 'https://www.voanews.com/a/scam-victims-say-human-trafficking-still-a-problem-in-cambodia/7520511.html'),
    ('Chinatown', 'violence', '警備員が23号棟で首吊り', 'https://vodenglish.news/body-found-hanging-in-sihanoukvilles-alleged-slave-compound-area/'),
    ('Chinatown', 'violence', '5〜10分の暴行', 'https://www.france24.com/en/live-news/20221109-inside-the-living-hell-of-cambodia-s-scam-operations'),
    ('Chinatown', 'control', '壁高3〜4m', 'https://www.scmp.com/news/asia/southeast-asia/article/3329341/abducted-trapped-forced-scam-inside-cambodias-chinese-run-sihanoukville-crime-hub'),
    ('Chinatown', 'control', '壁上に有刺鉄線+ガラス片', 'https://www.scmp.com/news/asia/southeast-asia/article/3329341/abducted-trapped-forced-scam-inside-cambodias-chinese-run-sihanoukville-crime-hub'),
    ('Chinatown', 'control', '内部食堂のみ、外出禁止', 'https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound'),
    ('Chinatown', 'control', '出前は中国人男性が受取', 'https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound'),
    ('Chinatown', 'trafficking', '手入れ後もJinshui拠点へ転売', 'https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/'),
    ('Chinatown', 'conditions', '週末で1,000人超を退去', 'https://globalinitiative.net/wp-content/uploads/2022/09/GI-TOC-report_Sihanoukville_For-upload.pdf'),

    # ===== Dara Sakor =====
    ('Dara Sakor', 'trafficking', '9時間ドライブで連行', 'https://asianews.network/i-was-told-to-scam-singaporeans-bangladeshi-man-who-was-trafficked-to-scam-compounds/'),
    ('Dara Sakor', 'conditions', '偽プロフィールを100個作成', 'https://www.humanity-consultancy.com/updates/the-horrible-5-month-life-in-scamming-compounds'),
    ('Dara Sakor', 'violence', '罰=腕立て25〜75回', 'https://www.humanity-consultancy.com/updates/the-horrible-5-month-life-in-scamming-compounds'),
    ('Dara Sakor', 'trafficking', '37日後に別の会社へ転売', 'https://www.humanity-consultancy.com/updates/the-horrible-5-month-life-in-scamming-compounds'),
    ('Dara Sakor', 'control', '「お前は奴隷だ、売られた」と言われる', 'https://asianews.network/i-was-told-to-scam-singaporeans-bangladeshi-man-who-was-trafficked-to-scam-compounds/'),
    ('Dara Sakor', 'complicity', '警察への告発が施設へ漏洩', 'https://vodenglish.news/rescue-reveals-scam-compound-at-koh-kongs-udg/'),
    ('Dara Sakor', 'complicity', '記者を撮影で拘束', 'https://thediplomat.com/2026/02/cambodian-reporter-detained-after-photographing-raid-on-scam-center'),
    ('Dara Sakor', 'conditions', '立退き先に電気・水道・仕事なし', 'https://dialogue.earth/en/justice/11735-cambodians-struggle-to-be-compensated-for-dara-sakor-megaproject-2/'),
    ('Dara Sakor', 'conditions', '広大な閉鎖区域(99年リース)', 'https://en.wikipedia.org/wiki/Dara_Sakor'),

    # ===== O'Smach =====
    ("O'Smach", 'trafficking', '$3,000で売買', AMNESTY),
    ("O'Smach", 'trafficking', '内部でさらに2回売買', AMNESTY),
    ("O'Smach", 'complicity', '警察は施設のために働く', AMNESTY),
    ("O'Smach", 'complicity', '救助要請をボスに密告', AMNESTY),
    ("O'Smach", 'control', '「残るか刑務所か」と脅迫', AMNESTY),
    ("O'Smach", 'violence', '集団脱出にベッド枠の鉄棒', 'https://www.rfa.org/english/cambodia/2025/01/06/cambodia-workers-flee-casino/'),
    ("O'Smach", 'control', '有刺鉄線をよじ登り脱出', AMNESTY),
    ("O'Smach", 'violence', '森で警備員に狩られる', AMNESTY),
    ("O'Smach", 'conditions', '砲撃下でも詐欺を強要', 'https://www.csis.org/analysis/fraud-frontlines-scam-centers-caught-cambodia-thailand-conflict'),
    ("O'Smach", 'complicity', '偽警察署の部屋(各国制服)', 'https://www.bangkokpost.com/thailand/general/3189395/cambodian-scam-compound-yields-trove-of-fraud-evidence-thai-military-says'),
    ("O'Smach", 'control', 'SIMカード871枚を押収', 'https://www.bangkokpost.com/thailand/general/3189395/cambodian-scam-compound-yields-trove-of-fraud-evidence-thai-military-says'),

    # ===== Poipet =====
    ('Poipet', 'conditions', '1日5人スカムのノルマ', 'https://english.cambodiadaily.com/2025/01/19/harrowing-ordeal-in-poipet-they-screamed-in-our-ears/'),
    ('Poipet', 'violence', '未達者は12時間立ち罰', 'https://english.cambodiadaily.com/2025/01/19/harrowing-ordeal-in-poipet-they-screamed-in-our-ears/'),
    ('Poipet', 'violence', '「ここで死ぬ」と毎日言われる', 'https://english.cambodiadaily.com/2025/01/19/harrowing-ordeal-in-poipet-they-screamed-in-our-ears/'),
    ('Poipet', 'violence', '野球バットで殴打', 'https://www.pattayamail.com/thailandnews/thai-man-escapes-cambodian-scam-compound-reveals-torture-of-nearly-100-foreigners-522980'),
    ('Poipet', 'violence', '3階から拷問の音', 'https://www.pattayamail.com/thailandnews/thai-man-escapes-cambodian-scam-compound-reveals-torture-of-nearly-100-foreigners-522980'),
    ('Poipet', 'trafficking', 'プラスチック容器で運河越え', AMNESTY),
    ('Poipet', 'control', '顔スキャンで銀行口座作成', AMNESTY),
    ('Poipet', 'violence', '暗い部屋+電気警棒+布袋', AMNESTY),
    ('Poipet', 'violence', '鉄棒と電気棒で拷問死(218号室)', 'https://www.nationthailand.com/blogs/news/asean/40058432'),
    ('Poipet', 'conditions', 'カジノ通路に物乞い', 'https://casinourbanism.wordpress.com/2015/10/10/poipet-a-casino-town-between-thailand-and-cambodia/'),

    # ===== Bavet =====
    ('Bavet', 'conditions', '16歳少年が強制労働', AMNESTY),
    ('Bavet', 'violence', '食事配り中に悲鳴を聞く', AMNESTY),
    ('Bavet', 'violence', '10階「会議室」=拷問室', AMNESTY),
    ('Bavet', 'control', '手錠で殴打・電気警棒', AMNESTY),
    ('Bavet', 'violence', '「最後の食事だ」と3択強迫', AMNESTY),
    ('Bavet', 'violence', '8階から飛び降りて脱出', AMNESTY),
    ('Bavet', 'trafficking', '$4,500の「借金」宣告', AMNESTY),
    ('Bavet', 'violence', 'ビール瓶で頭部', AMNESTY),
    ('Bavet', 'trafficking', '多数が複数回売られる', 'https://www.irrawaddy.com/news/burma/nearly-180-myanmar-workers-rescued-in-raid-on-cambodian-scam-center.html'),
    ('Bavet', 'violence', '24歳カジノ従業員が斬首遺体で発見', 'https://cambojanews.com/female-employee-of-tycoons-call-center-casino-in-bavet-beheaded/'),
    ('Bavet', 'violence', '28歳ベトナム人がカジノで首吊り', 'https://www.casino.org/news/vietnamese-worker-found-hanged-in-cambodia-casino/'),
]

cands = {lbl: cid for cid, lbl in cur.execute("SELECT id, label FROM compound_candidate")}
added = 0
for substr, cat, text, url in DETAILS:
    match = next((lbl for lbl in cands if substr in lbl), None)
    if not match:
        continue
    cur.execute("INSERT INTO danger_detail(candidate_id, category, text, source_url) VALUES(?,?,?,?)",
                (cands[match], cat, text, url))
    added += 1

con.commit()
print(f"[P11] added {added} danger details.")
for label, n in cur.execute("""SELECT c.label, COUNT(d.id) FROM compound_candidate c
                                LEFT JOIN danger_detail d ON d.candidate_id=c.id
                                GROUP BY c.id ORDER BY c.id"""):
    print(f"  {n:2d}  {label}")
con.close()
