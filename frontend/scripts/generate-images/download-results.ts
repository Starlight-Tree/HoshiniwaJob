import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import type { GenerateContentResponse } from '@google/genai'
import { createClient, extensionFor, fail, imageDimensions, JOB_FILE, OUTPUT_DIR } from './common.ts'
import { IMAGES } from './prompts.ts'

type Result = { key: string; response?: GenerateContentResponse; errorMessage?: string }

function whyNoImage(response: GenerateContentResponse): string {
  const candidate = response.candidates?.[0]
  const reasons = [
    response.promptFeedback?.blockReason ? `blockReason=${response.promptFeedback.blockReason}` : '',
    candidate?.finishReason ? `finishReason=${candidate.finishReason}` : '',
    candidate?.finishMessage ?? '',
  ].filter(Boolean)
  return reasons.length > 0 ? reasons.join(' ') : '画像パートがありません'
}

if (!existsSync(JOB_FILE)) {
  console.error('.last-batch-job.txt がありません。先に images:create-batch を実行してください。')
  process.exit(1)
}
const name = readFileSync(JOB_FILE, 'utf8').trim()

try {
  const ai = createClient()
  const job = await ai.batches.get({ name })
  if (job.state !== 'JOB_STATE_SUCCEEDED') {
    console.error(`状態が ${job.state ?? '(不明)'} です。JOB_STATE_SUCCEEDED のときだけ取得します。`)
    process.exit(1)
  }

  const results: Result[] = []
  if (job.dest?.inlinedResponses) {
    for (const item of job.dest.inlinedResponses) {
      results.push({
        key: item.metadata?.key ?? '(key なし)',
        response: item.response,
        errorMessage: item.error?.message,
      })
    }
  } else if (job.dest?.fileName) {
    // 結果ファイル（JSONL。1 行 1 レスポンス）。大きいバッチ用で、実際の呼び出しでは未検証。
    const downloadPath = path.join(tmpdir(), `seitei-batch-${Date.now()}.jsonl`)
    await ai.files.download({ file: job.dest.fileName, downloadPath })
    for (const line of readFileSync(downloadPath, 'utf8').split('\n').filter(Boolean)) {
      const row = JSON.parse(line) as { key?: string; response?: GenerateContentResponse; error?: { message?: string } }
      results.push({ key: row.key ?? '(key なし)', response: row.response, errorMessage: row.error?.message })
    }
  } else {
    throw new Error('結果が見つかりません（inlinedResponses も fileName もありません）')
  }

  mkdirSync(OUTPUT_DIR, { recursive: true })
  const failures: string[] = []

  for (const result of results) {
    const spec = IMAGES.find((img) => img.id === result.key)
    if (!spec) {
      failures.push(`${result.key}: prompts.ts に対応する id がありません`)
      continue
    }
    if (result.errorMessage || !result.response) {
      failures.push(`${result.key}: ${result.errorMessage ?? 'レスポンスがありません'}`)
      continue
    }
    const part = result.response.candidates?.[0]?.content?.parts?.find((p) => p.inlineData?.data)
    const data = part?.inlineData?.data
    if (!data) {
      failures.push(`${result.key}: ${whyNoImage(result.response)}`)
      continue
    }
    const ext = extensionFor(part?.inlineData?.mimeType)
    if (!ext) {
      failures.push(`${result.key}: 想定外の形式 ${part?.inlineData?.mimeType ?? '(不明)'}`)
      continue
    }
    const fileName = spec.outputFileName.replace(/\.[^.]+$/, '') + ext
    const bytes = Buffer.from(data, 'base64')
    mkdirSync(path.dirname(path.join(OUTPUT_DIR, fileName)), { recursive: true })
    writeFileSync(path.join(OUTPUT_DIR, fileName), bytes)
    const size = imageDimensions(bytes) ?? '不明'
    const usage = result.response.usageMetadata
    console.log(
      `保存: ${fileName} ${bytes.length} bytes 寸法=${size}` +
        (usage ? ` tokens(prompt=${usage.promptTokenCount ?? '-'} output=${usage.candidatesTokenCount ?? '-'} total=${usage.totalTokenCount ?? '-'})` : ''),
    )
  }

  console.log(`保存先: ${OUTPUT_DIR}`)
  if (failures.length > 0) {
    console.error('取得できなかった key:')
    for (const line of failures) console.error(`  - ${line}`)
    process.exit(1)
  }
} catch (error) {
  fail(error)
}
