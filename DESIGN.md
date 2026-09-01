---
version: alpha
name: ontology-map
description: Dark-first analytical workspace centered on a dynamic three-dimensional knowledge map.
colors:
  background: "#0B0F14"
  surface: "#121821"
  surface-elevated: "#18212C"
  border: "#2B3645"
  text-primary: "#F3F6FA"
  text-secondary: "#9CA8B7"
  interactive: "#72A7FF"
  focus-ring: "#B9D3FF"
  conflict: "#E6A23C"
  danger: "#F26D78"
  ready: "#4FD1A1"
  node-person: "#6EA8FE"
  node-company: "#B792F4"
  node-technology: "#43C6D9"
  node-topic: "#65C98B"
  node-event: "#F17C9E"
  relation: "#7B8797"
typography:
  screen-title:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 24px
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: -0.01em
  panel-title:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 12px
    fontWeight: 550
    lineHeight: 1.4
  technical:
    fontFamily: 'ui-monospace, "SFMono-Regular", Consolas, monospace'
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: 4px
  md: 8px
  lg: 12px
  full: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
components:
  search-control:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    height: 44px
    padding: 12px
  detail-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    width: 420px
    padding: 24px
  primary-action:
    backgroundColor: "{colors.interactive}"
    textColor: "{colors.background}"
    rounded: "{rounded.md}"
    height: 44px
    padding: 12px
  map-tooltip:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    padding: 8px
---

# ontology-map 디자인 계약

## Overview

ontology-map은 공개 자료에서 얻은 근거와 시간축을 탐색하는 분석 작업 공간이다. 사용자는 검색한 노드를 중심으로 동적 지식맵을 살펴보고, 10분 안에 맥락 설명 1개, 근거 있는 관계 3개와 후속 질문 2개를 얻을 수 있어야 한다.

화면의 중심은 3D 지식맵이다. header, 검색, 시간 범위, 범례와 상세 panel은 탐색을 돕는 보조 요소로 유지한다. 장식이나 브랜드 연출이 그래프, Evidence Trace와 읽기 흐름보다 먼저 보이지 않게 한다.

기본 화면은 어두운 분석 도구의 인상을 유지하되 네온 효과나 과장된 미래 이미지를 사용하지 않는다. 정보는 조용하고 밀도 있게 표현하며 선택, 충돌, 실패와 공개 준비 상태는 분명히 구분한다.

UI 문구는 한국어를 기본으로 한다. node type, relation type, model identifier, ontology code와 API 값처럼 정확한 식별이 필요한 값은 원래 영어 표기를 보존한다.

## Colors

배경은 `background` 하나를 기준으로 하고 panel은 `surface`, overlay와 입력 요소는 `surface-elevated`를 사용한다. 계층은 밝은 배경을 새로 만드는 대신 표면 색과 `border`로 표현한다.

`text-primary`는 제목과 본문, `text-secondary`는 metadata와 보조 설명에 사용한다. 본문 색을 투명하게 만들어 중요도를 조절하지 않는다. 오래된 지식의 투명도는 지식맵 표시 규칙에만 적용한다.

`interactive`는 링크, 선택 가능한 control과 주요 action에 사용한다. `focus-ring`은 키보드 focus 전용이며 `conflict`는 충돌 관계와 충돌 설명에만 사용한다. `danger`는 실행 실패와 복구할 수 없는 오류, `ready`는 공개 준비 완료 상태에 사용한다.

공개 node type은 다음 색을 사용한다.

| 유형 | 색 | 보조 표기 |
| --- | --- | --- |
| 사람 | `node-person` | `사람` label 또는 사람 icon |
| 회사 | `node-company` | `회사` label 또는 건물 icon |
| 기술 | `node-technology` | `기술` label 또는 도구 icon |
| 주제 | `node-topic` | `주제` label 또는 tag icon |
| 사건 | `node-event` | `사건` label 또는 calendar icon |

node type은 색만으로 구분하지 않는다. tooltip, 상세 panel과 keyboard accessible name에 유형을 포함하고 범례에는 색과 문자 label을 함께 표시한다.

## Typography

