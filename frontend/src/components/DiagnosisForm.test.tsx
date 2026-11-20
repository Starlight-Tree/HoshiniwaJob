import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Master } from '../lib/types';
import { DiagnosisForm } from './DiagnosisForm';

const MASTER: Master = {
  employments: [
    { code: 1, name: '常勤' },
    { code: 2, name: '短時間勤務' },
  ],
  areas: [{ code: 10, name: '第一環' }],
  stations: [],
  occupations: [{ category: '栽培', items: [{ code: 100, name: '蔓の育成' }] }],
};

describe('DiagnosisForm', () => {
  it('GET で /diagnosis に送り、質問は 3 つ（それぞれ名前つきのグループ）', () => {
    const { container } = render(<DiagnosisForm master={MASTER} answers={{ employment: null, area: null, occupation: null }} />);
    const form = container.querySelector('form')!;
    expect(form.getAttribute('method')).toBe('get');
    expect(form.getAttribute('action')).toBe('/diagnosis#result');
    expect(container.querySelectorAll('fieldset')).toHaveLength(3);
  });

  it('答えがないときは「こだわらない」が選ばれている', () => {
    const { container } = render(<DiagnosisForm master={MASTER} answers={{ employment: null, area: null, occupation: null }} />);
    const fieldsets = Array.from(container.querySelectorAll('fieldset'));
    for (const fieldset of fieldsets.slice(0, 2)) {
      expect(within(fieldset).getByRole('radio', { name: 'こだわらない' })).toBeChecked();
    }
    expect(screen.getByRole('combobox', { name: '職種' })).toHaveValue('');
  });

  it('前の答えを選んだ状態で出す（質問を変えて、やり直せる）', () => {
    render(<DiagnosisForm master={MASTER} answers={{ employment: 2, area: 10, occupation: 100 }} />);
    expect(screen.getByRole('radio', { name: '短時間勤務' })).toBeChecked();
    expect(screen.getByRole('radio', { name: '常勤' })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: '第一環' })).toBeChecked();
    expect(screen.getByRole('combobox', { name: '職種' })).toHaveValue('100');
  });

  it('職種は区分ごとの選択ボックス。送信ボタンがある', () => {
    const { container } = render(<DiagnosisForm master={MASTER} answers={{ employment: null, area: null, occupation: null }} />);
    expect(container.querySelector('optgroup')?.getAttribute('label')).toBe('栽培');
    expect(screen.getByRole('button', { name: '診断する' })).toBeInTheDocument();
  });
});
