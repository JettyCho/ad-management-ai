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

아래 서비스들은 `.env`에 인증 정보를 입력해야 합니다.

**Slack** (User OAuth Token):

1. [Slack App 설정 페이지](https://api.slack.com/apps)에서 팀 Slack App을 선택합니다.
2. **OAuth & Permissions**에서 **User OAuth Token** (`xoxp-`로 시작)을 복사합니다.
3. `.env`에 입력합니다.
   ```
   SLACK_USER_TOKEN=xoxp-xxxxxxxxxxxx
   ```

**GitHub** (Personal Access Token):

1. [GitHub 토큰 발급 페이지](https://github.com/settings/tokens)에서 토큰을 발급받습니다.
2. `.env`에 입력합니다.
   ```
   GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   ```

**Google Workspace** (OAuth Client ID):

1. [Google Cloud Console](https://console.cloud.google.com/)에서 OAuth 2.0 Client ID를 발급받습니다.
   - 승인된 리디렉션 URI에 `http://localhost:8000/oauth2callback`을 추가합니다.
2. `.env`에 입력합니다.
   ```
   GOOGLE_OAUTH_CLIENT_ID=your_client_id
   GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
   ```

**DataHub** (Personal Access Token):

1. [DataHub 웹 UI](https://datahub.buzzvil.dev)에서 Settings → Access Tokens → Generate Personal Access Token으로 토큰을 발급받습니다.
2. `.env`에 입력합니다.
   ```
   DATAHUB_GMS_URL=https://datahub.buzzvil.dev/api/gms
   DATAHUB_GMS_TOKEN=your_datahub_token
   ```

**Redash** (쿠키 세션 인증):

API Key 없이 브라우저 구글 로그인 세션으로 인증합니다. 최초 설정 시 `/redash-manage`를 실행하면 Playwright 브라우저가 열리고 구글 로그인 후 자동으로 쿠키가 `.env`에 저장됩니다.
```
REDASH_URL=https://redash.buzzvil.com
REDASH_SESSION_COOKIE=자동으로_저장됨
```

**Grafana** (쿠키 세션 인증):

Redash와 동일한 방식입니다. Service Account Token 없이 브라우저 구글 로그인 세션으로 인증합니다. 최초 설정 시 `/grafana-manage`를 실행하면 Playwright 브라우저가 열리고 구글 로그인 후 자동으로 쿠키가 `.env`에 저장됩니다.
```
GRAFANA_URL=https://grafana.buzzvil.dev
GRAFANA_SESSION_COOKIE=자동으로_저장됨
```

**Dash (Ad Dashboard)** (ID/PW 세션 인증):

Buzzvil Ad Dashboard(dash-api-gateway)의 REST API를 curl로 직접 호출합니다. 대시보드 계정의 ID/PW로 로그인하여 세션 쿠키를 획득하며, 세션 만료 시 자동으로 재로그인합니다. 환경은 동적으로 결정됩니다 (prod가 기본, 그 외 환경명 지정 시 `dash-api-gateway-{env}` 패턴).
```
DASH_API_GATEWAY_URL=https://dash-api-gateway.eks.buzzvil.com
DASH_ID=your_email@buzzvil.com
DASH_PW=your_password
DASH_PROD_SESSION_COOKIE=자동으로_저장됨
DASH_OTHER_SESSION_COOKIE=자동으로_저장됨
```

**Gitploy** (쿠키 세션 인증):

GitHub OAuth 로그인 세션으로 인증합니다. 최초 설정 시 `/gitploy-manage`를 실행하면 Playwright 브라우저가 열리고 GitHub 로그인 후 자동으로 쿠키가 `.env`에 저장됩니다. **env에 "prod"가 포함된 환경에는 배포/롤백이 차단됩니다.**
```
GITPLOY_URL=https://gitploy.buzzvil.dev
GITPLOY_SESSION_COOKIE=자동으로_저장됨
```

**Argo Workflows** (Playwright 토큰 인증):

`argo` CLI가 SSO를 지원하지 않으므로, 브라우저 SSO 로그인 후 토큰을 추출하여 사용합니다. 최초 설정 시 `/argo-workflows-manage`를 실행하면 Playwright 브라우저가 열리고 SSO 로그인 후 자동으로 토큰이 `.env`에 저장됩니다.
```
ARGO_WORKFLOWS_URL=https://argo.buzzvil.dev
ARGO_WORKFLOWS_DEV_URL=https://argo-dev.buzzvil.dev
ARGO_WORKFLOWS_TOKEN=자동으로_저장됨
ARGO_WORKFLOWS_DEV_TOKEN=자동으로_저장됨
```

### 3. MCP 서버 인증

MCP 서버 목록은 `.mcp.json`에서 중앙 관리됩니다.

**대부분의 서비스** (OAuth 방식):

Claude Code를 실행한 뒤 `/mcp` 명령어에서 각 서비스를 선택하면 브라우저 OAuth 인증 화면이 열립니다. 로그인하면 자동으로 연결됩니다.

**Salesforce** (CLI 설치 + Org 인증):

1. Salesforce CLI를 설치합니다.
   ```bash
   npm install -g @salesforce/cli
   ```
2. Salesforce Org에 로그인합니다.
   ```bash
   sf org login web --alias my-org --set-default
   ```
3. `/mcp`에서 salesforce 서버를 **재시작**합니다.

### 4. Skill 기반 도구

MCP가 아닌 CLI로 직접 동작하는 Skill 기반 도구들이 `.claude/skills/` 디렉토리에 정의되어 있습니다. 각 스킬의 `SKILL.md`를 참고하세요.

### 5. 연결 확인

Claude Code를 실행하면 MCP 서버 연결 상태를 확인해 주세요. 연결되지 않은 서비스가 있으면 안내에 따라 인증을 진행합니다.

---

## 스킬 (Skills)

스킬은 여러 도구를 조합하여 특정 업무를 자동화하는 커스텀 명령어입니다. `.claude/skills/` 디렉토리에서 관리됩니다.

`/스킬명`으로 직접 실행할 수도 있고, 자연어로 요청해도 Claude가 맥락을 파악하여 알맞은 스킬을 자동으로 실행합니다. 예를 들어 "슬랙 ad-management 채널 이번 주 요약해줘"라고 말하면 `/slack-summary`가 실행됩니다.

새로운 스킬을 추가하려면 `.claude/skills/` 아래에 디렉토리를 만들고 `SKILL.md` 파일을 작성하면 됩니다.

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
