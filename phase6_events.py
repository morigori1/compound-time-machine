"""Phase 6: collect & extract per-candidate events from public reporting.

Events were researched from public news/OSINT sources (Reuters, Al Jazeera, OCCRP,
CamboJA, RFA, Bangkok Post, Khmer Times, Wikipedia, ISEAS, Asia Times, etc.) and
curated here with date, kind, summary and a source URL. They feed the timeline-synced
event toasts in the dashboard.

`resolution` records date precision: 'day' / 'month' / 'year' (some events are only
known to month- or year-level; the day is then nominal).
Idempotent: re-running clears its own previously inserted rows first.
"""
import sqlite3, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')

con = sqlite3.connect(DB)
cur = con.cursor()

# (candidate_label_substring, kind, happened_on, resolution, summary, source_url)
EVENTS = [
    # ---- KK Park / Shwe Kokko ----
    ('KK Park', 'construction_start', '2017-03-01', 'month',
     'Yatai系 Shwe Kokko New City 着工。She Zhijiang主導の中国系開発として高層棟・カジノ群の建設が始まる',
     'https://thepeoplesmap.net/project/shwe-kokko-special-economic-zone-yatai-new-city/'),
    ('KK Park', 'permit', '2018-07-01', 'month',
     'ミャンマー投資委員会が第1期(約25.5エーカー・高級ヴィラ)のみ承認。実際の開発は承認範囲を大きく超過',
     'https://en.wikipedia.org/wiki/Shwe_Kokko'),
    ('KK Park', 'official_action', '2019-03-01', 'month',
     'カイン州政府、Yataiに対し承認範囲を超える建設の停止を命令',
     'https://en.wikipedia.org/wiki/Shwe_Kokko'),
    ('KK Park', 'investigation', '2020-06-01', 'month',
     'ミャンマー連邦政府、Shwe Kokkoの「不正」調査のため審判所(tribunal)を設置',
     'https://en.wikipedia.org/wiki/Shwe_Kokko'),
    ('KK Park', 'raid', '2025-10-21', 'day',
     'ミャンマー国軍、KK Park制圧を発表。2,000人超の労働者を解放し、Starlink端末30台を押収',
     'https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/'),
    ('KK Park', 'raid', '2025-11-19', 'day',
     'ミャンマー国軍がShwe Kokko地区を急襲、346人を拘束し携帯電話約1万台を押収',
     'https://www.aljazeera.com/news/2025/11/19/myanmar-military-raids-online-scam-hub-arrests-nearly-350-on-thai-border'),
    ('KK Park', 'demolition', '2025-12-13', 'day',
     'KK Parkで413棟を解体、残る222棟も解体予定と発表',
     'https://www.nationthailand.com/news/general/40059839'),
    ('KK Park', 'cross_border_op', '2025-12-15', 'day',
     'タイ・中国・ミャンマーがKK Park/Shwe Kokkoを合同視察。高層棟は恒久的に解体済みと発表',
     'https://www.nationthailand.com/news/general/40059839'),

    # ---- Jin Bei (Sihanoukville) ----
    ('Jin Bei', 'building_collapse', '2019-06-22', 'day',
     'シハヌークビルの建設現場が崩落、労働者28人が死亡。急速な中国系開発の歪みを象徴する事故',
     'https://asiatimes.com/2019/11/boom-to-bust-for-cambodias-chinese-casino-town/'),
    ('Jin Bei', 'gambling_ban', '2019-08-18', 'day',
     'カンボジアがオンライン賭博を禁止(フン・セン指令)。約12万人の中国人が流出しシハヌークビルはゴーストタウン化',
     'https://asiatimes.com/2019/11/boom-to-bust-for-cambodias-chinese-casino-town/'),
    ('Jin Bei', 'death', '2023-06-03', 'day',
     'Jin Bei 1の物業管理の身分証を持つ中国人 Yi Ming Dali(25歳)が、スーツケースに詰められた遺体で発見される',
     'https://cambojanews.com/dead-chinese-man-linked-to-alleged-scam-operation-sihanoukville-compound/'),
    ('Jin Bei', 'license_suspension', '2025-11-02', 'day',
     'カンボジア警察、Jin Bei Group系の4カジノを閉鎖・封印(技術詐欺の疑い)',
     'https://cambojanews.com/four-sville-casino-licenses-including-jin-bei-suspended/'),
    ('Jin Bei', 'license_revoked', '2026-02-22', 'day',
     'カンボジア、Chen Zhi系の5カジノ免許を正式に取消し',
     'https://agbrief.com/news/cambodia/22/02/2026/cambodia-revokes-five-casino-licenses-over-links-to-chen-zhis-cyber-fraud-network/'),

    # ---- Chinatown (Otres) ----
    ('Chinatown', 'building_collapse', '2019-06-22', 'day',
     'シハヌークビルの建設現場崩落で労働者28人死亡。詐欺都市化の前史となる開発バブル期の事故',
     'https://asiatimes.com/2019/11/boom-to-bust-for-cambodias-chinese-casino-town/'),
    ('Chinatown', 'gambling_ban', '2019-08-18', 'day',
     'オンライン賭博禁止でシハヌークビルから中国人約12万人が流出。空いた区画が詐欺拠点に転用されていく',
     'https://asiatimes.com/2019/11/boom-to-bust-for-cambodias-chinese-casino-town/'),
    ('Chinatown', 'media_investigation', '2022-11-09', 'day',
     'France24等がシハヌークビルのスキャムコンパウンドの実態(「生き地獄」)を報道',
     'https://www.france24.com/en/live-news/20221109-inside-the-living-hell-of-cambodia-s-scam-operations'),
    ('Chinatown', 'pre_raid_flight', '2026-01-15', 'month',
     'シハヌークビルで、摘発を察知した外国人労働者が一斉に退避したと住民が証言',
     'https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/'),

    # ---- Dara Sakor (UDG) ----
    ('Dara Sakor', 'lease_granted', '2008-01-01', 'year',
     '2008年、中国系 Union Development Group がコッコン州の広大な区域で99年リースを取得(空港・港・リゾートに39億ドル投資計画)',
     'https://en.wikipedia.org/wiki/Dara_Sakor'),
    ('Dara Sakor', 'land_dispute', '2018-03-01', 'month',
     '土地紛争を受け、カンボジア政府が一部用地の住民返還を環境省に指示',
     'https://en.wikipedia.org/wiki/Dara_Sakor'),
    ('Dara Sakor', 'sanction', '2020-09-01', 'month',
     '米政府(OFAC)が、土地収用・人権侵害・軍事転用懸念を理由にUDGを制裁対象に指定',
     'https://en.wikipedia.org/wiki/Dara_Sakor'),
    ('Dara Sakor', 'rescue', '2022-07-01', 'month',
     'Dara Sakor圏のLong Bayプロジェクトから人身売買被害者50人以上が救出される',
     'https://vodenglish.news/rescue-reveals-scam-compound-at-koh-kongs-udg/'),
    ('Dara Sakor', 'raid', '2026-02-04', 'day',
     'Dara Sakor圏で詐欺コンパウンドの急襲。撮影した記者が一時拘束される',
     'https://thediplomat.com/2026/02/cambodian-reporter-detained-after-photographing-raid-on-scam-center'),

    # ---- O'Smach ----
    ("O'Smach", 'sanction', '2024-09-12', 'day',
     'OFAC、O’Smach Resortと所有者 Ly Yong Phat 上院議員を強制労働関与で制裁対象に指定',
     'https://home.treasury.gov/news/press-releases/jy2576'),
    ("O'Smach", 'worker_escape', '2025-01-06', 'day',
     'ネパール・パキスタン人ら約60人が、ベッド枠で作った棒を手にO’Smachカジノから集団脱出',
     'https://www.rfa.org/english/cambodia/2025/01/06/cambodia-workers-flee-casino/'),
    ("O'Smach", 'border_clash', '2025-12-09', 'day',
     'タイ軍がO’Smachカジノを砲撃(国境衝突)。施設内に人身売買被害者の存在が懸念される',
     'https://mekongindependent.com/2025/12/shelling-one-dead-at-scam-linked-casino-in-renewed-border-clash-local-police/'),
    ("O'Smach", 'evidence_seized', '2025-12-15', 'month',
     'タイ軍がO’Smach複合体で詐欺の証拠(SIMカード871枚、各国の偽警察制服・偽警察署の部屋)を押収',
     'https://www.bangkokpost.com/thailand/general/3189395/cambodian-scam-compound-yields-trove-of-fraud-evidence-thai-military-says'),

    # ---- Poipet ----
    ('Poipet', 'rescue', '2025-02-12', 'month',
     'タイ・カンボジア警察が3か月の捜査の末、Poipetの3階建てから215人(タイ人109人ら)を救出',
     'https://thediplomat.com/2025/02/thai-cambodian-police-rescue-215-trafficked-scam-workers/'),
    ('Poipet', 'raid', '2025-07-16', 'day',
     'Poipet市スタントゥングン通りの3階建てで作戦、インドネシア人271人(うち女性45人)を発見',
     'https://www.khmertimeskh.com/501718769/271-foreigners-arrested-in-crackdown-on-poipet-scam-centre/'),

    # ---- Bavet ----
    ('Bavet', 'raid', '2025-11-04', 'day',
     'Bavet市の詐欺コンパウンド2棟(うち1棟は「Li Zhou」)で658人超を拘束。銃声の中を逃げる人々の映像が拡散',
     'https://cambojanews.com/police-arrest-over-600-foreigners-in-online-scam-compounds-in-bavet/'),
    ('Bavet', 'raid', '2026-01-31', 'day',
     '精鋭警官約700人がA7カジノ複合体(別名Wan Cheng)を急襲、2,044人を拘束(中国人1,792人)',
     'https://www.scmp.com/news/china/diplomacy/article/3342011/nearly-1800-chinese-among-thousands-held-huge-cambodian-raid-scam-compound'),

    # ===== older background events (2000s–2023) =====
    ('KK Park', 'construction', '2021-01-01', 'year',
     'KK Park本体(Shwe Kokkoとは別区画)が2019〜2021年に建設される。当初は国境貿易用途と説明されていた',
     'https://en.wikipedia.org/wiki/KK_Park'),
    ('KK Park', 'activity_surge', '2022-07-01', 'month',
     '衛星の夜間光が2022年半ばから急増。コンパウンドの稼働が一気に拡大したことを示す',
     'https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/'),
    ('KK Park', 'electricity_cut', '2023-06-07', 'day',
     'タイ電力公社がKK Park/Shwe Kokkoへの送電を停止(ミャンマー側が契約を更新せず)',
     'https://en.wikipedia.org/wiki/KK_Park'),
    ('KK Park', 'estimate', '2023-07-01', 'month',
     '2023年7月時点で、KK Park/Shwe Kokkoに少なくとも2万人の詐欺労働者がいると推計される',
     'https://en.wikipedia.org/wiki/KK_Park'),

    ('Jin Bei', 'bri_join', '2013-01-01', 'year',
     'カンボジアが中国の一帯一路に参加(2013年)。シハヌークビルへの中国資本流入の起点となる',
     'https://globalchinapulse.net/sihanoukville-rise-and-fall-of-a-frontier-city/'),
    ('Jin Bei', 'casino_boom', '2017-01-01', 'year',
     '2010年代半ば、シハヌークビルが中国人向けカジノ都市へ急変。Lixin Groupが2017年にWM Hotel & Casinoを開業',
     'https://globalchinapulse.net/sihanoukville-rise-and-fall-of-a-frontier-city/'),
    ('Jin Bei', 'media_investigation', '2022-08-23', 'day',
     'RFA等が、シハヌークビルの中国系カジノに絡む人身売買・求人詐欺を詳細に報道',
     'https://www.rfa.org/english/news/china/taiwan-cambodia-scam-08232022132211.html'),

    ('Chinatown', 'bri_join', '2013-01-01', 'year',
     'カンボジアの一帯一路参加(2013年)以降、中国投資が急増。シハヌークビル変貌の起点',
     'https://chinalaborwatch.org/the-aftermath-of-the-belt-and-road-initiative-human-trafficking-in-cambodia/'),
    ('Chinatown', 'casino_boom', '2017-01-01', 'year',
     '2010年代半ば、シハヌークビルは中国人向けカジノ都市へ。詐欺業務は合法カジノに紛れて拡大していく',
     'https://globalchinapulse.net/sihanoukville-rise-and-fall-of-a-frontier-city/'),

    ("O'Smach", 'rescue', '2022-10-18', 'day',
     'カンボジア当局、O’Smachのカジノ地区で人身売買被害者75人を救出',
     'https://www.business-humanrights.org/en/latest-news/cambodia-govt-rescue-75-foreign-victims-of-human-trafficking-in-oddar-meanchey-province-in-ongoing-efforts-to-combat-surging-online-scams-and-human-trifficking/'),
    ("O'Smach", 'rescue', '2024-03-16', 'day',
     'タイ・カンボジア合同部隊、O’Smach国境付近の詐欺拠点からタイ人を救出(救出人数は両国で食い違い)',
     'https://cambojanews.com/cambodian-authorities-dispute-thai-governments-account-of-scam-compound-rescue-in-osmach/'),

    ('Poipet', 'casino_development', '2000-01-01', 'year',
     'Poipetはタイ国境のカジノ街として2000年代に発展。Grand Diamond City等の大型カジノが立ち並ぶ',
     'https://en.wikipedia.org/wiki/Poipet'),
    ('Poipet', 'fire', '2022-12-28', 'day',
     'Poipetの大型カジノ Grand Diamond City が火災で全焼、27人以上死亡。後に「オンライン業務」部屋の存在が証言される',
     'https://en.wikipedia.org/wiki/Poipet_casino_hotel_fire'),

    ('Bavet', 'casino_development', '2005-01-01', 'year',
     'Bavetはベトナム国境のカジノ街として2000年代に発展。後に既存カジノへコンクリート棟群が増設されていく',
     'https://en.wikipedia.org/wiki/Scam_centers_in_Cambodia'),
    ('Bavet', 'violence', '2019-01-01', 'year',
     '2019年、Bavetの Oriental Paris カジノで警備員が中国人労働者を暴行したと中国系掲示板で告発される',
     'https://en.wikipedia.org/wiki/Scam_centers_in_Cambodia'),
    ('Bavet', 'worker_protest', '2023-07-18', 'day',
     'Bavetのオリエンタル・パリ・カジノでベトナム人従業員35人が救助を求め、警察が連れ出す',
     'https://cambojanews.com/dozens-of-vietnamese-questioned-by-police-after-allegedly-seeking-escape-from-bavet-casino/'),

    # ===== additional researched events (2020–2026, OSINT-sourced) =====
    ('Jin Bei', 'construction', '2020-03-09', 'day',
     'Jin Bei カジノ&ホテルの新タワーがシハヌークビルで正式オープン',
     'https://focusgn.com/asia-pacific/jin-bei-casino-and-hotel-in-sihanoukville-to-reopen'),
    ('Jin Bei', 'closure', '2021-02-25', 'day',
     '中国人客のコロナ感染を受け、Jin Bei カジノ&ホテル全館が警察に封鎖され従業員と客が閉じ込められる',
     'https://www.asgam.com/index.php/2021/02/25/sihanoukville-hotels-and-casinos-locked-down-after-covid-19-cases/'),
    ('Jin Bei', 'reopening', '2021-03-16', 'day',
     'プレアシハヌーク州知事が Jin Bei カジノ&ホテルの通常営業再開を許可',
     'https://pacificasiaholdings.com/2021/03/16/sihanoukvilles-jin-bei-casino-allowed-to-reopen-as-cambodian-covid-outbreak-spreads/'),
    ('Jin Bei', 'corporate', '2021-12-01', 'year',
     'Chen Zhi らが設立した Jin Bei(カンボジア)投資会社が解散される',
     'https://www.rfa.org/english/special-reports/prince-group/assets/p1-prince-group-investigation.html'),
    ('Jin Bei', 'worker_escape', '2023-02-01', 'month',
     '人身売買被害者「Ko」が Jin Bei 4 に転売され、3月末まで強制労働させられる',
     'https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/'),
    ('Jin Bei', 'arrest', '2023-06-10', 'day',
     'Yi Ming Dali 殺害に関与したとして中国人容疑者4人が逮捕される',
     'https://cambojanews.com/dead-chinese-man-linked-to-alleged-scam-operation-sihanoukville-compound/'),
    ('Jin Bei', 'raid', '2024-05-21', 'day',
     '警察が Jin Bei 4 カジノを家宅捜索、労働争議をめぐりインド人57人を聴取',
     'https://cambojanews.com/police-raid-jin-bei-casino-confirming-its-a-labor-dispute-not-online-scam-ops/'),
    ('Jin Bei', 'worker_escape', '2026-01-14', 'day',
     '警察が Jin Bei 6 に立ち入った日、労働者がスーツケースを引いて施設から退去する姿が確認される',
     'https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/'),

    ('Chinatown', 'rescue', '2022-02-18', 'day',
     '「チャイナタウン」GMオフィスからタイ人スキャム労働者13人が救出されたと報道',
     'https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/'),
    ('Chinatown', 'death', '2022-03-12', 'day',
     'チャイナタウンの23号棟で、カンボジア人警備員 Thun Thep(25歳)が首を吊った状態で発見される',
     'https://vodenglish.news/body-found-hanging-in-sihanoukvilles-alleged-slave-compound-area/'),
    ('Chinatown', 'worker_escape', '2022-09-17', 'day',
     '警察の手入れを前に、チャイナタウン一帯から労働者が一斉に運び出され始める',
     'https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/'),
    ('Chinatown', 'raid', '2022-09-18', 'day',
     '警察捜査でチャイナタウン(ブオン地区)の建物群が空に。週末に1,000人以上が退去',
     'https://globalinitiative.net/wp-content/uploads/2022/09/GI-TOC-report_Sihanoukville_For-upload.pdf'),
    ('Chinatown', 'report', '2023-06-01', 'month',
     '9月の手入れ後も、チャイナタウンの拠点 Jinshui に人身売買被害者が転売されていたと報道',
     'https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/'),
    ('Chinatown', 'sanction', '2023-12-07', 'day',
     '英国、チャイナタウンのKBホテル(Kaibo)を強制労働を伴うスキャム関与で制裁対象に指定',
     'https://www.opensanctions.org/entities/NK-LQBNzodiRNqduqKNCDqxUH/'),
    ('Chinatown', 'sanction', '2025-09-08', 'day',
     '米財務省OFAC、チャイナタウンのKBホテルをサイバースキャム支援で制裁対象に指定',
     'https://home.treasury.gov/news/press-releases/sb0237'),

    ('Dara Sakor', 'construction', '2007-01-01', 'year',
     '中国政府、Dara Sakor開発を一帯一路事業として採択し1,500万ドルの債券を引き受け',
     'https://en.wikipedia.org/wiki/Dara_Sakor'),
    ('Dara Sakor', 'construction', '2018-01-01', 'year',
     'UDGの45,000ヘクタール用地内で、ラグジュアリーリゾート「Long Bay」プロジェクトが立ち上げられる',
     'https://vodenglish.news/rescue-reveals-scam-compound-at-koh-kongs-udg/'),
    ('Dara Sakor', 'report', '2021-10-01', 'month',
     '土地紛争の被害世帯数百が、開発業者の抽選方式の補償案を不十分として拒否',
     'https://en.wikipedia.org/wiki/Dara_Sakor'),
    ('Dara Sakor', 'rescue', '2022-06-11', 'day',
     'Long Bayで人身売買された台湾人男性 Zheng Shu が、GASO等の介入で解放される',
     'https://www.globalantiscam.org/post/is-human-trafficking-victim-still-a-victim-in-the-end'),
    ('Dara Sakor', 'rescue', '2022-12-04', 'day',
     '中国人3人が、Long Bayカジノ&ホテルでの人身売買・監禁事件として救出を求める',
     'https://cambojanews.com/company-with-ties-to-scams-human-trafficking-ousted-from-cambodia-property-awards/'),
    ('Dara Sakor', 'construction', '2023-02-22', 'day',
     'コッコン州知事、Dara Sakor国際空港が2023年半ばに運用開始すると発表',
     'https://en.wikipedia.org/wiki/Dara_Sakor_International_Airport'),
    ('Dara Sakor', 'arrest', '2023-06-29', 'day',
     'UDGへの土地紛争抗議に向かう途中、コッコン州の検問所で村人11人が扇動罪で逮捕される',
     'https://www.rfa.org/english/news/cambodia/koh-kong-roadblock-06302023152042.html'),
    ('Dara Sakor', 'report', '2023-07-25', 'day',
     'カンボジア不動産賞が、Long Bay関連企業 Jenheng の全ノミネートを取り消し',
     'https://cambojanews.com/company-with-ties-to-scams-human-trafficking-ousted-from-cambodia-property-awards/'),
    ('Dara Sakor', 'construction', '2024-12-26', 'day',
     'Dara Sakor国際空港が、プノンペンからのチャーター便到着で試験運用を開始',
     'https://centreforaviation.com/news/dara-sakor-international-airport-receives-inaugural-domestic-flight-1297632'),
    ('Dara Sakor', 'construction', '2025-04-01', 'month',
     'カンボジア・エアウェイズが、Dara Sakor国際空港への初の定期商業便を就航',
     'https://www.ttrweekly.com/site/2025/04/cambodia-air-flies-to-dara-sakor/'),
    ('Dara Sakor', 'construction', '2025-12-14', 'day',
     'Air Cambodia が、テチョ国際空港と Dara Sakor 空港を結ぶ週2便の路線を開設',
     'https://www.aircambodia.com/en/offer/-welcome-the-new-domestic-route-to-the-southwest-of-cambodia'),
    ('Dara Sakor', 'raid', '2026-01-26', 'day',
     '全国的なスキャム摘発のなか、Dara Sakorで建物の退去と外国人労働者の出発が確認される',
     'https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/'),

    ('Poipet', 'fire', '2023-08-04', 'day',
     '旧V9インターナショナル・ホテルで火災。インドネシア人少なくとも3人がバルコニーから飛び降り重傷',
     'https://cyberscammonitor.net/profile/former-v9-international-hotel/'),
    ('Poipet', 'fire', '2023-09-15', 'day',
     'Poipetの10階建てMindoホテル屋上で火災。中国人ら宿泊客は全員避難',
     'https://thainewsroom.com/2023/09/16/another-hotel-in-poipet-catches-fire-but-no-casualties/'),
    ('Poipet', 'death', '2024-09-23', 'day',
     'Poipetのオンライン賭博会社で、盗みの疑いをかけられたインドネシア人男性が同胞22人に撲殺される',
     'https://jakartaglobe.id/news/22-indonesians-beat-fellow-indonesian-to-death-in-cambodia'),
    ('Poipet', 'arrest', '2025-07-05', 'day',
     'タイ警察、PoipetのPuryカジノ拠点の中国系詐欺グループ2人を逮捕(被害総額約3億バーツ)',
     'https://www.nationthailand.com/blogs/news/general/40052184'),
    ('Poipet', 'death', '2025-11-18', 'day',
     'PoipetのB棟218号室で、ノルマ未達のタイ人男性が鉄棒と電気棒で拷問され死亡',
     'https://www.nationthailand.com/blogs/news/asean/40058432'),
    ('Poipet', 'border_clash', '2025-12-19', 'day',
     'タイ空軍のF-16が、Poipet地区の詐欺センター5か所を爆撃',
     'https://cambojanews.com/after-thai-strikes-hit-cambodian-elites-casinos-trafficked-workers-feared-inside/'),
    ('Poipet', 'raid', '2026-03-12', 'day',
     'Poipet市外約30kmの遠隔地で、カンボジア国家警察が詐欺関連施設を急襲',
     'https://mekongindependent.com/2026/03/raids-strike-remote-compounds-outside-poipet-city/'),
    ('Poipet', 'shootout', '2026-04-30', 'day',
     'PoipetのBao Long 3詐欺施設で数時間にわたる銃撃戦が発生、労働者が逃走',
     'https://kouprey.substack.com/p/shootout-at-poipet-scam-compound'),

    ('Bavet', 'death', '2022-06-14', 'day',
     'Bavet経済特区のHeng Heカジノで、28歳のベトナム人労働者 Tran Van Ban が首を吊って死亡',
     'https://www.casino.org/news/vietnamese-worker-found-hanged-in-cambodia-casino/'),
    ('Bavet', 'worker_escape', '2022-09-16', 'day',
     'Bavetのモクバイ・カジノが倒産との噂を受け、ベトナム人60人超が逃走',
     'https://vodenglish.news/60-vietnamese-escape-bavet-moc-bai-casino/'),
    ('Bavet', 'fire', '2023-03-01', 'month',
     'Bavetのオリエンタル・パリ・カジノで、電気系統が原因の火災が発生',
     'https://cambojanews.com/dozens-of-vietnamese-questioned-by-police-after-allegedly-seeking-escape-from-bavet-casino/'),
    ('Bavet', 'death', '2023-04-20', 'day',
     'Bavet市で、カジノ従業員 Mon Sreymey(24歳)が斬首遺体で発見される',
     'https://cambojanews.com/female-employee-of-tycoons-call-center-casino-in-bavet-beheaded/'),
    ('Bavet', 'raid', '2025-11-01', 'day',
     'BavetのSilver Starカジノが詐欺ネットワーク摘発で急襲され、外国人23人拘束・免許停止',
     'https://news.worldcasinodirectory.com/silver-star-casino-closed-in-cambodia-after-cyber-fraud-operation-120437'),
    ('Bavet', 'report', '2026-01-18', 'day',
     'BavetのCrownカジノ等で有刺鉄線が撤去され、労働者が荷物を持って大量退去',
     'https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/'),
    ('Bavet', 'raid', '2026-04-07', 'day',
     'BavetのGolden Galaxyカジノが急襲され、容疑者244人拘束・運営会社の免許取消',
     'https://www.akp.gov.kh/post/detail/367178'),
]

