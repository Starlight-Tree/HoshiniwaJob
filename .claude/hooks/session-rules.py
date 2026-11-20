#!/usr/bin/env python3
"""SessionStart（resume / compact）: 星庭ジョブの重要ルールの固定文を文脈へ入れる。

会話の再開・圧縮のあとに、CLAUDE.md の要点が抜けるのを防ぐ。決定は返さず、読み込みに失敗しても作業は止めない。
固定文だけを出す（ファイルの読み込み・外部への通信・環境変数の参照はしない）。詳細は CLAUDE.md と docs/image-gen-resources.md。
"""
import json

MAX_CHARS = 1200  # 超えたら注入しない（長文の事故防止）
RULES = """【再注入: 星庭ジョブの重要ルール】
■必ず守る
1. 画像生成のデプロイ・モデル・保存先を変えたら、docs/image-gen-resources.md（台帳）を更新するまで「完了」にしない。デプロイ・実行・生成成功・保存と回収・画面表示は別々に記録し、成功版はイメージのダイジェストで識別する。
2. 頼まれた範囲だけ編集する。範囲外は提案にとどめる。未コミットの差分は、頼まれない限り触らず、コミットにも含めない。
■承認が必要（承認は、その操作だけに有効）
3. 実 API・課金（Gemini Batch など）、R2 への書き込み、本番の DB・デプロイ: 件数・回数・概算費用を先に示す。マイグレーションの適用の前は、DB のバックアップ。
4. git push、git reset / restore、フック・権限・CLAUDE.md の変更: 差分を示してから。止められたら回避せず報告する。
■禁止
5. .env・backups/ を読まない。認証情報（STORAGE_S3_* など）は、表示・記録・コミットをしない。
6. seed / seed-images を本番の DB に向けない。適用済みのマイグレーションを書き換えない。DROP / TRUNCATE を足さない。
詳細は CLAUDE.md と台帳。"""


def main():
    text = RULES.strip()
    if len(text) > MAX_CHARS:
        return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, ensure_ascii=False))


main()
