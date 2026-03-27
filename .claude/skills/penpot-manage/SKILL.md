---
name: penpot-manage
description: Penpot MCP 서버와 REST API를 사용하여 디자인 파일을 생성, 편집, 조회, 내보내기합니다. MCP(execute_code)로 열려 있는 디자인을 실시간 조작하고, REST API(curl)로 파일/프로젝트를 관리합니다. TRIGGER when: 사용자가 Penpot 디자인 작업, UI 디자인 생성, 디자인 편집, CSS/HTML 추출, 디자인 토큰, Penpot 파일/프로젝트 관리 등을 요청할 때. "penpot", "펜팟", "디자인", "UI 디자인", "컴포넌트 디자인", "CSS 추출", "디자인 토큰" 등 관련 키워드가 포함될 때 사용. 단, OpenPencil(.fig 파일)이나 Figma MCP(figma.com URL)와는 다른 도구이므로 구분한다.
argument-hint: (자연어로 Penpot 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, Edit, mcp__penpot__execute_code, mcp__penpot__export_shape, mcp__penpot__high_level_overview, mcp__penpot__penpot_api_info, mcp__penpot__import_image
---

# Penpot 관리 (MCP + REST API)

Penpot은 오픈소스 브라우저 기반 디자인 도구다. **MCP**로 열려 있는 디자인 파일을 실시간 조작하고, **REST API**로 파일/프로젝트를 관리한다.

## 도구 역할 분담

| 작업 | 사용할 도구 | 이유 |
|------|-----------|------|
| 셰이프 생성/수정/삭제 | **MCP** `execute_code` | Plugin API로 실시간 조작 |
| CSS/HTML/SVG 코드 추출 | **MCP** `execute_code` | `penpot.generateStyle()`, `penpot.generateMarkup()` |
| 디자인 토큰 관리 | **MCP** `execute_code` | `penpot.library.local.tokens` |
| 시각 확인 (PNG/SVG) | **MCP** `export_shape` | 텍스트/이모지 포함 정상 렌더링 |
| API 타입 문서 조회 | **MCP** `penpot_api_info` | Plugin API 타입/인터페이스 확인 |
| 이미지 가져오기 | **MCP** `import_image` | 로컬 이미지 → 디자인에 삽입 |
| 파일/프로젝트 목록 조회 | **REST API** curl | MCP 없이 사용 가능 |
| 파일 생성/삭제/검색 | **REST API** curl | 서버 수준 관리 |
| 팀/라이브러리/댓글 관리 | **REST API** curl | 서버 수준 관리 |

---

## 환경 설정

`.env` 파일에서 아래 값을 사용한다:

- `PENPOT_TOKEN`: Penpot Personal Access Token (design.penpot.app → Your account → Access tokens)

**REST API 호출 시:**

```bash
source .env
curl -s -H "Authorization: Token $PENPOT_TOKEN" \
  https://design.penpot.app/api/rpc/command/{명령}
```

---

## MCP 서버 자동 관리

MCP 도구를 사용하기 전에 **항상** 아래 순서로 서버 상태를 확인하고 필요 시 자동으로 시작/갱신한다. 사용자에게 서버 시작을 안내하지 않고, 직접 처리한다.

### 1. 서버 실행 여부 확인 및 기존 mcp-remote 정리

```bash
# 기존 mcp-remote → localhost:4401 연결을 모두 종료 (다중 인스턴스 충돌 방지)
pkill -f "mcp-remote.*localhost:4401" 2>/dev/null || true
sleep 1

curl -s -m 2 -o /dev/null -w "%{http_code}" http://localhost:4401/sse 2>/dev/null
```

> **⚠ 다중 인스턴스 주의:** `mcp-remote` 프로세스가 여러 개 동시에 같은 서버에 연결되면, 응답이 다른 인스턴스로 전달되어 무한 대기에 빠진다. MCP 도구 호출 전에 반드시 기존 연결을 정리한다.

- `200`: 서버 실행 중 → 2단계로 진행
- 그 외: 서버 안 떠 있음 → 3단계로 서버 시작

### 2. 서버 버전 확인 (실행 중일 때)

```bash
# 최신 버전 조회
LATEST=$(npm view @penpot/mcp version 2>/dev/null)

# 현재 캐시된 버전 조회
CURRENT=$(find ~/.npm/_npx -path "*/@penpot/mcp/package.json" -exec python3 -c "import sys,json; print(json.load(open(sys.argv[1]))['version'])" {} \; 2>/dev/null | sort -u | head -1)
```

`CURRENT`와 `LATEST`가 다르면 기존 서버를 종료하고 최신 버전으로 재시작한다.

### 3. 서버 시작/재시작

```bash
# 기존 Penpot MCP 프로세스 종료
pkill -f "penpot-mcp" 2>/dev/null || true
sleep 1

# 최신 버전으로 백그라운드 시작
nohup npx -y @penpot/mcp < /dev/null > /tmp/penpot-mcp.log 2>&1 &
disown

# 서버가 준비될 때까지 대기 (빌드 포함 최대 60초)
for i in $(seq 1 30); do
  if curl -s -m 1 -o /dev/null http://localhost:4401/sse 2>/dev/null; then
    break
  fi
  sleep 2
done
```

서버가 시작되면 **"서버가 시작되었습니다. Claude Code 새 세션을 열어주세요."** 라고 안내하고 작업을 중단한다. 현재 세션에서는 MCP 연결이 안 되기 때문이다.

### MCP 에러 대응

#### "No Penpot plugin instances are currently connected"

MCP 도구는 연결됐지만 브라우저 플러그인이 연결되지 않은 상태다. 사용자에게 아래를 안내한다:

1. 브라우저에서 design.penpot.app을 열고 디자인 파일을 연다
2. `Cmd+Alt+P`로 플러그인 매니저를 열고 `http://localhost:4400/manifest.json`을 입력한다
3. 플러그인 UI에서 **"Connect to MCP server"** 를 클릭한다

---

## MCP 작업 흐름

### 1. 디자인 구조 탐색

```javascript
// 현재 페이지 구조 확인
return penpotUtils.shapeStructure(penpot.currentPage.root, 3);

// 이름으로 셰이프 찾기
const shape = penpotUtils.findShape(s => s.name === 'MyButton');

// 사용자가 선택한 요소 확인
return penpotUtils.shapeStructure(penpot.selection[0]);
```

### 2. 셰이프 생성

```javascript
// 보드 (프레임) 생성
const board = penpot.createBoard();
board.name = "Card";
board.resize(320, 200);
board.fills = [{ fillColor: "#FFFFFF", fillOpacity: 1 }];
board.borderRadius = 12;

// Flex Layout 추가
const flex = board.addFlexLayout();
flex.dir = "column";
flex.rowGap = 12;
flex.horizontalPadding = 20;
flex.verticalPadding = 20;

// 텍스트 생성
const text = penpot.createText("제목");
text.fontSize = 18;
text.fontFamily = "Pretendard";
text.fontWeight = "bold";
text.fills = [{ fillColor: "#111827", fillOpacity: 1 }];
text.growType = "auto-width";
board.appendChild(text);
```

### 3. CSS/HTML 추출

```javascript
// 선택된 요소의 CSS 생성
return penpot.generateStyle(penpot.selection, { type: "css", withChildren: true });

// HTML 마크업 생성
return penpot.generateMarkup(penpot.selection, { type: "html" });

// SVG 마크업 생성
return penpot.generateMarkup(penpot.selection, { type: "svg" });
```

### 4. 결과물 확인

사용자가 결과물을 "보고 싶다"고 요청하면 **이미지로 보여달라는 뜻**이다. `export_shape` 도구로 PNG를 반환한다.

```
export_shape(shapeId: "셰이프ID", format: "png")
```

파일로 저장하고 싶으면 `filePath` 파라미터를 지정한다:

```
export_shape(shapeId: "셰이프ID", format: "png", filePath: "/absolute/path/to/output.png")
```

---

## REST API (MCP 없이 사용 가능)

MCP 서버가 없어도 REST API로 파일/프로젝트를 관리할 수 있다.

### 프로필 확인

```bash
source .env
curl -s -H "Authorization: Token $PENPOT_TOKEN" \
  https://design.penpot.app/api/rpc/command/get-profile | python3 -m json.tool
```

### 팀/프로젝트 조회

```bash
# 소속 팀 목록
curl -s -H "Authorization: Token $PENPOT_TOKEN" \
  https://design.penpot.app/api/rpc/command/get-teams | python3 -m json.tool

# 프로젝트 내 파일 목록
curl -s -H "Authorization: Token $PENPOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"projectId":"프로젝트ID"}' \
  https://design.penpot.app/api/rpc/command/get-project-files | python3 -m json.tool
```

### 파일 관리

```bash
# 파일 생성
curl -s -H "Authorization: Token $PENPOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"새 파일","projectId":"프로젝트ID"}' \
  https://design.penpot.app/api/rpc/command/create-file | python3 -m json.tool

# 파일 검색
curl -s -H "Authorization: Token $PENPOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"teamId":"팀ID","search-term":"검색어"}' \
  https://design.penpot.app/api/rpc/command/search-files | python3 -m json.tool
```

### API 문서

- **자동 생성 문서**: `https://design.penpot.app/api/_doc`
- **공식 가이드**: `https://help.penpot.app/technical-guide/integration/`

> **⚠ Cloudflare 주의:** 클라우드(design.penpot.app) API는 Cloudflare 보호로 간헐적 차단될 수 있다. 브라우저에서 먼저 로그인하면 일정 기간 정상 동작한다.

---

## 도움말 및 참고

- **MCP API 문서**: `penpot_api_info` 도구로 타입/인터페이스를 조회한다
- **고수준 가이드**: `high_level_overview` 도구를 한 번 읽으면 API 전체 구조를 파악할 수 있다 (세션당 1회)
- **공식 GitHub**: https://github.com/penpot/penpot

---

## 응답 원칙

1. **MCP 연결 상태를 먼저 확인한다** — MCP 도구가 필요한 작업인데 연결이 안 되어 있으면, 서버 시작 절차를 안내한다. REST API로 가능한 작업이면 MCP 없이 진행한다.
2. **결과 확인은 `export_shape`로 이미지를 보여준다** — 사용자가 "보고 싶다"고 하면 PNG 이미지로 반환한다.
3. **코드 추출은 MCP를 사용한다** — `penpot.generateStyle()`, `penpot.generateMarkup()`으로 CSS/HTML/SVG를 추출한다.
4. **조회 명령은 바로 실행한다** — 구조 탐색, API 문서 조회 등은 확인 없이 즉시 실행한다.
5. **삭제/덮어쓰기는 사용자에게 확인한다** — 셰이프 삭제, 파일 삭제 등은 확인 후 실행한다.
6. **`penpotUtils` 유틸리티를 우선 사용한다** — 셰이프 검색, 구조 분석 등은 직접 구현하지 않고 `penpotUtils`의 함수를 사용한다.
7. **`penpot_api_info`로 API를 확인한 뒤 코드를 작성한다** — 타입이나 메서드가 불확실하면 먼저 API 문서를 조회한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
