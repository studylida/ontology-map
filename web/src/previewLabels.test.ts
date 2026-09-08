import { expect, it, vi } from "vitest";
import { placePreviewLabels } from "./previewLabels";

it("겹친 이름을 가까운 빈자리로 옮기고 정지한 화면에서는 다시 측정하지 않는다", () => {
  const container = document.createElement("div");
  container.getBoundingClientRect = () => new DOMRect(0, 0, 400, 300);
  const labels = ["center", "direct"].map((tier) => {
    const label = document.createElement("span");
    label.dataset.nodeId = tier;
    label.dataset.tier = tier;
    label.style.opacity = "1";
    label.getBoundingClientRect = vi.fn(() => new DOMRect(100, 100, 100, 20));
    container.append(label);
    return label;
  });
  placePreviewLabels(container);
  expect(labels[0]?.style.translate).toBe("0px 0px");
  expect(labels[1]?.style.translate).not.toBe("0px 0px");
  placePreviewLabels(container);
  expect(labels[0]?.getBoundingClientRect).toHaveBeenCalledTimes(1);
});