# idempotent: drop rows inserted by a previous phase6 run
cur.execute("DELETE FROM event WHERE source_id IN (SELECT id FROM source WHERE kind='news_p6')")
cur.execute("DELETE FROM source WHERE kind='news_p6'")
con.commit()

cands = {}
for cid, label, pid in cur.execute(
        "SELECT id, label, place_id FROM compound_candidate"):
    cands[label] = (cid, pid)

now = datetime.datetime.now(datetime.timezone.utc).isoformat()[:19] + 'Z'
added, skipped = 0, 0
for substr, kind, date, resolution, summary, url in EVENTS:
    match = next((lbl for lbl in cands if substr in lbl), None)
    if not match:
        print(f"  [P6 SKIP] no candidate matches '{substr}'")
        skipped += 1
        continue
    cid, pid = cands[match]
    cur.execute("INSERT INTO source(kind, url, captured_at) VALUES('news_p6', ?, ?)", (url, now))
    src_id = cur.lastrowid
    cur.execute("""INSERT INTO event(kind, happened_on, resolution, place_id, candidate_id, summary, source_id)
                   VALUES(?,?,?,?,?,?,?)""",
                (kind, date, resolution, pid, cid, summary, src_id))
    added += 1

con.commit()
print(f"[P6] added {added} events ({skipped} skipped).")
print("--- events per candidate (incl. earlier phases) ---")
for label, n in cur.execute("""SELECT c.label, COUNT(e.id) FROM compound_candidate c
                                LEFT JOIN event e ON e.candidate_id=c.id
                                GROUP BY c.id ORDER BY c.id"""):
    print(f"  {n:2d}  {label}")
print(f"  total events: {cur.execute('SELECT COUNT(*) FROM event').fetchone()[0]}")
con.close()
