"""ローカル用のダミーデータ（架空の宇宙の植物園・ガーデンの法人と利用者）を入れる。実在の人・法人のデータは使わない。

    python -m app.seed_demo          # 求人・利用者・園アカウントが空のときだけ入れる
    python -m app.seed_demo --reset  # 求人・応募・アカウントを消して入れ直す（マスタは触らない）
    python -m app.seed_demo --extend # 求人 EXTRA_RECRUITS（18 件）のうち、demo_key がまだ無いものだけを足す（--reset と併用で 30 件構成）

ログイン確認用: 利用者 hoshiniwa-user@example.com / 園 hoshiniwa-garden@example.com と hoshiniwa-garden2@example.com、
パスワードはどれも README に書いたダミー（ローカル専用）。
"""

import sys

import psycopg
from argon2 import PasswordHasher

from app.settings import database_url, require_demo_data_allowed

# ローカル専用のダミー。実在のパスワードは使わない。
DEMO_PASSWORD = "star-garden-demo"

# 給与は架空の通貨「ルミ」（常勤は月給制、それ以外は時給制。通貨の表示は画面側）。
# (demo_key, 法人名, 職種名, 雇用形態コード, 最低給与, 最高給与, 地域コード, 乗り場コード, 職種コード, 表示)
RECRUITS = [
    ("greenhouse-vine-grower", "環軌道植物公社", "無重力蔓の育成士", 1, 180000, 240000, [3], [5], [1], True),
    ("artificial-night-keeper", "環軌道植物公社", "人工夜の温室管理員", 1, 190000, 250000, [4], [2], [2], True),
    ("garden-storyteller", "ミルフェン月面植物園", "植物園の語り部", 2, 1100, 1300, [8], [7], [9], True),
    ("night-blossom-guide", "ミルフェン月面植物園", "夜の花見ガイド", 1, 200000, 260000, [9, 10], [7, 9], [11], True),
    ("oxygen-unit-maintainer", "ザーハード砂漠温室組合", "酸素供給装置の保守員", 1, 210000, 270000, [12], [4, 11], [6], True),
    ("dune-vehicle-guide", "ザーハード砂漠温室組合", "砂丘の高機動車の運転案内", 3, 1000, 1200, [12], [4, 11], [12], True),
    ("ruins-storyteller", "遺跡前ガーデン", "遺跡前の語り部", 2, 1150, 1350, [13, 14], [10, 11], [10], True),
    ("ruins-soil-surveyor", "遺跡前ガーデン", "遺跡周辺の土壌の調査員", 4, 1500, 1700, [14], [10], [19], True),
    ("gravity-crossbreeding-coordinator", "星庭財団", "重力別の交配調整員", 3, 1300, 1500, [3, 4], [5, 6], [17], True),
    ("seed-recorder", "星庭財団", "種子の記録係", 1, 185000, 230000, [4], [1], [16], True),
    ("plant-quarantine-officer", "静止軌道ガーデンズ", "持ち込み植物の検疫官", 2, 1100, 1250, [6], [1, 6], [25], True),
    ("hidden-test-lead", "非表示のテスト求人", "栽培の統括", 1, 100000, 100000, [1], [1], [7], False),
]


# 園のアカウント（メール, 法人名）。求人は、法人名が同じ園のアカウントに紐づける（どの園にも紐づかない求人もある）。
GARDENS = [
    ("hoshiniwa-garden@example.com", "環軌道植物公社"),
    ("hoshiniwa-garden2@example.com", "ミルフェン月面植物園"),
]
# 「非表示のテスト求人」は、1 つ目の園の非表示の求人として使う
GARDEN_OF_CORPORATE = {"環軌道植物公社": 0, "非表示のテスト求人": 0, "ミルフェン月面植物園": 1}


