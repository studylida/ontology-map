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

기본 화면은 어두운 분석 도구의 인상을 유지하면서 Obsidian 지식그래프처럼 작은 node와 가는 관계선이 군집을 이루는 은하형 3D 장면을 사용한다. node의 발광, 제한된 bloom과 거리 안개는 깊이와 탐색 초점을 드러내는 데 사용할 수 있다. 여러 색의 네온을 장식처럼 섞거나 광원이 정보보다 먼저 보이게 만들지 않는다.

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

지도의 활성 graph에는 중심 node의 직접 이웃과 중요한 2단계 이웃을 우선 표시한다. 활성 graph 바깥의 공개 node는 3단계 이후의 주변부로 제한해 더 낮은 밝기로 함께 표시할 수 있다. 전체 graph를 한 화면에 축소해 보여주거나 고정 좌표·전체 지도 version이 존재하는 것처럼 표현하지 않는다.

지식맵은 x·y 평면의 군집 배치를 주된 구조로 사용하는 얕은 2.5D 장면이다. 초기 깊이 범위는 중심 기준 약 ±20으로 제한하고 z축은 node 겹침과 앞뒤 구분에만 사용한다. 회전은 제공하지 않으며 빈 map 영역을 drag하면 평행 이동하고 wheel이나 trackpad로 확대·축소한다.

기본 카메라 배율에서는 중심 node, 직접 이웃과 중요한 2단계 이웃의 대부분을 한 화면에서 함께 탐색할 수 있어야 한다. node 간격은 label과 발광 core가 겹치지 않는 범위에서 조밀하게 유지하며, 다른 node를 찾기 위해 매번 축소한 뒤 다시 확대하도록 만들지 않는다. node 사이 거리는 탐색을 위한 layout 값일 뿐 관계 강도나 다른 의미를 나타내지 않는다.

### Motion

control의 hover·focus 강조와 panel의 짧은 상태 전환은 160ms, 시간 범위처럼 관측 활동량이 바뀔 때의 node 크기·밝기 전환은 320ms, 새 중심 node로 이동하는 전체 전환은 1200ms를 기본으로 한다. 1200ms 전환은 천천히 출발해 중간 구간에서 가속하고 도착 전에 다시 감속하는 ease-in-out 하나를 사용한다.

node를 선택하면 카메라는 선택한 node의 현재 위치를 새 중심으로 바라보며 이동한다. 같은 1200ms 동안 이전 중심의 고정을 풀고 선택한 node를 그 위치에 고정하며, 새 직접 이웃과 중요한 2단계 이웃의 force 재배치를 연속해서 진행한다. 카메라 위치, node 위치, core 밝기, halo와 외곽선, node와 label의 불투명도, 관계선 색과 불투명도는 하나의 진행률로 보간한다. 기존 graph와 새 graph에 함께 속한 node와 관계선은 같은 객체와 위치를 이어서 사용하고, 진입 요소는 불투명도 0에서 시작하며 이탈 요소는 정확히 0까지 낮춘다. 전체 canvas나 panel을 다시 그리는 fade는 적용하지 않는다.

전환 중에는 기존 중심을 확정 상태로 유지하고 새 중심은 pending 상태로만 다룬다. header, 검색값, 범위 요약과 상세 panel의 동적 문구는 전환 중간인 600ms에 불투명도 0에서 한 번 교체한 뒤 다시 나타나며, `재배치 중` 같은 별도 문구로 내용을 바꾸지 않는다. graph 영역은 전환 시작부터 종료까지 busy 상태를 알리고, 중심 node의 accessible name과 확정 상태는 전환이 끝난 뒤 함께 갱신한다.

부분 graph와 force simulation은 전환 시작 시 한 번만 갱신한다. 전환 종료 시 graph를 다시 교체하거나 force를 다시 시작하지 않으며, 이탈 node와 관계선은 보이지 않는 상태로 위치를 고정하고 force 영향을 0으로 둔 뒤 다음 전환을 시작할 때 제거한다. force simulation은 layout이 안정되면 멈추고 장식 목적으로 계속 흔들지 않는다. `prefers-reduced-motion`에서는 같은 상태를 한 번에 적용하고 반복 animation을 끈다.

전환 시작 시에는 현재 node 위치를 한 render frame 동안 고정한 상태에서 관계선의 source와 target을 새 graph에 다시 연결한다. 다음 frame에 이웃 node의 고정을 풀고 force를 시작해 관계선 끝점 재계산과 위치 이동이 같은 frame에서 겹치지 않게 한다. 전환이 끝나면 남은 node 속도를 0으로 만들고 안정된 위치를 고정해 관계선이 뒤늦게 움찔하거나 장면이 계속 흐르지 않게 한다.

## Elevation & Depth

