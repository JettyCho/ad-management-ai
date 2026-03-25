---
name: teleport-manage
description: Teleport CLI(tsh)를 사용하여 DB 접속, EKS/Kubernetes 접근, SSH 서버 접속, 접근 권한 요청/조회, 포트포워딩 등을 수행합니다. CLI 자체 SSO 인증으로 별도 토큰 없이 동작합니다. TRIGGER when: 사용자가 Teleport, DB 접속, EKS 접근, SSH, 서버 접속, 접근 권한, 포트포워딩 등을 요청할 때. "teleport", "텔레포트", "tsh", "DB 접속", "디비 접속", "EKS", "쿠버네티스", "k8s", "SSH", "서버 접속", "접근 권한", "access request", "포트포워딩" 등 관련 키워드가 포함될 때 사용. 단, AWS CLI(aws-manage)나 Argo CD(argocd-manage)와는 다른 도구이므로 구분한다.
argument-hint: (자연어로 Teleport 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob
---

# Teleport 관리 (tsh CLI)

## 환경 설정

### CLI 설치 확인

```bash
tsh version
```

설치되어 있지 않으면 사용자에게 안내한다:
- **macOS**: https://goteleport.com/download/client-tools/?os=darwin
- **Teleport Connect (GUI)**: 같은 페이지에서 다운로드 가능 (tsh 번들 포함)

### 서버 및 인증

Teleport Proxy 주소는 `tsh status`의 `Profile URL`에서 확인한다. 인증 상태는 `~/.tsh/` 디렉토리에 저장된다.

```bash
# 인증 상태 확인
tsh status
```

출력에서 `Valid until` 항목으로 세션 만료 시간을 확인한다.

### SSO 세션 만료 시 (재로그인)

명령 실행 중 인증 오류가 발생하면:
1. 사용자에게 SSO 세션이 만료되었음을 알린다.
2. `tsh status`에서 확인한 Proxy 주소로 재로그인한다. 브라우저가 열리면 사용자가 Google/GitHub 로그인을 완료할 때까지 기다린다.
   ```bash
   tsh login --proxy={Profile URL의 호스트:포트}
   ```
3. 인증 완료 후 원래 요청했던 명령을 다시 실행한다.

---

## 명령 실행 방식

모든 tsh 명령은 아래 형식으로 실행한다:

```bash
tsh {명령} {서브명령} [옵션]
```

### 모르는 명령이 있을 때

특정 명령의 사용법을 모르면 `--help`를 활용한다:

```bash
tsh --help
tsh db --help
tsh kube --help
tsh request --help
```

---

## 환경 구분

하나의 Teleport 클러스터에서 prod/staging/dev를 모두 관리한다. **리소스 이름 prefix**로 환경을 구분한다.

### DB 이름 컨벤션

| Prefix | 환경 | 예시 |
|--------|------|------|
| `prod-` | Production | `prod-buzzad-replica` |
| `staging-` | Staging | `staging-buzzad` |
| `dev-` | Development | `dev-consolidated` |

### Kubernetes 클러스터

| 클러스터 | 환경 |
|----------|------|
| `eks-prod` | Production |
| `eks-dev` | Development (staging 포함) |

### 역할 이름 패턴

역할은 `{리소스}-{환경}-{서비스}-{권한유형}` 패턴을 따른다:
- `rds-staging-buzzad-all-viewer-access` → staging buzzad DB 읽기 (즉시 접근)
- `rds-prod-buzzad-all-viewer-request` → prod buzzad DB 읽기 (요청 필요)
- `eks-prod-buzzad-editor-request` → prod EKS buzzad 네임스페이스 편집 (요청 필요)

**`-access` 접미사**: 즉시 사용 가능한 권한
**`-request` 접미사**: 접근 요청(Access Request)을 통해 임시로 획득하는 권한

사용자가 환경을 명시하지 않으면 어떤 환경인지 확인한다.

---

## 데이터베이스 접근

### DB 목록 조회

```bash
# 전체 DB 목록
tsh db ls

# 환경별 필터
tsh db ls | grep staging
tsh db ls | grep prod

# 상세 정보 (JSON)
tsh db ls --format=json
```

### DB 로그인 (인증서 획득)

DB에 연결하기 전에 먼저 로그인하여 인증서를 발급받아야 한다:

```bash
# DB 로그인 (db-user 지정 필수)
tsh db login --db-user=viewer {DB명}
tsh db login --db-user=editor {DB명}

# 특정 데이터베이스(스키마) 지정
tsh db login --db-user=viewer --db-name=buzzad {DB명}
```

### DB 연결

```bash
# 직접 연결 (MySQL CLI)
tsh db connect --db-user=viewer {DB명}

# 특정 데이터베이스 지정
tsh db connect --db-user=viewer --db-name=buzzad {DB명}
```

### DB 연결 정보 확인

```bash
# GUI 클라이언트(TablePlus 등)용 연결 정보
tsh db config {DB명}

# 환경변수 출력
tsh db env {DB명}
```

### DB 로그아웃

```bash
# 특정 DB 로그아웃
tsh db logout {DB명}

# 전체 DB 로그아웃
tsh db logout --all
```

---

## Kubernetes 접근

### 클러스터 목록

```bash
tsh kube ls
```

### 클러스터 로그인

```bash
# 클러스터 로그인 (kubectl context 자동 설정)
tsh kube login {클러스터명}
```

로그인 후 일반 `kubectl` 명령을 사용할 수 있다. Teleport이 투명하게 프록시한다.

### Pod에서 명령 실행

```bash
tsh kube exec -n {네임스페이스} {파드명} -- {명령}
```

---

## 접근 권한 요청 (Access Request)

prod 환경 등 `-request` 접미사 역할은 즉시 접근이 불가하며, Access Request를 통해 임시 권한을 획득해야 한다.

### 요청 목록 조회

```bash
tsh request ls
```

### 요청 가능한 리소스 검색

```bash
# 요청 가능한 역할 검색
tsh request search --kind role

# 특정 키워드로 검색
tsh request search --kind role | grep buzzad

# DB 리소스 검색
tsh request search --kind db

# K8s 리소스 검색
tsh request search --kind kube_cluster
```

### 접근 권한 요청 생성

```bash
# 역할 기반 요청 (사유 필수)
tsh request create --roles={역할명} --reason="작업 사유"

# 리소스 기반 요청
tsh request create --resource=/{리소스종류}/{리소스명} --reason="작업 사유"
```

### 요청 상세 조회

```bash
tsh request show {요청ID}
```

### 승인된 요청으로 로그인

```bash
tsh login --request-id={요청ID}
```

### 요청 해제

```bash
tsh request drop {요청ID}
```

---

## SSH 서버 접근

### 서버 목록

```bash
tsh ls
```

### SSH 접속

```bash
# 서버 접속
tsh ssh {사용자}@{서버명}

# 명령 실행
tsh ssh {사용자}@{서버명} {명령}
```

### 파일 전송

```bash
# 파일 업로드
tsh scp {로컬파일} {사용자}@{서버명}:{원격경로}

# 파일 다운로드
tsh scp {사용자}@{서버명}:{원격경로} {로컬경로}
```

---

## 기타 유용한 명령

### 앱 접근

```bash
# 앱 목록
tsh apps ls

# 앱 로그인
tsh apps login {앱명}
```

### MCP 서버

```bash
# MCP 서버 목록
tsh mcp ls

# MCP 설정 생성 (Claude Code용)
tsh mcp config --all --client-config=claude-code

# DB MCP 설정
tsh mcp db config --db-user=viewer --client-config=claude {DB명}
```

### 세션 관리

```bash
# 활성 세션 목록
tsh sessions ls

# 녹화된 세션 목록
tsh recordings ls

# 세션 재생
tsh play {세션ID}
```

### 클러스터 정보

```bash
# 연결된 클러스터 목록
tsh clusters

# 현재 상태
tsh status
```

---

## 전체 명령어 참조

위 목록은 자주 사용하는 것만 정리한 것이다. 전체 명령어는 아래에서 확인할 수 있다:

- **CLI 공식 문서**: https://goteleport.com/docs/reference/cli/tsh/
- **`tsh --help`로 전체 명령어 목록 확인 가능**

### 주요 명령어 카테고리

| 카테고리 | 명령 | 설명 |
|----------|------|------|
| 인증 | `tsh login/logout/status` | 클러스터 인증 및 세션 관리 |
| DB | `tsh db ls/login/connect/config/env/logout` | 데이터베이스 접근 |
| K8s | `tsh kube ls/login/exec/join` | Kubernetes 클러스터 접근 |
| SSH | `tsh ssh/ls/scp` | SSH 서버 접근 및 파일 전송 |
| 앱 | `tsh apps ls/login/logout/config` | 웹 앱 접근 |
| 접근 요청 | `tsh request ls/show/create/review/search/drop` | Access Request 관리 |
| MCP | `tsh mcp ls/config` | MCP 서버 접근 |
| 세션 | `tsh sessions ls/join/play` | 세션 관리 및 녹화 |

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 `tsh status`로 인증 상태를 확인한다. 실패 시 재로그인 절차를 진행한다.
2. **DB 쓰기 작업은 반드시 사용자에게 확인받는다** — `editor` 권한으로 DB 연결 시 연결 대상과 권한 수준을 보여주고 승인 후 실행한다.
3. **Access Request 생성은 사용자에게 확인받는다** — 요청할 역할과 사유를 보여주고 승인 후 실행한다.
4. **조회 명령은 바로 실행한다** — DB 목록, 클러스터 목록, 상태 확인, 요청 목록 등은 확인 없이 실행한다.
5. **결과를 읽기 좋게 정리한다** — 긴 출력은 핵심 정보만 표 또는 목록으로 정리한다.
6. **에러 발생 시 원인을 분석한다** — 인증 만료, 권한 부족, 리소스 미존재 등 원인을 파악하여 안내한다.
7. **권한이 없을 때 Access Request를 안내한다** — 접근 거부 시 `tsh request search`로 요청 가능한 역할을 찾아 안내한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
