"""ローカル用のダミーデータ（架空の宇宙の植物園・ガーデンの法人と利用者）を入れる。実在の人・法人のデータは使わない。

    python -m app.seed_demo          # 求人・利用者・園アカウントが空のときだけ入れる
    python -m app.seed_demo --reset  # 求人・応募・アカウントを消して入れ直す（マスタは触らない）

ログイン確認用: 利用者 hoshiniwa-user@example.com / 園 hoshiniwa-garden@example.com と hoshiniwa-garden2@example.com、
パスワードはどれも README に書いたダミー（ローカル専用）。
"""

import sys

import psycopg
from argon2 import PasswordHasher

from app.settings import database_url

# ローカル専用のダミー。実在のパスワードは使わない。
DEMO_PASSWORD = "star-garden-demo"

# 給与は架空の通貨「ノクト」（常勤は月給制、それ以外は時給制。通貨の表示は画面側）。
# (法人名, 職種名, 雇用形態コード, 最低給与, 最高給与, 地域コード, 乗り場コード, 職種コード, 表示)
RECRUITS = [
    ("環軌道植物公社", "無重力蔓の育成士", 1, 180000, 240000, [3], [5], [1], True),
    ("環軌道植物公社", "人工夜の温室管理員", 1, 190000, 250000, [4], [2], [2], True),
    ("ミルフェン月面植物園", "植物園の語り部", 2, 1100, 1300, [8], [7], [9], True),
    ("ミルフェン月面植物園", "夜の花見ガイド", 1, 200000, 260000, [9, 10], [7, 9], [11], True),
    ("ザーハード砂漠温室組合", "酸素供給装置の保守員", 1, 210000, 270000, [12], [4, 11], [6], True),
    ("ザーハード砂漠温室組合", "砂丘の高機動車の運転案内", 3, 1000, 1200, [12], [4, 11], [12], True),
    ("遺跡前ガーデン", "遺跡前の語り部", 2, 1150, 1350, [13, 14], [10, 11], [10], True),
    ("遺跡前ガーデン", "遺跡周辺の土壌の調査員", 4, 1500, 1700, [14], [10], [19], True),
    ("星庭財団", "重力別の交配調整員", 3, 1300, 1500, [3, 4], [5, 6], [17], True),
    ("星庭財団", "種子の記録係", 1, 185000, 230000, [4], [1], [16], True),
    ("静止軌道ガーデンズ", "持ち込み植物の検疫官", 2, 1100, 1250, [6], [1, 6], [25], True),
    ("非表示のテスト求人", "栽培の統括", 1, 100000, 100000, [1], [1], [7], False),
]


# 園のアカウント（メール, 法人名）。求人は、法人名が同じ園のアカウントに紐づける（どの園にも紐づかない求人もある）。
GARDENS = [
    ("hoshiniwa-garden@example.com", "環軌道植物公社"),
    ("hoshiniwa-garden2@example.com", "ミルフェン月面植物園"),
]
# 「非表示のテスト求人」は、1 つ目の園の非表示の求人として使う
GARDEN_OF_CORPORATE = {"環軌道植物公社": 0, "非表示のテスト求人": 0, "ミルフェン月面植物園": 1}


def main(reset: bool) -> None:
    hasher = PasswordHasher()
    pw_hash = hasher.hash(DEMO_PASSWORD)
    with psycopg.connect(database_url()) as conn:
        if reset:
            conn.execute(
                "TRUNCATE entries, password_resets, recruits, users, user_sessions, garden_accounts, garden_sessions RESTART IDENTITY CASCADE"
            )
        elif conn.execute("SELECT (SELECT count(*) FROM recruits) + (SELECT count(*) FROM users)").fetchone()[0]:
            print("すでにデータがあります。入れ直すなら --reset を付けてください。")
            return
        garden_ids = [
            conn.execute(
                "INSERT INTO garden_accounts (corporate, email, password_hash) VALUES (%s, %s, %s) RETURNING id", (corporate, email, pw_hash)
            ).fetchone()[0]
            for email, corporate in GARDENS
        ]
        for corporate, category, employ, pay_min, pay_max, areas, stations, occupations, shown in RECRUITS:
            rid = conn.execute(
                "INSERT INTO recruits (garden_account_id, employ, category, corporate, profile, place, salary, pay_min, pay_max, comment1, note1,"
                " start_hour, start_minute, end_hour, end_minute, workday, insurance, is_displayed)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '09', '00', '18', '00', '月〜金', '連邦保険・園共済', %s)"
                " RETURNING id",
                (
                    garden_ids[GARDEN_OF_CORPORATE[corporate]] if corporate in GARDEN_OF_CORPORATE else None,
                    employ, category, corporate, f"{corporate}は、これは練習用の架空の法人です。", "翠環連邦内（架空の住所）",
                    2 if employ == 1 else 4, pay_min, pay_max, f"{category}の業務です（ダミー）。", "ダミーの備考です。", shown,
                ),
            ).fetchone()[0]
            for code in areas:
                conn.execute("INSERT INTO recruit_areas VALUES (%s, %s)", (rid, code))
            for code in stations:
                conn.execute("INSERT INTO recruit_stations VALUES (%s, %s)", (rid, code))
            for code in occupations:
                conn.execute("INSERT INTO recruit_occupations VALUES (%s, %s)", (rid, code))
            conn.execute("INSERT INTO recruit_employments VALUES (%s, %s)", (rid, employ))
        conn.execute(
            "INSERT INTO users (last_name, first_name, email, password_hash) VALUES ('苔野', 'ひかり', 'hoshiniwa-user@example.com', %s)",
            (pw_hash,),
        )
    print(f"求人 {len(RECRUITS)} 件、利用者 1 人、園アカウント {len(GARDENS)} 件を入れました。")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv[1:])
