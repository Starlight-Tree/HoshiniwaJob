#!/usr/bin/env bash
# 画像生成の Cloud Run Job について、デプロイ済みの設定・直近の成功した実行・イメージのダイジェスト・ログを読む。読み取り専用。
# 台帳（docs/image-gen-resources.md）を更新する材料を、最短で集めるための道具。
#
# 行わないこと: 画像の生成、ジョブの実行・更新・デプロイ、IAM の変更、DB の変更、ファイルへの書き込み。
# 使う gcloud:  run jobs list / describe、run jobs executions list / describe、artifacts docker images describe、logging read
# 使う docker:  --read-source のときだけ。pull、image inspect、--entrypoint を上書きした run（cat / ls / pip だけ。既定の生成処理は起動しない）
# 認証: 呼び出した人の gcloud の認証をそのまま使う。認証の設定・なりすましの設定は、読みも変えもしない。
# 出力: 秘密のパターンを伏せる。環境変数は、名前と、許可リストの値だけを出す。ログは、保存・終了・警告・エラーの行だけで、プロンプトの本文は出さない。
#
#   scripts/inspect-image-gen.sh                 # ジョブ・直近の成功した実行・イメージ・ログ
#   scripts/inspect-image-gen.sh --read-source   # さらに、そのダイジェストのイメージから /app/main.py を読む（docker が要る）
#
# 環境変数（省略時は台帳の値）:
#   IMAGEN_PROJECT IMAGEN_JOB_REGION IMAGEN_JOB_NAME
#   IMAGEN_EXECUTION   実行の名前。空なら、完了した直近の実行
#   GCLOUD DOCKER      テスト用に差し替える
set -euo pipefail

PROJECT="${IMAGEN_PROJECT:-imagen-app-2026}"
REGION="${IMAGEN_JOB_REGION:-asia-northeast1}"
JOB="${IMAGEN_JOB_NAME:-image-generation-job}"
EXECUTION="${IMAGEN_EXECUTION:-}"
GCLOUD="${GCLOUD:-gcloud}"
DOCKER="${DOCKER:-docker}"
PYTHON="${PYTHON:-python3}"

read_source=0
case "${1:-}" in
  "") ;;
  --read-source) read_source=1 ;;
  -h | --help)
    sed -n '2,/^set -euo/p' "$0" | sed '$d'
    exit 0
    ;;
  *)
    echo "使い方: $0 [--read-source]" >&2
    exit 2
    ;;
esac

# 秘密の形をしたものを伏せる。出力はすべてここを通す。
redact() {
  LC_ALL=C sed -E \
    -e 's/AIza[0-9A-Za-z_-]{20,}/[伏せた:APIキー]/g' \
    -e 's/ya29\.[0-9A-Za-z_.-]+/[伏せた:トークン]/g' \
    -e 's/eyJ[0-9A-Za-z_-]{10,}\.[0-9A-Za-z_-]{10,}(\.[0-9A-Za-z_-]*)?/[伏せた:JWT]/g' \
    -e 's#postgres(ql)?://[^[:space:]"'"'"']+#[伏せた:DB接続文字列]#g' \
    -e 's/-----BEGIN [A-Z ]*PRIVATE KEY-----/[伏せた:秘密鍵]/g' \
    -e 's/(Bearer )[0-9A-Za-z._~+\/=-]{12,}/\1[伏せた]/g'
}

section() { printf '\n== %s ==\n' "$1"; }
# 読めない・失敗した手順は、その旨を出して続ける（権限が足りない場合の切り分けに使う）。
try() {
  local label="$1" rc
  shift
  set +e
  "$@" 2>&1 | redact
  rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$rc" -ne 0 ]]; then
    echo "(${label}: コマンドが失敗しました。権限、プロジェクト、リージョン、名前を確かめてください)"
  fi
}

# JSON を標準入力から読み、python で整形する。キーが無ければ「キー無し」と出す（推測で埋めない）。
pyjson() { "$PYTHON" -I -c "$1"; }

echo "対象: project=${PROJECT} region=${REGION} job=${JOB}"
echo "実行日時(UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"

section "1. ジョブの存在と配置リージョン"
try "run jobs list" "$GCLOUD" run jobs list --project "$PROJECT"

section "2. デプロイ済みの設定（ジョブの現在の定義）"
job_json="$("$GCLOUD" run jobs describe "$JOB" --region "$REGION" --project "$PROJECT" --format=json 2>/dev/null || true)"
if [[ -z "$job_json" ]]; then
  echo "(読めませんでした。ジョブ名・リージョン・権限を確かめてください)"
else
  printf '%s' "$job_json" | pyjson '
