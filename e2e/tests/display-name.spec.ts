import { expect, test } from '@playwright/test';
import pg from 'pg';
import { E2E_USER, assertE2eDatabase, requiredEnv, signIn, signInWithWrongSignature } from '../support/session';

const BEFORE = 'E2E 太郎';
const AFTER = 'E2E 花子';

async function storedDisplayName(): Promise<string | null | undefined> {
  const connectionString = requiredEnv('E2E_DATABASE_URL');
  assertE2eDatabase(connectionString);
  const client = new pg.Client({ connectionString });
  await client.connect();
  try {
    const result = await client.query<{ display_name: string | null }>('SELECT display_name FROM users WHERE auth_user_id = $1', [E2E_USER.id]);
    return result.rows[0]?.display_name;
  } finally {
    await client.end();
  }
}

test('Google ログイン後、アカウントメニューから表示名を変更して保存できる（画面と API の DB に反映される）', async ({ page }) => {
  await signIn(page);

  // (1) ログイン済みの画面
  await page.goto('/');
  const accountButton = page.getByRole('button', { name: `${BEFORE}のアカウントメニュー` });
  await expect(accountButton).toBeVisible();

  // (2) メニューを開く。ハイドレーションの前の押下は素通りしうるので、開くまで押し直す（固定の待ちは使わない）
  const menu = page.getByRole('menu', { name: 'アカウント' });
  await expect(async () => {
    if ((await accountButton.getAttribute('aria-expanded')) !== 'true') await accountButton.click();
    await expect(menu).toBeVisible({ timeout: 1_000 });
  }).toPass();
  await expect(menu.getByText(E2E_USER.email)).toBeVisible();
  await menu.getByRole('menuitem', { name: '表示名を変更' }).click();

  // (3) ダイアログ。入力欄にフォーカスが移った時点で、画面は操作できる状態
  const dialog = page.getByRole('dialog', { name: '表示名を変更' });
  await expect(dialog).toBeVisible();
  const nameInput = dialog.getByRole('textbox', { name: '表示名', exact: true });
  await expect(nameInput).toBeFocused();
  await expect(nameInput).toHaveValue(BEFORE);
  await nameInput.fill(AFTER);

  // (4) 保存 → ダイアログが閉じる
  await dialog.getByRole('button', { name: '保存' }).click();
  await expect(dialog).toBeHidden();

  // (5) 画面の反映（再読み込みしても同じ）
  await expect(page.getByRole('button', { name: `${AFTER}のアカウントメニュー` })).toBeVisible();
  await expect(page.getByRole('button', { name: `${BEFORE}のアカウントメニュー` })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('button', { name: `${AFTER}のアカウントメニュー` })).toBeVisible();

  // (6) API 側（DB）
  expect(await storedDisplayName()).toBe(AFTER);
});

// 対照: 署名が実際に検査されていること（DB には有効なセッションがあるのに、署名が違う Cookie ではログインにならない）。偽の成功を防ぐ
test('対照: 別の秘密で署名した Cookie では、ログインしていない表示になる', async ({ page }) => {
  await signInWithWrongSignature(page);

  await page.goto('/');
  const menuButton = page.getByRole('button', { name: 'メニュー', exact: true });
  await expect(menuButton).toBeVisible();
  await expect(page.getByRole('button', { name: /のアカウントメニュー$/ })).toHaveCount(0);

  await expect(async () => {
    if ((await menuButton.getAttribute('aria-expanded')) !== 'true') await menuButton.click();
    await expect(page.getByRole('menu', { name: 'メニュー' })).toBeVisible({ timeout: 1_000 });
  }).toPass();
  await expect(page.getByRole('menuitem', { name: 'Google でログイン' })).toBeVisible();

  // API 側にも、プロフィール（users）の行が作られていない（JWT が一度も発行されていない）
  expect(await storedDisplayName()).toBeUndefined();
});
