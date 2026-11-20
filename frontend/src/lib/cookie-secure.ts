// 園のセッション Cookie に Secure を付けるかを決める。
// 以前は SESSION_COOKIE_SECURE=true を渡したときだけ付けていたので、付け忘れると、本番でも http 用の Cookie になった。
// 本番（NODE_ENV=production）では既定で付け、外せるのは SESSION_COOKIE_SECURE=false と明示したときだけにする。
export type CookieSecureEnv = { SESSION_COOKIE_SECURE?: string; NODE_ENV?: string };

export function sessionCookieSecure(env: CookieSecureEnv = process.env): boolean {
  // 前後の空白と大小文字の違い（True・" true "）で、意図に反して既定へ落ちないようにする
  const flag = env.SESSION_COOKIE_SECURE?.trim().toLowerCase();
  if (flag === 'true') return true;
  if (flag === 'false') return false;
  // 未設定や、true・false 以外（1・yes・空文字など）は、明示とみなさず既定に従う。
  // 「1」を false 扱いにすると、本番で Secure が外れる事故になる
  return env.NODE_ENV === 'production';
}
