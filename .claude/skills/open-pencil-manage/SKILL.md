---
name: open-pencil-manage
description: OpenPencil MCP 서버와 CLI를 사용하여 .fig 디자인 파일을 생성, 편집, 분석, 코드 변환합니다. MCP로 .fig 파일을 생성/수정하고, CLI로 코드 변환(JSX/Tailwind) 및 XPath 쿼리를 수행합니다. TRIGGER when: 사용자가 명시적으로 OpenPencil 또는 .fig 파일을 언급할 때만 사용한다. "openpencil", "오픈펜슬", ".fig", "fig 파일", "피그 파일", "jsx 변환", "tailwind 변환" 등 OpenPencil/.fig 전용 키워드가 포함될 때 사용. 범용 디자인 요청("디자인 만들어줘", "UI 디자인", "컴포넌트 디자인" 등)은 penpot-manage 스킬이 담당하므로 이 스킬을 사용하지 않는다. Figma MCP(figma.com URL 기반 작업)와도 다른 도구이므로 구분한다.
argument-hint: (자연어로 OpenPencil 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, Edit, mcp__open-pencil__new_document, mcp__open-pencil__open_file, mcp__open-pencil__save_file, mcp__open-pencil__get_page_tree, mcp__open-pencil__get_node, mcp__open-pencil__find_nodes, mcp__open-pencil__list_pages, mcp__open-pencil__create_shape, mcp__open-pencil__render, mcp__open-pencil__create_component, mcp__open-pencil__create_instance, mcp__open-pencil__node_to_component, mcp__open-pencil__set_fill, mcp__open-pencil__set_stroke, mcp__open-pencil__set_font, mcp__open-pencil__set_text, mcp__open-pencil__set_layout, mcp__open-pencil__set_layout_child, mcp__open-pencil__set_effects, mcp__open-pencil__set_radius, mcp__open-pencil__set_opacity, mcp__open-pencil__set_rotation, mcp__open-pencil__node_move, mcp__open-pencil__node_resize, mcp__open-pencil__clone_node, mcp__open-pencil__delete_node, mcp__open-pencil__reparent_node, mcp__open-pencil__group_nodes, mcp__open-pencil__export_image, mcp__open-pencil__export_svg, mcp__open-pencil__analyze_colors, mcp__open-pencil__analyze_typography, mcp__open-pencil__analyze_spacing, mcp__open-pencil__analyze_clusters, mcp__open-pencil__eval
---

# OpenPencil 관리 (MCP + CLI)

OpenPencil은 .fig 디자인 파일을 프로그래밍 방식으로 생성, 편집, 분석하는 도구다. MCP 서버와 CLI 두 가지 인터페이스를 제공하며, 각각 역할이 다르다.

## 도구 역할 분담

| 작업 | 사용할 도구 | 이유 |
|------|-----------|------|
| 디자인 생성/편집 | **MCP** | 개별 도구로 세밀한 조작 가능 |
| 디자인 조회/분석 | **MCP** | `get_page_tree`, `analyze_*` 등 |
| 디자인 시각 확인 | **MCP** `export_svg` | `export_image`는 텍스트를 렌더링하지 못함 — 반드시 `export_svg` 사용 |
| 코드 변환 (JSX/Tailwind) | **CLI** `export -f jsx` | MCP에는 코드 변환 기능 없음 |
| XPath 노드 검색 | **CLI** `query` | MCP에는 XPath 검색 없음 |
| 문서 요약 | **CLI** `info` | MCP에는 요약 기능 없음 |

---

## MCP 작업 흐름

1. **열기** — `open_file` 또는 `new_document`
2. **조회** — `get_page_tree`, `find_nodes`, `get_node`
3. **생성/수정** — `render` (JSX), `create_shape`, `set_fill`, `set_layout` 등
4. **확인** — 항상 `export_svg`를 사용한다 (**`export_image`는 텍스트 노드를 렌더링하지 못하므로 사용 금지**)
5. **저장** — `save_file` (**모든 생성/수정 작업 후 반드시 저장한다.** MCP, CLI, 데스크톱 앱은 각각 독립적으로 파일을 읽으므로 저장하지 않으면 변경사항이 반영되지 않는다)

### 결과물 확인

사용자가 결과물을 "보고 싶다"고 요청하면 **이미지로 보여달라는 뜻**이다 (SVG 코드를 텍스트로 출력하는 것이 아님). 아래 순서로 처리한다:

1. `export_svg`로 SVG 데이터를 얻는다.
2. SVG를 `.svg` 파일로 저장한다 (`out/{사용자명}/` 디렉토리).
3. `open` 명령으로 브라우저에서 열어 사용자가 이미지로 확인할 수 있게 한다.

더 자세히 확인하고 싶다면, `save_file` 후 OpenPencil 데스크톱 앱에서 직접 .fig 파일을 열어 확인하도록 안내한다.

> **⚠ `export_image` 사용 금지:** `export_image`(PNG/JPG/WEBP)는 텍스트 노드를 렌더링하지 못한다. 도형과 배경만 출력되고 텍스트는 빈 영역으로 나타나므로, 디자인 확인 용도로 절대 사용하지 않는다. 반드시 `export_svg`를 사용한다.

> **⚠ 이모지 렌더링 미지원:** OpenPencil은 이모지를 렌더링하지 못한다. `.fig` 파일 포맷 자체는 `PaintType.EMOJI`와 `emojiCodePoints` 필드를 지원하지만, 변환 코드(`convertFills`)에서 EMOJI 타입을 처리하지 않고, 폰트 폴백에도 이모지 폰트(Apple Color Emoji 등)가 없다. 따라서 **이모지 대신 텍스트("!", "주의" 등)나 도형으로 아이콘을 표현**해야 한다.

### render 도구 (JSX → 디자인 노드)

`render`는 JSX 한 번으로 전체 컴포넌트 트리를 생성하는 **주요 생성 도구**다. 개별 `create_shape` + `set_fill` + `set_font`를 반복하는 것보다 훨씬 효율적이므로, 컴포넌트 생성 시 우선 사용한다.

```jsx
<Frame name="Card" w={320} h="hug" flex="col" gap={16} p={24} bg="#FFF" rounded={16} shadow="0 4 12 #00000014">
  <Text font="Pretendard" size={18} weight="bold" color="#111">제목</Text>
  <Text font="Pretendard" size={14} color="#666">설명 텍스트</Text>
</Frame>
```

**한글 폰트:** 모든 텍스트에 `font="Pretendard"`를 지정한다. 기본 폰트 Inter는 한글을 지원하지 않으므로, 한글이 포함될 가능성이 있는 텍스트에는 항상 Pretendard를 사용한다. (시스템에 `brew install --cask font-pretendard`로 설치됨, SIL OFL 1.1 라이선스)

**알아야 할 특수 문법:**
- `h="hug"`: 자식 크기에 맞춤, `w="fill"`: 부모 너비 채움
- `shadow`: `"offsetX offsetY blur #color"` 형식 (문자열)
- `flex`: `"row"` 또는 `"col"` (Auto Layout 방향)

나머지 props (`w`, `h`, `gap`, `p`, `bg`, `rounded`, `stroke`, `opacity`, `size`, `weight`, `color`, `textAlign` 등)는 CSS/Tailwind와 유사하므로 직관적으로 사용 가능하다.

### 결과물 저장 위치

`.fig` 파일은 `out/{사용자명}/` 디렉토리에 저장한다. 현재 사용자는 `.env`의 `ME` 값으로 판단한다.

---

## CLI 고유 기능

CLI는 `openpencil` 명령어로 실행한다 (`bun add -g @open-pencil/cli`로 글로벌 설치됨). MCP에 없는 기능만 CLI를 사용한다.

### 코드 변환

```bash
openpencil export design.fig -f jsx --style tailwind -o out/david/component.tsx
```

**`-o` 옵션으로 출력 파일 경로를 반드시 지정한다.** 생략하면 현재 디렉토리에 `<name>.<format>`으로 생성되므로, `.fig` 파일과 같은 `out/{사용자명}/` 디렉토리에 저장되도록 `-o` 경로를 명시한다.

**디자인→코드 변환 시 반드시 CLI `export -f jsx`를 사용한다. AI가 디자인을 보고 직접 코드를 작성하지 않는다.**

### XPath 노드 검색

```bash
openpencil query design.fig "//FRAME[@width < 300]"
```

---

## 도움말 및 참고

명령이나 도구 사용법이 확실하지 않을 때는 아래를 참고한다:

- **CLI**: `openpencil --help`, `openpencil export --help` 등 `--help` 플래그로 확인
- **MCP**: `mcp__open-pencil__` 접두사로 사용 가능한 도구를 ToolSearch로 검색
- **코드베이스**: `~/.bun/install/global/node_modules/@open-pencil/` (cli, core, mcp 패키지)
- **GitHub**: https://github.com/open-pencil/open-pencil

---

## 응답 원칙

1. **디자인 생성은 `render` 도구를 우선 사용한다** — JSX 한 번으로 전체 구조를 만든 뒤, 세부 조정이 필요하면 개별 도구(`set_fill`, `set_font` 등)를 사용한다.
2. **코드 변환은 반드시 CLI를 사용한다** — AI가 직접 코드를 작성하지 않고, `openpencil export -f jsx --style tailwind`로 디자인 데이터에서 추출한다.
3. **결과 확인은 `export_svg`만 사용한다** — `export_image`는 텍스트를 렌더링하지 못하므로 절대 사용하지 않는다.
4. **조회 명령은 바로 실행한다** — `get_page_tree`, `find_nodes`, `analyze_*` 등은 확인 없이 즉시 실행한다.
5. **삭제/덮어쓰기는 사용자에게 확인한다** — `delete_node`, 기존 파일 덮어쓰기 등은 확인 후 실행한다.
6. **저장 후 확인을 안내한다** — `save_file` 후 OpenPencil 앱에서 파일을 다시 열어 확인하도록 안내한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
