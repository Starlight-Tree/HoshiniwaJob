#!/usr/bin/env bash
# scripts/inspect-image-gen.sh のテスト。偽の gcloud と docker で、次を確かめる。実際の gcloud・docker・GCP には触れない。
#   1. 呼ばれるコマンドが、読み取り専用の許可リストの中だけである（run jobs execute / update / deploy、IAM、gsutil、既定の生成処理は 1 つも呼ばれない）
#   2. 秘密のパターンと、プロンプトの本文が、出力に出ない
#   3. ダイジェストで固定されていないイメージは、読みに行かない
# 実際の gcloud の出力の形に対する動作は、このテストでは確かめられない（未確認）。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

script="scripts/inspect-image-gen.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
calls="$work/calls.log"
: >"$calls"

# 偽の秘密は、ソースに文字列として書かず、実行時に組み立てる（秘密スキャンに引っかからないように）。
fake_key="AIza$(printf 'x%.0s' $(seq 1 35))"
fake_prompt="SECRET-PROMPT-BODY-DO-NOT-PRINT"
digest="sha256:$(printf 'a%.0s' $(seq 1 64))"
image="asia-northeast1-docker.pkg.dev/p/image-repo/imagen-fast-job@${digest}"

cat >"$work/gcloud" <<EOF
#!/usr/bin/env bash
echo "gcloud \$*" >>"$calls"
case "\$1 \$2 \$3 \$4" in
  "run jobs list "*) echo "JOB image-generation-job asia-northeast1" ;;
  "run jobs describe "*)
    cat <<'JSON'
{"metadata":{"name":"image-generation-job","generation":3},
 "spec":{"template":{"spec":{"taskCount":2,"template":{"spec":{"maxRetries":1,"timeoutSeconds":"600","serviceAccountName":"123-compute@developer.gserviceaccount.com",
  "containers":[{"image":"$image","env":[
    {"name":"GOOGLE_CLOUD_PROJECT","value":"p"},{"name":"GOOGLE_CLOUD_LOCATION","value":"global"},
    {"name":"IMAGE_PROMPT","value":"$fake_prompt"},{"name":"API_TOKEN","value":"$fake_key"},
    {"name":"FROM_SECRET","valueFrom":{"secretKeyRef":{"name":"s","key":"latest"}}}],
   "args":["--prompt","$fake_prompt"]}]}}}}}}
JSON
    ;;
  "run jobs executions list")
    echo '[{"metadata":{"name":"image-generation-job-fjtcv"},"spec":{"taskCount":2},"status":{"succeededCount":2,"completionTime":"2026-10-29T13:41:00Z"}},
           {"metadata":{"name":"image-generation-job-bad"},"spec":{"taskCount":2},"status":{"succeededCount":1,"failedCount":1,"completionTime":"2026-10-30T00:00:00Z"}}]'
    ;;
  "run jobs executions describe")
    cat <<JSON
{"spec":{"taskCount":2,"template":{"spec":{"maxRetries":1,"serviceAccountName":"sa@example","containers":[{"image":"$image"}]}}},
 "status":{"succeededCount":2,"failedCount":0,"startTime":"2026-10-29T13:40:00Z","completionTime":"2026-10-29T13:41:00Z"}}
JSON
    ;;
  "artifacts docker images describe") echo "image_summary: digest ${digest}" ;;
  "artifacts docker images list") echo "PACKAGE VERSION TAGS CREATE_TIME" ;;
  "logging read "*)
    cat <<JSON
[{"timestamp":"2026-10-29T13:40:30Z","labels":{"run.googleapis.com/task_index":"0"},"textPayload":"Generating image with Nano Banana 2 Lite: '$fake_prompt'"},
 {"timestamp":"2026-10-29T13:40:40Z","labels":{"run.googleapis.com/task_index":"0"},"textPayload":"Saved Nano Banana 2 Lite image to output_task0_0.png"},
 {"timestamp":"2026-10-29T13:40:41Z","labels":{"run.googleapis.com/task_index":"0"},"textPayload":"Container called exit(0)."},
 {"timestamp":"2026-10-29T13:40:42Z","labels":{"run.googleapis.com/task_index":"0"},"textPayload":"unrelated line $fake_key"}]
JSON
    ;;
  *) echo "許可されていない gcloud の呼び出し: \$*" >&2; exit 99 ;;
esac
EOF

