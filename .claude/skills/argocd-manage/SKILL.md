---
name: argocd-manage
description: Argo CD CLI를 사용하여 애플리케이션 배포 상태 조회, 싱크, 롤백, 로그 확인 등을 수행합니다. CLI 자체 SSO 인증으로 별도 토큰 없이 동작합니다. TRIGGER when: 사용자가 Argo CD, 배포 상태, 싱크, 롤백, 앱 목록, 배포 히스토리 등을 요청할 때. "argocd", "argo cd", "아르고", "배포 상태", "싱크", "롤백", "deploy", "sync", "rollback" 등 관련 키워드가 포함될 때 사용.
argument-hint: (자연어로 Argo CD 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob
---

# Argo CD 관리 (argocd CLI)

## 환경 설정

### CLI 설치 확인

```bash
argocd version --client --short
```

설치되어 있지 않으면 사용자에게 안내한다:
```bash
brew install argocd
```

### 서버 및 인증

Argo CD 서버: `argo-cd.buzzvil.dev` (하나의 서버에서 모든 환경을 관리)

인증 상태는 `~/.config/argocd/config`에 저장된다. 모든 명령에는 `--grpc-web` 플래그를 붙인다.

### 환경 구분

하나의 Argo CD 서버에서 prod/staging/dev를 모두 관리한다. **앱 이름 prefix**와 **클러스터**로 환경을 구분한다.

**앱 이름 prefix 컨벤션:**

| Prefix | 환경 | 예시 |
|--------|------|------|
| `prod-` | Production | `prod-adserver` |
| `staging-` | Staging | `staging-adserver` |
| `dev-` | Development | `dev-adserver` |
| `beta-` | Beta | `beta-dash-api-gateway` |
| (없음) | 인프라/공통 | `buzzvil-argocd-apps` |

**클러스터:**

| 클러스터 | 환경 |
|----------|------|
| `buzzvil-eks` | Production |
| `buzzvil-eks-dev` | Development |
| `honeyscreen-eks` | Honeyscreen |

사용자가 "dev adserver", "프로덕션 adserver" 등으로 환경을 언급하면 해당 prefix를 붙여 앱을 찾는다. 환경을 명시하지 않으면 사용자에게 어떤 환경인지 확인한다.

```bash
# 인증 상태 확인
argocd account get-user-info --grpc-web
```

### SSO 세션 만료 시 (재로그인)

명령 실행 중 인증 오류가 발생하면:
1. 사용자에게 SSO 세션이 만료되었음을 알린다.
2. 아래 명령을 실행한다. 브라우저가 열리면 사용자가 GitHub/Google 로그인을 완료할 때까지 기다린다.
   ```bash
   argocd login argo-cd.buzzvil.dev --sso --grpc-web
   ```
3. 인증 완료 후 원래 요청했던 명령을 다시 실행한다.

---

## 명령 실행 방식

모든 argocd 명령은 아래 형식으로 실행한다:

```bash
argocd {명령} {서브명령} [옵션] --grpc-web
```

### 모르는 명령이 있을 때

특정 명령의 사용법을 모르면 `--help`를 활용한다:

```bash
argocd --help
argocd app --help
argocd app sync --help
```

---

## 자주 사용하는 명령

### 애플리케이션 목록 조회

```bash
# 전체 앱 목록
argocd app list --grpc-web

# 환경별 필터 (앱 이름 prefix로 grep)
argocd app list --grpc-web | grep "dev-"
argocd app list --grpc-web | grep "prod-"
argocd app list --grpc-web | grep "staging-"

# 특정 프로젝트 필터
argocd app list --project devops --grpc-web

# 상태별 필터
argocd app list --sync-status OutOfSync --grpc-web
argocd app list --health-status Degraded --grpc-web

# 특정 서비스 찾기 (환경 prefix + 서비스명)
argocd app list --grpc-web | grep "adserver"

# JSON 출력 (파싱용)
argocd app list -o json --grpc-web
```

### 애플리케이션 상세 조회

```bash
# 앱 상태 상세
argocd app get {앱명} --grpc-web

# JSON 출력
argocd app get {앱명} -o json --grpc-web

# 리소스 트리
argocd app resources {앱명} --grpc-web
```

### 싱크 (배포)

```bash
# 기본 싱크
argocd app sync {앱명} --grpc-web

# 프루닝 포함 싱크
argocd app sync {앱명} --prune --grpc-web

# 드라이런 (실제 적용하지 않고 확인만)
argocd app sync {앱명} --dry-run --grpc-web

# 싱크 후 완료 대기
argocd app sync {앱명} --prune --wait --grpc-web
```

### Diff (라이브 vs Git 비교)

```bash
argocd app diff {앱명} --grpc-web
```

### 배포 히스토리 및 롤백

```bash
# 배포 히스토리
argocd app history {앱명} --grpc-web

# 롤백 (히스토리 ID 지정)
argocd app rollback {앱명} {히스토리_ID} --grpc-web
```

### 로그 조회

```bash
# 앱 전체 로그
argocd app logs {앱명} --grpc-web

# 실시간 로그 스트리밍
argocd app logs {앱명} -f --grpc-web

# 최근 N줄
argocd app logs {앱명} --tail 100 --grpc-web

# 특정 컨테이너
argocd app logs {앱명} --container {컨테이너명} --grpc-web

# 필터
argocd app logs {앱명} --filter "error" --grpc-web
```

### 매니페스트 조회

```bash
# 현재 적용된 매니페스트
argocd app manifests {앱명} --grpc-web

# Git 소스 매니페스트
argocd app manifests {앱명} --source git --grpc-web
```

### 컨텍스트 관리

```bash
# 현재 컨텍스트 확인
argocd context

# 사용자 정보
argocd account get-user-info --grpc-web
```

---

## 전체 명령어 참조

위 목록은 자주 사용하는 것만 정리한 것이다. 전체 명령어는 아래에서 확인할 수 있다:

- **CLI 공식 문서**: https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd/
- **`argocd --help`로 전체 명령어 목록 확인 가능**

### 주요 명령어 카테고리

| 카테고리 | 명령 | 설명 |
|----------|------|------|
| app | `argocd app` | 애플리케이션 CRUD, 싱크, 롤백, 로그 |
| repo | `argocd repo` | Git 저장소 관리 |
| proj | `argocd proj` | 프로젝트 관리 |
| cluster | `argocd cluster` | 클러스터 관리 |
| account | `argocd account` | 계정/인증 관리 |

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 `argocd account get-user-info --grpc-web`로 인증 상태를 확인한다. 실패 시 재로그인 절차를 진행한다.
2. **싱크/롤백은 반드시 사용자에게 확인받는다** — 앱명과 작업 내용을 보여주고 승인 후 실행한다.
3. **조회 명령은 바로 실행한다** — 앱 목록, 상태, 히스토리, 로그 등은 확인 없이 실행한다.
4. **결과를 읽기 좋게 정리한다** — 긴 출력은 핵심 정보만 표 또는 목록으로 정리한다.
5. **에러 발생 시 원인을 분석한다** — 인증 만료, 앱 미존재, 권한 부족 등 원인을 파악하여 안내한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
