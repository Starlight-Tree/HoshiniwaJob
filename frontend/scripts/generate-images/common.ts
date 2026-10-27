import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { GoogleGenAI, JobState } from '@google/genai'

export const MODEL = 'gemini-nano-banana-2.1'

const here = path.dirname(fileURLToPath(import.meta.url))
export const JOB_FILE = path.join(here, '.last-batch-job.txt')
export const OUTPUT_DIR = path.resolve(here, '../../public/images/generated')

export const TERMINAL_STATES: string[] = [
  JobState.JOB_STATE_SUCCEEDED,
  JobState.JOB_STATE_FAILED,
  JobState.JOB_STATE_CANCELLED,
  JobState.JOB_STATE_EXPIRED,
]

export function createClient(): GoogleGenAI {
  const apiKey = process.env.GEMINI_API_KEY
  if (!apiKey) {
    console.error('GEMINI_API_KEY が未設定です。scripts/generate-images/.env か環境変数で渡してください。')
    process.exit(1)
  }
  return new GoogleGenAI({ apiKey })
}

// モデルは PNG と JPEG のどちらでも返しうる。拡張子は返ってきた形式に合わせる。
export function extensionFor(mimeType: string | undefined): string | null {
  if (mimeType === 'image/png') return '.png'
  if (mimeType === 'image/jpeg') return '.jpg'
  return null
}

// 画像の寸法（幅x高さ）。PNG と JPEG のヘッダーだけを見る。
export function imageDimensions(buf: Buffer): string | null {
  if (buf.length >= 24 && buf.readUInt32BE(0) === 0x89504e47) {
    return `${buf.readUInt32BE(16)}x${buf.readUInt32BE(20)}`
  }
  if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8) {
    let i = 2
    while (i + 9 < buf.length) {
      if (buf[i] !== 0xff) return null
      const marker = buf[i + 1] ?? 0
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return `${buf.readUInt16BE(i + 7)}x${buf.readUInt16BE(i + 5)}`
      }
      i += 2 + buf.readUInt16BE(i + 2)
    }
  }
  return null
}

// 例外の文面にキーが混ざっても出さない。
export function describeError(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  const key = process.env.GEMINI_API_KEY
  return key ? text.split(key).join('[redacted]') : text
}

export function fail(error: unknown): never {
  console.error(`失敗しました: ${describeError(error)}`)
  process.exit(1)
}
