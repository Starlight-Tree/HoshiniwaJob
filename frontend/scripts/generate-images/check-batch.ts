import { existsSync, readFileSync } from 'node:fs'
import { createClient, describeError, fail, JOB_FILE, TERMINAL_STATES } from './common.ts'

const POLL_MS = 30_000

if (!existsSync(JOB_FILE)) {
  console.error('.last-batch-job.txt がありません。先に images:create-batch を実行してください。')
  process.exit(1)
}
const name = readFileSync(JOB_FILE, 'utf8').trim()
const once = process.argv.includes('--once')
const ai = createClient()

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

try {
  console.log(`job: ${name}${once ? '（1 回だけ確認）' : '（30 秒ごとに確認）'}`)
  for (;;) {
    let state: string | undefined
    try {
      const job = await ai.batches.get({ name })
      state = job.state
      console.log(`${new Date().toISOString()} ${state ?? '(不明)'}`)
      if (state && TERMINAL_STATES.includes(state)) {
        if (state !== 'JOB_STATE_SUCCEEDED') {
          console.error(`終了: ${state}`)
          if (job.error) console.error(`エラー: code=${job.error.code ?? '-'} message=${job.error.message ?? '-'}`)
          process.exit(1)
        }
        console.log('完了しました。次: npm run images:download-results')
        process.exit(0)
      }
    } catch (error) {
      // 一時的な取得失敗では止めない（ポーリング中のみ）
      if (once) throw error
      console.error(`状態の取得に失敗（再試行します）: ${describeError(error)}`)
    }
    if (once) process.exit(0)
    await sleep(POLL_MS)
  }
} catch (error) {
  fail(error)
}