별도 웹 폰트를 내려받지 않고 운영체제의 system sans-serif를 사용한다. 숫자, hash, code와 정밀한 시점처럼 기술 값에만 `technical` typography를 제한적으로 사용한다.

화면 제목은 `screen-title`, node 상세 제목은 `panel-title`, 설명과 Evidence Trace는 `body`, node label과 metadata는 `label`을 사용한다. 본문을 14px보다 작게 만들지 않고 긴 인용문은 충분한 줄 간격을 유지한다.

굵기만으로 의미를 구분하지 않는다. 제목 수준, 간격, label과 상태 문구를 함께 사용한다. 전체 대문자는 짧은 ontology code 외에는 사용하지 않는다.

## Layout

화면은 viewport를 채운다. 56px header 아래에서 지식맵이 남은 영역 전체를 사용하며 검색과 시간 범위는 맵의 왼쪽 위에 겹쳐 놓는다. 검색 control의 desktop 너비는 360px로 고정한다.

너비가 1024px 이상이면 상세 panel은 오른쪽에 420px 너비로 겹쳐 표시한다. panel을 열어도 중심 node와 주요 직접 이웃을 가리지 않도록 카메라 중심을 남은 map 영역에 맞춘다.

너비가 768px 이상 1024px 미만이면 상세 panel은 화면 너비의 46%를 사용하되 420px을 넘지 않는다. 너비가 768px 미만이면 검색은 좌우 16px 여백을 두고, 상세 정보는 전체 너비의 bottom sheet로 표시하며 높이는 viewport의 72%를 넘지 않는다.

간격은 front matter의 4·8·12·16·24·32px 단계만 사용한다. map 위 overlay 사이에는 최소 12px, panel section 사이에는 24px, 관련된 label과 값 사이에는 8px을 둔다.

지도에는 중심 node의 직접 이웃과 중요한 2단계 이웃만 우선 표시한다. 전체 graph를 한 화면에 축소해 보여주거나 고정 좌표·전체 지도 version이 존재하는 것처럼 표현하지 않는다.

### Motion

control hover와 panel 상태 전환은 160ms, 새 중심 node로 이동하는 카메라 전환은 280ms를 기본으로 한다. easing은 급격한 bounce가 없는 ease-out을 사용한다.

force simulation은 layout이 안정되면 멈추고 장식 목적으로 계속 흔들지 않는다. `prefers-reduced-motion`에서는 카메라 이동을 즉시 전환하거나 짧은 fade로 바꾸고 반복 animation을 끈다.

## Elevation & Depth

UI panel의 깊이는 `surface`, `surface-elevated`와 1px `border`로 구분한다. 넓고 흐린 shadow, glass blur와 배경 gradient는 사용하지 않는다.

3D 깊이는 관계 묶음을 읽기 위한 보조 표현이다. node 사이 거리는 대략적인 관련 묶음 배치만 나타내며 관계 강도, 조직 서열, 시간이나 인과를 뜻하지 않는다.

선택한 node에는 `focus-ring` 색의 얇은 외곽선과 가벼운 glow를 함께 사용한다. glow는 선택 상태 이외에 사용하지 않고 node label의 대비를 낮추지 않는다.

## Shapes

일반 control과 입력은 `rounded.md`, tooltip과 작은 label은 `rounded.sm`, 큰 panel과 sheet는 `rounded.lg`를 사용한다. `rounded.full`은 status badge처럼 짧고 독립된 상태 표시에만 사용한다.

모든 클릭·터치 target은 최소 44px을 확보한다. 작은 icon 자체가 44px일 필요는 없지만 icon을 포함한 button의 hit area는 이 기준을 충족해야 한다.

관계선은 기본적으로 실선이다. 충돌 관계만 `conflict` 색의 점선을 사용한다. 단순한 시각적 다양성을 위해 선 모양이나 node geometry를 늘리지 않는다.

## Components

### Header와 검색

header에는 제품명, 현재 시간 범위와 필요한 map control만 둔다. navigation이 실제로 생기기 전에는 빈 menu와 미래 기능 entry를 만들지 않는다.

