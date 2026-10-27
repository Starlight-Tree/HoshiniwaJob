'use client';

import { useActionState, useEffect, useRef, useState } from 'react';
import { type ImageFormState, uploadImageAction } from '../actions/garden-images';

const ALLOWED = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES = 5 * 1024 * 1024; // API の既定の上限と同じ（本当の検査は API）

type UploadAction = (prev: ImageFormState, data: FormData) => Promise<ImageFormState>;

/** 選んだファイルを、保存前に手元で確かめる（形式と容量だけ。寸法や実データの検査は API）。問題がなければ null。 */
export function checkImageFile(file: Pick<File, 'type' | 'size'>): string | null {
  if (!ALLOWED.includes(file.type)) return 'JPEG・PNG・WebP の画像だけ登録できます';
  if (file.size > MAX_BYTES) return '画像は 5MB 以下にしてください';
  return null;
}

const sizeLabel = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)}MB` : `${Math.max(1, Math.round(bytes / 1024))}KB`);

export function ImageUploadForm({ recruitId, action: upload = uploadImageAction }: { recruitId: number; action?: UploadAction }) {
  const picker = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [alt, setAlt] = useState('');
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  // 保存前のプレビューは、手元のファイルから作る（API には送らない）。差し替え・取りやめ・画面を離れるときに解放する
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  const reset = () => {
    setFile(null);
    setPreviewUrl(null);
    setAlt('');
    if (picker.current) picker.current.value = '';
  };

  const accept = (picked: File | undefined) => {
    if (!picked) return;
    const found = checkImageFile(picked);
    setProblem(found);
    if (found) {
      reset();
      return;
    }
    setFile(picked);
    setPreviewUrl(URL.createObjectURL(picked));
  };

  // 送るファイルは、選んだ（またはドロップした）ものを、ここで入れる。フォームの自動リセットで入力欄が空になっても、失敗後にやり直せる
  const [state, submit, pending] = useActionState(async (prev: ImageFormState, data: FormData) => {
    if (file) data.set('file', file);
    const next = await upload(prev, data);
    if (next.ok) reset();
    return next;
  }, {});

  return (
    <div className="image-upload">
      <div
        className={`image-drop${dragging ? ' dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files[0]);
        }}
      >
        <p className="image-drop-title">ここに画像をドラッグ＆ドロップ</p>
        <p className="image-drop-help">JPEG・PNG・WebP、5MB まで、短辺 200px 以上（1 回に 1 枚）</p>
        <button type="button" className="small-button" onClick={() => picker.current?.click()}>
          ファイルを選ぶ
        </button>
        <input ref={picker} type="file" accept={ALLOWED.join(',')} hidden aria-label="画像のファイル" onChange={(e) => accept(e.target.files?.[0])} />
      </div>

      {problem ? (
        <p className="notice" role="alert">
          {problem}
        </p>
      ) : null}
      {state.ok && !file ? (
        <p className="image-ok" role="status">
          {state.ok}
        </p>
      ) : null}

      {file && previewUrl ? (
        <form action={submit} className="image-preview-card">
          <input type="hidden" name="recruit_id" value={recruitId} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt="保存前のプレビュー" className="image-preview" />
          <div className="image-preview-side">
            <p className="image-drop-help">
              {file.name}・{sizeLabel(file.size)}
            </p>
            <label className="field">
              <span>代替テキスト（画像が見えない人に読み上げる説明。必須・300 文字まで）</span>
              <input type="text" name="alt" value={alt} onChange={(e) => setAlt(e.target.value)} maxLength={300} required />
            </label>
            {state.error ? (
              <p className="notice" role="alert">
                {state.error}
              </p>
            ) : null}
            <div className="image-preview-actions">
              <button type="submit" className="primary-button inline" disabled={pending}>
                {pending ? '公開しています…' : '公開する'}
              </button>
              <button
                type="button"
                className="small-button"
                disabled={pending}
                onClick={() => {
                  setProblem(null);
                  reset();
                }}
              >
                やめる
              </button>
            </div>
            <p className="image-drop-help">「公開する」を押すと、すぐに求人ページへ表示されます。</p>
          </div>
        </form>
      ) : null}
    </div>
  );
}
