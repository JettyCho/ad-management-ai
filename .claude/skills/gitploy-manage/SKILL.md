---
name: gitploy-manage
description: Gitploy를 curl로 직접 호출하여 배포 생성, 배포 목록 조회, 배포 상태 확인, 환경 잠금/해제, 브랜치/커밋 조회 등을 수행합니다. 쿠키 기반 세션 인증으로 동작합니다. TRIGGER when: 사용자가 Gitploy, 배포, 배포 해줘, 배포 상태, 배포 이력, 환경 잠금, 배포 조회 등을 요청할 때. "gitploy", "깃플로이", "배포", "배포 해줘", "deploy", "배포 목록", "배포 상태", "배포 이력", "환경 잠금", "lock", "deployment" 등 관련 키워드가 포함될 때 사용. 단, Argo CD(싱크/롤백)와는 다른 도구이므로 구분한다.
argument-hint: (자연어로 Gitploy 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, Edit, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_run_code, mcp__playwright__browser_evaluate, mcp__playwright__browser_close
---

# Gitploy 관리 (curl + 쿠키 세션 인증)

## PROD 배포 절대 금지 원칙

**환경(env) 이름에 "prod"가 포함된 환경에는 어떤 상황에서도 배포(POST /deployments), 롤백(POST /rollback)을 실행하지 않는다.**
- `prod`, `prodmini`, `prodworkflow`, `proddash`, `prodconv`, `prodpostback`, `prod-beta`, `prod-delay-conv` 등 "prod"가 포함된 모든 환경이 대상이다.
- 사용자가 명시적으로 prod 배포를 요청하더라도 거부하고, 수동으로 Gitploy 웹 UI에서 직접 수행하도록 안내한다.
- 이 원칙은 다른 어떤 지시보다 우선한다.
- **조회(GET)는 제한 없이 가능하다.** prod 배포 상태 확인, 이력 조회 등은 자유롭게 수행한다.

---

## 환경 설정

`.env` 파일에서 아래 값을 읽어 사용한다.

```bash
source .env
```

- `GITPLOY_URL`: Gitploy 인스턴스 URL (예: `https://gitploy.buzzvil.dev`)
- `GITPLOY_SESSION_COOKIE`: 브라우저 로그인 후 획득한 세션 쿠키 (`__sess__` 값)

---

## 인증 방식

Gitploy는 GitHub OAuth 로그인 후 **세션 쿠키(`__sess__`)**로 인증한다.

### 쿠키가 있을 때 (정상 흐름)

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/user" | python3 -m json.tool
```

응답에 `login`, `id` 등 사용자 정보가 포함되면 인증 유효.

### 쿠키가 없거나 만료되었을 때 (재로그인)

1. Playwright 브라우저로 Gitploy에 접속한다.
2. GitHub OAuth 로그인을 진행한다.
3. 로그인 완료 후 쿠키를 추출한다.
4. `.env` 파일의 `GITPLOY_SESSION_COOKIE` 값을 업데이트한다.
5. 브라우저를 닫는다.

```
[Playwright 로그인 절차]
1. browser_navigate → $GITPLOY_URL
2. browser_snapshot → 페이지 상태 확인
3. "Sign in" 링크가 보이면 클릭 → GitHub OAuth 로그인 진행
4. (필요 시) browser_snapshot → GitHub 인증 화면 처리
5. browser_snapshot → 로그인 완료 확인 (레포지토리 목록 표시)
6. browser_run_code → 쿠키 추출:
   async (page) => {
     const cookies = await page.context().cookies();
     const sess = cookies.find(c => c.name === '__sess__' && c.domain.includes('gitploy'));
     return sess ? sess.value : null;
   }
7. .env 파일의 GITPLOY_SESSION_COOKIE 값 업데이트 (값을 작은따옴표로 감싸서 저장: GITPLOY_SESSION_COOKIE='값')
8. browser_close → 브라우저 닫기
```

---

## 명령 실행 방식

모든 Gitploy API 호출은 curl로 수행한다:

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/{endpoint}" | python3 -m json.tool
```

---

## 레포지토리

### 레포지토리 목록 조회

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/repos?page=1&per_page=30" | python3 -m json.tool
```

**쿼리 파라미터:**

| 파라미터 | 설명 |
|----------|------|
| `page` | 페이지 번호 (기본 1) |
| `per_page` | 페이지당 결과 수 (기본 30) |
| `q` | 검색어 |
| `sort` | 정렬: `latest_deployed_at` 등 |

### 레포지토리 상세 조회

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}" | python3 -m json.tool
```

### 레포지토리 설정 (환경 목록 포함)

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/config" | python3 -m json.tool
```

응답의 `envs` 배열에 배포 가능한 환경 목록과 설정(auto_merge, required_contexts, dynamic_payload 등)이 포함된다.

---

## 배포 (Deployments)

### 배포 목록 조회

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments?page=1&per_page=10" | python3 -m json.tool
```

**쿼리 파라미터:**

| 파라미터 | 설명 |
|----------|------|
| `page` | 페이지 번호 |
| `per_page` | 페이지당 결과 수 |
| `env` | 환경으로 필터 (예: `staging`, `dev`) |
| `status` | 상태로 필터 (`waiting`, `created`, `queued`, `running`, `success`, `failure`, `canceled`) |

### 배포 상세 조회

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments/{number}" | python3 -m json.tool
```

### 배포 상태 이력

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments/{number}/statuses" | python3 -m json.tool
```

### 배포 변경사항 (Changes)

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments/{number}/changes" | python3 -m json.tool
```

### 배포 검색

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/search/deployments?query={검색어}&page=1&per_page=10" | python3 -m json.tool
```

### 배포 생성 (NON-PROD ONLY)

**주의: env에 "prod"가 포함된 환경에는 절대 실행하지 않는다.**

```bash
curl -s -X POST -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "branch",
    "ref": "{branch_name}",
    "env": "{env_name}",
    "dynamic_payload": null
  }' \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments" | python3 -m json.tool
```

**필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `type` | string | `branch`, `commit`, 또는 `tag` |
| `ref` | string | Git 참조 (브랜치명, 커밋 SHA, 태그명) |
| `env` | string | 배포 환경 (**prod 포함 불가**) |
| `dynamic_payload` | object/null | 환경별 추가 설정 (config에서 확인) |

### 배포 롤백 (NON-PROD ONLY)

**주의: env에 "prod"가 포함된 환경에는 절대 실행하지 않는다.**

```bash
curl -s -X POST -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments/{number}/rollback" | python3 -m json.tool
```

---

## 환경 잠금 (Locks)

### 잠금 목록 조회

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/locks" | python3 -m json.tool
```

### 잠금 생성

```bash
curl -s -X POST -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "env": "{env_name}",
    "expired_at": "2026-03-25T00:00:00Z"
  }' \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/locks" | python3 -m json.tool
