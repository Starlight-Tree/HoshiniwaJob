import { ApiError } from './api';

// API の応答は、ここで固定の文に直す（API の本文や例外の文字列は画面に出さない）
export function messageFor(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return 'メールアドレスまたはパスワードが違います';
    if (e.status === 409) return 'このメールアドレスは登録できません';
    if (e.status === 422) return '入力内容を確認してください';
  }
  return 'ただいま利用できません。しばらくしてから、もう一度お試しください';
}
