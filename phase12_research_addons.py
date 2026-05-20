"""Phase 12: exhaustive research add-ons (events / testimony / snippets / details).

Two research agents made a maximum-collection pass with no per-compound cap, returning
~430 additional sourced items beyond what phase6/9/10/11 already curated. This script
inserts those add-ons on top of the existing data, marked with origin='p12' so the
dashboard shows everything together while the script stays idempotent.

Some items will overlap with phase6/9/10/11 entries (same date, same speaker, similar
detail). That is accepted: the user's instruction was "do not stop data collection
partway through". Duplicates are a price for completeness.
"""
import sqlite3, os, html, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')

con = sqlite3.connect(DB)
cur = con.cursor()

# Make sure the three reporting tables have an `origin` column we can filter on.
for table in ('testimony', 'life_snippet', 'danger_detail'):
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
    if 'origin' not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN origin TEXT DEFAULT 'core'")
con.commit()

# idempotent cleanup of previous phase12 inserts
cur.execute("DELETE FROM event WHERE source_id IN (SELECT id FROM source WHERE kind='news_p12')")
cur.execute("DELETE FROM source WHERE kind='news_p12'")
cur.execute("DELETE FROM testimony WHERE origin='p12'")
cur.execute("DELETE FROM life_snippet WHERE origin='p12'")
cur.execute("DELETE FROM danger_detail WHERE origin='p12'")
con.commit()

