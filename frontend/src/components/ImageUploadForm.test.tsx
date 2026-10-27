import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ImageFormState } from '../actions/garden-images';
import { checkImageFile, ImageUploadForm } from './ImageUploadForm';

vi.mock('../actions/garden-images', () => ({ uploadImageAction: vi.fn() }));

const picture = (name = 'a.jpg', type = 'image/jpeg', bytes = 1200) => new File([new Uint8Array(bytes)], name, { type });
const input = () => screen.getByLabelText('画像のファイル', { selector: 'input' }) as HTMLInputElement;
const dropZone = () => screen.getByText('ここに画像をドラッグ＆ドロップ').closest('.image-drop') as HTMLElement;

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
});

describe('checkImageFile', () => {
  it('JPEG・PNG・WebP の 5MB 以下だけを通す', () => {
    expect(checkImageFile({ type: 'image/png', size: 1 })).toBeNull();
    expect(checkImageFile({ type: 'image/gif', size: 1 })).toContain('JPEG・PNG・WebP');
    expect(checkImageFile({ type: 'image/jpeg', size: 5 * 1024 * 1024 + 1 })).toContain('5MB');
  });
});

describe('ImageUploadForm', () => {
  it('最初は、ドロップ領域だけが出る（プレビューも「公開する」も無い）', () => {
    render(<ImageUploadForm recruitId={1} action={vi.fn()} />);
    expect(dropZone()).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '公開する' })).toBeNull();
  });

  it('ファイルを選ぶと、保存前のプレビューと「公開する」が出る。API にはまだ送らない', async () => {
    const action = vi.fn(async (): Promise<ImageFormState> => ({}));
    render(<ImageUploadForm recruitId={1} action={action} />);
    await userEvent.upload(input(), picture('greenhouse.jpg'));
    expect(screen.getByAltText('保存前のプレビュー')).toHaveAttribute('src', 'blob:preview');
    expect(screen.getByText(/greenhouse\.jpg/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '公開する' })).toBeEnabled();
    expect(action).not.toHaveBeenCalled();
  });

  it('ドロップしたファイルも同じ流れで、プレビューになる', async () => {
    render(<ImageUploadForm recruitId={1} action={vi.fn()} />);
    const file = picture('dropped.webp', 'image/webp');
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.dragOver(dropZone());
    expect(dropZone()).toHaveClass('dragging');
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file] } });
    expect(dropZone()).not.toHaveClass('dragging');
    expect(await screen.findByAltText('保存前のプレビュー')).toBeInTheDocument();
  });

  it('形式や容量が合わないファイルは、プレビューにせず、理由を出す', async () => {
    render(<ImageUploadForm recruitId={1} action={vi.fn()} />);
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.drop(dropZone(), { dataTransfer: { files: [picture('a.gif', 'image/gif')] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('JPEG・PNG・WebP');
    expect(screen.queryByAltText('保存前のプレビュー')).toBeNull();
  });

  it('「公開する」で、選んだファイルと代替テキストと求人 ID を送り、成功したら入力を空に戻す', async () => {
    const seen: { file?: File; alt?: string; recruit?: string } = {};
    const action = vi.fn(async (_prev: ImageFormState, data: FormData): Promise<ImageFormState> => {
      seen.file = data.get('file') as File;
      seen.alt = String(data.get('alt'));
      seen.recruit = String(data.get('recruit_id'));
      return { ok: '画像を公開しました。' };
    });
    render(<ImageUploadForm recruitId={7} action={action} />);
    const file = picture('x.jpg');
    await userEvent.upload(input(), file);
    await userEvent.type(screen.getByLabelText(/代替テキスト/), '温室の朝');
    await userEvent.click(screen.getByRole('button', { name: '公開する' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('画像を公開しました。'));
    expect(seen).toMatchObject({ alt: '温室の朝', recruit: '7' });
    expect(seen.file?.name).toBe('x.jpg');
    expect(screen.queryByAltText('保存前のプレビュー')).toBeNull(); // 次の画像を追加できる状態に戻る
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview');
  });

  it('失敗したら、プレビューと入力を残して理由を出し、そのまま押し直せる（送るファイルは毎回入れ直す）', async () => {
    const files: (File | undefined)[] = [];
    const action = vi.fn(async (_prev: ImageFormState, data: FormData): Promise<ImageFormState> => {
      files.push(data.get('file') as File);
      return files.length === 1 ? { error: 'ただいま利用できません。しばらくしてから、もう一度お試しください' } : { ok: '画像を公開しました。' };
    });
    render(<ImageUploadForm recruitId={1} action={action} />);
    await userEvent.upload(input(), picture('retry.jpg'));
    await userEvent.type(screen.getByLabelText(/代替テキスト/), '説明');
    await userEvent.click(screen.getByRole('button', { name: '公開する' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('ただいま利用できません');
    expect(screen.getByLabelText(/代替テキスト/)).toHaveValue('説明');
    await userEvent.click(screen.getByRole('button', { name: '公開する' }));
    await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument());
    expect(files.map((f) => f?.name)).toEqual(['retry.jpg', 'retry.jpg']);
  });

  it('「やめる」で、プレビューを消して、何も送らない', async () => {
    const action = vi.fn();
    render(<ImageUploadForm recruitId={1} action={action} />);
    await userEvent.upload(input(), picture());
    await userEvent.click(screen.getByRole('button', { name: 'やめる' }));
    expect(screen.queryByAltText('保存前のプレビュー')).toBeNull();
    expect(action).not.toHaveBeenCalled();
  });

  it('送信中は、ボタンを押せず、文言が変わる（二重送信を防ぐ）', async () => {
    let release: () => void = () => {};
    const action = vi.fn(() => new Promise<ImageFormState>((resolve) => (release = () => resolve({ ok: 'ok' }))));
    render(<ImageUploadForm recruitId={1} action={action} />);
    await userEvent.upload(input(), picture());
    await userEvent.type(screen.getByLabelText(/代替テキスト/), 'x');
    await userEvent.click(screen.getByRole('button', { name: '公開する' }));
    expect(await screen.findByRole('button', { name: '公開しています…' })).toBeDisabled();
    release();
    await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument());
  });
});
