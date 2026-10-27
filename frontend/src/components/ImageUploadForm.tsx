'use client';

import { useActionState } from 'react';
import { type ImageFormState, uploadImageAction } from '../actions/garden-images';

const initial: ImageFormState = {};

export function ImageUploadForm({ recruitId }: { recruitId: number }) {
  const [state, action, pending] = useActionState(uploadImageAction, initial);
  return (
    <form action={action} className="image-upload">
      <input type="hidden" name="recruit_id" value={recruitId} />
      <label className="field">
        <span>画像（JPEG・PNG・WebP、5MB まで）</span>
        <input type="file" name="file" accept="image/jpeg,image/png,image/webp" required />
      </label>
      <label className="field">
        <span>代替テキスト（画像が見えない人に読み上げる説明。300 文字まで）</span>
        <input type="text" name="alt" maxLength={300} required />
      </label>
      {state.error ? (
        <p className="notice" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.ok ? (
        <p className="image-ok" role="status">
          {state.ok}
        </p>
      ) : null}
      <button type="submit" className="primary-button inline" disabled={pending}>
        {pending ? '登録しています…' : '画像を登録する'}
      </button>
    </form>
  );
}
