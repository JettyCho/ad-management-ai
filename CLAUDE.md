# ADM 팀 AI 작업 공간

ADM(Ad Management) 팀이 사용하는 AI 기반 업무 자동화 프로젝트입니다.

## 팀 자산 (`team/`)

`team/` 디렉토리는 ADM 팀의 자산을 관리하는 핵심 공간이다. 멤버 정보, 팀 문서, 자원 등 팀 운영에 필요한 모든 것이 이곳에서 관리된다.

- 하위 디렉토리에는 멤버 디렉토리(예: `david/`, `elle/`, `frank/`, `jetty/`)뿐 아니라, 팀 공유 문서 등 다양한 자산 디렉토리(예: `docs/`)가 존재할 수 있다.
- 팀원 정보, 팀 공유 문서, 자원 등 팀과 관련된 맥락이 필요할 때 반드시 `team/` 디렉토리를 우선 확인한다.

## MCP 서버 연결 확인

외부 도구(Slack, GitHub, Linear, Figma, Confluence, Datadog, Puppeteer 등)를 사용해야 할 때, 반드시 해당 MCP 서버가 연결되어 있는지 먼저 확인한다. 연결되지 않은 서버의 도구를 호출하면 실패하므로, 사용자에게 연결 방법을 안내한다.

### 연결 방법

- **Slack, Figma, Linear, Confluence, Datadog, Sentry 등**: `/mcp`에서 해당 서버를 선택하면 OAuth 인증 화면이 열린다. 브라우저에서 인증을 완료하면 자동으로 연결된다.
- **Puppeteer, Playwright**: 별도 인증 없이 자동으로 연결된다.

### `.env` 설정이 필요한 서비스

아래 서비스들은 `.env` 파일에 인증 정보를 입력해야 한다. `.env.example`을 참고하여 `.env` 파일을 생성한다.

- **GitHub**: Personal Access Token 방식.
  1. [GitHub 토큰 발급 페이지](https://github.com/settings/tokens)에서 토큰을 발급받는다.
  2. `.env` 파일에 `GITHUB_TOKEN=발급받은토큰`을 입력한다.
  3. `/mcp`에서 github 서버를 재연결한다.
- **Google Workspace** (Gmail, Drive, Calendar 등): OAuth + `.env` 방식.
  1. [Google Cloud Console](https://console.cloud.google.com/)에서 OAuth 2.0 Client ID를 발급받는다 (리디렉션 URI: `http://localhost:8000/oauth2callback`).
  2. `.env` 파일에 `GOOGLE_OAUTH_CLIENT_ID`와 `GOOGLE_OAUTH_CLIENT_SECRET`을 입력한다.
  3. `/mcp`에서 google_workspace 서버를 연결한다.
  4. 최초 사용 시 브라우저에서 Google 계정 인증을 완료하면 이후 자동 동작한다.
