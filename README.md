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

### 2. MCP 서버 인증

이 프로젝트에서 사용하는 외부 서비스(MCP 서버) 목록은 `.mcp.json` 파일에서 중앙 관리됩니다. 어떤 서비스가 연결되어 있는지는 해당 파일을 확인해 주세요.

**대부분의 서비스** (OAuth 방식):

Claude Code를 실행한 뒤 `/mcp` 명령어에서 각 서비스를 선택하면 브라우저 OAuth 인증 화면이 열립니다. 로그인하면 자동으로 연결됩니다.

**GitHub** (예외 — 토큰 방식):

1. `.env.example`을 복사하여 `.env` 파일을 생성합니다.
   ```bash
   cp .env.example .env
   ```
2. [GitHub 토큰 발급 페이지](https://github.com/settings/tokens)에서 Personal Access Token을 발급받아 `.env`에 입력합니다.
   ```
   GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   ```

### 3. 연결 확인

Claude Code를 실행하면 모든 MCP 서버의 연결 상태를 확인하셔야 합니다. 연결되지 않은 서비스가 있으면 안내에 따라 인증을 진행해 주세요.

---

## 스킬 (Skills)

스킬은 여러 도구를 조합하여 특정 업무를 한 번에 수행할 수 있도록 만든 커스텀 명령어입니다.

스킬 파일은 `.claude/skills/` 디렉토리에서 관리되며, Claude Code에서 `/스킬명` 형태로 바로 실행할 수 있습니다.

### 스킬 사용 예시

```
/slack-summary #ad-management 최근 3일
/slack-summary general이랑 dev-backend 이번 주
```

새로운 스킬을 추가하고 싶다면 `.claude/skills/` 아래에 디렉토리를 만들고 `SKILL.md` 파일을 작성하면 됩니다.

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
│   ├── skills/          ← 커스텀 스킬 정의
│   │   └── slack-summary/
│   │       └── SKILL.md
│   └── settings.json    ← Claude Code 설정
├── team/                ← 팀 자산 (멤버 정보, 역할, 자원 등)
│   ├── david/
│   ├── elle/
│   ├── frank/
│   └── jetty/
├── .mcp.json            ← MCP 서버 목록 (중앙 관리)
├── .env.example         ← 환경 변수 템플릿
├── .env                 ← 환경 변수 (git 미추적)
├── CLAUDE.md            ← AI 컨텍스트 설정
└── README.md
```
