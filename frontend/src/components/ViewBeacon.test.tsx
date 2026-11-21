import { render } from '@testing-library/react';
import { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ViewBeacon } from './ViewBeacon';

const action = vi.hoisted(() => ({ recordViewAction: vi.fn() }));
vi.mock('../actions/recruit-events', () => action);

beforeEach(() => {
  action.recordViewAction.mockReset();
  action.recordViewAction.mockResolvedValue(undefined);
});

describe('ViewBeacon（閲覧の記録を、マウントのあとに 1 回送る）', () => {
  it('マウントしたあとに 1 回、その求人の ID で呼ぶ。何も描かない', () => {
    const { container } = render(<ViewBeacon recruitId={7} />);
    expect(action.recordViewAction).toHaveBeenCalledOnce();
    expect(action.recordViewAction).toHaveBeenCalledWith(7);
    expect(container).toBeEmptyDOMElement();
  });

  it('同じ求人で再描画しても、もう一度は呼ばない', () => {
    const { rerender } = render(<ViewBeacon recruitId={7} />);
    rerender(<ViewBeacon recruitId={7} />);
    rerender(<ViewBeacon recruitId={7} />);
    expect(action.recordViewAction).toHaveBeenCalledOnce();
  });

  it('開発の StrictMode（副作用を 2 回流す）でも、1 回だけ呼ぶ', () => {
    render(
      <StrictMode>
        <ViewBeacon recruitId={7} />
      </StrictMode>,
    );
    expect(action.recordViewAction).toHaveBeenCalledOnce();
  });

  it('パネルの中で別の求人へ移った（同じ部品の ID が変わった）ときは、その求人で、もう 1 回呼ぶ', () => {
    const { rerender } = render(<ViewBeacon recruitId={7} />);
    rerender(<ViewBeacon recruitId={8} />);
    rerender(<ViewBeacon recruitId={8} />);
    expect(action.recordViewAction.mock.calls).toEqual([[7], [8]]);
  });

  it('呼び出しが失敗しても（拒否・同期の例外）、画面は何も変わらず、エラーにならない（拒否が漏れると、vitest が未処理の拒否として、この実行を失敗にする）', async () => {
    action.recordViewAction.mockRejectedValueOnce(new Error('boom'));
    const first = render(<ViewBeacon recruitId={7} />);
    action.recordViewAction.mockImplementationOnce(() => {
      throw new Error('sync boom');
    });
    const second = render(<ViewBeacon recruitId={8} />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(action.recordViewAction).toHaveBeenCalledTimes(2);
    expect(first.container).toBeEmptyDOMElement();
    expect(second.container).toBeEmptyDOMElement();
  });
});
