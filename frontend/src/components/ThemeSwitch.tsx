'use client';

import { useEffect, useState } from 'react';
import { chooseTheme, clearTheme, themeChoice } from '../lib/theme';
import type { Theme } from '../lib/theme';
import { THEME_OPTIONS } from './themeOptions';

/**
 * テーマの切り替え（ライト / ダーク / システム）。ログイン・会員登録の上の帯で使う（ほかの画面は、アカウントのメニューの中）。選ぶと localStorage に保存し、以後は OS より優先する。「システム」で OS に従う状態へ戻す。
 * 保存値は、描画のあとに読む（サーバーの出力と同じ「システム」で始め、ハイドレーションのずれを避ける）。
 */
export function ThemeSwitch() {
  const [choice, setChoice] = useState<Theme | 'system'>('system');

  useEffect(() => {
    setChoice(themeChoice());
  }, []);

  return (
    <div role="group" aria-label="テーマ" className="theme-switch">
      <span className="theme-switch-label" aria-hidden="true">
        テーマ
      </span>
      <span className="theme-switch-options">
        {THEME_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className="theme-switch-option"
            aria-pressed={choice === option.value}
            aria-label={option.label}
            title={option.label}
            onClick={() => {
              if (option.value === 'system') clearTheme();
              else chooseTheme(option.value);
              setChoice(option.value);
            }}
          >
            {option.icon}
          </button>
        ))}
      </span>
    </div>
  );
}