UI panel의 깊이는 `surface`, `surface-elevated`와 1px `border`로 구분한다. 넓고 흐린 shadow, glass blur와 panel 배경 gradient는 사용하지 않는다. 지식맵 canvas에는 node 군집의 공간 깊이를 읽을 수 있도록 낮은 강도의 거리 안개, vignette와 bloom 후처리를 사용할 수 있다.

3D 깊이는 관계 묶음을 읽기 위한 보조 표현이다. 제한된 z축 차이는 겹침을 줄이기 위한 시각 배치일 뿐이며 node 사이 거리와 높이는 관계 강도, 조직 서열, 시간이나 인과를 뜻하지 않는다.

모든 node는 유형 색을 유지하는 작은 발광 core와 낮은 강도의 halo를 가질 수 있다. 중심 node는 현재 탐색의 기준임을 바로 알아볼 수 있도록 활동량이나 hover 상태와 무관하게 장면에서 가장 밝게 유지한다. 다른 node의 기본 발광 강도는 관측 활동량에만 연동하고, 선택하거나 hover한 node와 그 직접 경로는 중심 node보다 밝아지지 않는 범위에서 bloom과 외곽선을 일시적으로 강화한다. bloom 반경이나 halo 크기에 confidence, 근거 수와 같은 별도 의미를 부여하지 않으며 node label과 관계선의 대비를 낮추지 않는다.

## Shapes

일반 control과 입력은 `rounded.md`, tooltip과 작은 label은 `rounded.sm`, 큰 panel과 sheet는 `rounded.lg`를 사용한다. `rounded.full`은 status badge처럼 짧고 독립된 상태 표시에만 사용한다.

모든 클릭·터치 target은 최소 44px을 확보한다. 작은 icon 자체가 44px일 필요는 없지만 icon을 포함한 button의 hit area는 이 기준을 충족해야 한다.

관계선은 선명한 core와 매우 낮은 강도의 외곽 halo를 겹친 절제된 필라멘트로 표현할 수 있다. 기본 관계는 실선이고 충돌 관계만 `conflict` 색의 점선을 사용한다. z축 위치와 node의 불투명도에 관계없이 관계선은 node 원형 안에서 완전히 가려져야 한다. node 표면 아래에 배경색의 불투명 가림 glyph를 먼저 그리고, 가림 glyph와 node 표면 및 label을 관계선과 같은 투명 렌더 단계의 더 높은 순서로 그린다. 외곽 halo는 관계선의 굵기 의미를 바꾸지 않으며 선택 경로에서도 node와 label을 가리지 않는 범위에서만 밝아진다. 단순한 시각적 다양성을 위해 선 모양이나 node geometry를 늘리지 않는다.

## Components

### Header와 검색

header는 56px 높이의 단색 분석 도구 bar로 유지한다. 작은 별자리형 product mark, `ontology-map`, 화면 이름, 현재 중심과 부분 graph 범위, 공개 상태만 표시한다. 검색, 시간 범위와 필요한 map control은 지도 위 overlay에 둔다. navigation이 실제로 생기기 전에는 빈 menu와 미래 기능 entry를 만들지 않는다.

검색 input에 문자를 입력하면 바로 아래 드롭다운에 node 후보를 표시한다. 각 후보에는 node 이름, 유형과 짧은 검색 이유를 표시하고 Claim과 출처는 결과 순위를 설명하는 보조 근거로만 사용한다. 검색 input과 결과는 keyboard로 이동하고 선택할 수 있어야 하며, 후보를 선택하면 node 클릭과 같은 중심 이동을 실행한다.

### Knowledge map

모든 공개 node는 pointer와 keyboard로 선택할 수 있고 선택하면 새 중심이 된다. 선택한 node의 현재 world position을 유지한 채 카메라 중심과 부분 graph가 함께 전환되며, 새 중심 기준의 직접 이웃과 중요한 2단계 이웃을 다시 계산한다. accessible name에는 node 이름과 유형을 포함한다.

주변부 공개 node는 중심과 1·2단계 이웃보다 작고 어둡게 보이되 선택 가능성을 잃지 않는다. 주변부 node와 활성 graph 사이에 실제 Relation이 있으면 낮은 불투명도의 관계선을 이어서 2단계 이웃 바깥의 탐색 경로를 보여준다. Relation이 없는 node나 검색으로만 정한 대상에는 관계선을 만들지 않는다. 주변부 node를 선택하면 현재 위치에서 같은 중심 이동을 시작하고, 해당 node 기준의 활성 graph와 주변부를 다시 계산한다.

제품은 임의의 공개 node 1,000개를 먼저 불러와 전체 graph처럼 보이게 만들지 않는다. 현재 활성 graph의 경계 node ID를 기준으로 다음 주변부를 제한된 page 단위로 불러오며, 사용자가 빈 map 영역을 이동해 경계에 접근하거나 주변부 node를 선택하기 전에 다음 page를 미리 준비한다. 멀어진 주변부는 짧은 유예 뒤 장면과 force 계산에서 제외하되 세션 동안의 위치만 cache해 다시 나타날 때 갑자기 다른 곳에 배치되지 않게 한다. 이 증분 로드는 서버에 저장된 지도 좌표나 기준 DB를 전제하지 않는다.