검색 결과는 node만 반환한다. 각 결과에는 node 이름, 유형과 짧은 검색 이유를 표시하고 Claim과 출처는 결과 순위를 설명하는 보조 근거로만 사용한다. 검색 input과 결과는 keyboard로 이동하고 선택할 수 있어야 한다.

### Knowledge map

모든 공개 node는 pointer와 keyboard로 선택할 수 있고 선택하면 새 중심이 된다. accessible name에는 node 이름과 유형을 포함한다.

node 크기와 밝기는 선택한 시간 범위의 관측 활동량을 나타낸다. 크기 범위는 가장 작은 node와 가장 큰 node가 지름 기준 1:2.2를 넘지 않게 제한하고, 활동량이 낮아도 label과 선택 가능성을 유지한다.

관계선 굵기는 독립 근거 묶음 수에 따른 근거 강도를 나타내며 화면에서는 1px에서 6px 사이로 제한한다. 관계 종류나 확신 점수를 굵기로 표현하지 않는다.

오래된 정보는 불투명도를 점진적으로 낮추되 선택한 시간 범위 안에서는 0.35 아래로 내리지 않는다. 충돌 관계는 나이와 무관하게 `conflict` 색의 점선으로 표시한다.

직접 이웃은 기본 불투명도로 표시한다. 중요한 2단계 이웃은 label과 관계 맥락을 유지하면서 시각 우선순위를 낮춘다. hover나 focus 중에는 연결된 node와 관계선을 강조하고 나머지를 완전히 숨기지 않는다.

### Detail panel

상세 panel은 node 이름과 유형, 맥락 설명 1개, 근거 확인된 관계, 원자적 Claim, 출처와 Evidence Trace, 후속 질문 2개 순서로 구성한다. Evidence Trace에는 source title, publisher, publication time, 인용문과 원문 위치를 구분해 표시한다.

후속 질문은 공개 가능한 target node로 이동하는 action이다. 일반 본문처럼 보이게 만들지 않고 명확한 button 또는 link로 표시한다. 클릭 중 모델 호출이 일어나는 것처럼 loading animation을 보여주지 않는다.

### 상태

loading은 어느 영역을 준비하는지 문구로 알리고 map 전체를 불필요하게 가리지 않는다. empty 상태는 시간 범위 변경이나 새 검색처럼 가능한 다음 행동을 하나 제시한다.

error 상태는 실패한 영역과 다시 시도할 수 있는지 설명한다. publication 준비 실패 중에는 이전 READY 결과를 계속 보여주고 최신 기준 지식이 사라진 것처럼 빈 화면으로 바꾸지 않는다.

## Do's and Don'ts

### Do

- 지식맵이 viewport와 시각적 관심의 대부분을 차지하게 한다.
- 선택한 중심, 시간 범위, node 유형과 관계 근거를 항상 확인할 수 있게 한다.
- 색과 함께 label, 선 모양, accessible name과 상태 문구를 사용한다.
- Evidence Trace와 충돌 근거를 읽기 쉬운 순서로 제공한다.
- 새 UI를 만들기 전에 기존 token과 component 역할로 표현할 수 있는지 확인한다.

### Don't

- node 크기, 밝기, 관계선 굵기와 거리에 승인되지 않은 의미를 추가하지 않는다.
- 의미가 섞인 단일 confidence 점수를 화면에 만들지 않는다.
- 전체 지도 version, 저장된 x/y/z 좌표나 확정된 조직 구조처럼 보이는 layout을 표현하지 않는다.
- neon rainbow, 넓은 gradient, 과도한 glow, 장식용 particle과 계속 움직이는 배경을 사용하지 않는다.
- 존재하지 않는 관리자, 인증, 후보 검토와 모델 실행 화면을 미리 설계하지 않는다.
- 다른 회사의 브랜드 색, typography, logo나 고유한 component 외형을 복제하지 않는다.

이 문서의 구조는 Apache-2.0으로 공개된 [Google DESIGN.md format](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/docs/spec.md)을 참고했으며, 시각 규칙과 제품 의미는 ontology-map 요구사항에 맞게 작성했다.