# --extend で足す求人（新規の 6 園を含む 18 件。表示 15 件・非表示 3 件）。形は RECRUITS と同じ。
# 新規の 6 園（霧樹の森ガーデン・北縁種苗センター・ノクティラ環 花の学校・岩山菌類園・根元迎賓ガーデン・南縁ドーム管理局）は法人名だけで、ログインのアカウントは作らない。
# 画像は demo_images.json が demo_key で結ぶ（画像の登録は seed_images。ここでは触らない）。清掃員・搬送員など、マスタに近い職種が無いものは、近いコードを当てている。
EXTRA_RECRUITS = [
    ("plant-doctor", "静止軌道ガーデンズ", "植物医", 1, 220000, 280000, [6], [1, 6], [23], True),
    ("garden-pr-officer", "ミルフェン月面植物園", "広報担当", 1, 190000, 240000, [9], [7], [33], True),
    ("entrance-receptionist", "根元迎賓ガーデン", "入園受付", 2, 1050, 1200, [6], [6], [30], True),
    ("water-cycle-technician", "南縁ドーム管理局", "水循環の技師", 1, 200000, 260000, [10], [9], [27], True),
    ("dome-glass-cleaner", "南縁ドーム管理局", "ドームのガラス清掃員", 3, 1000, 1250, [10], [9], [35], True),
    ("seedling-courier", "北縁種苗センター", "苗の搬送員", 2, 1100, 1300, [8], [7, 9], [4], True),
    ("fungi-cultivator", "岩山菌類園", "キノコの栽培員", 1, 195000, 250000, [13], [10], [8], True),
    ("pollinator-keeper", "霧樹の森ガーデン", "受粉昆虫の飼育員", 1, 190000, 240000, [3], [5], [8], True),
    ("flower-workshop-instructor", "ノクティラ環 花の学校", "花束体験教室の講師", 2, 1200, 1400, [2], [2], [13], True),
    ("mist-tree-pruner", "霧樹の森ガーデン", "霧樹の剪定士", 1, 200000, 260000, [3], [5], [3], True),
    ("hydroponic-shelf-manager", "北縁種苗センター", "水耕棚の管理員", 1, 185000, 235000, [8], [7], [5], True),
    ("soil-nutrient-analyst", "岩山菌類園", "土壌と培養液の分析員", 1, 210000, 270000, [13], [10], [18], True),
    ("rare-species-conservator", "星庭財団", "希少種の保全担当", 1, 220000, 280000, [4], [1], [20], True),
    ("guide-desk-staff", "根元迎賓ガーデン", "案内所の係", 3, 1000, 1200, [6], [6], [14], True),
    ("seasonal-event-planner", "ノクティラ環 花の学校", "季節の企画担当", 1, 190000, 250000, [2], [2], [31], True),
    ("hidden-gas-detector", "遺跡前ガーデン", "有害ガスの検知員", 1, 200000, 250000, [14], [10], [26], False),
    ("hidden-ticket-accountant", "ミルフェン月面植物園", "チケットと会計", 2, 1100, 1250, [9], [7], [32], False),
    ("hidden-research-assistant", "南縁ドーム管理局", "研究の補助員", 2, 1050, 1200, [10], [9], [21], False),
]

# 勤務時間と曜日（開始の時・分、終了の時・分、曜日）。RECRUITS は常に DEFAULT_SCHEDULE。EXTRA_RECRUITS は雇用形態で変える。
DEFAULT_SCHEDULE = ("09", "00", "18", "00", "月〜金")
SCHEDULE_OF_EMPLOY = {1: DEFAULT_SCHEDULE, 2: ("10", "00", "15", "00", "週3日〜（相談可）"), 3: ("08", "00", "17", "00", "シフト制（土日を含む）")}