홈페이지 첫 진입에서는 공개된 전체 graph의 분포가 안정된 뒤 화면에 맞춰 한 번 조망하고, 720ms 동안 유지한 다음 기본 중심 node로 1200ms 동안 확대한다. BISTelligence node가 fixture에 없는 검증 예시에서는 SK하이닉스를 기본 중심으로 사용한다. 이 전체 graph는 저장 좌표나 기준 DB를 뜻하지 않는 일시적인 intro 상태이며, intro가 끝나면 이후 탐색과 같은 동적 부분 graph만 유지한다.

node는 클릭하거나 keyboard로 선택해 중심을 바꾸지만 직접 끌어 배치할 수 없다. 빈 map 영역의 drag는 항상 카메라 평행 이동에만 사용하며, node drag로 force simulation을 다시 시작하거나 navigation control을 점유하지 않는다.

node 크기와 밝기는 선택한 시간 범위의 관측 활동량을 나타낸다. 크기 범위는 가장 작은 node와 가장 큰 node가 지름 기준 1:2.2를 넘지 않게 제한하고, 활동량이 낮아도 label과 선택 가능성을 유지한다.

node core, halo와 bloom은 하나의 밝기 체계로 다룬다. 중심 node는 별도의 영구 강조 단계로 두고 현재 장면에서 가장 밝게 유지한다. 중심이 아닌 node는 활동량이 같으면 같은 수준으로 빛나며, 선택·hover 강조는 사용자가 초점을 옮기는 동안에만 추가하되 중심 node의 밝기를 넘지 않는다. 선택한 node가 새 중심으로 전환되면 영구 강조도 그 node로 이동하고 이전 중심은 활동량 기반 밝기로 돌아간다. bloom이 node 크기 비율을 흐리거나 인접 node가 하나의 덩어리처럼 합쳐질 정도로 번지지 않게 한다.

관계선 굵기는 독립 근거 묶음 수에 따른 근거 강도를 나타내며 화면에서는 1px에서 6px 사이로 제한한다. 관계 종류나 확신 점수를 굵기로 표현하지 않는다.

오래된 정보는 불투명도를 점진적으로 낮추되 선택한 시간 범위 안에서는 0.35 아래로 내리지 않는다. 충돌 관계는 나이와 무관하게 `conflict` 색의 점선으로 표시한다.

직접 이웃은 기본 불투명도로 표시한다. 중요한 2단계 이웃은 label과 관계 맥락을 유지하면서 시각 우선순위를 낮춘다. 3단계 이후의 주변부 node와 관계선은 한 단계 더 낮은 불투명도로 표시하고 label은 hover·focus나 keyboard 탐색 중에만 나타낸다. hover나 focus 중에는 연결된 node와 관계선을 강조하고 나머지를 완전히 숨기지 않는다.

관계선은 군집의 깊이와 겹침을 읽기 위해 완만한 곡선을 사용할 수 있다. 곡률은 관계 종류나 강도를 뜻하지 않는다. 기본 필라멘트는 `relation` 색의 core와 약한 halo를 사용하고, hover·focus 경로는 같은 색 체계 안에서 불투명도와 halo만 높인다. node 유형 색을 관계선 양 끝에 섞어 관계 종류처럼 보이게 만들지 않는다. 뒤쪽 관계선은 거리 안개로 자연스럽게 낮아질 수 있지만 충돌 관계의 호박색 점선과 선택 경로는 식별할 수 있어야 한다.

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
- 작은 node, 가는 관계선과 선택적인 label로 군집이 별자리처럼 읽히게 한다.

### Don't

- node 크기, 밝기, 관계선 굵기와 거리에 승인되지 않은 의미를 추가하지 않는다.
- 의미가 섞인 단일 confidence 점수를 화면에 만들지 않는다.
- 전체 지도 version, 저장된 x/y/z 좌표나 확정된 조직 구조처럼 보이는 layout을 표현하지 않는다.
- 여러 색의 neon rainbow, 화면을 하얗게 덮는 flare, 계속 맥동하거나 깜박이는 glow, 장식용으로 이동하는 particle과 계속 움직이는 배경을 사용하지 않는다.
- bloom과 거리 안개로 node 유형 색, 오래된 정보의 불투명도, 충돌 점선, label과 focus 표시를 알아보기 어렵게 만들지 않는다.
- 존재하지 않는 관리자, 인증, 후보 검토와 모델 실행 화면을 미리 설계하지 않는다.
- 다른 회사의 브랜드 색, typography, logo나 고유한 component 외형을 복제하지 않는다.

이 문서의 구조는 Apache-2.0으로 공개된 [Google DESIGN.md format](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/docs/spec.md)을 참고했으며, 시각 규칙과 제품 의미는 ontology-map 요구사항에 맞게 작성했다.
