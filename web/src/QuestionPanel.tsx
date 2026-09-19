import { useCallback, useId, useState } from "react";
import styles from "./App.module.css";
import type { TimeRange } from "./data";
import { ClaimCard, PeriodNote } from "./PanelEvidence";
import type { EvidenceSelection } from "./RelationPanel";
import { PageNotice } from "./RelationPanel";
import {
  fetchPanelAnswer213,
  fetchPanelQuestions213,
  type PanelQuestion213,
} from "./read213";
import { useCursorPage } from "./useCursorPage";

type Props = {
  nodeId: string;
  range: TimeRange;
  onReport: (sectionId: string) => void;
  onEvidence: (selection: EvidenceSelection) => void;
  onLocate: (nodeId: string, relationId?: string) => void;
};
function Answer({
  questionId,
  nodeId,
  range,
  onReport,
  onEvidence,
  onLocate,
}: Props & { questionId: string }) {
  const page = useCursorPage(questionId, fetchPanelAnswer213);
  const answer = page.items[0];
  return (
    <div className={styles.questionAnswer}>
      <PageNotice {...page} empty={!answer} onRetry={page.retry} />
      {answer && (
        <>
          <p>{answer.answer}</p>
          {answer.caveat && (
            <p className={styles.panelCaveat}>{answer.caveat}</p>
          )}
          <PeriodNote range={range} asOf={answer.asOf} />
          {answer.claims.map((claim) => (
            <ClaimCard
              key={claim.id}
              nodeId={nodeId}
              claim={claim}
              range={range}
              onEvidence={onEvidence}
              onLocate={onLocate}
            />
          ))}
          {answer.sectionId && (
            <button
              type="button"
              onClick={() => onReport(answer.sectionId as string)}
            >
              관련 분석 읽기
            </button>
          )}
        </>
      )}
    </div>
  );
}
function Question({
  question,
  ...props
}: Props & { question: PanelQuestion213 }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <article className={styles.questionCard}>
      <button
        type="button"
        className={styles.panelDisclosure}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        <span>{question.text}</span>
        <span>{open ? "접기" : "답변 보기"}</span>
      </button>
      <div id={id} hidden={!open}>
        {open && <Answer {...props} questionId={question.id} />}
      </div>
    </article>
  );
}
function GeneratedQuestionPanel(props: Props) {
  const { nodeId, range } = props;
  const fetchPage = useCallback(
    (id: string, cursor: string | null, signal: AbortSignal) =>
      fetchPanelQuestions213(id, range, cursor, signal),
    [range],
  );
  const page = useCursorPage(nodeId, fetchPage);
  return (
    <section className={styles.followupSection} aria-label="더 알아보기">
      <h2>더 알아보기</h2>
      <PeriodNote range={range} />
      {page.items.map((question) => (
        <Question key={question.id} question={question} {...props} />
      ))}
      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        emptyMessage="이 기간에는 공개된 질문이 없습니다."
        onRetry={page.retry}
      />
      {page.nextCursor && (
        <button
          type="button"
          onClick={page.more}
          disabled={page.loading || !!page.error}
        >
          질문 4개 더 보기
        </button>
      )}
    </section>
  );
}

export function QuestionPanel(props: Props) {
  if (props.range === "all")
    return (
      <section className={styles.followupSection} aria-label="더 알아보기">
        <h2>더 알아보기</h2>
        <p className={styles.panelMeta}>
          최근 90일 또는 최근 1년을 선택하면 질문과 답변을 볼 수 있습니다.
        </p>
      </section>
    );
  return <GeneratedQuestionPanel {...props} />;
}
