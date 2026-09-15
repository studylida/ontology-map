import { useEffect, useRef, useState } from "react";
import styles from "./App.module.css";
import {
  fetchTopicReferences,
  type TopicReference,
} from "./topicData";

export function TopicPicker({
  onSelect,
}: {
  onSelect: (nodeId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [topics, setTopics] = useState<TopicReference[]>([]);
  const loadedRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  const showTopics = () => {
    setOpen((current) => !current);
    if (loadedRef.current) return;
    loadedRef.current = true;
    const controller = new AbortController();
    controllerRef.current = controller;
    void fetchTopicReferences(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setTopics(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) loadedRef.current = false;
      });
  };

  return (
    <div className={styles.topicPicker}>
      <button
        type="button"
        className={styles.topicButton}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={showTopics}
      >
        주제
      </button>
      {open && (
        <div className={styles.topicPopover} role="listbox" aria-label="주제 목록">
          {topics.map((topic) => (
            <button
              type="button"
              role="option"
              aria-selected={false}
              key={topic.nodeId}
              className={styles.topicOption}
              onClick={() => {
                setOpen(false);
                onSelect(topic.nodeId);
              }}
            >
              <span>{topic.name}</span>
              {!topic.isActive && <small>신규 연결 중단</small>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
