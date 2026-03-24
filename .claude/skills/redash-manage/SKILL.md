---
name: redash-manage
description: Redash의 쿼리, 대시보드, 데이터소스를 조회하고 쿼리를 실행합니다. 쿠키 기반 세션 인증으로 API Key 없이 동작합니다. TRIGGER when: 사용자가 Redash 쿼리 조회, 실행, 대시보드 확인, 데이터소스 조회 등을 요청할 때. "redash", "리대시", "쿼리 찾아줘", "대시보드", "쿼리 실행", "redash에서" 등 Redash 관련 키워드가 포함될 때 사용.
argument-hint: (자연어로 Redash 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_run_code, mcp__playwright__browser_evaluate, mcp__playwright__browser_close
---

# Redash 관리 (curl + 쿠키 세션 인증)

## 환경 설정

`.env` 파일에서 아래 값을 읽어 사용한다.

```bash
source .env
```

- `REDASH_URL`: Redash 인스턴스 URL (예: `https://redash.buzzvil.com`)
- `REDASH_SESSION_COOKIE`: 브라우저 로그인 후 획득한 세션 쿠키 (`remember_token` 값)

---

## 인증 방식

Redash API Key를 사용하지 않고, **브라우저 구글 로그인 세션 쿠키**로 인증한다.

### 쿠키가 있을 때 (정상 흐름)

```bash
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" "$REDASH_URL/api/session" | python3 -m json.tool
```

응답에 `user` 정보가 포함되면 인증 유효.

### 쿠키가 없거나 만료되었을 때 (재로그인)

1. Playwright 브라우저로 Redash 로그인 페이지에 접속한다.
2. "Login with Google" 버튼을 클릭하여 구글 로그인을 진행한다.
3. 로그인 완료 후 쿠키를 추출한다.
4. `.env` 파일의 `REDASH_SESSION_COOKIE` 값을 업데이트한다.
5. 브라우저를 닫는다.

```
[Playwright 로그인 절차]
1. browser_navigate → $REDASH_URL/login
2. browser_snapshot → "Login with Google" 버튼 확인
3. browser_click → 구글 로그인 버튼 클릭
4. browser_snapshot → 로그인 완료 확인
5. browser_run_code → 쿠키 추출:
   async (page) => {
     const cookies = await page.context().cookies();
     const token = cookies.find(c => c.name === 'remember_token');
     return token ? token.value : null;
   }
6. .env 파일의 REDASH_SESSION_COOKIE 값 업데이트 (값을 작은따옴표로 감싸서 저장: REDASH_SESSION_COOKIE='값')
7. browser_close → 브라우저 닫기
```

---

## 명령 실행 방식

모든 Redash API 호출은 curl로 수행한다:

```bash
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" "$REDASH_URL/api/{endpoint}" | python3 -m json.tool
```

---

## 자주 사용하는 API

### 쿼리 (Queries)

```bash
# 쿼리 목록 조회 (페이지네이션)
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries?page=1&page_size=20"

# 쿼리 검색 (q 파라미터 사용)
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries?q=검색어&page_size=20"

# 특정 쿼리 상세 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries/{query_id}"

# 내 쿼리 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries/my"

# 최근 쿼리 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries/recent"

# 즐겨찾기 쿼리 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries/favorites"

# 쿼리 태그 목록
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries/tags"
```

### 쿼리 실행 및 결과

```bash
# 기존 쿼리의 캐시된 결과 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/queries/{query_id}/results"

# 쿼리 새로 실행 (refresh)
curl -s -X POST -b "remember_token=$REDASH_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  "$REDASH_URL/api/queries/{query_id}/refresh"

# 임의 SQL 실행 요청
curl -s -X POST -b "remember_token=$REDASH_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"data_source_id": {ds_id}, "query": "SELECT 1", "max_age": 0}' \
  "$REDASH_URL/api/query_results"

# 실행 작업 상태 폴링
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/jobs/{job_id}"

# 쿼리 결과 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/query_results/{query_result_id}"

# 결과를 CSV로 다운로드
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/query_results/{query_result_id}.csv"
```

### 대시보드 (Dashboards)

```bash
# 대시보드 목록 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/dashboards?page=1&page_size=20"

# 특정 대시보드 상세 조회 (위젯, 시각화 포함)
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/dashboards/{dashboard_id}"

# 내 대시보드
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/dashboards/my"

# 즐겨찾기 대시보드
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/dashboards/favorites"

# 대시보드 태그 목록
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/dashboards/tags"
```

### 데이터소스 (Data Sources)

```bash
# 데이터소스 목록 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/data_sources"

# 특정 데이터소스 스키마 조회
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/data_sources/{data_source_id}/schema"
```

### Databricks 전용

```bash
# Databricks 데이터베이스 목록
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/databricks/databases/{data_source_id}"

# 특정 DB의 테이블 목록
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/databricks/databases/{data_source_id}/{database_name}/tables"

# 특정 테이블의 컬럼 목록
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/databricks/databases/{data_source_id}/{database_name}/columns/{table_name}"
```

### 사용자/세션

```bash
# 현재 세션 정보 (인증 확인용)
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/session"

# 사용자 목록
curl -s -b "remember_token=$REDASH_SESSION_COOKIE" \
  "$REDASH_URL/api/users"
```

---

## 전체 API 엔드포인트 참조

위 목록은 자주 사용하는 것만 정리한 것이다. 전체 API 목록은 소스코드에서 확인할 수 있다:

- **전체 라우트 정의**: https://github.com/getredash/redash/blob/master/redash/handlers/api.py
- **OpenAPI 3 스펙 (비공식)**: https://github.com/koooge/redash-api-doc

### 주요 엔드포인트 카테고리

| 카테고리 | 기본 경로 | 설명 |
|----------|-----------|------|
| Queries | `/api/queries` | 쿼리 CRUD, 검색, 즐겨찾기, 태그 |
| Query Results | `/api/query_results` | 쿼리 실행, 결과 조회, 다운로드 |
| Jobs | `/api/jobs` | 쿼리 실행 작업 상태 폴링 |
| Dashboards | `/api/dashboards` | 대시보드 CRUD, 공유 |
| Widgets | `/api/widgets` | 대시보드 위젯 관리 |
| Visualizations | `/api/visualizations` | 시각화 CRUD |
| Data Sources | `/api/data_sources` | 데이터소스 관리, 스키마 조회 |
| Databricks | `/api/databricks/databases` | Databricks DB/테이블/컬럼 탐색 |
| Alerts | `/api/alerts` | 알림 CRUD, 구독 |
| Users | `/api/users` | 사용자 관리 |
| Groups | `/api/groups` | 그룹, 멤버, 데이터소스 권한 |
| Query Snippets | `/api/query_snippets` | 쿼리 스니펫 관리 |
| Destinations | `/api/destinations` | 알림 대상 (이메일, Slack 등) |
| Settings | `/api/settings/organization` | 조직 설정 |
| Events | `/api/events` | 감사 로그 |

---

## 쿼리 실행 흐름 (중요)

쿼리를 새로 실행할 때는 비동기 작업으로 처리된다:

1. **실행 요청**: `POST /api/query_results` → `job` 객체 반환
2. **상태 폴링**: `GET /api/jobs/{job_id}` → `status`가 `3`(성공) 또는 `4`(실패)가 될 때까지 반복
3. **결과 조회**: 성공 시 `query_result_id`로 `GET /api/query_results/{id}` 호출

```bash
# 1. 실행 요청
RESPONSE=$(curl -s -X POST -b "remember_token=$REDASH_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d "{\"data_source_id\": $DS_ID, \"query\": \"$SQL\", \"max_age\": 0}" \
  "$REDASH_URL/api/query_results")

# job 응답이면 폴링, query_result 응답이면 바로 결과
JOB_ID=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('job',{}).get('id',''))" 2>/dev/null)

# 2. 상태 폴링 (job이 있는 경우)
if [ -n "$JOB_ID" ]; then
  while true; do
    JOB=$(curl -s -b "remember_token=$REDASH_SESSION_COOKIE" "$REDASH_URL/api/jobs/$JOB_ID")
    STATUS=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['job']['status'])")
    [ "$STATUS" = "3" ] || [ "$STATUS" = "4" ] && break
    sleep 2
  done
  RESULT_ID=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['job']['query_result_id'])")

  # 3. 결과 조회
  curl -s -b "remember_token=$REDASH_SESSION_COOKIE" "$REDASH_URL/api/query_results/$RESULT_ID"
fi
```

---

## 데이터소스 참조

현재 연결된 주요 데이터소스:

| ID | 이름 | 타입 |
|----|------|------|
| 27 | data-lake-analytics-tokyo | Athena |
| 36 | data-lake-analytics-tokyo-product-specialist | Athena |
| 13 | data-lake-de | Athena |
| 39 | sqlwarehouse-small | Databricks |
| 12 | prod_airflow | PostgreSQL |
| 18 | prod_redash | PostgreSQL |

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 `GET /api/session`으로 세션 유효성을 확인한다. 실패 시 재로그인 절차를 진행한다.
2. **쿼리 실행은 반드시 사용자에게 확인받는다** — SQL 내용과 대상 데이터소스를 보여주고 승인 후 실행한다.
3. **조회 명령은 바로 실행한다** — 쿼리 검색, 목록 조회, 대시보드 조회 등은 확인 없이 실행한다.
4. **결과를 읽기 좋게 정리한다** — JSON을 그대로 보여주지 않고 핵심 정보만 표 또는 목록으로 정리한다.
5. **에러 발생 시 원인을 분석한다** — 인증 만료, 권한 부족, 쿼리 오류 등 원인을 파악하여 안내한다.
6. **재로그인 후 브라우저를 닫는다** — Playwright로 로그인한 뒤에는 반드시 `browser_close`로 브라우저를 정리한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