```

### 잠금 해제 (삭제)

```bash
curl -s -X DELETE -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/locks/{lock_id}" | python3 -m json.tool
```

---

## 브랜치/태그/커밋

### 브랜치 목록

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/branches" | python3 -m json.tool
```

### 태그 목록

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/tags" | python3 -m json.tool
```

### 커밋 목록

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/commits" | python3 -m json.tool
```

### 커밋 상태 (CI 체크)

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/commits/{sha}/statuses" | python3 -m json.tool
```

---

## 권한 (Permissions)

### 레포지토리 권한 조회

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/perms" | python3 -m json.tool
```

---

## 기타 유용한 API

### 현재 사용자 정보 (인증 확인용)

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/user" | python3 -m json.tool
```

### Rate Limit 확인

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" "$GITPLOY_URL/api/v1/user/rate-limit" | python3 -m json.tool
```

---

## 배포 결과 파싱 팁

배포 목록에서 핵심 정보만 추출하는 패턴:

```bash
curl -s -b "__sess__=$GITPLOY_SESSION_COOKIE" \
  "$GITPLOY_URL/api/v1/repos/Buzzvil/{repo_name}/deployments?per_page=10" \
  | python3 -c "
import json, sys
deployments = json.load(sys.stdin)
for d in deployments:
    user = d.get('edges', {}).get('user', {}).get('login', 'unknown')
    print(f'#{d[\"number\"]}  env={d[\"env\"]}  status={d[\"status\"]}  ref={d[\"ref\"]}  by={user}  at={d[\"created_at\"][:19]}')
"
```

---

## 전체 API 엔드포인트 참조

위 목록은 자주 사용하는 것만 정리한 것이다. 전체 API 목록은 소스코드에서 확인할 수 있다:

- **라우트 정의**: `$GITPLOY_PATH/internal/server/api/v1/router.go`
- **핸들러 구현**: `$GITPLOY_PATH/internal/server/api/v1/` 디렉토리 내 각 핸들러 파일
- **GitHub 레포**: https://github.com/Buzzvil/gitploy

엔드포인트가 확실하지 않거나 파라미터를 모를 때는 소스코드를 직접 읽어서 확인한다.

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 `GET /api/v1/user`로 세션 유효성을 확인한다. 실패 시 재로그인 절차를 진행한다.
2. **PROD 배포는 절대 거부한다** — 환경명에 "prod"가 포함되면 배포/롤백 요청을 거부하고, Gitploy 웹 UI(https://gitploy.buzzvil.dev)에서 직접 수행하도록 안내한다.
3. **배포 전 환경 설정을 확인한다** — 배포 생성 전 `GET /config`로 해당 환경의 설정(required_contexts, dynamic_payload 등)을 확인한다.
4. **배포 생성/롤백은 사용자에게 확인받는다** — 환경, 브랜치, 레포를 보여주고 승인 후 실행한다.
5. **조회 명령은 바로 실행한다** — 배포 목록, 상태, 잠금 조회 등은 확인 없이 실행한다.
6. **결과를 읽기 좋게 정리한다** — JSON을 그대로 보여주지 않고 핵심 정보만 표 또는 목록으로 정리한다.
7. **에러 발생 시 원인을 분석한다** — 인증 만료, 권한 부족, 잠금 충돌 등 원인을 파악하여 안내한다.
8. **재로그인 후 브라우저를 닫는다** — Playwright로 로그인한 뒤에는 반드시 `browser_close`로 브라우저를 정리한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
