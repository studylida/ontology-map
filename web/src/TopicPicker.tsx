import { useEffect, useRef, useState } from "react";
import topicStyles from "./Topic.module.css";
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
    <div className={topicStyles.topicPicker}>
      <button
        type="button"
        className={topicStyles.topicButton}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={showTopics}
      >
        주제
      </button>
      {open && (
        <div
          className={topicStyles.topicPopover}
          role="listbox"
          aria-label="주제 목록"
        >
          {topics.map((topic) => (
            <button
              type="button"
              role="option"
              aria-selected={false}
              key={topic.nodeId}
              className={topicStyles.topicOption}
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