# Raw items from both research agents, pipe-delimited.
# E | LOCATION | YYYY-MM-DD | precision | kind | jp_summary | url
# T | LOCATION | role        | speaker_jp     | YYYY | quote_jp     | url
# S | LOCATION | topic_jp    | observation_jp | source_label | url
# D | LOCATION | category    | fragment_jp    | url
ADDONS = r"""
E | KK Park | 2016-12-01 | month | yatai_agreement_signed | BGFのソー・チットゥとシェー・ジージャンがShwe Kokko開発合意書に署名 | https://en.wikipedia.org/wiki/Shwe_Kokko
E | KK Park | 2017-01-01 | year | construction_begins | Shwe Kokko Yatai New Cityの大規模建設が許可範囲を超えて開始される | https://thepeoplesmap.net/project/shwe-kokko-special-economic-zone-yatai-new-city/
E | KK Park | 2021-02-01 | month | coup_resumes_construction | ミャンマー軍事クーデターで内戦化し、Yatai開発が再加速 | https://en.wikipedia.org/wiki/Shwe_Kokko
E | KK Park | 2022-08-01 | month | she_zhijiang_arrest_thailand | Yatai創業者 She Zhijiang がバンコクで国際手配により逮捕される | https://www.nationthailand.com/news/general/40046012
E | KK Park | 2022-08-01 | month | junta_sweep_myawaddy | ミャンマー軍がミャワディ地区のオンライン詐欺企業を一斉摘発 | https://en.wikipedia.org/wiki/KK_Park
E | KK Park | 2023-04-01 | month | kawthoolei_offensive | カウトレイ軍がBGFを攻撃し1万人以上がタイへ避難 | https://en.wikipedia.org/wiki/Shwe_Kokko
E | KK Park | 2023-12-01 | month | uk_sanctions_chit_thu | 英国が Saw Chit Thu と She Zhijiang らに人身売買絡みの制裁を発動 | https://en.wikipedia.org/wiki/Shwe_Kokko
E | KK Park | 2024-10-01 | month | eu_sanctions_yatai | EUがYatai計画関係者とChit Linn Myaing社に制裁を科す | https://en.wikipedia.org/wiki/Shwe_Kokko
E | KK Park | 2025-01-03 | day | wang_xing_kidnapping | 中国人俳優 Wang Xing がメソットからミャワディへ拉致されKK Parkに監禁 | https://en.wikipedia.org/wiki/Kidnapping_of_Wang_Xing
E | KK Park | 2025-01-07 | day | wang_xing_rescue | タイ警察がWang Xingをミャワディから救出しタイへ帰還 | https://en.wikipedia.org/wiki/Kidnapping_of_Wang_Xing
E | KK Park | 2025-02-01 | month | thailand_cuts_power_fuel | タイが越境送電と燃料輸出を停止し、KK Parkへの圧力が高まる | https://en.wikipedia.org/wiki/Shwe_Kokko
E | KK Park | 2025-05-05 | day | ofac_sanctions_kna | 米財務省がカレン民族軍と Saw Chit Thu 親子を越境犯罪組織として制裁 | https://home.treasury.gov/news/press-releases/sb0129
E | KK Park | 2025-09-08 | day | ofac_secondary_sanctions | OFACがKNA系列12社2人を追加制裁 | https://www.securityweek.com/us-sanctions-myanmar-militia-involved-in-cyber-scams/
E | KK Park | 2025-10-19 | day | junta_operation_begins | ミャンマー軍とBGFがKK Parkへの本格作戦を開始 | https://www.nationthailand.com/blogs/news/general/40057056
E | KK Park | 2025-10-22 | day | spacex_disables_starlink | SpaceXがミャンマー国内2,500台以上のStarlinkを無効化 | https://www.cnn.com/2025/10/23/asia/myanmar-starlink-scam-centers-spacex-intl-hnk
E | KK Park | 2025-10-23 | day | explosions_kkpark | KK Parkで複数の爆発が確認、タイ側にも音が響く | https://www.nationthailand.com/news/general/40057281
E | KK Park | 2025-10-24 | day | demolition_begins | ミャンマー軍が詐欺関連建物を爆破解体する作戦を本格化 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
E | KK Park | 2025-10-26 | day | fourth_explosion | 第四の大規模爆発でBGF系部隊が詐欺ビルを破壊 | https://www.nationthailand.com/news/general/40057351
E | KK Park | 2025-10-29 | day | thailand_processes_1563 | タイ側のメーソットに1,563人が越境し処理が開始 | https://www.chiangraitimes.com/news/thailand-help-kk-park-escapees/
E | KK Park | 2025-10-31 | day | escapees_reach_1667 | 越境者は1,667人に膨れ上がり、28カ国の国民が含まれた | https://newsletter.freedomcollaborative.org/kk-park-evacuees-face-dire-conditions-at-the-thai-myanmar-border/
E | KK Park | 2025-11-06 | day | india_airlift_270 | インド空軍C-130J 2機がメソットから270人のインド人を帰国させる | https://www.khaosodenglish.com/news/2025/11/02/indian-air-force-to-evacuate-workers-fleeing-kk-park-attacks/
E | KK Park | 2025-11-10 | day | india_airlift_197 | インド空軍が更に197人を退避させ累計467人に | https://en.wikipedia.org/wiki/KK_Park
E | KK Park | 2025-11-12 | day | she_zhijiang_extradition_order | タイ控訴裁が She Zhijiang の中国送還を90日以内に命じる | https://www.expressandstar.com/world-news/2025/11/12/thailand-court-orders-extradition-of-alleged-online-gambling-kingpin-to-china/
E | KK Park | 2025-11-13 | day | ofac_thai_company_sanctions | OFACがタイのTrans Asia社など詐欺施設関連企業を制裁 | https://www.khaosodenglish.com/politics/2025/11/13/u-s-sanctions-thai-company-tied-to-myanmar-scam-operations/
E | KK Park | 2025-11-21 | day | shunda_park_storm | KNUが Shunda Park 詐欺施設を制圧 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
E | KK Park | 2025-11-25 | day | myanmar_witness_report | Myanmar WitnessがKK Park破壊の限界を分析する衛星画像報告書を公開 | https://eng.mizzima.com/2025/11/25/28507
E | KK Park | 2025-12-10 | day | nepali_repatriation | 47人のネパール人がカトマンズに帰還 | https://kathmandupost.com/nepali-diaspora/2025/12/10/47-nepalis-rescued-from-online-scamming-centres-in-myanmar
E | KK Park | 2025-12-15 | day | global_new_light_coverage | ミャンマー政府機関紙が反詐欺対策を5ページ特集 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
E | KK Park | 2026-02-02 | day | china_executes_suspects | 中国がミャンマー詐欺施設関連の容疑者を追加処刑 | https://www.aljazeera.com/news/2026/2/2/china-carries-out-further-executions-of-myanmar-scam-centre-suspects
E | Jin Bei | 2017-01-01 | year | jinbei_hotel_opens | 7階建て16,500平米のJin Bei Hotel and Casinoがシハヌークビルで開業 | https://www.rfa.org/english/special-reports/prince-group/assets/p1-prince-group-investigation.html
E | Jin Bei | 2017-01-01 | year | jinbei_investment_founded | Chen Zhi が Sar Sokha と共に Jin Bei 投資社を設立 | https://thediplomat.com/2025/10/after-prince-group-sanctions-unanswered-questions-for-cambodias-interior-minister/
E | Jin Bei | 2018-01-01 | year | sokha_divests | Sar Sokha が Jin Bei 投資社の株式を売却したと当局は発表 | https://www.khmertimeskh.com/501776867/ministry-rejects-allegations-linking-sokha-to-jin-bei-casino/
E | Jin Bei | 2021-01-01 | year | jinbei_investment_dissolved | Chen Zhi と Sokha 家の Jin Bei 投資社が解散登記される | https://www.rfa.org/english/news/cambodia/prince-group-investigation-02022024124011.html
E | Jin Bei | 2024-05-20 | day | indians_rescued_jinbei4 | インド人約60人がJin Bei 4 から救出される | https://www.business-standard.com/india-news/cambodia-job-scam-60-rescued-2-days-after-stranded-indians-stage-revolt-124052200564_1.html
E | Jin Bei | 2024-05-20 | day | indian_revolt | 約300人のインド人がJin Bei 4内で暴動を起こす | https://www.business-standard.com/india-news/cambodia-job-scam-60-rescued-2-days-after-stranded-indians-stage-revolt-124052200564_1.html
E | Jin Bei | 2025-08-06 | day | park_minho_body_found | 韓国人留学生 Park Minho がカンポット州のフォードトラックで遺体発見 | https://www.koreatimes.co.kr/southkorea/law-crime/20251018/body-of-korean-student-killed-in-cambodia-awaits-autopsy-as-flawed-rescue-system-draws-criticism
E | Jin Bei | 2025-10-14 | day | ofac_prince_group_sanctions | OFACが Prince Group と Jin Bei 集団を含む146団体を制裁指定 | https://ofac.treasury.gov/recent-actions/20251014
E | Jin Bei | 2025-10-14 | day | uk_freeze_chen_assets | 英国が Chen Zhi の英国内資産を凍結 | https://www.gov.uk/government/news/uk-and-us-take-joint-action-to-disrupt-major-online-fraud-network
E | Jin Bei | 2025-10-15 | day | jinbei_palace_open_despite | 制裁発表後も Jin Bei Palace Hotel は通常営業を継続 | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/cambodian-hotel-under-us-sanctions-remains-open-as-tourism-crime-coexist-in-sihanoukville
E | Jin Bei | 2025-10-16 | day | rescued_koreans_testify | 救出された韓国人2名が金属パイプ拷問の体験を韓国紙に証言 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
E | Jin Bei | 2026-01-18 | day | sihanoukville_raid | カンボジア当局がシハヌークビルのカジノ施設で外国人多数を救出 | https://www.newsflare.com/video/830292/cambodia-raids-online-scam-center-in-sihanoukville-rescues-foreign-workers
E | Jin Bei | 2026-04-01 | month | amnesty_casino_state_report | アムネスティが詐欺施設関連カジノへの国家承認を批判する報告書を発表 | https://www.amnesty.org/en/latest/news/2026/04/cambodia-casinos-get-state-approval-despite-links-to-human-rights-abuse-at-scamming-compounds/
E | Chinatown | 2021-06-01 | month | corpse_chinatown | チャイナタウン詐欺施設付近で死体が発見される | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
E | Chinatown | 2021-09-01 | month | zhang_abducted | 中国人 Zhang が拉致されクラウン施設に売られる | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
E | Chinatown | 2021-11-01 | month | beach_club_opening | 副首相 Men Sam An 臨席のもとビーチクラブが開業 | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
E | Chinatown | 2022-08-01 | month | vietnamese_swim_kandal | ベトナム人労働者数十人がカジノから脱出しビンディ川を泳いで帰国 | https://www.rfa.org/english/news/cambodia/casino-workers-08222022191219.html
E | Chinatown | 2022-09-17 | day | big_transfer | 8千-1万人の労働者が国道4号沿いの新拠点へ深夜に一斉移送される | https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/
E | Chinatown | 2024-05-20 | day | indians_rescued_chinatown_area | チャイナタウン周辺施設からインド人60人が救出される | https://www.rfa.org/english/news/cambodia/indians-online-scams-05232024154819.html
E | Chinatown | 2025-09-29 | day | korean_rescue_160days | 160日間監禁された韓国人男性Aが警察に救出される | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
E | Chinatown | 2026-01-05 | day | sub_decree_owner_accountable | 内務省が違法テナント活動について所有者責任を問う準則を可決 | https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/
E | Chinatown | 2026-01-14 | day | mass_exodus_chinatown | チャイナタウンとオクチュテアル海岸で2時間以上の脱出行列が観察される | https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/
E | Chinatown | 2026-01-15 | day | sihanoukville_buses_overnight | オトレス2チャイナタウン地区で深夜に5-6台のバスが労働者を運び出す | https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/
E | Dara Sakor | 2020-09-15 | day | ofac_udg_sanctions | OFACがグローバル・マグニツキー権限でUDGを制裁指定 | https://home.treasury.gov/news/press-releases/sm1121
E | Dara Sakor | 2024-09-29 | day | airport_completion | Dara Sakor International Airport が完成し商用運用準備が整う | https://www.khmertimeskh.com/501611788/dara-sakor-airport-in-sw-cambodia-to-begin-operation-for-domestic-charter-flights/
E | Dara Sakor | 2025-04-18 | day | cambodia_airways_inaugural | Cambodia Airways がDara Sakor 定期便の就航式を実施 | https://www.ttrweekly.com/site/2025/04/cambodia-air-flies-to-dara-sakor/
E | Dara Sakor | 2026-01-25 | day | road_checkpoints_kohkong | コッコン州周辺に道路検問所が設置され詐欺労働者の移動が監視される | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
E | Dara Sakor | 2026-01-26 | day | long_bay_emptying | Long Bay 施設からの外国人労働者の退去と家具搬出が観察される | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
E | Dara Sakor | 2026-02-01 | month | long_bay_protest | Long Bay Century Hotel 前で未払い賃金を求める労働者抗議が発生 | https://mekongindependent.com/2026/02/sparks-of-unrest-at-construction-sites-as-cambodian-scam-raids-continue/
E | Dara Sakor | 2026-02-01 | month | prek_khsach_arson | プレッククサッ建設現場で労働者が未払い賃金抗議で建設機材を放火 | https://mekongindependent.com/2026/02/sparks-of-unrest-at-construction-sites-as-cambodian-scam-raids-continue/
E | Dara Sakor | 2026-02-11 | day | mech_dara_detained | 記者 Mech Dara が詐欺施設取材中に軍警察に1時間近く拘束される | https://thediplomat.com/2026/02/cambodian-reporter-detained-after-photographing-raid-on-scam-center
E | Poipet | 2024-10-03 | day | indian_67_rescue | インド大使館発表、ポイペトから印国民67人を救出し帰国手続き | https://kiripost.com/stories/authorities-rescue-67-indian-nationals-from-poipet-scam-centre
E | Poipet | 2025-01-08 | day | crown_tower_fatal_fall | Crown Tower 14階から31歳タイ人男性アロンコーン氏が転落死 | https://thai.news/news/thailand/heartbreaking-plunge-in-poipet-thai-nationals-tragic-fall-highlights-call-center-scam-crisis
E | Poipet | 2025-02-23 | day | joint_thai_cambodian_raid | タイ・カンボジア合同捜査で詐欺拠点から215人を救出 | https://www.bangkokpost.com/thailand/general/2966396/215-foreigners-including-thais-rescued-from-cambodian-scam-centre
E | Poipet | 2025-02-24 | day | police_statement_release | カンボジア国家警察、ポイペト3階建てビル摘発で230人発見と発表 | https://cambojanews.com/cambodian-police-raid-scam-centers-in-poipet-discover-over-200-foreigners/
E | Poipet | 2025-04-29 | day | sanko_borey_raid | プサーカンダル区Sanko Borey 施設で1,000人超を拘束 | https://www.khmertimeskh.com/501891344/over-4000-foreigners-arrested-since-march-in-poipet-scam-crackdown/
E | Poipet | 2025-04-29 | day | hotel_raid_400 | ポイペト市内ホテル摘発で詐欺容疑者400人を逮捕 | https://www.khmertimeskh.com/501891344/over-4000-foreigners-arrested-since-march-in-poipet-scam-crackdown/
E | Poipet | 2025-05-27 | day | japanese_nationals_raid | PVN ドライポート地区で日本人約30人を含む詐欺拠点を摘発 | https://www.japantimes.co.jp/news/2025/05/29/japan/crime-legal/cambodia-detention-japanese/
E | Poipet | 2025-10-15 | day | south_korea_code_black | 韓国がポイペトを含む地域に最高度の渡航禁止令を発令 | https://www.usnews.com/news/world/articles/2025-10-15/south-korea-issues-travel-ban-for-parts-of-cambodia-after-nationals-trapped-in-scam-centres
E | Poipet | 2025-10-29 | day | thai_woman_kanokwan_fall | Kanokwan 氏(27歳)が3階から転落死、詐欺拠点関連事件 | https://thainewsroom.com/2025/11/23/another-thai-man-tortured-to-death-at-poipet/
E | Poipet | 2025-11-03 | day | thai_woman_suthatip_hanged | Suthatip 氏(28歳)が首吊り状態で発見 | https://thainewsroom.com/2025/11/23/another-thai-man-tortured-to-death-at-poipet/
E | Poipet | 2025-11-13 | day | thai_woman_suda_body_found | プノンペン寺院で詐欺拠点犠牲者 Suda 氏(26歳)の遺体発見 | https://www.nationthailand.com/news/general/40058225
E | Poipet | 2025-11-22 | day | thai_man_narong_tortured_death | チェンマイ出身 Narong 氏、Bua Lai 地区で電気拷問により死亡 | https://thainewsroom.com/2025/11/23/another-thai-man-tortured-to-death-at-poipet/
E | Poipet | 2025-12-08 | day | thai_f16_airstrikes | タイF-16がポイペト地区の5箇所を爆撃、詐欺拠点破壊作戦 | https://cambojanews.com/after-thai-strikes-hit-cambodian-elites-casinos-trafficked-workers-feared-inside/
E | Poipet | 2026-01-06 | day | new_compound_50km_discovered | ポイペトから50km離れたマライ郡で新たな詐欺拠点を発見 | https://www.khaosodenglish.com/news/crimecourtscalamity/2026/01/06/global-fraud-hub-exposed-new-scam-compound-50km-from-poipet/
E | Poipet | 2026-03-12 | day | malai_raid_811_arrested | マライ郡で811人(ベトナム776人含む)を一斉摘発 | https://mekongindependent.com/2026/03/raids-strike-remote-compounds-outside-poipet-city/
E | Poipet | 2026-04-29 | day | orchid_rich_casino_raid | Orchid Hotel & Rich Casino 摘発、1,000人超拘束、銃撃戦発生 | https://www.akp.gov.kh/post/detail/369383
E | Poipet | 2026-04-30 | day | mass_deportation_thais | カンボジア当局がポイペトで逮捕したタイ人635人をバスで国外退去 | https://www.france24.com/en/live-news/20260430-cambodia-deports-more-than-600-thais-linked-to-cyberscams-minister
E | Poipet | 2026-05-03 | day | indonesian_raid_150 | バリレイ1村で約150人のインドネシア人を早朝摘発 | https://www.khmertimeskh.com/501894739/over-4600-foreigners-arrested-in-online-scam-crackdown-in-banteay-meanchey/
E | Poipet | 2026-05-04 | day | orchid_license_revoked | 商業ギャンブル管理委員会、Orchid のライセンス053号を取り消し | https://www.akp.gov.kh/post/detail/369383
E | Poipet | 2026-05-06 | day | crackdown_total_4656 | 1月以降の摘発総数が11カ国国籍4,656人に到達 | https://www.khmertimeskh.com/501894739/over-4600-foreigners-arrested-in-online-scam-crackdown-in-banteay-meanchey/
E | Poipet | 2026-05-14 | day | thai_police_arrest_16 | ポイペト拠点から逃走した16人のタイ人をタイ警察が国境付近で逮捕 | https://www.khaosodenglish.com/news/2026/05/14/thai-police-arrest-16-fleeing-poipet-scam-compound/
E | O'Smach | 2025-06-01 | month | thai_checkpoint_suspension | タイ政府がオースマッチ国境検問所を一方的に閉鎖、市場が閑散化 | https://www.khmertimeskh.com/501841961/thai-army-presence-turns-osmach-market-into-ghost-town/
E | O'Smach | 2025-07-24 | day | armed_border_clashes | カンボジア・タイ国境で武力衝突が勃発、オースマッチ周辺で交戦 | https://www.khmertimeskh.com/501841961/thai-army-presence-turns-osmach-market-into-ghost-town/
E | O'Smach | 2025-12-08 | day | shelling_begins | タイ軍による砲撃開始、住民約64万人が避難 | https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/
E | O'Smach | 2025-12-09 | day | gripen_strike_royal_hill | スウェーデン製グリペン機がRoyal Hill Resortを爆撃、警備員1人死亡 | https://asiatimes.com/2025/12/thais-bomb-three-cambodian-border-casinos-deemed-military-threats/
E | O'Smach | 2025-12-31 | day | ceasefire_announced | タイ・カンボジア両国が国境衝突の停戦に合意 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
E | O'Smach | 2026-02-02 | day | fbi_attache_inspection | FBIと20カ国の駐在武官がオースマッチ詐欺拠点を視察 | https://www.nationthailand.com/news/general/40062017
E | O'Smach | 2026-03-12 | day | media_tour_scam_hub | タイ軍がBBCら国際メディアに6階建て詐欺拠点を公開 | https://www.yahoo.com/news/articles/fake-australian-chinese-brazilian-police-230929556.html
E | O'Smach | 2026-04-07 | day | journalists_tour_resort | タイ軍がワシントン・ポストら記者団に157棟・10,000人規模を公開 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
E | Bavet | 2022-04-28 | day | building_q_fall_death | Crown 地区Q棟5階から21歳ベトナム人男性が転落死 | https://vodenglish.news/falling-death-at-senators-border-casino/
E | Bavet | 2022-05-11 | day | crown_8th_floor_death | Crown Casino 8階から22歳ベトナム人男性が転落死 | https://vodenglish.news/falling-death-at-senators-border-casino/
E | Bavet | 2022-06-03 | day | indonesian_22_rescued | スバイリエン州で22人のインドネシア人「奴隷労働者」を救出 | https://www.khmertimeskh.com/501091325/captive-labour-22-indonesian-slave-workers-rescued-in-svay-rieng
E | Bavet | 2022-07-01 | month | mocbai_murder | Moc Bai 施設でベトナム人労働者の殺害事件発生 | https://vodenglish.news/echoes-of-sihanoukville-troubles-in-cambodian-border-town/
E | Bavet | 2022-08-26 | day | duong_beaten_outside_67 | Casino 67 前で34歳ベトナム人料理人 Duong 氏が4-5人に殴殺される | https://www.khmertimeskh.com/501139833/foreigner-beaten-to-death-outside-bavet-casino/
E | Bavet | 2022-09-13 | day | jumped_from_paris_bopear | Paris Bopear 社2階から逃走を図ったベトナム人が転落死 | https://vodenglish.news/bavet-escape-attempt-leads-to-falling-death/
E | Bavet | 2022-09-17 | day | mass_escape_60_vietnamese | Bavet Moc Bai Casino から60人以上のベトナム人が雨中脱出 | https://www.rfa.org/english/news/vietnam/60-vietnamese-escape-09182022234713.html
E | Bavet | 2022-10-25 | day | mass_escape_window_jump | 数百人のベトナム人が脱走、窓から飛び降りた1人死亡 | https://vodenglish.news/chaotic-scenes-in-bavet-amid-apparent-exodus/
E | Bavet | 2023-02-01 | day | jumped_from_4th_floor | 23歳ベトナム人 Tan Thuan An 氏がカジノ4階から飛び降り死亡 | https://www.casino.org/news/vietnamese-worker-found-hanged-in-cambodia-casino/
E | Bavet | 2023-02-03 | day | king_crown_drug_arrests | King Crown Casino で麻薬密売容疑のベトナム人5人を逮捕 | https://cambodiaexpatsonline.com/post582197.html
E | Bavet | 2023-12-07 | day | uk_sanctions_heng_he | 英国がHeng He Casinoを人権制裁規則の対象に追加 | https://www.opensanctions.org/entities/NK-MYZmyJmk5zwjQ2b2RwRsJm/
E | Bavet | 2025-02-22 | day | bavet_city_14_rescue | Bavet 市カジノ摘発でベトナム人犠牲者14人を救出 | https://www.khmertimeskh.com/501632602/bavet-city-casino-raid-rescues-14-vietnamese-victims/
E | Bavet | 2025-10-30 | day | venus_park_violent_escape | Venus Park 警備員が逃走者を警棒で殴打、動画拡散 | https://cambojanews.com/security-guards-beat-men-fleeing-notorious-venus-park-compound/
E | Bavet | 2025-11-04 | day | li_zhou_venus_raid_658 | Li Zhou と Venus 施設で658人の外国人を一斉摘発 | https://cambojanews.com/police-arrest-over-600-foreigners-in-online-scam-compounds-in-bavet/
E | Bavet | 2026-01-22 | day | mass_deportation_1620 | 1月初旬から21カ国国籍1,620人が国外追放される | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
E | Bavet | 2026-02-01 | day | warning_shots_fired | 警察がA7 Complex 入口で空中に約100発を発砲 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
E | Bavet | 2026-04-24 | day | ofac_kok_an_sanctions | 米財務省が Kok An 上院議員と28関連を制裁、Crown Bavet 指定 | https://home.treasury.gov/news/press-releases/sb0469

T | KK Park | survivor | フィリピン人男性 Mateo | 2025 | 「毎日何百人にメッセージを送り信頼させてから詐欺チームに引き渡すよう命じられた」と6ヶ月の監禁体験を語る | https://the420.in/myanmar-scam-centres-human-trafficking-kk-park-exposed/
T | KK Park | survivor | フィリピン人女性 Jane | 2025 | 背中と肩に残る傷を見せながら「傷が癒えるまで10日待たされた末に解放された」と7月の出来事を証言 | https://the420.in/myanmar-scam-centres-human-trafficking-kk-park-exposed/
T | KK Park | survivor | 中国人俳優 Wang Xing | 2025 | 「3日間頭を剃られタイプを強要され眠れず恐怖の中で過ごした」と1月の監禁を振り返る | https://en.wikipedia.org/wiki/Kidnapping_of_Wang_Xing
T | KK Park | rescuer | カレン民族同盟広報 Padoh Saw Taw Nee | 2025 | KK Park の建物が爆破解体された後も「再建と再利用の意図がある可能性がある」と警鐘 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
T | KK Park | witness | KK Park 脱出者男性 | 2025 | 「人々は川にたどり着くため互いを踏みつけ叫び、舟が転覆し溺れた者もいた」とモエイ川越境の混乱を語る | https://www.chiangraitimes.com/news/foreigners-flee-kk-park-to-mae-sot/
T | KK Park | family | 香港人被害者家族 | 2025 | 元区議 Andy Yu に「最近数週間で6件の新たな相談を受けた」と訴え救出を求める | https://www.rfa.org/english/china/2025/01/13/china-hong-kong-myanmar-kk-park-scam-victims/
T | KK Park | rescuer | GI-TOC 専門家 Jason Tower | 2025 | KK Park の破壊は「演出的」であり構造物の多くが再利用可能な状態で残っていると分析 | https://dnyuz.com/2025/11/26/the-destruction-of-a-notorious-myanmar-scam-compound-appears-to-have-been-performative/
T | Jin Bei | survivor | 台湾人男性 Ko(53歳) | 2023 | 「彼らが私を殺さないとわかった、彼らが欲しいのは金だから」と債務奴隷化の心理を語る | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
T | Jin Bei | survivor | 台湾人男性 Ko(53歳) | 2023 | 「債務票には12営業日連続で毎日1万ドルを支払えと書かれていた」と監禁中の脅迫を証言 | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
T | Jin Bei | survivor | 韓国人男性A(28歳) | 2025 | 「いまだに鍵が回る音を聞くだけで体が震える」と数ヶ月の拷問体験を吐露 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
T | Jin Bei | survivor | 韓国人男性B(35歳) | 2025 | 「ベッド2台に12人で寝かされ1日1食の麺だけだった」と劣悪な居住環境を語る | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
T | Jin Bei | survivor | 韓国人男性A(28歳) | 2025 | 「最低でも1,000人の韓国人がこうした施設に閉じ込められている可能性がある」と公式集計の不十分さを訴える | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
T | Chinatown | survivor | 中国人男性 Lin(24歳) | 2021 | 「外の世界を見たかっただけだ、こうなるとは思わなかった」と拉致後に語る | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
T | Chinatown | survivor | 中国人男性 Zhang(24歳) | 2021 | 「毎日仕事の後に逃げ道を探して建物の周りを歩いた」とクラウン施設からの脱出計画を語る | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
T | Chinatown | survivor | 中国人脱走者 Feng Kai | 2022 | 「移送バスでは50人ずつ2班が満員で通路にも立つ者がいた」と9月の大移送を語る | https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/
T | Chinatown | survivor | 中国人男性 Liu Hua | 2022 | 「カンボジアには数千の詐欺会社があり数十万人がそこに閉じ込められている」と内情を告発 | https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/
T | Chinatown | survivor | インド人男性 Akshit | 2024 | 「毎晩パキスタン人の悲鳴が聞こえ、電気スタンガンで打たれていた」と拒否者への暴力を証言 | https://theconversation.com/inside-southeast-asias-scam-compounds-a-trafficked-worker-tells-of-fraud-coercion-and-torture-280311
T | Chinatown | witness | 韓国食堂経営者 | 2025 | 「配達に行くといつも中国人が出てきて受け取る」と接触統制を観察 | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
T | Chinatown | witness | 韓国人会代表 Oh Chan-su | 2025 | 「シハヌークビル全体が事実上の刑務所都市だ」と現地韓国人会代表として語る | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
T | Chinatown | witness | トゥクトゥク運転手 Nua | 2026 | オトレス2近くで「夜中の0時から3時にバス5-6台が出て行った」と大移動を目撃 | https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/
T | Chinatown | witness | Nan Hai カジノ従業員(17歳) | 2026 | 「人々が逃げ回るのを通り中ずっと見ている」と脱出パニックを語る | https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/
T | Chinatown | survivor | 韓国人男性A(28歳) | 2025 | 「逃亡しようとした中国人男性が目の前で殴り殺され、焼却炉で焼くと脅された」と虐殺を証言 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
T | Dara Sakor | survivor | 台湾人男性 Zheng Shu | 2022 | 「彼らは支出を補填する7,530ドルを払えと言った」と二度目の身代金要求を語る | https://www.globalantiscam.org/post/is-human-trafficking-victim-still-a-victim-in-the-end
T | Dara Sakor | worker | カンボジア人建設労働者 | 2026 | 「7ヶ月間ボーナスが未払いだった」とLong Bay Century Hotel 前抗議で訴える | https://mekongindependent.com/2026/02/sparks-of-unrest-at-construction-sites-as-cambodian-scam-raids-continue/
T | Dara Sakor | witness | コッコン州の村長 | 2026 | 「何も持たず逃げ出した人々に対し私たちは深い同情を感じる」と労働者への憐憫を述べる | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
T | Dara Sakor | witness | コッコン州のタクシー運転手 | 2026 | 「少なくとも100人の中国人が私の牛小屋に隠れていた」と発見の様子を語る | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
T | Dara Sakor | worker | 中国人食品納入業者 | 2026 | 「納品量が日量50kgから10kgに激減し解雇を覚悟している」と地域経済縮小を訴える | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
T | Poipet | survivor | 28歳インドネシア人女性歌手 Kiki | 2024 | 「友達が電気ショックを受け、人々が殴られるのを見た」と仲間への暴力を証言 | https://www.rappler.com/newsbreak/investigative/ordeal-poipet-cambodia-scams/
T | Poipet | survivor | アムネスティ取材の元被害者(Crown) | 2025 | 「警備員は警棒のスイッチを入れた…恐ろしい音がした。部屋の子供達は泣いていた」 | https://www.amnesty.org/en/latest/news/2026/04/cambodia-casinos-get-state-approval-despite-links-to-human-rights-abuse-at-scamming-compounds/
T | Poipet | family | Suda Chonlaket の遺族(タイ・パンガー) | 2025 | 「ノルマ未達でスクワット1,000〜2,000回を強要され、失神するたび電気ショックで意識を戻された」 | https://www.nationthailand.com/news/general/40058225
T | Poipet | rescuer | Immanuel 財団スポークスパーソン | 2025 | 「私が介入していなければ、彼女は無意味に火葬されていただろう」 | https://www.nationthailand.com/news/general/40058225
T | Poipet | rescuer | Immanuel 財団 | 2025 | 「同じポイペト施設に100人以上のタイ人が拘束され、最低5人が最近死亡している」 | https://world.thaipbs.or.th/detail/thai-woman-found-dead-in-poipet/59544
T | Poipet | family | 拷問死 Sarawut 氏の友人 | 2025 | 「中国人ボスの命令で金属棒と電気棒で殴打されノルマ未達を罰せられた」 | https://www.nationthailand.com/blogs/news/asean/40058432
T | Poipet | survivor | 16歳タイ人少年(仮名 Chatri) | 2024 | 「どうやって生き延びるか分からなかった。地獄に逆戻りするようだった」 | https://www.vice.com/en/article/thai-rescue-trafficking-cambodia/
T | Poipet | survivor | アムネスティ証言 Siti(インドネシア人) | 2025 | 「ベトナム人を紫になるまで叩き続け、電気警棒で叫べなくなるまで殴打した」 | https://www.amnesty.org/en/latest/news/2025/06/cambodia-government-allows-slavery-torture-flourish-inside-scamming-compounds/
T | Poipet | survivor | 元被害労働者(アムネスティ) | 2025 | 「部屋に閉じ込められ、顔写真を撮られタイの銀行口座開設に使われた」 | https://www.amnesty.org/en/wp-content/uploads/2025/06/ASA2394472025ENGLISH.pdf
T | O'Smach | worker | 34歳カンボジア人清掃員 | 2026 | 「扉を閉めて、私たちを中に入れさせなかった…規律はとても厳しかった」 | https://www.thestar.com.my/aseanplus/aseanplus-news/2026/01/16/i-saw-even-the-mountains-shake-fear-lingers-in-cambodian-town-after-thai-strikes-on-alleged-scam-sites
T | O'Smach | worker | オースマッチの保守作業員 | 2026 | 「山さえも揺れるのを見た」と空爆の凄まじさを証言 | https://www.thestar.com.my/aseanplus/aseanplus-news/2026/01/16/i-saw-even-the-mountains-shake-fear-lingers-in-cambodian-town-after-thai-strikes-on-alleged-scam-sites
T | O'Smach | worker | オースマッチ清掃員 | 2026 | 「私は建物から逃げたが、雇い主は外国人をすぐには逃がさなかった」 | https://www.thestar.com.my/aseanplus/aseanplus-news/2026/01/16/i-saw-even-the-mountains-shake-fear-lingers-in-cambodian-town-after-thai-strikes-on-alleged-scam-sites
T | O'Smach | witness | 43歳避難民 Sen Chany 氏 | 2026 | 「まだ戦闘の再発が怖い。タイの兵士を信用していない、全くだ」 | https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/
T | O'Smach | witness | オースマッチ住民 | 2026 | 「Ly Yong Phat、これはすべて彼のものだ」と巨大施設を指さす | https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/
T | O'Smach | witness | タイ陸軍情報局長 Theeranan Nantakwang 中将 | 2026 | 「インフラは整備されており、多数の手口と技術が見られる組織的な操作だ」 | https://www.nationthailand.com/news/general/40062017
T | O'Smach | witness | タイ国防省報道官 Surasant Kongsiri | 2026 | 「カジノの背後にある施設が詐欺センターだったと判明した」 | https://www.digitaljournal.com/tech-science/behind-cambodian-border-casino-thai-military-shows-off-a-scam-hub/article
T | O'Smach | worker | 雑貨商売り子の発言(オースマッチ) | 2025 | 「Ly Yong Phat がオースマッチを支配し、市場の店舗も貸している」と語る | https://www.khmertimeskh.com/501841961/thai-army-presence-turns-osmach-market-into-ghost-town/
T | Bavet | survivor | 24歳ケニア人女性 Clare | 2025 | 「他社に売り飛ばすことに失敗したので、身代金を払って自分の自由を買った」 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
T | Bavet | survivor | 18歳インドネシア人男性スマトラ出身 | 2026 | 「8ヶ月間給与なしで強制詐欺労働、パスポートは中国人ボスが保管していた」 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
T | Bavet | survivor | 18歳インドネシア人男性 | 2026 | 「警察が来ると聞いた幹部が全員を解放した」とパニック退避の様子を述懐 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
T | Bavet | witness | スナック販売員 Vut 氏 | 2026 | 「もう何も残っていない…建設労働者まで撤収準備をしている」 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
T | Bavet | witness | トゥクトゥク運転手 | 2026 | 「人々は巨大施設を出て行った。昼夜を問わず去って行った」と大量退出を証言 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
T | Bavet | witness | 雑貨商 Len 氏 | 2026 | 「中の暴力は凄まじかった、気絶するまで殴られた」と内部の残虐性を述べる | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
T | Bavet | worker | 料理人 Mueng Chan 氏 | 2026 | 「まだ確かではない…給料が支払われなければ問題になる」と未払い不安を訴える | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
T | Bavet | witness | Venus Park 近くの露天商(匿名) | 2025 | 「ここには多くの噂がある。逃げようとして死んでいる人もいると聞く」 | https://cambojanews.com/security-guards-beat-men-fleeing-notorious-venus-park-compound/
T | Bavet | witness | バベット副警察署長 Puthea Nutset | 2022 | 「あの場所には入ったことがない、出入りが非常に困難だ」 | https://www.casino.org/news/vietnamese-worker-found-hanged-in-cambodia-casino/
T | Bavet | witness | Heng He 警察署長 Em Sovannareth | 2022 | 「ベトナム人がカジノ8階から落ちて死んだ、遺体はプノンペンのベトナム大使館へ」 | https://vodenglish.news/falling-death-at-senators-border-casino/
T | Bavet | witness | 匿名警察官(A7襲撃時) | 2026 | 「叫べば叫ぶほど苦しむことになる」と暴行を受けた中国人について発言 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
T | Bavet | witness | 建設労働者(A7襲撃目撃) | 2026 | 「土曜午後12時頃、警察が空に向かって何発も発砲した、少なくとも100発はあった」 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/

S | KK Park | 舗装路と街路樹 | 並木の植えられた舗装道路とビルボードがホテルと共存し正規ビジネス地区を装う | CNN | https://www.cnn.com/2025/04/02/asia/myanmar-scam-center-crackdown-intl-hnk-dst
S | KK Park | 赤い屋根群 | 詐欺と密輸の象徴とされる広大な赤屋根群が両棟構成で広がる | South China Morning Post | https://www.pulitzercenter.org/stories/exclusive-inside-chinese-run-crime-hubs-myanmar-are-conning-world-we-can-kill-you-here
S | KK Park | 田園に浮かぶ高層棟 | 山とトウモロコシ畑に囲まれた中に多層棟と通信塔が並び国境風景を歪める | CNN | https://www.cnn.com/2025/04/02/asia/myanmar-scam-center-crackdown-intl-hnk-dst
S | KK Park | 解体後の静寂 | 爆破解体後の街路は空き、廃墟の中を歩く者は見えなくなった | PBS Frontline | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
S | KK Park | 越境難民の野営 | メソットでは越境者が駐車場や空き地でゴザと枕だけで寝起きする | Freedom Collaborative | https://newsletter.freedomcollaborative.org/kk-park-evacuees-face-dire-conditions-at-the-thai-myanmar-border/
S | KK Park | KNA制服の警備員 | 詐欺施設を警備する兵士の制服にKNAの徽章が確認される | US Treasury | https://home.treasury.gov/news/press-releases/sb0129
S | Jin Bei | 五つ星の盛況 | 200室の高級ホテルが中国語客で賑わい高級車が夜通し玄関に到着する | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/cambodian-hotel-under-us-sanctions-remains-open-as-tourism-crime-coexist-in-sihanoukville
S | Jin Bei | 制裁無視の通常営業 | 2025年10月15日の制裁発動後もホテルは明るく灯され通常通り営業 | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/cambodian-hotel-under-us-sanctions-remains-open-as-tourism-crime-coexist-in-sihanoukville
S | Jin Bei | 閉鎖中のJin Bei 5 | 営業停止のJin Bei 5は重い南京錠でガラス扉が固く閉ざされていた | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/cambodian-hotel-under-us-sanctions-remains-open-as-tourism-crime-coexist-in-sihanoukville
S | Jin Bei | スタッフの黙殺 | 制裁について尋ねると従業員は「何も知らない」と答え記者を即座に追い出す | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/cambodian-hotel-under-us-sanctions-remains-open-as-tourism-crime-coexist-in-sihanoukville
S | Chinatown | 高い灰色の壁 | 3-4mのコンクリート壁の上に有刺鉄線とガラス片が並ぶ | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 低層階の鉄格子 | 飛び降り自殺防止のため下層階の窓が鉄格子で塞がれている | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 唯一の門と検問 | 単一の出入口で車両と訪問者を厳格に検査する体制 | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 監視カメラの密集 | ほぼ全ての角に監視カメラが設置されている | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 内部食堂と韓国料理配達 | 内部食堂のほか近隣の韓国料理店からキンパとキムチが宅配される | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 上層階の犯罪基地 | あるホテルでは下層10階が一般客室で上層5階が犯罪拠点 | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 名なしの廃墟群 | 入居前に放棄された無名の白い建物が街並みに不気味な気配を与える | Nikkei Asia | https://asia.nikkei.com/business/markets/property/chinese-exodus-leaves-cambodia-boomtown-with-500-ghost-buildings
S | Chinatown | マスク値段の高騰 | 脱出ラッシュで通常500リエルのマスクが1-2.5ドルで売られた | Mekong Independent | https://mekongindependent.com/2026/01/foreign-workers-flee-ahead-of-online-scam-raids-sihanoukville-locals-say/
S | Chinatown | 武装ガードの威嚇 | 車を降りて撮影した記者を武装した警備員が睨みつけた | Korea Times | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
S | Chinatown | 「金摑みダンス」 | 労働者は毎日テクノのビートで「金摑みダンス」を踊らされた | VOD English | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
S | Dara Sakor | 完成した空港 | 218haの空港が完成し週1便のチャーター便が運航 | TTR Weekly | https://www.ttrweekly.com/site/2025/04/cambodia-air-flies-to-dara-sakor/
S | Dara Sakor | 牛小屋に隠れた中国人 | 脱出した中国人約100人が農家の牛小屋に潜伏 | Mekong Independent | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
S | Dara Sakor | 街道を歩く脱走者 | 外国人労働者が最寄りの町まで数十kmを徒歩で移動する姿が目撃 | Mekong Independent | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
S | Dara Sakor | 家具搬出の光景 | 黒いソファ、洗濯機、マットレス、ベッド枠がバイクや軽トラで運び出された | Mekong Independent | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
S | Dara Sakor | 仕事を失う地元民 | カンボジア人警備員と清掃員、トゥクトゥク運転手が客を失い職を失う | Mekong Independent | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
S | Dara Sakor | 蚊に咬まれる脱走者 | 茂みに潜む中国人男性が大量の蚊に咬まれ重症化していた | Mekong Independent | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
S | Dara Sakor | 国道4号沿いの店舗 | カジノ建物から撤去された機材が露店のように国道沿いに並ぶ | Mekong Independent | https://mekongindependent.com/2026/02/some-koh-kong-compounds-emptied-others-still-lively-amid-scam-crackdown/
S | Dara Sakor | 警察の監視下抗議 | 警察と軍警察が立ち並ぶ中で建設労働者数十人がホテル前で抗議 | Mekong Independent | https://mekongindependent.com/2026/02/sparks-of-unrest-at-construction-sites-as-cambodian-scam-raids-continue/
S | Poipet | カジノ街と国境市場 | 国境に150以上のカジノが並び、客の80%はタイ人ギャンブラーで占められる | Bangkok Post | https://www.bangkokpost.com/thailand/general/3054385/poipet-casinos-desperate-to-woo-thai-patrons-back
S | Poipet | 24時間営業の街 | Holiday Palace やStar Vegas など10大カジノが昼夜なくネオンを灯し続ける | Cambodia Immigration | https://www.cambodiaimmigration.org/news/things-to-do-in-poipet-cambodia-a-gateway-to-cultural-fusion
S | Poipet | 国境市場の混沌 | 越境点 Rong Klua 市場は中古品、海賊版、低価値雑貨が無尽蔵に積まれた大規模卸売市場 | Wikipedia | https://en.wikipedia.org/wiki/Rong_Kluea_Market
S | Poipet | 高い壁と有刺鉄線 | 詐欺施設は高い壁と有刺鉄線で囲まれ、武装ガードが監視する暑く息苦しい環境 | Wikipedia | https://en.wikipedia.org/wiki/Scam_centers_in_Cambodia
S | Poipet | 隠された施設 | 中央市場地区の施設は他建物の陰に巧妙に隠され、外からほぼ見えない構造 | Japan Times | https://www.japantimes.co.jp/news/2025/05/29/japan/crime-legal/cambodia-detention-japanese/
S | Poipet | 建物の高層化 | Crown Tower 18階、CC Tower 25階、HI-SO ビルなど高層が林立するスカイライン | Cyber Scam Monitor | https://cyberscammonitor.net/profile/crown-resorts-poipet-2/
S | Poipet | 国境閉鎖の影響 | 国境衝突後、観光カジノは閑散とし50社の越境送迎業者が廃業 | Thai Newsroom | https://thainewsroom.com/2025/06/10/10-casinos-at-cambodias-border-town-hit-by-border-dispute/
S | Poipet | 大量退去のバス | 4月30日、635人のタイ人が長距離バスに乗り送還される光景 | Khmer Times | https://www.khmertimeskh.com/501889582/video-cambodian-authorities-deport-over-600-thai-nationals/
S | Poipet | 都市近郊新都市計画 | Poipet Satellite City 計画が宣伝されつつ実体はカジノ詐欺施設だった | Mekong Independent | https://mekongindependent.com/2026/03/raids-strike-remote-compounds-outside-poipet-city/
S | O'Smach | 国境カジノ・ストリップ | カンボジアとタイの入国審査の間に2軒のカジノとマーケットが構えられた特異な空間 | Wikipedia | https://en.wikipedia.org/wiki/O_Smach
S | O'Smach | 旧市場の規模 | 新オースマッチ国境市場は721区画、店舗624、ショップハウス94から成る大規模商業地 | Wikipedia | https://en.wikipedia.org/wiki/O_Smach
S | O'Smach | ゴーストタウン化 | タイ軍駐留後、市場は誰もいない通りと閉ざされた店舗だけが残る幽霊都市となる | Khmer Times | https://www.khmertimeskh.com/501841961/thai-army-presence-turns-osmach-market-into-ghost-town/
S | O'Smach | 仏教寺院の被害 | 仏塔は砲撃で損傷、住居の庭には不発弾が落下する状況 | Asia News Network | https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/
S | O'Smach | 中華料理のバラエティ | 施設内には湖南・沙県・四川の各料理を出す複数の中華レストランが営業 | DVB | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
S | O'Smach | 残された生活痕 | 机にはスナック菓子が残り、空のコーラ缶と食べかけの麺が部屋に放置されていた | BBC/Yahoo | https://www.yahoo.com/news/articles/fake-australian-chinese-brazilian-police-230929556.html
S | O'Smach | 道路の無人化 | 12月8日以降の砲撃で空っぽの道路と未完成のクレーンだけが残された景色 | Asia News Network | https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/
S | O'Smach | サロンの略奪 | 市場のサロン店主は帰宅すると財産の大半が盗まれていた事を発見 | Khmer Times | https://www.khmertimeskh.com/501841961/thai-army-presence-turns-osmach-market-into-ghost-town/
S | O'Smach | 太陽光パネル | 建物の屋根に太陽光発電パネルが設置され停電対策が施されていた | Nation Thailand | https://www.nationthailand.com/news/general/40062017
S | O'Smach | 駐車の重機 | バリケード周辺には放棄された大型トラックや建設用クレーンが立ち並ぶ | Asia News Network | https://asianews.network/fear-suspicion-and-destroyed-scam-compounds-at-cambodian-border-town-weeks-after-thai-air-strikes/
S | O'Smach | 道沿いの監視 | カジノ街は監視カメラと武装ガードに囲まれ、入場時はカメラ・武器を没収される | Live Less Ordinary | https://live-less-ordinary.com/thailand-cambodia-border-crossing/
S | O'Smach | 国境市の路上の僧侶 | 国境市場のジューススタンドの隣で僧侶が日常的に往来する平凡な光景 | Live Less Ordinary | https://live-less-ordinary.com/thailand-cambodia-border-crossing/
S | Bavet | ネオンの国境カジノ街 | 国境ゲート直下にネオンとアーケードのカジノ街が連なり昼夜なく輝く | Take Your Backpack | https://www.takeyourbackpack.com/backpacking-in-cambodia/visit-bavet/
S | Bavet | 14のカジノ群 | 小さなBavetには14のカジノが集中し、さらに数件が建設中 | Inside Asian Gaming | https://www.asgam.com/index.php/2010/10/01/borderline-case/
S | Bavet | 闘鶏場 | カジノ街沿いに14の闘鶏場が並びベトナム南部住民を惹き寄せる | VietnamNet | https://vietnamnet.vn/en/cambodian-casinos-enclosure-vietnamese-border-E79144.html
S | Bavet | 有刺鉄線の撤去 | 1月、Crown Casino 西側に張られた有刺鉄線が静かに撤去された | Mekong Independent | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
S | Bavet | スーツケースの行列 | 大型スーツケースを引く労働者と客待ちのトゥクトゥク運転手で道が溢れた | Mekong Independent | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
S | Bavet | 解体する建設労働者 | 建設労働者が金属とケーブルを救い出し、メインロードを家具運搬トレーラーが走る | Mekong Independent | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
S | Bavet | ガード詰所と検問所 | 施設は有刺鉄線、金属棒、施錠ゲート、警備車止め、検問所で外界と隔てられた | VOD English | https://vodenglish.news/echoes-of-sihanoukville-troubles-in-cambodian-border-town/
S | Bavet | 並行する仮想の街 | 内部にサービス機能を持つ「閉鎖された並行都市」として機能 | VOD English | https://vodenglish.news/echoes-of-sihanoukville-troubles-in-cambodian-border-town/
S | Bavet | 田圃を走る逃走者 | A7襲撃時、労働者は割れた窓やドアから田圃やバイクで逃走を図る | Mekong Independent | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
S | Bavet | 緑のミニバス輸送 | 一斉摘発時には複数の緑色ミニバスが拘束者を輸送する光景 | Mekong Independent | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
S | Bavet | テニスラケットの押収 | 警察はパソコン以外にテニスラケットと電子機器を押収物として持ち出す | Mekong Independent | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
S | Bavet | 雨中の逃走 | 2022年9月、激しい雨の中でベトナム人労働者が次々と脱出する映像が拡散 | RFA | https://www.rfa.org/english/news/vietnam/60-vietnamese-escape-09182022234713.html
S | Bavet | TikTokの記録 | 早朝の逃走シーンは住民により TikTok で世界に拡散された | VOD English | https://vodenglish.news/chaotic-scenes-in-bavet-amid-apparent-exodus/
S | Bavet | OP科学技術団地 | 中国人労働者中心の OP 科学技術工業園、シフトごとに警備員200人配置 | Mekong Independent | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/

D | KK Park | conditions | 17時間労働シフト | https://en.wikipedia.org/wiki/KK_Park
D | KK Park | conditions | 12-16時間シフト交代 | https://the420.in/myanmar-scam-centres-human-trafficking-kk-park-exposed/
D | KK Park | conditions | 210haの壁囲い | https://the420.in/myanmar-scam-centres-human-trafficking-kk-park-exposed/
D | KK Park | conditions | 計635棟のうち413棟解体 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
D | KK Park | conditions | 4階建ての病院併設 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
D | KK Park | conditions | カラオケ施設併設 | https://www.pbs.org/wgbh/frontline/article/myanmar-cyberscam-scam-compound/
D | KK Park | control | Starlink 30台押収 | https://www.rfa.org/english/myanmar/2025/10/20/myanmar-starlink-scam-center-raid/
D | KK Park | violence | 手錠と目隠し就寝 | https://pulitzercenter.org/stories/survivors-myanmars-scam-mills-talk-torture-death-organ-harvesting-and-battle-escape
D | KK Park | violence | 殺害脅迫の常態化 | https://en.wikipedia.org/wiki/KK_Park
D | KK Park | trafficking | 身代金100万香港ドル超 | https://www.rfa.org/english/china/2025/01/13/china-hong-kong-myanmar-kk-park-scam-victims/
D | KK Park | trafficking | 56カ国から人員調達 | https://www.pbs.org/newshour/world/why-southeast-asias-online-scam-industry-is-so-hard-to-shut-down
D | KK Park | trafficking | インド人最大492人 | https://newsletter.freedomcollaborative.org/kk-park-evacuees-face-dire-conditions-at-the-thai-myanmar-border/
D | KK Park | trafficking | 4ヶ国にまたがる斡旋経路 | https://www.rfa.org/english/china/2024/12/17/china-hong-kong-kk-park-myanmar-scammers/
D | KK Park | complicity | KNA制服の警備員 | https://home.treasury.gov/news/press-releases/sb0129
D | KK Park | complicity | BGFが土地を貸与 | https://www.justiceformyanmar.org/stories/the-karen-border-guard-force-karen-national-army-criminal-business-network-exposed
D | KK Park | complicity | Trans Asia 社経由 | https://home.treasury.gov/news/press-releases/sb0312
D | KK Park | conditions | 川岸の有刺鉄線フェンス | https://www.bangkokpost.com/learning/advanced/3141730/three-chinese-fleeing-myanmar-scam-centre-sneak-into-thailand
D | KK Park | conditions | 2万人規模の労働者 | https://en.wikipedia.org/wiki/KK_Park
D | KK Park | trafficking | 28カ国から越境1,667人 | https://newsletter.freedomcollaborative.org/kk-park-evacuees-face-dire-conditions-at-the-thai-myanmar-border/
D | Jin Bei | violence | 部屋715に拘束 | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
D | Jin Bei | violence | 鉄ベッドに手錠 | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
D | Jin Bei | violence | 拳銃を頭に突きつけ | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
D | Jin Bei | violence | 10人に殴打される | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
D | Jin Bei | trafficking | 売値1万5,000ドル | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
D | Jin Bei | trafficking | 債務票12万6,700ドル | https://cambojanews.com/beaten-handcuffed-and-ransomed-in-post-crackdown-sihanoukville/
D | Jin Bei | conditions | 1日12-16時間勤務 | https://www.france24.com/en/live-news/20221109-inside-the-living-hell-of-cambodia-s-scam-operations
D | Jin Bei | complicity | Sar Sokha 前役員就任 | https://thediplomat.com/2025/10/after-prince-group-sanctions-unanswered-questions-for-cambodias-interior-minister/
D | Jin Bei | complicity | Prince Group 傘下 | https://ofac.treasury.gov/recent-actions/20251014
D | Jin Bei | trafficking | 約200人の韓国人監禁 | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/cambodian-hotel-under-us-sanctions-remains-open-as-tourism-crime-coexist-in-sihanoukville
D | Jin Bei | violence | スーツケース遺棄死体 | https://cambojanews.com/dead-chinese-man-linked-to-alleged-scam-operation-sihanoukville-compound/
D | Jin Bei | conditions | 7階建て16,500平米 | https://www.rfa.org/english/special-reports/prince-group/assets/p1-prince-group-investigation.html
D | Jin Bei | complicity | 1,800万ドル米国被害 | https://www.casino.org/news/us-uk-sanction-cambodian-casino-empire-over-cyber-scams-human-trafficking/
D | Chinatown | trafficking | スキル者は5万ドル | https://www.koreatimes.co.kr/southkorea/law-crime/20251017/its-practically-a-prison-city-inside-sihanoukvilles-largest-scam-compound
D | Chinatown | trafficking | 売値5,000ドル斡旋 | https://theconversation.com/inside-southeast-asias-scam-compounds-a-trafficked-worker-tells-of-fraud-coercion-and-torture-280311
D | Chinatown | conditions | 月10,000ドル詐取ノルマ | https://theconversation.com/inside-southeast-asias-scam-compounds-a-trafficked-worker-tells-of-fraud-coercion-and-torture-280311
D | Chinatown | conditions | 10時半-2時の勤務 | https://theconversation.com/inside-southeast-asias-scam-compounds-a-trafficked-worker-tells-of-fraud-coercion-and-torture-280311
D | Chinatown | violence | 拷問室G106 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
D | Chinatown | violence | 天井吊るし拷問 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
D | Chinatown | violence | 太腿への電気スタンガン | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
D | Chinatown | violence | 焼却炉脅迫 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
D | Chinatown | violence | 指切断罰 | https://www.amnesty.org/en/latest/news/2025/06/cambodia-government-allows-slavery-torture-flourish-inside-scamming-compounds/
D | Chinatown | control | 足首鎖で拘束 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
D | Chinatown | control | 12人で2ベッド共用 | https://www.koreatimes.co.kr/southkorea/society/20251016/rescued-koreans-reveal-horrors-of-cambodian-scam-rings-metal-pipes-and-electric-torture
D | Chinatown | conditions | 8,000-10,000人収容規模 | https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/
D | Chinatown | trafficking | バス約50人一気移送 | https://vodenglish.news/the-big-transfer-sihanoukville-scammers-scatter/
D | Chinatown | violence | 1分10ドル罰金 | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
D | Chinatown | trafficking | 売値1万2,000-2万ドル | https://vodenglish.news/victims-allege-sihanoukville-precincts-with-ties-to-major-businesses-are-sites-of-scams-torture-detention/
D | Chinatown | conditions | 53施設13地区確認 | https://www.amnesty.org/en/latest/news/2025/06/cambodia-government-allows-slavery-torture-flourish-inside-scamming-compounds/
D | Dara Sakor | conditions | 139平方マイル区画 | https://en.wikipedia.org/wiki/Dara_Sakor
D | Dara Sakor | conditions | 39億ドル投資計画 | https://en.wikipedia.org/wiki/Dara_Sakor
D | Dara Sakor | trafficking | 身代金7,530ドル | https://www.globalantiscam.org/post/is-human-trafficking-victim-still-a-victim-in-the-end
D | Dara Sakor | trafficking | 初回身代金2,000ドル超 | https://vodenglish.news/rescue-reveals-scam-compound-at-koh-kongs-udg/
D | Dara Sakor | complicity | UDG中国軍利用懸念 | https://en.wikipedia.org/wiki/Dara_Sakor
D | Dara Sakor | complicity | 副首相息子と関連企業 | https://en.wikipedia.org/wiki/Dara_Sakor
D | Dara Sakor | violence | 村民住居の放火 | https://www.business-humanrights.org/en/latest-news/cambodia-villagers-in-koh-kong-province-struggle-to-get-compensation-for-chinese-funded-dara-sakor-mega-project/
D | Dara Sakor | complicity | Kun Kim 将軍関与 | https://www.business-humanrights.org/en/latest-news/cambodia-villagers-in-koh-kong-province-struggle-to-get-compensation-for-chinese-funded-dara-sakor-mega-project/
D | Dara Sakor | conditions | 99年リース期間 | https://en.wikipedia.org/wiki/Dara_Sakor
D | Dara Sakor | conditions | 1,000家族超影響 | https://en.wikipedia.org/wiki/Dara_Sakor
D | Dara Sakor | conditions | 218ha空港 | https://www.khmertimeskh.com/501611788/dara-sakor-airport-in-sw-cambodia-to-begin-operation-for-domestic-charter-flights/
D | Dara Sakor | trafficking | 7ヶ月ボーナス未払い | https://mekongindependent.com/2026/02/sparks-of-unrest-at-construction-sites-as-cambodian-scam-raids-continue/
D | Dara Sakor | conditions | 90%労働者解雇 | https://mekongindependent.com/2026/02/sparks-of-unrest-at-construction-sites-as-cambodian-scam-raids-continue/
D | Poipet | conditions | 17時間労働シフト | https://thediplomat.com/2026/03/i-was-forced-to-shock-them-life-inside-cambodias-online-scam-compounds/
D | Poipet | conditions | ノルマ未達は罰金50ドル | https://www.rappler.com/newsbreak/investigative/ordeal-poipet-cambodia-scams/
D | Poipet | violence | 金属棒で殴打・電気警棒 | https://www.nationthailand.com/blogs/news/asean/40058432
D | Poipet | violence | スクワット1,000-2,000回 | https://www.nationthailand.com/news/general/40058225
D | Poipet | violence | 失神→電気で蘇生→死亡 | https://www.nationthailand.com/news/general/40058225
D | Poipet | violence | 1日10万バーツのノルマ | https://www.nationthailand.com/news/general/40058225
D | Poipet | violence | Crown Tower 14階転落死 | https://thai.news/news/thailand/heartbreaking-plunge-in-poipet-thai-nationals-tragic-fall-highlights-call-center-scam-crisis
D | Poipet | violence | 11階転落自殺ルール | https://cyberscammonitor.net/profile/crown-resorts-poipet-2/
D | Poipet | control | 部屋に2週間軟禁 | https://cyberscammonitor.net/profile/crown-resorts-poipet-2/
D | Poipet | trafficking | 5,000米ドルで売買 | https://theconversation.com/inside-southeast-asias-scam-compounds-a-trafficked-worker-tells-of-fraud-coercion-and-torture-280311
D | Poipet | trafficking | 月給10,000米ドルのノルマ | https://www.cnn.com/2026/01/26/asia/south-korean-victims-southeast-asia-scam-network-intl-hnk-dst
D | Poipet | trafficking | 達成時に給与800ドル | https://www.cnn.com/2026/01/26/asia/south-korean-victims-southeast-asia-scam-network-intl-hnk-dst
D | Poipet | complicity | Kok An 上院議員の所有 | https://home.treasury.gov/news/press-releases/sb0469
D | Poipet | complicity | Crown Resorts 5カジノ統合 | https://cyberscammonitor.net/profile/crown-resorts-poipet-2/
D | Poipet | complicity | 偽SNS口座パッケージ販売 | https://cyberscammonitor.net/profile/crown-resorts-poipet/
D | Poipet | complicity | Angkor Brothers 免許所有 | https://home.treasury.gov/news/press-releases/sb0469
D | Poipet | violence | 拷問用金属棒・プラ管 | https://www.amnesty.org/en/latest/news/2025/06/cambodia-government-allows-slavery-torture-flourish-inside-scamming-compounds/
D | Poipet | control | 寝るとプッシュアップ罰 | https://vodenglish.news/learning-to-scam-under-threat-of-tasers/
D | Poipet | complicity | Pury Casino 25階建て | https://www.nationthailand.com/blogs/news/general/40052184
D | Poipet | complicity | 詐欺被害3億バーツ規模 | https://www.nationthailand.com/blogs/news/general/40052184
D | Poipet | complicity | Pury Casino 7階に200人収容 | https://www.bangkokpost.com/opinion/opinion/2938290/time-to-tackle-scam-bases
D | Poipet | complicity | Kok An 家族50社 | https://cyberscammonitor.net/profile/crown-resorts-poipet/
D | Poipet | conditions | PC 341・携帯352押収 | https://www.khmertimeskh.com/501718769/271-foreigners-arrested-in-crackdown-on-poipet-scam-centre/
D | Poipet | conditions | 4階52室のホテル詐欺施設 | https://www.khmertimeskh.com/501891344/over-4000-foreigners-arrested-since-march-in-poipet-scam-crackdown/
D | O'Smach | conditions | 80ha 157棟 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
D | O'Smach | conditions | 詐欺事務所29棟が稼働 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
D | O'Smach | conditions | 10,000人居住推定 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
D | O'Smach | conditions | Royal Hill 430室超 | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | conditions | 1部屋14段ベッド共用浴 | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | conditions | フォーム防音ブース | https://wtop.com/world/2026/02/photos-show-a-former-scam-compound-at-the-thai-cambodian-border/
D | O'Smach | conditions | 偽米百ドル札の山 | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | conditions | 7カ国の偽警察制服 | https://wtop.com/world/2026/02/photos-show-a-former-scam-compound-at-the-thai-cambodian-border/
D | O'Smach | conditions | 上海式拷問椅子発見 | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | conditions | ベトナム銀行偽カウンター | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | violence | 警備員1名死亡5名負傷 | https://cambojanews.com/after-thai-strikes-hit-cambodian-elites-casinos-trafficked-workers-feared-inside/
D | O'Smach | control | 空爆中も労働継続強制 | https://cambojanews.com/after-thai-strikes-hit-cambodian-elites-casinos-trafficked-workers-feared-inside/
D | O'Smach | control | 米国向けSIMが大量散乱 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
D | O'Smach | control | 24頁役柄詳細台本 | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
D | O'Smach | trafficking | 5万円程度の身代金要求 | https://home.treasury.gov/news/press-releases/jy2576
D | O'Smach | trafficking | 飛び降り死2件報告 | https://home.treasury.gov/news/press-releases/jy2576
D | O'Smach | complicity | Ly Yong Phat LYP 保有 | https://home.treasury.gov/news/press-releases/jy2576
D | O'Smach | complicity | Royal Hill はLim Heng所有 | https://cambojanews.com/cambodian-authorities-dispute-thai-governments-account-of-scam-compound-rescue-in-osmach/
D | O'Smach | complicity | OFAC 4社同時指定 | https://home.treasury.gov/news/press-releases/jy2576
D | O'Smach | conditions | 3階建ての高級ヴィラ | https://english.dvb.no/inside-a-huge-compound-on-thailand-cambodia-border-where-10000-workers-scammed-people-globally/
D | O'Smach | conditions | 6階建てRoyal Hill別棟 | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | conditions | フロア24室の標準 | https://nikkei.shorthandstories.com/Abandoned-Scam-Centre/
D | O'Smach | conditions | 国籍別フロア区分け | https://www.nationthailand.com/news/general/40062017
D | O'Smach | conditions | タイ軍100ライ管理下 | https://www.nationthailand.com/news/general/40062017
D | O'Smach | violence | 国境侵入500m前進 | https://atlasinstitute.org/thailands-osmach-spectacle-and-the-forging-of-visual-sovereignty-amid-southeast-asias-scam-crisis/
D | O'Smach | violence | グリペン高性能爆弾投下 | https://asiatimes.com/2025/12/thais-bomb-three-cambodian-border-casinos-deemed-military-threats/
D | Bavet | conditions | 22棟のA7 Complex | https://www.khmertimeskh.com/501837647/in-pictures-over-2000-foreigners-arrested-in-weekend-bavet-city-scam-centre-raid/
D | Bavet | conditions | Heng He 約20ha・30棟 | https://vodenglish.news/echoes-of-sihanoukville-troubles-in-cambodian-border-town/
D | Bavet | conditions | Moc Bai 23万平米敷地 | https://bavetmocbai.wixsite.com/mocbai/about
D | Bavet | conditions | 国境50m内に位置 | https://bavetmocbai.wixsite.com/mocbai/about
D | Bavet | violence | Crown 8階転落死 | https://vodenglish.news/falling-death-at-senators-border-casino/
D | Bavet | violence | Q棟5階転落死 | https://vodenglish.news/falling-death-at-senators-border-casino/
D | Bavet | violence | カジノ階段で首吊死 | https://www.casino.org/news/vietnamese-worker-found-hanged-in-cambodia-casino/
D | Bavet | violence | Casino 67 前で4-5人殴殺 | https://www.khmertimeskh.com/501139833/foreigner-beaten-to-death-outside-bavet-casino/
D | Bavet | violence | A7警告射撃約100発 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
D | Bavet | violence | 中国人労働者を意識不明殴打 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
D | Bavet | violence | AK-47で空中威嚇 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
D | Bavet | control | 結束バンドで手首拘束 | https://mekongindependent.com/2026/02/massive-raid-nabs-more-than-2000-workers-with-warning-shots/
D | Bavet | control | 西側に有刺鉄線設置 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
D | Bavet | control | パスポート中国人ボス保管 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
D | Bavet | control | 600ドル/月の約束で無給 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
D | Bavet | control | 警備員シフト毎200人体制 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
D | Bavet | trafficking | 身代金で自由を購入 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
D | Bavet | trafficking | 別会社への売却失敗 | https://www.thenewhumanitarian.org/news-feature/2026/02/25/cambodia-mass-scam-centre-escapes-reveal-humanitarian-crisis
D | Bavet | trafficking | 238人インドネシア被害 | https://www.khmertimeskh.com/501091325/captive-labour-22-indonesian-slave-workers-rescued-in-svay-rieng
D | Bavet | trafficking | 翻訳者月給450ドル | https://vodenglish.news/echoes-of-sihanoukville-troubles-in-cambodian-border-town/
D | Bavet | complicity | Kok An が Crown 所有 | https://vodenglish.news/falling-death-at-senators-border-casino/
D | Bavet | complicity | Heng He は陳爾人・フントー関連 | https://www.casino.org/news/vietnamese-worker-found-hanged-in-cambodia-casino/
D | Bavet | complicity | 英国制裁 Heng He 2023.12 | https://www.opensanctions.org/entities/NK-MYZmyJmk5zwjQ2b2RwRsJm/
D | Bavet | complicity | OFAC指定 Heng He 2026 | https://home.treasury.gov/news/press-releases/sb0469
D | Bavet | complicity | Oriental Paris は無認可 | https://cambojanews.com/dozens-of-vietnamese-questioned-by-police-after-allegedly-seeking-escape-from-bavet-casino/
D | Bavet | complicity | 李涛がOriental Paris取締役 | https://cambojanews.com/dozens-of-vietnamese-questioned-by-police-after-allegedly-seeking-escape-from-bavet-casino/
D | Bavet | conditions | 「死ぬまで殴る」と Siti 証言 | https://www.amnesty.org/en/latest/news/2025/06/cambodia-government-allows-slavery-torture-flourish-inside-scamming-compounds/
D | Bavet | conditions | 新ベネチアン施設の存在 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
D | Bavet | conditions | Bauhinia Boutique 小規模 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
D | Bavet | violence | 1,620人を21国籍が国外退去 | https://mekongindependent.com/2026/01/barbed-wire-comes-down-at-bavet-scam-compound/
"""

