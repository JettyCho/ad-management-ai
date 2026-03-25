---
name: dash-manage
description: Buzzvil Ad Dashboard(dash-api-gateway)를 curl로 직접 호출하여 광고 조회, 라인아이템 관리, 크리에이티브 조회, 유닛/앱/조직 관리 등을 수행합니다. 쿠키 기반 세션 인증으로 동작합니다. TRIGGER when: 사용자가 대시, 광고 조회, 라인아이템, 크리에이티브, 유닛, 앱, 조직, 애드그룹, 허브프로모션 등 광고 운영 관련 작업을 요청할 때. "대시", "dash", "광고 조회", "라인아이템", "lineitem", "creative", "크리에이티브", "유닛", "unit", "앱", "app", "조직", "org", "애드그룹", "adgroup" 등 관련 키워드가 포함될 때 사용.
argument-hint: (자연어로 대시 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Dash 관리 (curl + 쿠키 세션 인증)

## 환경 설정

`.env` 파일에서 아래 값을 읽어 사용한다.

```bash
source .env
```

- `DASH_API_GATEWAY_URL`: prod 환경 Base URL (`https://dash-api-gateway.eks.buzzvil.com`)
- `DASH_ID`: 로그인 계정 (이메일) — 모든 환경 공통
- `DASH_PW`: 로그인 비밀번호 — 모든 환경 공통
- `DASH_PROD_SESSION_COOKIE`: prod 환경 세션 쿠키 (안정적으로 유지)
- `DASH_OTHER_SESSION_COOKIE`: prod 외 환경 세션 쿠키 (환경 변경 시 덮어씀)

---

## 환경 선택 (동적)

사용자가 환경을 명시하지 않으면 **prod**가 기본이다.

### URL 규칙

`DASH_API_GATEWAY_URL` (`.env`)이 prod Base URL이다. 다른 환경은 이 URL에서 파생한다:

| 환경명 | Base URL |
|--------|----------|
| `prod` | `$DASH_API_GATEWAY_URL` (= `https://dash-api-gateway.eks.buzzvil.com`) |
| 그 외 (`{env}`) | `https://dash-api-gateway-{env}.eks.buzzvil.com` |

예: staging → `dash-api-gateway-staging`, stagingqa → `dash-api-gateway-stagingqa`, dev → `dash-api-gateway-dev`

### 환경 변수 세팅

```bash
source .env

# prod (기본)
DASH_TARGET_URL="$DASH_API_GATEWAY_URL"
DASH_COOKIE="$DASH_PROD_SESSION_COOKIE"

# prod 외 (환경명을 대입)
ENV="staging"  # 또는 stagingqa, dev, ...
DASH_TARGET_URL="https://dash-api-gateway-${ENV}.eks.buzzvil.com"
DASH_COOKIE="$DASH_OTHER_SESSION_COOKIE"
```

이후 모든 API 호출에서 `$DASH_TARGET_URL`과 `$DASH_COOKIE`를 사용한다.

---

## 인증 방식

### 세션 확인

```bash
RESULT=$(curl -s -w "\n%{http_code}" -b "connect.sid=$DASH_COOKIE" "$DASH_TARGET_URL/ba/campaign/service/units?page_size=1")
HTTP_CODE=$(echo "$RESULT" | tail -1)
```

`HTTP_CODE`가 `200`이면 세션 유효. `401`이면 재로그인 필요.

### 로그인 (세션 만료 시)

```bash
COOKIE=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"username\":\"$DASH_ID\",\"password\":\"$DASH_PW\"}" \
  -c - "$DASH_TARGET_URL/user/login" | grep 'connect.sid' | awk '{print $NF}')
echo "New cookie: $COOKIE"
```

로그인 성공 시 `.env` 파일의 쿠키 값을 업데이트한다 (작은따옴표로 감싸서 저장):
- **prod** → `DASH_PROD_SESSION_COOKIE='새쿠키값'`
- **그 외** → `DASH_OTHER_SESSION_COOKIE='새쿠키값'` (어차피 다른 환경 전환 시 덮어씌워짐)

그리고 `DASH_COOKIE` 변수도 새 값으로 갱신하여 이후 요청에 사용한다.

---

## 명령 실행 방식

모든 API 호출은 curl로 수행한다:

```bash
curl -s -b "connect.sid=$DASH_COOKIE" "$DASH_TARGET_URL/{endpoint}" | python3 -m json.tool
```

---

## 라우트 구조

dash-api-gateway는 Express 기반 프록시 서버로, 요청을 백엔드 서비스로 전달한다:

| 경로 접두사 | 백엔드 | 설명 |
|------------|--------|------|
| `/ba/*` | buzzad (BA) | 광고 관리 (라인아이템, 크리에이티브, 유닛 등) |
| `/bs/*` | buzzscreen (BS) | 퍼블리셔/스크린 관련 |
| `/bsapi/*` | bsapi | BS API |
| `/user/*` | 자체 처리 | 로그인/로그아웃/MFA |
| `/gql/*` | GraphQL | GraphQL 엔드포인트 |
| `/booster/*` | buzzbooster | 부스터 관련 |

---

## 자주 사용하는 API

### 라인아이템 (광고)

```bash
# 라인아이템 목록 조회
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ads?page_size=20&item_type__in=A"

# 라인아이템 검색
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ads?page_size=20&search=검색어"

# item_type 필터: A=direct_sales, E=static_networks

# 라인아이템 상세 조회
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ads/{id}"

# 라인아이템 일별 리포트
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ads/{id}/reports?start_date=2026-03-01&end_date=2026-03-24"

# 라인아이템 히스토리
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ads/{id}/history"

# 크리에이티브 셋 조회
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ads/{lineitem_id}/creative_sets"
```

### 크리에이티브

```bash
# 크리에이티브 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/creatives?page_size=20"

# 크리에이티브 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/creatives/{id}"

# 크리에이티브 리포트
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/creatives/{id}/reports?start_date=2026-03-01&end_date=2026-03-24"
```

### 애드그룹

```bash
# 애드그룹 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adgroups?page_size=20"

# 애드그룹 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adgroups/{id}"

# 애드그룹 리포트
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adgroups/{id}/reports?start_date=2026-03-01&end_date=2026-03-24"

# 애드그룹 소속 라인아이템 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adgroups/{id}/lineitems"
```

### 앱

```bash
# 앱 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/apps?page_size=20"

# 앱 검색
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/apps?search=검색어"

# 앱 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/apps/{id}"
```

### 유닛

```bash
# 유닛 목록 (campaign 경로)
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/campaign/service/units?page_size=20"

# 유닛 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/campaign/service/units/{id}"

# 유닛 히스토리
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/campaign/service/units/{id}/histories"
```

### 유닛그룹

```bash
# 유닛그룹 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/unitgroups?page_size=20"

# 유닛그룹 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/unitgroups/{id}"

# 유닛그룹에 유닛 추가/제거
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/unitgroups/{id}/units/{unit_id}"
```

### 사용자 (계정)

```bash
# 사용자 상세 조회 (owner_id 등으로 누구인지 확인할 때)
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/users/{id}"

# 사용자 목록 검색
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/users?search=검색어"
```

주요 응답 필드: `id`, `email`, `name`, `role_type`, `organization_id`, `is_staff`, `last_login` 등.
adserver의 `owner_id` (라인아이템, 타겟그룹 등)는 이 사용자 ID를 참조한다.

### 조직

```bash
# 조직 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/orgs?page_size=20"

# 조직 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/orgs/{id}"
```

### 애드네트워크

```bash
# 애드네트워크 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adnetworks?page_size=20"

# 애드네트워크 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adnetworks/{id}"

# 애드네트워크별 유닛그룹
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/adnetworks/{id}/unitgroups"
```

### 이벤트 소스

```bash
# 이벤트소스 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/event_sources?page_size=20"

# 이벤트소스 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/event_sources/{id}"
```

### UA / 허브프로모션

```bash
# UA 허브 라인아이템
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ua/hub/lineitems"

# UA 미션 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/ua/missions"
```

### 정산 (Payout)

```bash
# 정산 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/payouts?page_size=20"

# 정산 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/payouts/{id}"
```

### 자동화 규칙

```bash
# 자동화 규칙 목록
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/automated_rules?page_size=20"

# 자동화 규칙 상세
curl -s -b "connect.sid=$DASH_COOKIE" \
  "$DASH_TARGET_URL/ba/automated_rules/{id}"
```

---

## 쓰기 작업 (Create/Update)

```bash
# POST 예시 (조직 생성)
curl -s -X POST -b "connect.sid=$DASH_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"name":"테스트 조직","email":"org@example.com"}' \
  "$DASH_TARGET_URL/ba/orgs"

# PUT 예시 (라인아이템 수정)
curl -s -X PUT -b "connect.sid=$DASH_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"item_name":"수정된 이름"}' \
  "$DASH_TARGET_URL/ba/ads/{id}"

# PATCH 예시
curl -s -X PATCH -b "connect.sid=$DASH_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"is_active":"N"}' \
  "$DASH_TARGET_URL/ba/ads/{id}"
```

---

## 전체 엔드포인트 참조

위 목록은 자주 사용하는 것만 정리한 것이다. 전체 라우트는 소스코드에서 확인할 수 있다:

- **BA 라우터**: `$DASH_API_GATEWAY_PATH/routers/ba.js`
- **BS 라우터**: `$DASH_API_GATEWAY_PATH/routers/bs.js`
- **BSAPI 라우터**: `$DASH_API_GATEWAY_PATH/routers/bsapi.js`
- **라우트 마운트**: `$DASH_API_GATEWAY_PATH/server/routing.js`

엔드포인트가 확실하지 않을 때는 라우터 소스코드를 직접 읽어서 확인한다.

---

## 공통 쿼리 파라미터

| 파라미터 | 설명 |
|---------|------|
| `page_size` | 한 페이지 결과 수 (기본 20) |
| `page` | 페이지 번호 |
| `search` | 검색 키워드 |
| `ordering` | 정렬 기준 (예: `-created_at`, `name`) |
| `item_type__in` | 라인아이템 타입 필터 (A/E) |
| `organization_id` | 조직 ID 필터 |
| `start_date` / `end_date` | 리포트 기간 필터 |

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 세션 유효성을 확인한다. 401 시 해당 환경에 대해 자동 재로그인 후 재시도한다.
2. **쓰기 작업은 반드시 사용자에게 확인받는다** — 요청 내용(환경, 메서드, URL, 페이로드)을 보여주고 승인 후 실행한다.
3. **조회 명령은 바로 실행한다** — 목록 조회, 검색, 상세 조회 등은 확인 없이 실행한다.
4. **결과를 읽기 좋게 정리한다** — JSON을 그대로 보여주지 않고 핵심 정보만 표 또는 목록으로 정리한다.
5. **에러 발생 시 원인을 분석한다** — 인증 만료, 권한 부족, 404 등 원인을 파악하여 안내한다.
6. **현재 환경을 명시한다** — 결과 보고 시 어느 환경에서 조회한 것인지 표시한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