import json, sys
ALLOW = {"GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "CLOUD_RUN_TASK_INDEX"}
d = json.load(sys.stdin)
def dig(o, *path):
    for p in path:
        if isinstance(o, dict) and p in o:
            o = o[p]
        elif isinstance(o, list) and isinstance(p, int) and p < len(o):
            o = o[p]
        else:
            return "(キー無し)"
    return o
md = d.get("metadata", {})
t = dig(d, "spec", "template", "spec")
tt = dig(t, "template", "spec") if isinstance(t, dict) else "(キー無し)"
c = dig(tt, "containers", 0) if isinstance(tt, dict) else "(キー無し)"
print("name:", md.get("name"))
print("generation:", md.get("generation"))
print("image:", dig(c, "image") if isinstance(c, dict) else c)
print("command:", dig(c, "command") if isinstance(c, dict) else c)
print("args:", "(あり。内容は出さない)" if isinstance(c, dict) and c.get("args") else "(なし)")
print("taskCount:", dig(t, "taskCount") if isinstance(t, dict) else t)
print("parallelism:", dig(t, "parallelism") if isinstance(t, dict) else t)
print("maxRetries:", dig(tt, "maxRetries") if isinstance(tt, dict) else tt)
print("timeoutSeconds:", dig(tt, "timeoutSeconds") if isinstance(tt, dict) else tt)
sa = dig(tt, "serviceAccountName") if isinstance(tt, dict) else tt
print("serviceAccountName:", sa)
if isinstance(sa, str) and sa.endswith("-compute@developer.gserviceaccount.com"):
    print("注意: 実行身分は既定の Compute Engine サービスアカウント（VM は起動しない。Cloud Run Jobs が身分として使うだけ）。広い権限（editor など）が付いていることがある。")
tc, mr = (t.get("taskCount") if isinstance(t, dict) else None), (tt.get("maxRetries") if isinstance(tt, dict) else None)
if isinstance(tc, int) and isinstance(mr, int):
    print("1 回の execute での生成呼び出しの上限:", tc * (1 + mr), "（taskCount × (1 + maxRetries)。失敗時の再試行を含む）")
env = c.get("env", []) if isinstance(c, dict) else []
print("env（名前。許可リストの値だけ表示）:")
for e in env:
    n = e.get("name", "?")
    if "valueFrom" in e:
        print("  ", n, "= (Secret などの参照。値は出さない)")
    elif n in ALLOW:
        print("  ", n, "=", e.get("value"))
    else:
        print("  ", n, "= (値は出さない)")
vols = tt.get("volumes", []) if isinstance(tt, dict) else []
print("volumes:", [{"name": v.get("name"), "kind": [k for k in v if k != "name"]} for v in vols] or "(なし)")
mounts = c.get("volumeMounts", []) if isinstance(c, dict) else []
print("volumeMounts:", [m.get("mountPath") for m in mounts] or "(なし)")
' || echo "(整形に失敗しました)"
fi

section "3. 直近の成功した実行"
if [[ -z "$EXECUTION" ]]; then
  execs_json="$("$GCLOUD" run jobs executions list --job "$JOB" --region "$REGION" --project "$PROJECT" --limit 20 --format=json 2>/dev/null || true)"
  if [[ -z "$execs_json" ]]; then
    echo "(実行の一覧を読めませんでした)"
  else
    EXECUTION="$(printf '%s' "$execs_json" | pyjson '
import json, sys
rows = json.load(sys.stdin)
ok = []
for r in rows:
    st, sp = r.get("status", {}), r.get("spec", {})
    tc = sp.get("taskCount")
    if tc and st.get("succeededCount") == tc and not st.get("failedCount"):
        ok.append((st.get("completionTime", ""), r.get("metadata", {}).get("name", "")))
ok.sort()
print(ok[-1][1] if ok else "")
' || true)"
    if [[ -z "$EXECUTION" ]]; then
      echo "(完了した実行が、直近 20 件に見つかりませんでした)"
    fi
  fi
fi
image=""
if [[ -n "$EXECUTION" ]]; then
  echo "実行: ${EXECUTION}"
  exec_json="$("$GCLOUD" run jobs executions describe "$EXECUTION" --region "$REGION" --project "$PROJECT" --format=json 2>/dev/null || true)"
  if [[ -z "$exec_json" ]]; then
    echo "(実行を読めませんでした)"
  else
    printf '%s' "$exec_json" | pyjson '
import json, sys
d = json.load(sys.stdin)
sp, st = d.get("spec", {}), d.get("status", {})
tt = sp.get("template", {}).get("spec", {})
c = (tt.get("containers") or [{}])[0]
print("image:", c.get("image", "(キー無し)"))
print("taskCount:", sp.get("taskCount", "(キー無し)"))
print("maxRetries:", tt.get("maxRetries", "(キー無し)"))
print("serviceAccountName:", tt.get("serviceAccountName", "(キー無し)"))
print("succeeded/failed/running:", st.get("succeededCount"), st.get("failedCount"), st.get("runningCount"))
print("startTime:", st.get("startTime"), " completionTime:", st.get("completionTime"))
' || echo "(整形に失敗しました)"
    image="$(printf '%s' "$exec_json" | pyjson '
import json, sys
d = json.load(sys.stdin)
tt = d.get("spec", {}).get("template", {}).get("spec", {})
print((tt.get("containers") or [{}])[0].get("image", ""))
' || true)"
  fi
fi

section "4. 成功した実行のイメージ"
if [[ -z "$image" ]]; then
  echo "(イメージを特定できませんでした)"
elif [[ "$image" != *@sha256:* ]]; then
  echo "イメージ: ${image}"
  echo "(ダイジェストで固定されていません。タグは、成功版の識別情報になりません)"
else
  echo "イメージ: ${image}"
fi

section "5. Artifact Registry にイメージが残っているか"
if [[ "$image" == *@sha256:* ]]; then
  try "artifacts docker images describe" "$GCLOUD" artifacts docker images describe "$image" --project "$PROJECT"
else
  echo "(ダイジェストが無いので確かめません)"
fi

section "5b. リポジトリのイメージ一覧（成功した実行より後に作られたもの、タグ付きのものを探す）"
# 手順 4 のイメージの場所（…/<プロジェクト>/<リポジトリ>/<イメージ名>）から、ダイジェストを除いたものを使う。取れなければ、台帳の既定。
repo_path="${image%@*}"
if [[ -z "$repo_path" || "$repo_path" == "$image" && "$image" != */* ]]; then
  repo_path="${REGION}-docker.pkg.dev/${PROJECT}/image-repo/imagen-fast-job"
fi
echo "対象: ${repo_path}"
try "artifacts docker images list" "$GCLOUD" artifacts docker images list "$repo_path" --include-tags --project "$PROJECT" \
  --sort-by=~UPDATE_TIME --limit 20 --format="table(package,version,tags,createTime,updateTime)"

section "6. 成功した実行のログ（保存・終了・警告・エラーの行だけ。プロンプトの本文は出さない）"
if [[ -n "$EXECUTION" ]]; then
  log_json="$("$GCLOUD" logging read \
    "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB}\" AND labels.\"run.googleapis.com/execution_name\"=\"${EXECUTION}\"" \
    --project "$PROJECT" --limit 300 --format=json 2>/dev/null || true)"
  if [[ -z "$log_json" ]]; then
    echo "(ログを読めませんでした)"
  else
    printf '%s' "$log_json" | pyjson '
import json, re, sys
rows = json.load(sys.stdin)
rows.sort(key=lambda r: r.get("timestamp", ""))
KEEP = re.compile(r"^(Initializing GenAI Client|Saved |Warning|Container called exit|Traceback|.*Error)", re.I)
gen = 0
for r in rows:
    task = r.get("labels", {}).get("run.googleapis.com/task_index", "?")
    text = r.get("textPayload") or ""
    if text.startswith("Generating image"):
        gen += 1
        print("task", task, "| Generating の行あり（本文は出さない）")
    elif KEEP.match(text):
        print("task", task, "|", text[:200])
print("Generating の行:", gen, "件")
' || echo "(整形に失敗しました)"
  fi
else
  echo "(実行が特定できないので読みません)"
fi

if [[ "$read_source" -eq 1 ]]; then
  section "7. イメージ内のコードを読む（生成は起動しない）"
  if [[ "$image" != *@sha256:* ]]; then
    echo "(ダイジェストで固定されたイメージが無いので、読みません)"
  else
    "$DOCKER" pull --platform linux/amd64 "$image" >/dev/null 2>&1 || echo "(docker pull に失敗。Artifact Registry への docker の認証〔configure-docker〕を、利用者自身で済ませているか確かめてください)"
    try "image inspect" "$DOCKER" image inspect "$image" \
      --format 'entrypoint={{json .Config.Entrypoint}} cmd={{json .Config.Cmd}} workdir={{.Config.WorkingDir}} created={{.Created}}'
    echo "-- /app --"
    try "ls /app" "$DOCKER" run --rm --platform linux/amd64 --entrypoint ls "$image" -la /app
    echo "-- /app/main.py の SHA-256 --"
    "$DOCKER" run --rm --platform linux/amd64 --entrypoint cat "$image" /app/main.py 2>/dev/null |
      "$PYTHON" -I -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())' || echo "(読めませんでした)"
    echo "-- モデル・場所・クライアント・保存先に関係する行（先頭 60 行、各 160 文字まで）--"
    "$DOCKER" run --rm --platform linux/amd64 --entrypoint cat "$image" /app/main.py 2>/dev/null |
      { grep -n -i -E 'model|location|vertexai|Client\(|gs://|storage|bucket|\.save|open\(|aspect|response_modalities' || true; } |
      cut -c1-160 | head -60 | redact
    echo "-- ライブラリーの版 --"
    "$DOCKER" run --rm --platform linux/amd64 --entrypoint pip "$image" list 2>/dev/null | { grep -i -E 'genai|google-cloud|google-auth' || true; } | redact
  fi
fi

echo
echo "完了。出力を目で確かめて、秘密が無ければ docs/image-gen-evidence/ に保存し、docs/image-gen-resources.md の「未確認」を更新してください。"
