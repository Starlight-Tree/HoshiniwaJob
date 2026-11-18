#!/usr/bin/env python3
"""PreToolUse(Bash) の小さなガード: wrangler・infisical・prisma の書き込み系を、実行前に確認（ask）へ回す。

  - wrangler: 読み取り・ローカルの許可リスト（dev / whoami / types / tail / deployments list / versions list・view /
    secret list / d1 list・info・migrations list / d1 execute --local / kv key list・get / r2 bucket list / r2 object get /
    --version・--help）以外はすべて確認。deploy・secret put・delete・rollback・login なども、ここに入る。
  - infisical: 値が出る・書き込む操作（secrets の表示・set・delete・folders・export・login・init など）を確認。
    `infisical run` と `infisical --version` は確認しない（値を表示しない）。
  - prisma: migrate deploy / reset / dev / resolve、db push / execute を確認。

確認の理由には、コマンドの種類だけを出す（引数・接続文字列の値は出さない）。`bash -c` / `sh -c` の中身も同じ規則で調べる。
`deny` ではなく `ask` にしているのは、ユーザーが明示して頼んだときに実行できるようにするため（例: 検証用の画面 Worker の配備）。
guard-cloud-cli.py（gcloud・gh など）と guard-git-write.py（git・PR コメント）は別の役割で、ここは重ねない。

限界: コマンド文字列の解析なので、別名・スクリプト経由・シェルの変数展開は防げない。誤操作と、取り込んだ文書に
埋め込まれた指示への網で、完全な防御ではない（権限の deny と併用する）。
"""

from __future__ import annotations

import json
import re
import shlex
import sys

SEPARATORS = re.compile(r"&&|\|\||;|\||\n")
RUNNERS = {"npx", "pnpm", "pnpx", "bunx", "yarn", "npm", "dlx", "exec", "x", "run"}
SHELLS = {"bash", "sh", "zsh"}

# wrangler: 確認なしにしてよい（読み取り・ローカル）。サブコマンド列の先頭から一致を見る
WRANGLER_SAFE = [
    ("dev",),
    ("whoami",),
    ("types",),
    ("tail",),
    ("check",),
    ("docs",),
    ("deployments", "list"),
    ("deployments", "status"),
    ("versions", "list"),
    ("versions", "view"),
    ("secret", "list"),
    ("d1", "list"),
    ("d1", "info"),
    ("d1", "migrations", "list"),
    ("kv", "key", "list"),
    ("kv", "key", "get"),
    ("kv", "namespace", "list"),
    ("r2", "bucket", "list"),
    ("r2", "object", "get"),
]
INFISICAL_SAFE_FIRST = {"run", "--version", "-v", "version", "--help", "-h", "help", "user"}
PRISMA_ASK = [
    ("migrate", "deploy"),
    ("migrate", "reset"),
    ("migrate", "dev"),
    ("migrate", "resolve"),
    ("db", "push"),
    ("db", "execute"),
]

Decision = tuple[str, str]  # ("ask", 理由)


def segments(command: str) -> list[list[str]]:
    out: list[list[str]] = []
    for part in SEPARATORS.split(command):
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        while tokens and (
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]) or tokens[0] in {"command", "env", "sudo"}
        ):
            tokens = tokens[1:]
        if tokens:
            out.append(tokens)
    return out


def positional(tokens: list[str]) -> list[str]:
    """オプション（- で始まる語）を除いた語の列。値つきオプションの値は区別しない（保守的に確認側へ倒れる）。"""
    return [t for t in tokens if not t.startswith("-")]


def match_prefix(words: list[str], prefixes: list[tuple[str, ...]]) -> bool:
    return any(tuple(words[: len(p)]) == p for p in prefixes)


def tool_and_rest(tokens: list[str]) -> tuple[str, list[str]]:
    """`npx wrangler …` / `pnpm exec wrangler …` のような実行ラッパーを外して、(ツール名, 残りの引数) を返す。"""
    i = 0
    while (
        i < len(tokens)
        and (tokens[i] in RUNNERS or tokens[i].startswith("-"))
        and tokens[i] not in {"wrangler", "infisical", "prisma"}
    ):
        i += 1
    if i >= len(tokens):
        return "", []
    name = tokens[i].rsplit("/", 1)[-1]
    name = re.sub(r"@[\w.^~-]+$", "", name)  # wrangler@4.1 → wrangler
    return name, tokens[i + 1 :]


def decide_tokens(tokens: list[str], depth: int = 0) -> Decision | None:
    if tokens and tokens[0].rsplit("/", 1)[-1] in SHELLS and depth < 3 and "-c" in tokens:
        idx = tokens.index("-c")
        if idx + 1 < len(tokens):
            return decide(tokens[idx + 1], depth + 1)
        return None
    tool, rest = tool_and_rest(tokens)
    if tool == "wrangler":
        if any(a in {"--version", "-v", "--help", "-h"} for a in rest) and not positional(rest):
            return None
        words = positional(rest)
        if not words:
            return None
        if match_prefix(words, WRANGLER_SAFE):
            return None
        if words[:2] == ["d1", "execute"] and "--local" in rest:
            return None
        return "ask", f"wrangler {words[0]} は、配備・Secret・データの書き込みになりうるため確認します"
    if tool == "infisical":
        if not rest:
            return None
        first = next((a for a in rest if not a.startswith("-") or a in INFISICAL_SAFE_FIRST), rest[0])
        if first in INFISICAL_SAFE_FIRST:
            return None
        return (
            "ask",
            f"infisical {first} は、値を表示する・書き込む・ログインする操作になりうるため確認します（書き込みはユーザーの操作）",
        )
    if tool == "prisma":
        words = positional(rest)
        if match_prefix(words, PRISMA_ASK):
            return "ask", f"prisma {' '.join(words[:2])} は、データベースを変更するため確認します"
    return None


def decide(command: str, depth: int = 0) -> Decision | None:
    for tokens in segments(command):
        result = decide_tokens(tokens, depth)
        if result:
            return result
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = (event.get("tool_input") or {}).get("command") or ""
    if event.get("tool_name") != "Bash" or not command:
        return 0
    result = decide(command)
    if result:
        decision, reason = result
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": decision,
                        "permissionDecisionReason": f"guard-deploy-cli: {reason}",
                    }
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
