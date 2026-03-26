# ad-management-ai

ADM(Ad Management) 팀의 AI 작업 공간입니다.

---

## 시작하기 전에

이 프로젝트는 **Claude Code**가 설치되어 있어야만 사용할 수 있습니다.

Claude Code가 없다면 아래 공식 문서를 참고하여 먼저 설치해 주세요:

> https://docs.anthropic.com/en/docs/claude-code/overview

---

## 설치 및 설정

### 1. 저장소 클론

```bash
git clone <repository-url>
cd ad-management-ai
```

### 2. 환경 변수 설정

`.env` 파일을 생성합니다.

```bash
cp .env.example .env
```

`.env`에는 인증 토큰, 프로젝트 경로, 사용자 식별 정보 등이 포함됩니다. 각 도구별 필요한 환경 변수는 아래 [MCP 서버](#mcp-서버) 및 [스킬](#스킬-skills) 섹션에서 설명합니다.

**공통 환경 변수:**

| 변수 | 설명 |
|------|------|
| `ME` | 현재 사용자 이름 (`team/{ME}/` 디렉토리와 매칭) |
| `ADSERVER_PATH` | adserver 프로젝트 로컬 경로 |
| `ADS_CENTER_PATH` | ads-center 프로젝트 로컬 경로 |
| `ADS_CENTER_ID` / `ADS_CENTER_PW` | ads-center 계정 |
| `DASH_API_GATEWAY_PATH` | dash-api-gateway 프로젝트 로컬 경로 |
| `DASH_PATH` | dash 프로젝트 로컬 경로 |
| `GITPLOY_PATH` | gitploy 프로젝트 로컬 경로 |

### 3. 연결 확인

Claude Code를 실행한 뒤 MCP 서버 연결 상태를 확인해 주세요. 연결되지 않은 서비스가 있으면 아래 안내에 따라 인증을 진행합니다.

---

## MCP 서버

MCP 서버 목록은 `.mcp.json`에서 중앙 관리됩니다. 인증 방식에 따라 세 가지로 구분됩니다.

### OAuth 방식 (브라우저 클릭 인증)

`/mcp`에서 해당 서버를 선택하면 브라우저 OAuth 인증 화면이 열립니다. 로그인하면 자동으로 연결됩니다.

| 서버 | 용도 |
|------|------|
| **Figma** | 디자인 파일 조회, 코드 변환, FigJam 다이어그램 |
| **Linear** | 이슈/프로젝트 관리, 상태 추적 |
| **Confluence** | 페이지 조회/생성/편집, 검색 |
| **Datadog** | 로그/메트릭/모니터/대시보드 조회 |
| **Sentry** | 에러 이슈 조회/분석, 이벤트 검색 |
| **Slack** | 채널 읽기, 메시지 전송, 검색, 캔버스 |

### `.env` 설정 방식

`.env` 파일에 인증 정보를 입력한 뒤 `/mcp`에서 서버를 연결합니다.

**Google Workspace** (Gmail, Drive, Calendar 등) — OAuth Client

1. [Google Cloud Console](https://console.cloud.google.com/)에서 OAuth 2.0 Client ID를 발급받습니다.
   - 승인된 리디렉션 URI에 `http://localhost:8000/oauth2callback`을 추가합니다.
2. `.env`에 입력합니다.
   ```
   GOOGLE_OAUTH_CLIENT_ID=your_client_id
   GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
   ```
3. `/mcp`에서 google_workspace 서버를 연결합니다.
4. 최초 사용 시 브라우저에서 Google 계정 인증을 완료하면 이후 자동 동작합니다.

**DataHub** — Personal Access Token

1. [DataHub 웹 UI](https://datahub.buzzvil.dev)에서 Settings → Access Tokens → Generate Personal Access Token으로 토큰을 발급받습니다.
2. `.env`에 입력합니다.
   ```
   DATAHUB_GMS_URL=https://datahub.buzzvil.dev/api/gms
   DATAHUB_GMS_TOKEN=your_datahub_token
   ```
3. `/mcp`에서 datahub 서버를 연결합니다.

### CLI 설치 + 인증 방식

별도 CLI를 설치하고, 터미널에서 인증을 완료한 뒤 MCP 서버를 재시작합니다.

**Salesforce** — Salesforce CLI + Org 인증

1. Salesforce CLI를 설치합니다.
   ```bash
   npm install -g @salesforce/cli
   ```
2. Salesforce Org에 로그인합니다.
   ```bash
   sf org login web --alias my-org --set-default
   ```
   - Sandbox org인 경우 `--instance-url https://test.salesforce.com` 플래그를 추가합니다.
3. 인증 확인:
   ```bash
   sf org list
   ```
4. `/mcp`에서 salesforce 서버를 **재시작**합니다. (인증 전에 시작된 서버는 org 정보를 인식하지 못합니다.)

**OpenPencil** — Bun + OpenPencil MCP/CLI + 데스크톱 앱

Figma `.fig` 파일을 로컬에서 열고, 구조 탐색·디자인 토큰 분석·이미지/SVG 내보내기·프로그래밍 방식의 디자인 수정 등을 수행하는 MCP 서버입니다. CLI는 코드 변환(JSX/Tailwind), XPath 쿼리 등 MCP에 없는 기능을 제공합니다.

1. Bun 런타임을 설치합니다.
   ```bash
   brew install oven-sh/bun/bun
   ```
2. 데스크톱 앱을 설치합니다. 디자인 결과물을 시각적으로 확인할 때 사용합니다.
   ```bash
   brew install open-pencil/tap/open-pencil
   ```
3. MCP 서버와 CLI를 글로벌로 설치합니다.
   ```bash
   bun add -g @open-pencil/mcp @open-pencil/cli
   ```
4. 설치 후 `openpencil-mcp`, `openpencil` 명령어를 터미널에서 사용할 수 있도록 PATH를 등록합니다.
   - `bun add -g` 실행 시 안내되는 글로벌 bin 경로(예: `~/.bun/bin`)를 셸 설정 파일에 추가합니다.
   ```bash
   # ~/.zshrc 또는 ~/.bashrc에 추가
   export PATH="$HOME/.bun/bin:$PATH"
   ```
   - 변경 후 터미널을 재시작하거나 `source ~/.zshrc`를 실행합니다.
5. `/mcp`에서 open-pencil 서버를 연결합니다.

**Penpot** — MCP 서버 + 브라우저 플러그인

오픈소스 브라우저 기반 디자인 도구입니다. MCP로 열려 있는 디자인을 실시간 조작하고, REST API로 파일/프로젝트를 관리합니다.

1. [design.penpot.app](https://design.penpot.app)에서 회원가입합니다.
2. Access Token을 발급받습니다.
   - 좌측 하단 프로필 → **Your account** → **Access tokens** → **Generate new token**
3. `.env`에 입력합니다.
   ```
   PENPOT_TOKEN=your_penpot_token
   ```
4. MCP 서버는 스킬이 필요 시 자동으로 시작합니다. 서버가 시작되면 브라우저에서 플러그인을 연결합니다.
   - `Cmd+Alt+P` → `http://localhost:4400/manifest.json` 입력 → **Connect to MCP server** 클릭

### 자동 연결

| 서버 | 설명 |
|------|------|
| **Playwright** | 별도 인증 없이 자동 연결. 브라우저 자동화에 사용 |
| **DuckDB** | 로컬 `local.duckdb` 파일 기반. `duckdb-init.sql`로 초기화 |

---

## 스킬 (Skills)

스킬은 여러 도구를 조합하여 특정 업무를 자동화하는 커스텀 명령어입니다. `.claude/skills/` 디렉토리에서 관리되며, 각 스킬의 `SKILL.md`에 상세 사용법이 정의되어 있습니다.

`/스킬명`으로 직접 실행할 수도 있고, 자연어로 요청해도 Claude가 맥락을 파악하여 알맞은 스킬을 자동으로 실행합니다. 예를 들어 "슬랙 ad-management 채널 이번 주 요약해줘"라고 말하면 `/slack-summary`가 실행됩니다.

새로운 스킬을 추가하려면 `.claude/skills/` 아래에 디렉토리를 만들고 `SKILL.md` 파일을 작성하면 됩니다.

### 스킬 목록

#### Slack

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **Slack 요약** | `/slack-summary` | 채널 대화 분석 및 주제/과제/이슈 요약 | Slack MCP (OAuth) |

- 메시지 전송, 채널 조회, 검색 등 일반 Slack 작업은 **Slack MCP**를 통해 자연어로 직접 요청하면 됩니다.
- `/slack-summary`는 채널 대화를 기간별로 분석하여 구조화된 보고서를 생성하는 전용 스킬입니다.

#### 광고 운영

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **Dash 관리** | `/dash-manage` | 라인아이템, 크리에이티브, 유닛, 앱, 조직, 애드그룹 등 광고 데이터 조회/관리 | `DASH_ID`, `DASH_PW` (세션 자동 관리) |

Dash 환경 변수:
```
DASH_API_GATEWAY_URL=https://dash-api-gateway.eks.buzzvil.com
DASH_ID=your_email@buzzvil.com
DASH_PW=your_password
DASH_PROD_SESSION_COOKIE=자동으로_저장됨
DASH_OTHER_SESSION_COOKIE=자동으로_저장됨
```
- prod 쿠키는 안정적으로 유지하고, 그 외 환경은 `DASH_OTHER_SESSION_COOKIE`에 덮어씌워 사용합니다.
- 환경 URL은 `dash-api-gateway-{env}` 패턴으로 동적 생성됩니다.

#### 배포 및 인프라

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **Gitploy 관리** | `/gitploy-manage` | 배포 생성, 상태 조회, 환경 잠금/해제, 브랜치/커밋 조회 | `GITPLOY_SESSION_COOKIE` (Playwright 자동 갱신) |
| **Argo CD 관리** | `/argocd-manage` | 앱 배포 상태 조회, 싱크, 롤백, 로그 확인 | `argocd` CLI (SSO 인증) |
| **Argo Workflows 관리** | `/argo-workflows-manage` | 워크플로우 목록/상태/로그 조회, 제출, 재시도 | `argo` CLI + 토큰 (Playwright 추출) |
| **AWS 관리** | `/aws-manage` | S3, EC2, EKS, IAM, Lambda, CloudWatch 등 AWS 리소스 조회/관리 | aws-vault (SSO 인증) |
| **Teleport 관리** | `/teleport-manage` | DB 접속, EKS/Kubernetes 접근, SSH, 접근 권한 요청/조회 | `tsh` CLI (SSO 인증) |

**Gitploy** 설정:
```
GITPLOY_URL=https://gitploy.buzzvil.dev
GITPLOY_SESSION_COOKIE=자동으로_저장됨
```
- 최초 설정 시 `/gitploy-manage`를 실행하면 Playwright 브라우저가 열리고 GitHub OAuth 로그인 후 자동으로 쿠키가 저장됩니다.
- **env에 "prod"가 포함된 환경에는 배포/롤백이 차단됩니다.**

**Argo CD** 설정:
```bash
brew install argocd
argocd login argo-cd.buzzvil.dev --sso --grpc-web  # 최초 또는 세션 만료 시
```

**Argo Workflows** 설정:
```bash
brew install argo
```
```
ARGO_WORKFLOWS_URL=https://argo.buzzvil.dev
ARGO_WORKFLOWS_DEV_URL=https://argo-dev.buzzvil.dev
ARGO_WORKFLOWS_TOKEN=자동으로_저장됨
ARGO_WORKFLOWS_DEV_TOKEN=자동으로_저장됨
```
- 최초 설정 시 `/argo-workflows-manage`를 실행하면 Playwright 브라우저가 열리고 SSO 로그인 후 자동으로 토큰이 저장됩니다.

**AWS** 설정:
- aws-vault와 AWS CLI가 설치되어 있어야 합니다.
- SSO 세션이 만료되면 `aws-vault login`으로 재인증합니다.

**Teleport** 설정:
- macOS: https://goteleport.com/download/client-tools/ 에서 `tsh` CLI를 설치합니다.
- 최초 또는 세션 만료 시 `tsh login`으로 브라우저 SSO 재인증합니다.

#### 모니터링 및 데이터

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **Redash 관리** | `/redash-manage` | 쿼리 조회/실행, 대시보드 조회, 데이터소스 탐색 | `REDASH_SESSION_COOKIE` (Playwright 자동 갱신) |
| **Grafana 관리** | `/grafana-manage` | Loki 로그, Prometheus 메트릭, 대시보드, 알림 조회 | `GRAFANA_SESSION_COOKIE` (Playwright 자동 갱신) |

**Redash** 설정:
```
REDASH_URL=https://redash.buzzvil.com
REDASH_SESSION_COOKIE=자동으로_저장됨
```
- 최초 설정 시 `/redash-manage`를 실행하면 Playwright 브라우저가 열리고 구글 로그인 후 자동으로 쿠키가 저장됩니다.

**Grafana** 설정:
```
GRAFANA_URL=https://grafana.buzzvil.dev
GRAFANA_SESSION_COOKIE=자동으로_저장됨
```
- 최초 설정 시 `/grafana-manage`를 실행하면 Playwright 브라우저가 열리고 구글 로그인 후 자동으로 쿠키가 저장됩니다.

#### GitHub

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **GitHub 관리** | `/github-manage` | PR 생성/조회/리뷰, 이슈 관리, 레포 조회, Actions 확인 등 | `GITHUB_TOKEN` (`gh` CLI) |

GitHub 설정:
```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```
- [GitHub 토큰 발급 페이지](https://github.com/settings/tokens)에서 Classic 토큰을 발급받습니다 (`repo` scope 필요).
- `gh` CLI가 설치되어 있어야 합니다: `brew install gh`

#### 디자인

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **Penpot 관리** | `/penpot-manage` | UI 디자인 생성/편집, CSS/HTML 추출, 디자인 토큰, 파일/프로젝트 관리 | `PENPOT_TOKEN` + MCP 서버 |
| **OpenPencil 관리** | `/open-pencil-manage` | .fig 파일 생성/편집, JSX/Tailwind 코드 변환, XPath 쿼리 | `openpencil-mcp` (Bun) |

- **Penpot**: 브라우저 기반 디자인 도구. MCP(`execute_code`)로 디자인을 실시간 조작하고 REST API로 파일을 관리합니다. 텍스트/이모지 렌더링이 정상 동작합니다.
- **OpenPencil**: 로컬 .fig 파일 기반. `render` 도구로 JSX→디자인 변환, CLI로 디자인→JSX/Tailwind 코드 변환을 지원합니다. 현재 Figma 호환성 수정 릴리즈를 대기 중입니다.

#### 코드 품질

| 스킬 | 명령어 | 설명 | 인증 |
|------|--------|------|------|
| **Sentry 수정** | `/sentry-fix` | Sentry 이슈 분석 → adserver 코드 원인 조사 → 수정 PR 생성 | Sentry MCP + `gh` CLI + `ADSERVER_PATH` |

---

## 팀 자산 (`team/`)

`team/` 디렉토리는 ADM 팀의 자산을 관리하는 공간입니다. 팀에 대한 소개, 멤버 정보, 문서, 자원 등 팀 운영에 필요한 모든 것을 이곳에서 기록하고 관리합니다.

이 디렉토리에는 다양한 하위 디렉토리가 존재할 수 있습니다:
- **멤버 디렉토리** (예: `david/`, `elle/`, `frank/`, `jetty/`) — 각 팀원의 역할, 담당 업무, 보유 기술, 관리 자원 등
- **그 외 디렉토리** (예: `docs/` 등) — 팀 공유 문서, 가이드, 정책 등 팀 단위 자산

필요에 따라 새로운 디렉토리나 문서를 자유롭게 추가해 나갈 예정입니다.

---

## 프로젝트 구조

```
ad-management-ai/
├── .claude/
│   ├── skills/            ← 커스텀 스킬 정의 (각 디렉토리의 SKILL.md 참고)
│   └── settings.json      ← Claude Code 설정
├── adm/                   ← Python 유틸리티
│   ├── cmd/               ← CLI 명령어
│   └── lib/               ← 공통 라이브러리
├── team/                  ← 팀 자산 (멤버 정보, 역할, 자원 등)
│   ├── david/
│   │── elle/
│   │── frank/
│   └── jetty/
├── .mcp.json              ← MCP 서버 목록 (중앙 관리)
├── .env.example           ← 환경 변수 템플릿
├── .env                   ← 환경 변수 (git 미추적)
├── pyproject.toml         ← Python 프로젝트 설정
├── CLAUDE.md              ← AI 컨텍스트 설정
└── README.md
```
