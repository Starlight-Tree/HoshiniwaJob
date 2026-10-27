import { writeFileSync } from 'node:fs'
import type { InlinedRequest } from '@google/genai'
import { createClient, fail, JOB_FILE, MODEL } from './common.ts'
import { IMAGES } from './prompts.ts'

const USAGE = `使い方:
  npm run images:create-batch -- --only top-hero     # 1 枚だけ（最初の検証）
  npm run images:create-batch -- --all               # prompts.ts の全件
  npm run images:create-batch -- --all --dry-run     # API を呼ばずに送る内容だけ表示`

function jstStamp(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date())
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return `${get('year')}${get('month')}${get('day')}-${get('hour')}${get('minute')}`
}

const args = process.argv.slice(2)
const dryRun = args.includes('--dry-run')
const onlyIndex = args.indexOf('--only')
const onlyIds = onlyIndex >= 0 ? (args[onlyIndex + 1] ?? '').split(',').filter(Boolean) : []

if (!args.includes('--all') && onlyIds.length === 0) {
  console.error(USAGE)
  process.exit(1)
}

const unknown = onlyIds.filter((id) => !IMAGES.some((img) => img.id === id))
if (unknown.length > 0) {
  console.error(`prompts.ts に無い id: ${unknown.join(', ')}`)
  process.exit(1)
}
const selected = onlyIds.length > 0 ? IMAGES.filter((img) => onlyIds.includes(img.id)) : IMAGES

const requests: InlinedRequest[] = selected.map((img) => ({
  contents: [{ role: 'user', parts: [{ text: img.prompt }] }],
  metadata: { key: img.id },
  config: {
    responseModalities: ['TEXT', 'IMAGE'],
    imageConfig: { aspectRatio: img.aspectRatio, imageSize: img.imageSize },
  },
}))

const displayName = `seitei-job-image-batch-${jstStamp()}`

if (dryRun) {
  console.log(`[dry-run] model=${MODEL} displayName=${displayName} 枚数=${requests.length}`)
  console.log(JSON.stringify(requests, null, 2))
  process.exit(0)
}

try {
  const ai = createClient()
  const job = await ai.batches.create({ model: MODEL, src: requests, config: { displayName } })
  if (!job.name) throw new Error('job name が返りませんでした')
  writeFileSync(JOB_FILE, `${job.name}\n`)
  console.log(`バッチを作成しました: ${job.name}`)
  console.log(`状態: ${job.state ?? '(不明)'} / 枚数: ${requests.length} / 表示名: ${displayName}`)
  console.log('次: npm run images:check-batch')
} catch (error) {
  fail(error)
}