# 一覧に出す「業務内容」（recruits.comment1）。demo_key ごとの 2 文ほど（一覧では 2 行で切れ、全文は詳細に出る）。実在の仕事の紹介のような書き方にして、「ダミー」とは書かない
# （架空のサイトであることは、画面の下の注記で 1 回だけ伝える）。ここに無い demo_key は、職種名だけの短い文を使う。
COMMENTS = {
    "greenhouse-vine-grower": "無重力の温室で、蔓の苗の剪定と誘引、伸び方の記録をお任せします。蔓は光の向きに合わせて育つため、毎日の観察が大切な仕事です。",
    "artificial-night-keeper": "人工の夜をつくる温室で、照明と温度の切り替えを見守ります。植物の眠りと目覚めの時刻を整え、夜の開花を支える仕事です。",
    "garden-storyteller": "来園者に、植物と園の歴史をお話しする仕事です。台本はありますが、お客様の反応に合わせて話し方を工夫できます。短い時間から働けます。",
    "night-blossom-guide": "夜にだけ咲く花の見どころへ来園者を案内し、観賞の時間と安全を見守ります。花の種類や咲く時刻について、先輩が一から教えます。",
    "oxygen-unit-maintainer": "温室の酸素供給装置を点検し、フィルターの交換と不具合の一次対応を行います。数値の記録と報告も業務に含まれます。",
    "dune-vehicle-guide": "砂丘を走る高機動車で、来園者を温室群へ案内します。運転と車内でのご案内をお願いします。シフト制で、土日の勤務もあります。",
    "ruins-storyteller": "遺跡の前庭で、遺跡と植物のかかわりを来園者にお話しします。現地の調査員から聞いた話も交えて、わかりやすく伝える仕事です。",
    "ruins-soil-surveyor": "遺跡の周辺で土を採取し、成分と湿り気を調べて記録します。屋外での作業があり、調査の結果は園の栽培計画に使われます。",
    "gravity-crossbreeding-coordinator": "重力の違う区画の間で、交配の日程と花粉の受け渡しを調整します。区画ごとの担当者と連絡を取り合う、段取りの仕事です。",
    "seed-recorder": "集めた種子の採取日・産地・保管場所を記録し、台帳を整えます。正確さが求められる、落ち着いた事務の仕事です。",
    "plant-quarantine-officer": "ステーションへ持ち込まれる植物を調べ、害虫や病気の有無を確かめて、通してよいかを判断します。園の植物を守る、最初の砦の仕事です。",
    "hidden-test-lead": "栽培チームをまとめ、作業の計画と引き継ぎを管理します。メンバーの相談に乗り、育成の方針を決める立場です。",
    "plant-doctor": "弱った植物の症状を見立て、治療の方針を決めて、園の栽培員に伝えます。原因を突き止めるまでの観察と記録が仕事の中心です。",
    "garden-pr-officer": "園の魅力を、掲示や案内資料、来園者向けの知らせにして発信します。季節の見どころを取材し、わかりやすい言葉にまとめます。",
    "entrance-receptionist": "入園の受付で、来園者の案内と入園票の確認を行います。はじめての方に園内の回り方をお伝えする、笑顔が大切な仕事です。",
    "water-cycle-technician": "ドーム内の水の循環装置を点検し、水質の記録と部品の交換を行います。止まると園全体に響くため、日々の点検が欠かせません。",
    "dome-glass-cleaner": "ドームの外壁ガラスを清掃し、日差しを妨げる汚れや傷の有無を確認します。高所での作業があり、安全の研修を受けてから始めます。",
    "seedling-courier": "育てた苗を、園や温室へ運びます。運搬中の温度と湿り気にも気を配る、丁寧さが求められる仕事です。短い時間から働けます。",
    "fungi-cultivator": "キノコの菌床を用意し、湿度と温度を見ながら栽培と収穫を行います。暗く涼しい培養室での作業が中心です。",
    "pollinator-keeper": "受粉を担う昆虫を飼育し、温室へ放す時期と数を調整します。生き物の世話が好きな方に向いています。",
    "flower-workshop-instructor": "花束づくり体験の教室で、参加者に花の選び方と束ね方をお教えします。人に教えることが好きな方、短い時間から働きたい方を歓迎します。",
    "mist-tree-pruner": "霧樹の森で、枝の込み具合を見ながら剪定します。高所での作業があり、道具の扱いは入社後に研修でお伝えします。",
    "hydroponic-shelf-manager": "水耕栽培の棚で、培養液の濃度を管理し、苗の育ちを記録します。毎日の変化に気づける、細やかな方に向いています。",
    "soil-nutrient-analyst": "土壌と培養液の成分を分析し、結果を栽培員へ報告します。数値から育ち方を読み解く、研究に近い仕事です。",
    "rare-species-conservator": "希少な植物の保全計画を立て、保存株の状態を定期的に点検します。種を絶やさないための、長い目で取り組む仕事です。",
    "guide-desk-staff": "案内所で、来園者の道案内と問い合わせへの対応をします。シフト制で、土日の勤務もあります。接客が好きな方を歓迎します。",
    "seasonal-event-planner": "季節ごとの催しを企画し、会場づくりと運営の段取りを担当します。催しの当日は、現場で来園者を迎える役割も担います。",
    "hidden-gas-detector": "遺跡前の園で、有害なガスの発生を検知し、安全を確かめて報告します。異常の早期発見が、来園者と職員を守ります。",
    "hidden-ticket-accountant": "入園券の売上を集計し、日々の会計を記録します。数字を正確に扱う、落ち着いた事務の仕事です。",
    "hidden-research-assistant": "研究チームの観察と測定を補助し、記録を整理します。研究の現場を支える、補助的な役割です。",
}
PAY_NOTE = "交通費は規定により支給します。"  # recruits.note1（詳細の「給与の備考」）


