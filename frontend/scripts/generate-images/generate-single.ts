import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { createClient, extensionFor, fail, imageDimensions, MODEL, OUTPUT_DIR } from './common.ts'
import { IMAGES } from './prompts.ts'

// Batch を使わず、Standard API（interactions.create）で 1 枚ずつ生成する。
const USAGE = `使い方:
  npm run images:generate-single -- --id job-detail-sample             # 1 枚だけ生成して保存（課金）
  npm run images:generate-single -- --id job-detail-sample --dry-run   # API を呼ばずに送る内容だけ表示`

const args = process.argv.slice(2)
const idIndex = args.indexOf('--id')
const id = idIndex >= 0 ? args[idIndex + 1] : undefined
const dryRun = args.includes('--dry-run')

if (!id) {
  console.error(USAGE)
  process.exit(1)
}
const spec = IMAGES.find((img) => img.id === id)
if (!spec) {
  console.error(`prompts.ts に無い id: ${id}`)
  process.exit(1)
}

const request = {
  model: MODEL,
  input: spec.prompt,
  response_modalities: ['image'],
  generation_config: {
    image_config: { aspect_ratio: spec.aspectRatio, image_size: spec.imageSize },
  },
  store: false,
}

if (dryRun) {
  console.log('[dry-run] interactions.create に送る内容:')
  console.log(JSON.stringify(request, null, 2))
  process.exit(0)
}

try {
  const ai = createClient()
  const interaction = await ai.interactions.create(request)
  const image = 'output_image' in interaction ? interaction.output_image : undefined
  if (!image?.data) {
    const text = 'output_text' in interaction ? interaction.output_text : undefined
    throw new Error(`画像が返りませんでした${text ? `（テキスト: ${text.slice(0, 200)}）` : ''}`)
  }
  // 課金済みの画像を捨てないよう、PNG / JPEG ならどちらも保存する（拡張子は返ってきた形式に合わせる）。
  const ext = extensionFor(image.mime_type)
  if (!ext) {
    throw new Error(`想定外の形式です: ${image.mime_type ?? '(不明)'}`)
  }
  const bytes = Buffer.from(image.data, 'base64')
  const target = path.join(OUTPUT_DIR, spec.outputFileName.replace(/\.[^.]+$/, '') + ext)
  mkdirSync(path.dirname(target), { recursive: true })
  writeFileSync(target, bytes)
  console.log(`保存: ${target}`)
  console.log(`形式: ${image.mime_type} / サイズ: ${bytes.length} bytes / 寸法 ${imageDimensions(bytes) ?? '不明'}`)
  const usage = 'usage' in interaction ? JSON.stringify(interaction.usage) : undefined
  if (usage) console.log(`usage: ${usage}`)
} catch (error) {
  fail(error)
}
