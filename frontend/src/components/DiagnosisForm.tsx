import { QUESTION_LABEL, type Answers } from '../lib/diagnosis';
import type { Code, Master } from '../lib/types';

type Props = { master: Master; answers: Answers };

/** 選択肢の 1 つ（丸いボタン）。実際の入力はラジオボタンで、見た目だけを CSS で変える（キーボードと読み上げは、ふつうのラジオボタンのまま）。 */
function Choice({ name, value, label, checked }: { name: string; value: string; label: string; checked: boolean }) {
  return (
    <label className="quiz-option">
      <input type="radio" name={name} value={value} defaultChecked={checked} />
      <span>{label}</span>
    </label>
  );
}

function RadioQuestion({ kind, step, items, answer }: { kind: 'employment' | 'area'; step: number; items: Code[]; answer: number | null }) {
  return (
    <fieldset className="quiz-question">
      <legend>
        <span className="quiz-step">質問 {step}</span> {QUESTION_LABEL[kind]}は？
      </legend>
      <div className="quiz-options">
        <Choice name={kind} value="" label="こだわらない" checked={answer === null} />
        {items.map((c) => (
          <Choice key={c.code} name={kind} value={String(c.code)} label={c.name} checked={answer === c.code} />
        ))}
      </div>
    </fieldset>
  );
}

/**
 * 3 つの質問のフォーム。送ると GET で /diagnosis に戻り、答えがクエリに入る（JavaScript が無くても動く。結果は URL で共有できる）。
 * 職種は選択肢が多いので、区分ごとに分けた選択ボックスにする。
 */
export function DiagnosisForm({ master, answers }: Props) {
  return (
    <form className="quiz" method="get" action="/diagnosis#result">
      <RadioQuestion kind="employment" step={1} items={master.employments} answer={answers.employment} />
      <RadioQuestion kind="area" step={2} items={master.areas} answer={answers.area} />
      <fieldset className="quiz-question">
        <legend>
          <span className="quiz-step">質問 3</span> {QUESTION_LABEL.occupation}は？
        </legend>
        <select className="quiz-select" name="occupation" defaultValue={answers.occupation === null ? '' : String(answers.occupation)} aria-label="職種">
          <option value="">こだわらない</option>
          {master.occupations.map((group) => (
            <optgroup key={group.category} label={group.category}>
              {group.items.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </fieldset>
      <button type="submit" className="primary-button inline">
        診断する
      </button>
    </form>
  );
}
