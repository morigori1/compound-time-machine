"""Phase 9: testimony layer — the human voices of each compound.

First-person accounts from survivors, trafficked workers, rescuers and witnesses,
collected from public reporting (Amnesty International, Reuters, RFA, CamboJA, VOD,
France24, VOA, CSIS, The Irrawaddy, etc.). Victims are anonymized — described by
nationality / role / age only; pseudonyms shown are those already used by the outlets.

These are real accounts of human trafficking and abuse; they are presented factually
and with attribution, to give the dataset a human dimension. Idempotent.
"""
import sqlite3, os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')

con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS testimony (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    role TEXT,
    speaker TEXT,
    year TEXT,
    quote TEXT,
    source_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_testimony_cand ON testimony(candidate_id);
""")
cur.execute("DELETE FROM testimony")
con.commit()

# (candidate_substr, role, speaker_jp, year, quote_jp, source_url)
TESTIMONY = [
    # ---- KK Park / Shwe Kokko ----
    ('KK Park', 'survivor', 'ケニア人男性(26歳)', '2025',
     '「昨年、タイでのカスタマーサービスの仕事を約束されて東南アジアへ誘い出された」— 空港で拉致され、KK Parkへ送り込まれた。',
     'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'survivor', 'ケニア人男性(26歳)', '2025',
     'ノルマを外した労働者は「辱められ、殴られ、電気警棒で感電させられた」。1日20時間働かされ、コンクリートの床で眠った。',
     'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'survivor', 'ケニア人男性(26歳)', '2025',
     'アメリカ人投資家になりすます指示について—「自然に振る舞わなければならない。一点でも外せば、相手に詐欺だと気づかれる」。',
     'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'survivor', 'ケニア人男性(26歳)', '2025',
     'タイがKK Parkへの送電を止めて、ようやく脱出できた。帰国後は偏見・困窮、そして脅迫電話に苦しんでいる。',
     'https://www.insurancejournal.com/news/international/2025/09/17/839355.htm'),
    ('KK Park', 'survivor', 'インド人男性(20人超で人身売買された一人)', '2025',
     'KK Park内に閉じ込められ、携帯電話を頻繁に検められ、1日18時間働かされたと証言した。',
     'https://www.techpolicy.press/as-authorities-crack-down-on-scam-compounds-victims-are-getting-left-behind/'),
    ('KK Park', 'survivor', 'エチオピア人男性', '2025',
     '長時間、人をだます作業をさせられ、監禁者に繰り返し殴られた。帰還を待つ間、パニック発作に苦しんでいる。',
     'https://www.techpolicy.press/as-authorities-crack-down-on-scam-compounds-victims-are-getting-left-behind/'),

    # ---- Jin Bei ----
    ('Jin Bei', 'survivor', 'ベトナム人女性', '2022',
     'Jin Bei 4で1日14〜15時間働かされた。3か月後、会社は退所を拒み、さらに6か月の契約を迫った。',
     'https://vodenglish.news/woman-pleads-in-khmer-for-scam-rescue/'),
    ('Jin Bei', 'survivor', 'インド人男性ら(アンドラ・プラデシュ州出身、約150人)', '2024',
     'Jinbei 4内でサイバー犯罪とポンジ詐欺を強要され、バスケットコートで「解放とパスポート返還を」と叫んで蜂起した。',
     'https://www.business-standard.com/india-news/cambodia-job-scam-60-rescued-2-days-after-stranded-indians-stage-revolt-124052200564_1.html'),
    ('Jin Bei', 'survivor', '台湾人男性(53歳)', '2024',
     '「当時は疑わなかった。シハヌークビルに着くまで、自分が売られたとは知らなかった」。',
     'https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/'),
    ('Jin Bei', 'survivor', '台湾人男性(53歳)', '2024',
     '摘発下の深夜の突然の移送について—「全部まとめろと急に言われ、深夜1〜2時まで待たされた」。',
     'https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/'),

    # ---- Chinatown (Otres) ----
    ('Chinatown', 'survivor', '中国人の建設労働者(男性・姓 Lu)', '2022',
     '「着いた時にはもう逃げ遅れていた。それでも生きている限り、逃げ続けようと思った」。逃亡を試みて捕まり「頻繁に殴られた」。',
     'https://www.france24.com/en/live-news/20221109-inside-the-living-hell-of-cambodia-s-scam-operations'),
    ('Chinatown', 'survivor', 'マレーシア華人男性(38歳・仮名 Roy)', '2022',
     '「人を寝かせて、犬のように蹴る。電気ショックを与えることもある…5分から10分の暴行だ」。',
     'https://www.france24.com/en/live-news/20221109-inside-the-living-hell-of-cambodia-s-scam-operations'),
    ('Chinatown', 'survivor', '台湾人男性(38歳・仮名 Michael)', '2024',
     'チャイナタウン地区の拠点 Jinshui の建物に売られた—「一棟に最大800人収容できた。うちの会社だけで400〜500人いた」。',
     'https://www.voanews.com/a/scam-victims-say-human-trafficking-still-a-problem-in-cambodia/7520511.html'),
    ('Chinatown', 'survivor', '台湾人男性(38歳・仮名 Michael)', '2024',
     'カンボジアの施設で1年間、殴られ、暗闇に隔離され、電気警棒で感電させられた—「人生で最も暗い経験は、カンボジアだった」。',
     'https://www.voanews.com/a/scam-victims-say-human-trafficking-still-a-problem-in-cambodia/7520511.html'),
    ('Chinatown', 'witness', 'コンパウンド近くの韓国人レストラン経営者', '2025',
     '「これらのコンパウンドの多くは内部に独自の食堂を持つ。出前注文が入ると、たいてい中国人男性が料理を取りに出てくる」。',
     'https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound'),

    # ---- Dara Sakor (UDG / Long Bay) ----
    ('Dara Sakor', 'survivor', 'バングラデシュ人男性(27歳前後)', '2024',
     '幼なじみの「高給の仕事」の誘いで9時間かけてLong Bayへ—「すべての命令に従うしかない。お前は奴隷だ、彼らに売られたのだから」。',
     'https://asianews.network/i-was-told-to-scam-singaporeans-bangladeshi-man-who-was-trafficked-to-scam-compounds/'),
    ('Dara Sakor', 'survivor', 'バングラデシュ人男性(27歳前後)', '2024',
     '強要された恋愛詐欺について—「恋人を探している相手には恋人になり、友達がほしい相手には親友になる」。',
     'https://asianews.network/i-was-told-to-scam-singaporeans-bangladeshi-man-who-was-trafficked-to-scam-compounds/'),
    ('Dara Sakor', 'survivor', 'バングラデシュ人男性(1996年生)', '2024',
     'Long Bayで偽プロフィールを約100個作らされた。罰は腕立て25〜75回。「37日働かせた後、本当に我々を別の会社に売った」。',
     'https://www.humanity-consultancy.com/updates/the-horrible-5-month-life-in-scamming-compounds'),
    ('Dara Sakor', 'survivor', '台湾人男性(32歳・仮名 Sonny)', '2023',
     'Long Bayの暗号資産詐欺について—「相手を『先生』と呼び、まず客に儲けさせる。だが正しくないと思った。この人たちは後で騙されるのだと」。',
     'https://vodenglish.news/rescue-reveals-scam-compound-at-koh-kongs-udg/'),
    ('Dara Sakor', 'family', '台湾人の継父(58歳・仮名 Alex)', '2023',
     'Dara Sakorに囚われた継子を危険に晒した告発の漏洩後—「警察署を出た時は希望に満ちていた。だが夜、思った。『ああ、しくじった』と」。',
     'https://vodenglish.news/rescue-reveals-scam-compound-at-koh-kongs-udg/'),

    # ---- O'Smach ----
    ("O'Smach", 'survivor', 'ベトナム人女性(仮名 Diep)', '2025',
     '「3,000ドルでここに売られたと言われた」。リクルーターとボスが自分の値段を交渉するのを聞き、その後O’Smach内でさらに2回売られた。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ("O'Smach", 'survivor', 'ベトナム人女性(仮名 Diep)', '2025',
     'O’Smachの警察は「コンパウンドのために働いていて、救助要請をボスに通報する」。救出を求めた後、ボスに「残るか刑務所か」と迫られた。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ("O'Smach", 'rescuer', 'カンボジアの州警察幹部(Bou Boran)', '2025',
     'ネパール・パキスタン人ら約57人がベッド枠の鉄棒でO’Smach Resortから脱出した後—「何が問題かと尋ねると、Poipetへ働きに行きたいと言った」。',
     'https://www.rfa.org/english/cambodia/2025/01/06/cambodia-workers-flee-casino/'),
    ("O'Smach", 'witness', 'コンパウンド近くの地元住民', '2024',
     '「彼らの手は血だらけだった。足首も脚も—有刺鉄線の壁をよじ登るからだ。森に隠れると、カジノの警備員が探しに来る」。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ("O'Smach", 'worker', 'コンパウンド内に閉じ込められた労働者(国籍不明)', '2025',
     '2025年12月のタイ軍の攻撃中も、外国人労働者は「退去を許されず」、爆発で建物が揺れる中も詐欺を続けさせられたと目撃者が証言。',
     'https://www.csis.org/analysis/fraud-frontlines-scam-centers-caught-cambodia-thailand-conflict'),

    # ---- Poipet ----
    ('Poipet', 'survivor', 'インドネシア人女性(28歳・歌手・仮名 Kiki)', '2025',
     '「全員に1日5人を騙すノルマがあった。達成できないと翌日は12時間立たされたまま、朝8時半から夜6時まで働かされる」。',
     'https://english.cambodiadaily.com/2025/01/19/harrowing-ordeal-in-poipet-they-screamed-in-our-ears/'),
    ('Poipet', 'survivor', 'インドネシア人女性(28歳・仮名 Kiki)', '2025',
     '中国人の監督者は毎日「お前たちはインドネシアに帰れない、ここで死ぬ」と言った。「毎日が悲鳴に満ちていた…絶えず耳元で叫ばれた」。',
     'https://english.cambodiadaily.com/2025/01/19/harrowing-ordeal-in-poipet-they-screamed-in-our-ears/'),
    ('Poipet', 'survivor', 'タイ人男性(21歳)', '2025',
     '働くのを拒んで野球バットで殴られ監禁された後、Poipetのコンパウンドから脱出。3階から「拷問される人々の音」が聞こえ、そこを「生き地獄」と呼んだ。',
     'https://www.pattayamail.com/thailandnews/thai-man-escapes-cambodian-scam-compound-reveals-torture-of-nearly-100-foreigners-522980'),
    ('Poipet', 'survivor', 'タイ人女性(仮名 Yathada)', '2024',
     '泳げないため、プラスチック容器に入れられて小さな川を渡りカンボジアへ—「怖かった。運河のような所で…容器に入れと言われ、対岸で人が引っ張った」。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ('Poipet', 'survivor', 'タイ人男性(仮名 Jumpon)', '2024',
     'Poipetのコンパウンドで警備員に「暗い部屋」へ引きずり込まれ、殴られ、電気警棒で感電させられ、頭に布袋をかぶせられた。痛みで何度も気を失った。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),

    # ---- Bavet ----
    ('Bavet', 'survivor', '中国人の少年(16歳・仮名 Haoyu)', '2024',
     '「2日後にはBavetにいて、コンパウンド内に連れて行かれ、パソコンで入力しろと言われた」。ミスをすると上司に蹴られた。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ('Bavet', 'survivor', '中国人の少年(16歳・仮名 Haoyu)', '2024',
     'コンパウンド内で食事を配る途中、ある部屋から悲鳴が聞こえた—「自分も拷問されるのが怖くて、料理をその場に置いて逃げた」。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ('Bavet', 'survivor', 'ベトナム人の少年(15〜16歳・仮名 Van)', '2024',
     '夜のジャングルの小道からBavetのコンパウンドへ。手錠をかけられ、労働者が拷問用と知る10階の「会議室」で殴られ感電させられた。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ('Bavet', 'survivor', 'タイ人の少年(17歳・仮名 Sawat)', '2024',
     'Bavetの暗い部屋で上司が「これがお前の最後の食事だ」と言い、身代金・餓死・手足を折る、の3択を迫った。8階から飛び降りて脱出した。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ('Bavet', 'survivor', '中国人男性(19歳・仮名 Hongxi)', '2024',
     '到着時、4,500ドルで買われたのでその額の借金があると告げられた。ボスは「警察に位置情報を送った罰だ」とビール瓶を頭に叩き割った。',
     'https://www.amnesty.or.th/en/wp-content/uploads/sites/2/2025/06/I-was-someone-elses-property.pdf'),
    ('Bavet', 'worker', '急襲後に取材されたミャンマー人労働者', '2025',
     'Bavetのコンパウンドは国内で「最悪」だと語った。多くの被害者が、そこへ至るまでに何度も売られていたという。',
     'https://www.irrawaddy.com/news/burma/nearly-180-myanmar-workers-rescued-in-raid-on-cambodian-scam-center.html'),
]

cands = {lbl: cid for cid, lbl in cur.execute("SELECT id, label FROM compound_candidate")}
added = 0
for substr, role, speaker, year, quote, url in TESTIMONY:
    match = next((lbl for lbl in cands if substr in lbl), None)
    if not match:
        print(f"  [P9 SKIP] no candidate for '{substr}'")
        continue
    cur.execute("""INSERT INTO testimony(candidate_id, role, speaker, year, quote, source_url)
                   VALUES(?,?,?,?,?,?)""", (cands[match], role, speaker, year, quote, url))
    added += 1

con.commit()
print(f"[P9] added {added} testimonies.")
for label, n in cur.execute("""SELECT c.label, COUNT(t.id) FROM compound_candidate c
                                LEFT JOIN testimony t ON t.candidate_id=c.id
                                GROUP BY c.id ORDER BY c.id"""):
    print(f"  {n}  {label}")
con.close()
