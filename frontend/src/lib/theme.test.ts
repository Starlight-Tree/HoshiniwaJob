import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { THEME_INIT_SCRIPT, THEME_KEY, chooseTheme, clearTheme, currentTheme, storedTheme, systemTheme, themeChoice } from './theme';

function stubSystem(dark: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: dark && query === '(prefers-color-scheme: dark)', media: query }));
}

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});
afterEach(() => vi.unstubAllGlobals());

describe('テーマ', () => {
  it('選んでいなければ OS に従う（保存も data-theme も無い）', () => {
    stubSystem(true);
    expect(storedTheme()).toBeNull();
    expect(themeChoice()).toBe('system');
    expect(systemTheme()).toBe('dark');
    expect(currentTheme()).toBe('dark');
    stubSystem(false);
    expect(currentTheme()).toBe('light');
  });

  it('選ぶと、適用して保存し、OS より優先する', () => {
    stubSystem(true);
    chooseTheme('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(window.localStorage.getItem(THEME_KEY)).toBe('light');
    expect(storedTheme()).toBe('light');
    expect(themeChoice()).toBe('light');
    expect(currentTheme()).toBe('light');
  });

  it('選択を取り消すと、保存と data-theme を消して OS に従う', () => {
    stubSystem(true);
    chooseTheme('light');
    clearTheme();
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(window.localStorage.getItem(THEME_KEY)).toBeNull();
    expect(currentTheme()).toBe('dark');
  });

  it('保存が無くても、適用中の data-theme があれば、それを選択として返す（保存できない環境）', () => {
    document.documentElement.dataset.theme = 'dark';
    expect(storedTheme()).toBeNull();
    expect(themeChoice()).toBe('dark');
    document.documentElement.dataset.theme = 'blue';
    expect(themeChoice()).toBe('system');
  });

  it('保存値が壊れていれば、無いものとして扱う', () => {
    window.localStorage.setItem(THEME_KEY, 'blue');
    expect(storedTheme()).toBeNull();
  });

  it('localStorage が使えなくても、例外にせず、このページでは適用する', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(storedTheme()).toBeNull();
    expect(() => chooseTheme('dark')).not.toThrow();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(() => clearTheme()).not.toThrow();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it('描画前のスクリプトは、保存値（light / dark）だけを data-theme へ入れる', () => {
    window.localStorage.setItem(THEME_KEY, 'dark');
    new Function(THEME_INIT_SCRIPT)();
    expect(document.documentElement.dataset.theme).toBe('dark');

    delete document.documentElement.dataset.theme;
    window.localStorage.setItem(THEME_KEY, '<script>');
    new Function(THEME_INIT_SCRIPT)();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});

describe('globals.css のダークの値（2 か所と、直書きの色）', () => {
  const css = readFileSync(join(process.cwd(), 'app', 'globals.css'), 'utf8');
  const declarations = (block: string) =>
    [...block.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map(([, name, value]) => `${name}: ${value?.trim()}`).sort();

  // CSS では 2 つの条件で共有できないので、同じ内容を 2 か所に書いている。ずれたらここで気づく。
  it('OS 追従と data-theme の 2 か所に、同じ宣言が入っている', () => {
    const media = /@media \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme='light'\]\) \{([^}]*)\}/.exec(css)?.[1];
    const manual = /:root\[data-theme='dark'\] \{([^}]*)\}/.exec(css)?.[1];
    expect(media).toBeDefined();
    expect(manual).toBeDefined();
    expect(declarations(manual ?? '')).toEqual(declarations(media ?? ''));
  });

  it('ダークは、ライトと同じ変数をすべて定義している（定義漏れで、ライトの色が残らない）', () => {
    const light = /^:root \{([^}]*)\}/m.exec(css)?.[1] ?? '';
    const manual = /:root\[data-theme='dark'\] \{([^}]*)\}/.exec(css)?.[1] ?? '';
    const names = (block: string) => declarations(block).map((d) => d.split(':')[0]);
    const colorNames = names(light).filter((n) => n !== '--radius' && n !== '--font');
    expect(colorNames.length).toBeGreaterThan(10);
    expect(names(manual).sort()).toEqual(colorNames.sort());
  });

  it('色の直書き（#xxxxxx・rgba）は、変数の定義だけに置く（本体は var(--…) を使う）', () => {
    const body = css.slice(css.indexOf(":root[data-theme='dark'] { color-scheme: dark; }"));
    expect(body.length).toBeGreaterThan(1000);
    expect(body.match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g)).toBeNull();
  });
});

describe('app/layout.tsx', () => {
  it('描画前のスクリプトを <head> に置き、data-theme の差を警告しない', () => {
    const layout = readFileSync(join(process.cwd(), 'app', 'layout.tsx'), 'utf8');
    expect(layout).toContain("import { THEME_INIT_SCRIPT } from '../src/lib/theme';");
    expect(layout).toMatch(/<head>\s*<script>\{THEME_INIT_SCRIPT\}<\/script>\s*<\/head>/);
    expect(layout).toContain('suppressHydrationWarning');
  });
});
