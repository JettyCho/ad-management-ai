---
name: argo-workflows-manage
description: Argo Workflows CLI를 사용하여 워크플로우 목록 조회, 상태 확인, 로그 조회, 제출, 재시도 등을 수행합니다. CLI SSO 미지원으로 Playwright 브라우저 로그인 후 토큰을 추출하여 사용합니다. TRIGGER when: 사용자가 Argo Workflows, 워크플로우 실행, 워크플로우 상태, 워크플로우 로그, cron workflow 등을 요청할 때. "argo workflows", "아르고 워크플로우", "워크플로우", "workflow", "argo list", "argo submit", "cron workflow" 등 관련 키워드가 포함될 때 사용. 단, Argo CD(배포/싱크/롤백)와는 다른 도구이므로 구분한다.
argument-hint: (자연어로 Argo Workflows 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_run_code, mcp__playwright__browser_evaluate, mcp__playwright__browser_close
---

# Argo Workflows 관리 (argo CLI + Playwright 토큰 인증)

## 환경 설정

### CLI 설치 확인

```bash
argo version --short
```

설치되어 있지 않으면 사용자에게 안내한다:
```bash
brew install argo
```

### 환경 변수

`.env` 파일에서 아래 값을 읽어 사용한다.

```bash
source .env
```

- `ARGO_WORKFLOWS_URL`: Argo Workflows 서버 URL (예: `https://argo.buzzvil.dev`)
- `ARGO_WORKFLOWS_DEV_URL`: Argo Workflows Dev 서버 URL (예: `https://argo-dev.buzzvil.dev`)
- `ARGO_WORKFLOWS_TOKEN`: Prod 서버용 Bearer 토큰 (브라우저 SSO 로그인 후 획득)
- `ARGO_WORKFLOWS_DEV_TOKEN`: Dev 서버용 Bearer 토큰 (Prod과 별도 — 서버 간 토큰이 호환되지 않음)

### 서버 환경

| 환경 | URL | 설명 |
|------|-----|------|
| Production | `https://argo.buzzvil.dev` | 프로덕션 워크플로우 |
| Staging (Dev) | `https://argo-dev.buzzvil.dev` | 스테이징 워크플로우 |

사용자가 환경을 명시하지 않으면 Production(`ARGO_WORKFLOWS_URL`)을 기본으로 사용한다. "dev", "staging", "스테이징" 등을 언급하면 Dev(`ARGO_WORKFLOWS_DEV_URL`)를 사용한다.

---

## 인증 방식

`argo` CLI는 SSO 로그인을 지원하지 않는다. **브라우저 SSO 로그인 후 토큰을 추출**하여 사용한다.

### 토큰이 있을 때 (정상 흐름)

**중요**: 토큰은 반드시 `ARGO_TOKEN` **환경변수**로 전달해야 한다. `--token` 플래그는 Kubernetes API 서버용이므로 Argo Server 인증에는 동작하지 않는다.

```bash
ARGO_SERVER="${ARGO_WORKFLOWS_URL#https://}:443" \
ARGO_SECURE=true ARGO_HTTP1=true \
ARGO_TOKEN="$ARGO_WORKFLOWS_TOKEN" \
argo list -n argo-workflows 2>&1 | head -5
```

정상 출력이 나오면 토큰 유효.

### 토큰이 없거나 만료되었을 때 (재로그인)

1. Playwright 브라우저로 Argo Workflows 로그인 페이지에 접속한다.
2. SSO Login 버튼을 클릭하여 GitHub/Google 로그인을 진행한다.
3. 로그인 완료 후 `authorization` 쿠키에서 토큰을 추출한다.
4. `.env` 파일의 `ARGO_WORKFLOWS_TOKEN` 값을 업데이트한다.
5. 브라우저를 닫는다.

```
[Playwright 로그인 절차]
1. browser_navigate → $ARGO_WORKFLOWS_URL (또는 $ARGO_WORKFLOWS_DEV_URL)
2. browser_snapshot → Login 페이지 확인 (SSO Login 버튼)
3. browser_click → SSO Login 버튼 클릭
4. (GitHub/Google 로그인 화면 처리)
5. browser_snapshot → 로그인 완료 확인 (Workflows 화면)
6. browser_run_code → 토큰 추출:
   async (page) => {
     const targetDomain = 'argo.buzzvil.dev'; // Dev면 'argo-dev.buzzvil.dev'
     const cookies = await page.context().cookies();
     const auth = cookies.find(c => c.name === 'authorization' && c.domain === targetDomain);
     return auth ? auth.value : null;
   }
7. 추출된 값에서 앞뒤 따옴표(")를 제거한 후 .env 파일의 ARGO_WORKFLOWS_TOKEN 값 업데이트
   (값을 작은따옴표로 감싸서 저장: ARGO_WORKFLOWS_TOKEN='Bearer v2:...')
8. browser_close → 브라우저 닫기 (**토큰 추출 직후 즉시 실행 — .env 저장과 browser_close를 연속으로 처리하고, 이후에 토큰 검증 등 나머지 작업을 진행한다**)
```

**주의: 쿠키 추출 시 반드시 도메인으로 필터링해야 한다.** Playwright 브라우저에는 Prod(`argo.buzzvil.dev`)와 Dev(`argo-dev.buzzvil.dev`) 쿠키가 동시에 존재할 수 있다. 도메인 필터 없이 `cookies.find(c => c.name === 'authorization')`만 사용하면 다른 서버의 토큰을 가져올 수 있으며, Prod/Dev 서버는 암호화 키가 달라 호환되지 않으므로 인증이 실패한다.

**참고**: Prod와 Dev 서버는 서로 다른 암호화 키를 사용하므로 **토큰이 호환되지 않는다**. 각 서버별로 별도 로그인하여 토큰을 획득해야 한다. Dev 서버 토큰 획득 시에는 `$ARGO_WORKFLOWS_DEV_URL`로 접속하여 동일한 절차를 수행하고 `ARGO_WORKFLOWS_DEV_TOKEN`에 저장한다.

---

## 명령 실행 방식

**중요**: 토큰은 `ARGO_TOKEN` 환경변수로 전달한다. `--token` 플래그는 사용하지 않는다.

모든 argo 명령은 아래 형식으로 실행한다:

```bash
source .env && \
ARGO_SERVER="${ARGO_WORKFLOWS_URL#https://}:443" \
ARGO_SECURE=true ARGO_HTTP1=true \
ARGO_TOKEN="$ARGO_WORKFLOWS_TOKEN" \
argo {명령} -n {네임스페이스} [옵션]
```

편의를 위해 환경변수를 먼저 export하고 명령을 실행할 수 있다:

```bash
source .env
export ARGO_SERVER="${ARGO_WORKFLOWS_URL#https://}:443"
export ARGO_SECURE=true
export ARGO_HTTP1=true
export ARGO_TOKEN="$ARGO_WORKFLOWS_TOKEN"

argo list -n argo-workflows
```

Dev 서버를 사용할 때는 `ARGO_SERVER`와 `ARGO_TOKEN` 둘 다 바꿔야 한다:

```bash
export ARGO_SERVER="${ARGO_WORKFLOWS_DEV_URL#https://}:443"
export ARGO_TOKEN="$ARGO_WORKFLOWS_DEV_TOKEN"
```

### 네임스페이스

워크플로우는 서비스별 네임스페이스에서 실행된다. `-A` 플래그로 전체 목록을 보거나, 사용자가 언급한 서비스에 맞는 네임스페이스를 지정한다. 네임스페이스를 모를 때는 `argo list -A`로 먼저 확인한다.

주요 네임스페이스 (Prod 기준):

| 네임스페이스 | 서비스 |
|-------------|--------|
| `buzzad` | 광고 서버 (adserver) 관련 워크플로우 |
| `buzzscreen` | 버즈스크린 |
| `adtracker` | 광고 트래커 |
| `billingsvc` | 빌링 서비스 |
| `postbacksvc` | 포스트백 서비스 |
| `statssvc` | 통계 서비스 |
| `argo-workflows` | 인프라/공통 (보통 비어 있음) |

### 모르는 명령이 있을 때

특정 명령의 사용법을 모르면 `--help`를 활용한다:

```bash
argo --help
argo list --help
argo submit --help
argo logs --help
```

---

## 자주 사용하는 명령

### 워크플로우 목록 조회

```bash
# 전체 목록
argo list -n argo-workflows

# 실행 중인 워크플로우만
argo list --running -n argo-workflows

# 완료된 워크플로우만
argo list --completed -n argo-workflows

# 실패한 워크플로우만
argo list --status Failed -n argo-workflows

# 최근 N시간 이내 생성된 것만
argo list --since 1h -n argo-workflows

# 모든 네임스페이스
argo list -A
```

### 워크플로우 상세 조회

```bash
# 워크플로우 상세 정보
argo get {워크플로우명} -n argo-workflows

# JSON 출력
argo get {워크플로우명} -o json -n argo-workflows
```

### 워크플로우 로그

```bash
# 전체 워크플로우 로그
argo logs {워크플로우명} -n argo-workflows

# 실시간 로그 스트리밍
argo logs {워크플로우명} -f -n argo-workflows

# 특정 컨테이너 로그 (-c 옵션)
argo logs {워크플로우명} -n argo-workflows -c {컨테이너명}

# 특정 노드(스텝) 로그
argo logs {워크플로우명} {노드명} -n argo-workflows
```

**로그가 비어 있을 때**: 기본 명령은 `main` 컨테이너의 로그만 보여준다. 로그가 비어 있으면 Pod에 다른 컨테이너가 있을 수 있으므로, `argo get`으로 노드 구조를 확인하고 `-c {컨테이너명}` 옵션으로 다른 컨테이너(예: `workflow-main`)를 시도한다.

### 워크플로우 실시간 모니터링

```bash
# 워크플로우 완료까지 실시간 감시
argo watch {워크플로우명} -n argo-workflows

# 워크플로우 완료까지 대기
argo wait {워크플로우명} -n argo-workflows
```

### 워크플로우 제출

```bash
# YAML 파일에서 제출
argo submit {워크플로우.yaml} -n argo-workflows

# WorkflowTemplate에서 제출
argo submit --from workflowtemplate/{템플릿명} -n argo-workflows

# 파라미터 전달
argo submit {워크플로우.yaml} -p key=value -n argo-workflows
```

### 워크플로우 제어

```bash
# 재시도 (실패한 워크플로우)
argo retry {워크플로우명} -n argo-workflows

# 재제출 (완료된 워크플로우를 새로 실행)
argo resubmit {워크플로우명} -n argo-workflows

# 일시 중지
argo suspend {워크플로우명} -n argo-workflows

# 재개
argo resume {워크플로우명} -n argo-workflows

# 중지 (exit handler 실행)
argo stop {워크플로우명} -n argo-workflows

# 즉시 종료 (exit handler 미실행)
argo terminate {워크플로우명} -n argo-workflows

# 삭제
argo delete {워크플로우명} -n argo-workflows
```

### WorkflowTemplate 관리

```bash
# 템플릿 목록
argo template list -n argo-workflows

# 템플릿 상세
argo template get {템플릿명} -n argo-workflows
```

### CronWorkflow 관리

```bash
# 크론 워크플로우 목록
argo cron list -n argo-workflows

# 크론 워크플로우 상세
argo cron get {크론명} -n argo-workflows

# 크론 일시 중지
argo cron suspend {크론명} -n argo-workflows

# 크론 재개
argo cron resume {크론명} -n argo-workflows
```

---

## 전체 명령어 참조

위 목록은 자주 사용하는 것만 정리한 것이다. 전체 명령어는 아래에서 확인할 수 있다:

- **CLI 공식 문서**: https://argo-workflows.readthedocs.io/en/stable/cli/argo/
- **`argo --help`로 전체 명령어 목록 확인 가능**

### 주요 명령어 카테고리

| 카테고리 | 명령 | 설명 |
|----------|------|------|
| 워크플로우 | `argo list/get/logs/watch/wait` | 워크플로우 조회, 로그, 모니터링 |
| 제출/제어 | `argo submit/retry/resubmit/stop/terminate` | 워크플로우 제출 및 제어 |
| 템플릿 | `argo template` | WorkflowTemplate 관리 |
| 크론 | `argo cron` | CronWorkflow 관리 |
| 아카이브 | `argo archive` | 워크플로우 아카이브 관리 |
| 인증 | `argo auth token` | 현재 토큰 출력 |

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 간단한 `argo list` 명령으로 토큰 유효성을 확인한다. 실패 시 Playwright 재로그인 절차를 진행한다.
2. **워크플로우 제출/중지/삭제는 반드시 사용자에게 확인받는다** — 워크플로우명과 작업 내용을 보여주고 승인 후 실행한다.
3. **조회 명령은 바로 실행한다** — 워크플로우 목록, 상태, 로그, 템플릿 조회 등은 확인 없이 실행한다.
4. **결과를 읽기 좋게 정리한다** — 긴 출력은 핵심 정보만 표 또는 목록으로 정리한다.
5. **에러 발생 시 원인을 분석한다** — 토큰 만료, 워크플로우 미존재, 네임스페이스 오류 등 원인을 파악하여 안내한다.
6. **재로그인 후 브라우저를 닫는다** — Playwright로 로그인한 뒤에는 반드시 `browser_close`로 브라우저를 정리한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
