# ADM 팀 AI 작업 공간

ADM(Ad Management) 팀이 사용하는 AI 기반 업무 자동화 프로젝트입니다.

## 용어 확인 원칙

**확실하지 않은 용어는 절대 추측하지 않는다.** 사용자가 언급한 서비스명, 프로젝트명, 팀 용어 등의 의미가 불확실할 때는 아래 순서대로 확인하고, 확인되기 전에는 행동(도구 호출, 코드 작성 등)하지 않는다.

1. **`team/` 디렉토리 확인** — `team/README.md`와 하위 README 파일들에 서비스, 프로젝트, 용어 정의가 정리되어 있다. 가장 먼저 여기서 찾는다.
2. **프로젝트 내 검색** — `team/`에서 찾지 못하면 현재 프로젝트의 코드, 설정 파일, 문서에서 유사한 단어를 검색한다.
3. **주어진 컨텍스트에서 추론** — 대화 맥락, 열려 있는 파일, 최근 작업 이력 등 현재 컨텍스트에서 논리적으로 추론한다.
4. **외부 조사** — 위 단계로 부족하면 인터넷 검색 등으로 배경 지식을 확보한 뒤 다시 추론한다.
5. **사용자에게 질문** — 위 모든 단계를 거쳐도 확신이 없고, 잘못된 해석이 후속 작업에 영향을 줄 수 있다면 사용자에게 직접 묻는다.

핵심: "아마 이것일 것이다"라는 추측으로 행동하지 않는다. 확인 비용은 낮고, 잘못된 추측의 비용은 높다.

## 팀 자산 (`team/`)

`team/` 디렉토리는 ADM 팀의 자산을 관리하는 핵심 공간이다. 멤버 정보, 팀 문서, 자원 등 팀 운영에 필요한 모든 것이 이곳에서 관리된다.

- 하위 디렉토리에는 멤버 디렉토리(예: `david/`, `elle/`, `frank/`, `jetty/`)뿐 아니라, 팀 공유 문서 등 다양한 자산 디렉토리(예: `docs/`)가 존재할 수 있다.
- 팀원 정보, 팀 공유 문서, 자원 등 팀과 관련된 맥락이 필요할 때 반드시 `team/` 디렉토리를 우선 확인한다.
- 현재 사용자가 누구인지는 `.env`의 `ME` 값으로 식별한다. 해당 값과 일치하는 `team/{ME}/` 디렉토리에서 사용자의 상세 정보(역할, 담당 업무, 연락처 등)를 확인할 수 있다.
- **`team/` 폴더 내의 모든 `README.md`를 반드시 읽어야 한다.** 팀원의 이름, 이메일, 각종 서비스 ID, 담당 프로젝트의 코드 위치 등 핵심 정보가 README에 기록되어 있다. 특정 멤버 정보나 프로젝트 위치를 모를 때는 `team/` 내 README 파일들을 확인하면 대부분 알아낼 수 있다.

## 도구 우선 원칙

**어떤 요청이든 행동하기 전에, 사용 가능한 MCP 서버와 Skill을 먼저 검토하라.** 직접 구현하거나 우회하기 전에 이미 연결된 도구로 해결할 수 있는지 판단하고, 가능하다면 반드시 활용한다. 도구가 있는데 안 쓰는 것은 낭비다.

## MCP 서버 연결 확인

외부 도구(GitHub, Linear, Figma, Confluence, Datadog 등)를 사용해야 할 때, 반드시 해당 MCP 서버가 연결되어 있는지 먼저 확인한다. 연결되지 않은 서버의 도구를 호출하면 실패하므로, 사용자에게 연결 방법을 안내한다.

### 연결 방법

- **Figma, Linear, Confluence, Datadog, Sentry 등**: `/mcp`에서 해당 서버를 선택하면 OAuth 인증 화면이 열린다. 브라우저에서 인증을 완료하면 자동으로 연결된다.
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

### CLI 설치 + 인증이 필요한 서비스

아래 서비스들은 OAuth 클릭 한 번으로 연결되지 않는다. 별도 CLI를 설치하고, 터미널에서 인증을 완료한 뒤, MCP 서버를 재시작해야 한다.

- **Salesforce**: Salesforce CLI(`sf`) 설치 + Org 인증 방식.
  1. Salesforce CLI를 설치한다.
     ```bash
     npm install -g @salesforce/cli
     ```
  2. 터미널에서 Salesforce Org에 로그인한다. 브라우저가 열리면 Salesforce 계정으로 로그인하고 권한을 허용한다.
     ```bash
     sf org login web --alias my-org --set-default
     ```
     - Sandbox org인 경우 `--instance-url https://test.salesforce.com` 플래그를 추가한다.
  3. 인증이 완료되었는지 확인한다.
     ```bash
     sf org list
     ```
  4. `/mcp`에서 salesforce 서버를 **재시작**한다. (이미 연결된 상태라도, 인증 전에 시작된 서버는 org 정보를 인식하지 못하므로 반드시 재시작해야 한다.)

## Skill 기반 도구

MCP 서버가 아닌, CLI(curl 등)로 직접 동작하는 Skill 기반 도구들이다. `.env`에 인증 정보를 설정하면 사용할 수 있다.

- **Slack** (`slack-manage`, `slack-summary`): curl + Slack Web API 방식. User Token(`xoxp-`)을 사용하여 사용자 본인 이름으로 메시지 전송, 채널 조회, 검색, 요약 등이 가능하다.
  - `.env`에 `SLACK_USER_TOKEN` 설정 필요. [Slack App 설정 페이지](https://api.slack.com/apps)의 OAuth & Permissions에서 User OAuth Token을 복사한다.
- **AWS** (`aws-manage`): aws-vault + AWS CLI 방식. SSO 인증으로 AWS 리소스를 조회/관리한다.
  - aws-vault와 AWS CLI가 설치되어 있어야 한다. SSO 세션이 만료되면 `aws-vault login`으로 재인증한다.