# Map candidate substring -> id and place_id
cand_map = {row[1]: (row[0], row[2]) for row in cur.execute(
    "SELECT id, label, place_id FROM compound_candidate")}


def find_candidate(substr):
    for label, (cid, pid) in cand_map.items():
        if substr in label:
            return cid, pid
    return None, None


now = datetime.datetime.now(datetime.timezone.utc).isoformat()[:19] + 'Z'
n_e = n_t = n_s = n_d = 0
skipped = 0
for raw in ADDONS.strip().splitlines():
    line = raw.strip()
    if not line:
        continue
    parts = [html.unescape(p.strip()) for p in line.split('|')]
    tag = parts[0]
    loc = parts[1] if len(parts) > 1 else ''
    cid, pid = find_candidate(loc)
    if not cid:
        skipped += 1
        continue
    try:
        if tag == 'E' and len(parts) >= 7:
            _, _, date, prec, kind, summary, url = parts[:7]
            cur.execute("INSERT INTO source(kind, url, captured_at) VALUES('news_p12', ?, ?)", (url, now))
            sid = cur.lastrowid
            cur.execute("""INSERT INTO event(kind, happened_on, resolution, place_id,
                                              candidate_id, summary, source_id)
                           VALUES(?,?,?,?,?,?,?)""",
                        (kind, date, prec, pid, cid, summary, sid))
            n_e += 1
        elif tag == 'T' and len(parts) >= 7:
            _, _, role, speaker, year, quote, url = parts[:7]
            cur.execute("""INSERT INTO testimony(candidate_id, role, speaker, year, quote,
                                                  source_url, origin)
                           VALUES(?,?,?,?,?,?,'p12')""",
                        (cid, role, speaker, year, quote, url))
            n_t += 1
        elif tag == 'S' and len(parts) >= 6:
            _, _, topic, text, src_label, url = parts[:6]
            cur.execute("""INSERT INTO life_snippet(candidate_id, ord, topic, text,
                                                      source_label, source_url, origin)
                           VALUES(?,999,?,?,?,?,'p12')""",
                        (cid, topic, text, src_label, url))
            n_s += 1
        elif tag == 'D' and len(parts) >= 5:
            _, _, cat, text, url = parts[:5]
            cur.execute("""INSERT INTO danger_detail(candidate_id, category, text,
                                                      source_url, origin)
                           VALUES(?,?,?,?,'p12')""",
                        (cid, cat, text, url))
            n_d += 1
        else:
            skipped += 1
    except Exception as exc:
        skipped += 1
        print(f"  [P12 SKIP] {tag} {loc}: {exc}")

con.commit()
print(f"[P12] inserted: {n_e} events / {n_t} testimony / {n_s} snippets / {n_d} details "
      f"(skipped {skipped})")
print("--- per-candidate totals (incl. all phases) ---")
for label, e, t, s, d in cur.execute("""
    SELECT c.label,
      (SELECT COUNT(*) FROM event x WHERE x.candidate_id=c.id),
      (SELECT COUNT(*) FROM testimony x WHERE x.candidate_id=c.id),
      (SELECT COUNT(*) FROM life_snippet x WHERE x.candidate_id=c.id),
      (SELECT COUNT(*) FROM danger_detail x WHERE x.candidate_id=c.id)
    FROM compound_candidate c ORDER BY c.id"""):
    print(f"  {label[:32]:32s}  E:{e:3d}  T:{t:3d}  S:{s:3d}  D:{d:3d}")
con.close()
