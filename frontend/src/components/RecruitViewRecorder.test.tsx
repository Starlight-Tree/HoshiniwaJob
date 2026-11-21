import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RecruitViewRecorder } from './RecruitViewRecorder';

const token = vi.hoisted(() => ({ value: null as string | null }));
vi.mock('../lib/session', () => ({ userToken: async () => token.value }));
const action = vi.hoisted(() => ({ recordViewAction: vi.fn() }));
vi.mock('../actions/recruit-events', () => action);

beforeEach(() => {
  token.value = null;
  action.recordViewAction.mockReset();
  action.recordViewAction.mockResolvedValue(undefined);
});

describe('RecruitViewRecorder（ログイン中の求職者のときだけ、記録を送る）', () => {
  it('ログイン中（JWT が取れる）は、マウントのあとに、その求人の閲覧を 1 回記録する。何も描かない', async () => {
    token.value = 'jwt-123';
    const { container } = render(await RecruitViewRecorder({ recruitId: 7 }));
    expect(action.recordViewAction).toHaveBeenCalledOnce();
    expect(action.recordViewAction).toHaveBeenCalledWith(7);
    expect(container).toBeEmptyDOMElement();
  });

  it('未ログイン（JWT が取れない）は、何も出さず、記録を呼ばない（401 を出さない）', async () => {
    const ui = await RecruitViewRecorder({ recruitId: 7 });
    expect(ui).toBeNull();
    const { container } = render(ui);
    expect(container).toBeEmptyDOMElement();
    expect(action.recordViewAction).not.toHaveBeenCalled();
  });

  it('描画しただけでは（サーバーの描画・プリフェッチの段階では）、記録を呼ばない。呼ぶのは、クライアントで、マウントしたあと', async () => {
    token.value = 'jwt-123';
    const ui = await RecruitViewRecorder({ recruitId: 7 });
    expect(action.recordViewAction).not.toHaveBeenCalled();
    render(ui);
    expect(action.recordViewAction).toHaveBeenCalledOnce();
  });
});