def _insert_recruit(conn, garden_account_id, row, schedule) -> int:
    demo_key, corporate, category, employ, pay_min, pay_max, areas, stations, occupations, shown = row
    start_hour, start_minute, end_hour, end_minute, workday = schedule
    rid = conn.execute(
        "INSERT INTO recruits (garden_account_id, employ, category, corporate, profile, place, salary, pay_min, pay_max, comment1, note1,"
        " start_hour, start_minute, end_hour, end_minute, workday, insurance, is_displayed, demo_key)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '連邦保険・園共済', %s, %s)"
        " RETURNING id",
        (
            garden_account_id,
            employ, category, corporate, f"{corporate}は、これは練習用の架空の法人です。", "翠環連邦内（架空の住所）",
            2 if employ == 1 else 4, pay_min, pay_max, COMMENTS.get(demo_key, f"{category}の仕事です。"), PAY_NOTE,
            start_hour, start_minute, end_hour, end_minute, workday, shown, demo_key,
        ),
    ).fetchone()[0]
    for code in areas:
        conn.execute("INSERT INTO recruit_areas VALUES (%s, %s)", (rid, code))
    for code in stations:
        conn.execute("INSERT INTO recruit_stations VALUES (%s, %s)", (rid, code))
    for code in occupations:
        conn.execute("INSERT INTO recruit_occupations VALUES (%s, %s)", (rid, code))
    conn.execute("INSERT INTO recruit_employments VALUES (%s, %s)", (rid, employ))
    return rid


def add_extra_recruits(conn) -> int:
    """EXTRA_RECRUITS のうち、demo_key がまだ無い求人だけを足す。既存の求人・アカウント・画像との関連は変えない。何度実行しても同じ。
    園のアカウントは作らない。GARDENS のメールのアカウントが DB にあるときだけ、法人名が同じ求人をそのアカウントに紐づける。"""
    present = {r[0] for r in conn.execute("SELECT demo_key FROM recruits WHERE demo_key = ANY(%s)", ([row[0] for row in EXTRA_RECRUITS],)).fetchall()}
    account_of = {}
    for email, corporate in GARDENS:
        found = conn.execute("SELECT id FROM garden_accounts WHERE email = %s", (email,)).fetchone()
        if found:
            account_of[corporate] = found[0]
    added = 0
    for row in EXTRA_RECRUITS:
        if row[0] in present:
            continue
        _insert_recruit(conn, account_of.get(row[1]), row, SCHEDULE_OF_EMPLOY[row[3]])
        added += 1
    return added


def backfill_demo_keys(conn) -> int:
    """すでにある DB の求人に、固定の demo_key を一度だけ結ぶ。ID が RECRUITS の並び（1〜）と同じで、法人名と職種名も一致する行だけ。
    名前を唯一のキーとして使うのではなく、「想定どおりの行か」の二重の確認に使う。一致しない行は触らない（demo_key が付かないので、画像も結ばれない）。"""
    linked = 0
    for ordinal, (demo_key, corporate, category, *_rest) in enumerate(RECRUITS, start=1):
        linked += conn.execute(
            "UPDATE recruits SET demo_key = %s WHERE id = %s AND demo_key IS NULL AND corporate = %s AND category = %s",
            (demo_key, ordinal, corporate, category),
        ).rowcount
    return linked


def main(reset: bool, extend: bool = False) -> None:
    hasher = PasswordHasher()
    pw_hash = hasher.hash(DEMO_PASSWORD)
    with psycopg.connect(database_url()) as conn:
        if reset:
            conn.execute(
                "TRUNCATE entries, password_resets, recruits, users, user_sessions, garden_accounts, garden_sessions RESTART IDENTITY CASCADE"
            )
        elif conn.execute("SELECT (SELECT count(*) FROM recruits) + (SELECT count(*) FROM users)").fetchone()[0]:
            linked = backfill_demo_keys(conn)
            added = add_extra_recruits(conn) if extend else 0
            print("すでにデータがあります。入れ直すなら --reset を付けてください。" + (f"（求人 {linked} 件に demo_key を結びました）" if linked else ""))
            if extend:
                print(f"--extend: 求人 {added} 件を足しました（demo_key がすでにある求人は触りません）。")
            return
        garden_ids = [
            conn.execute(
                "INSERT INTO garden_accounts (corporate, email, password_hash) VALUES (%s, %s, %s) RETURNING id", (corporate, email, pw_hash)
            ).fetchone()[0]
            for email, corporate in GARDENS
        ]
        for row in RECRUITS:
            corporate = row[1]
            _insert_recruit(conn, garden_ids[GARDEN_OF_CORPORATE[corporate]] if corporate in GARDEN_OF_CORPORATE else None, row, DEFAULT_SCHEDULE)
        conn.execute(
            "INSERT INTO users (display_name, email, password_hash) VALUES ('ひかり', 'hoshiniwa-user@example.com', %s)",
            (pw_hash,),
        )
        added = add_extra_recruits(conn) if extend else 0
    print(f"求人 {len(RECRUITS) + added} 件、利用者 1 人、園アカウント {len(GARDENS)} 件を入れました。")


if __name__ == "__main__":
    require_demo_data_allowed()
    main(reset="--reset" in sys.argv[1:], extend="--extend" in sys.argv[1:])