cat >"$work/docker" <<EOF
#!/usr/bin/env bash
echo "docker \$*" >>"$calls"
case "\$1" in
  pull) exit 0 ;;
  image) echo 'entrypoint=null cmd=["python","main.py"] workdir=/app created=2026-10-29T00:00:00Z' ;;
  run)
    # 既定の生成処理を起動しないこと: --entrypoint が必須で、cat / ls / pip だけ。
    ep=""
    prev=""
    for a in "\$@"; do
      if [[ "\$prev" == "--entrypoint" ]]; then ep="\$a"; fi
      prev="\$a"
    done
    case "\$ep" in
      cat) printf 'MODEL = "gemini-test-model"\nclient = genai.Client(vertexai=True, location="global")\nkey = "%s"\n' "$fake_key" ;;
      ls) echo "main.py" ;;
      pip) echo "google-genai 1.0" ;;
      *) echo "--entrypoint が無い、または許可されていない docker run: \$*" >&2; exit 99 ;;
    esac
    ;;
  *) echo "許可されていない docker の呼び出し: \$*" >&2; exit 99 ;;
esac
EOF
chmod +x "$work/gcloud" "$work/docker"

fail=0
check() {
  if ! eval "$2"; then
    echo "失敗: $1"
    fail=1
  fi
}

out="$work/out.txt"
GCLOUD="$work/gcloud" DOCKER="$work/docker" "$script" --read-source >"$out" 2>&1 || {
  echo "失敗: スクリプトが異常終了した"
  cat "$out"
  exit 1
}

# 1. 許可リスト
bad="$(grep -v -E '^(gcloud (run jobs (list|describe|executions (list|describe))|artifacts docker images (describe|list)|logging read)|docker (pull|image inspect|run --rm --platform linux/amd64 --entrypoint (cat|ls|pip) ))' "$calls" || true)"
check "許可リスト外のコマンドが呼ばれた: ${bad}" '[[ -z "$bad" ]]'
check "execute / update / deploy / IAM / gsutil を呼んでいる" '! grep -q -E "^gcloud (run jobs (execute|update|deploy|create|delete|replace)|.* (add|set|remove)-iam-policy-binding|projects|iam|auth|config)|^gsutil|^docker (push|rm|rmi|build|tag)" "$calls"'
check "スクリプトの本文に、書き込み系のコマンドがある" '! grep -n -E "run jobs (execute|update|deploy|create|delete)|add-iam-policy-binding|gsutil|gcloud auth|--impersonate-service-account|config set|CLOUDSDK_" "$script" | grep -v "^[0-9]*:#"'

# 2. 秘密とプロンプト
check "偽の API キーが出力に出た" '! grep -q "$fake_key" "$out"'
check "プロンプトの本文が出力に出た" '! grep -q "$fake_prompt" "$out"'
check "環境変数 IMAGE_PROMPT の値が出た" '! grep -q "IMAGE_PROMPT = SECRET" "$out"'
check "許可リストの環境変数が出ない" 'grep -q "GOOGLE_CLOUD_LOCATION = global" "$out"'

# 3. 期待する内容
check "完了した直近の実行を選んでいない" 'grep -q "実行: image-generation-job-fjtcv" "$out"'
check "既定の Compute SA の注意が出ない" 'grep -q "既定の Compute Engine サービスアカウント" "$out"'
check "生成呼び出しの上限（2 x (1+1) = 4）が出ない" 'grep -q "生成呼び出しの上限: 4" "$out"'
check "ダイジェストを出していない" 'grep -q "$digest" "$out"'
check "main.py のモデル行を出していない" 'grep -q "gemini-test-model" "$out"'
check "保存の行を出していない" 'grep -q "Saved Nano Banana 2 Lite image to output_task0_0.png" "$out"'

# 4. タグだけのイメージは、読みに行かない
: >"$calls"
sed -e "s#@${digest}#:latest#g" "$work/gcloud" >"$work/gcloud-tag"
chmod +x "$work/gcloud-tag"
GCLOUD="$work/gcloud-tag" DOCKER="$work/docker" "$script" --read-source >"$out" 2>&1 || true
check "タグだけのイメージで docker を呼んだ" '! grep -q "^docker" "$calls"'
check "タグだけのイメージの警告が無い" 'grep -q "ダイジェストで固定されていません" "$out"'

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "OK: scripts/inspect-image-gen.sh"
