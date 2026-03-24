---
name: grafana-manage
description: Grafana를 curl로 직접 호출하여 Loki 로그 쿼리, Prometheus 메트릭 쿼리, 대시보드 검색/조회, 알림 확인 등을 수행합니다. 쿠키 기반 세션 인증으로 Service Account Token 없이 동작합니다. TRIGGER when: 사용자가 Grafana, Loki, Prometheus, 대시보드, 로그 조회, 메트릭 조회, 알림 확인 등을 요청할 때. "grafana", "그라파나", "loki", "로키", "prometheus", "프로메테우스", "로그 조회", "메트릭", "대시보드", "알림" 등 관련 키워드가 포함될 때 사용.
argument-hint: (자연어로 Grafana 관련 요청을 자유롭게 입력)
disable-model-invocation: false
context: compress
allowed-tools: Bash, Read, Grep, Glob, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_run_code, mcp__playwright__browser_evaluate, mcp__playwright__browser_close
---

# Grafana 관리 (curl + 쿠키 세션 인증)

**Grafana 버전 확인**: 작업 전 `GET /api/health`로 현재 버전을 확인한다. 버전에 따라 사용 가능한 API가 다를 수 있으므로, 예상과 다른 응답이 나오면 해당 버전의 소스코드(`https://github.com/grafana/grafana/blob/v{버전}/pkg/api/api.go`)에서 라우트를 더블체크한다.

## 환경 설정

`.env` 파일에서 아래 값을 읽어 사용한다.

```bash
source .env
```

- `GRAFANA_URL`: Grafana 인스턴스 URL (예: `https://grafana.buzzvil.dev`)
- `GRAFANA_SESSION_COOKIE`: 브라우저 로그인 후 획득한 세션 쿠키 (`grafana_session` 값)

---

## 인증 방식

Grafana Service Account Token을 사용하지 않고, **브라우저 로그인 세션 쿠키**로 인증한다.

### 쿠키가 있을 때 (정상 흐름)

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" "$GRAFANA_URL/api/user" | python3 -m json.tool
```

응답에 `login`, `email` 등 사용자 정보가 포함되면 인증 유효.

### 쿠키가 없거나 만료되었을 때 (재로그인)

1. Playwright 브라우저로 Grafana 로그인 페이지에 접속한다.
2. OAuth 로그인 버튼을 클릭하여 구글/SSO 로그인을 진행한다.
3. 로그인 완료 후 쿠키를 추출한다.
4. `.env` 파일의 `GRAFANA_SESSION_COOKIE` 값을 업데이트한다.
5. 브라우저를 닫는다.

```
[Playwright 로그인 절차]
1. browser_navigate → $GRAFANA_URL/login
2. browser_snapshot → 로그인 버튼 확인 (OAuth/Google 등)
3. browser_click → 로그인 버튼 클릭
4. (필요 시) browser_snapshot → 구글 계정 선택/인증 화면 처리
5. browser_snapshot → 로그인 완료 확인 (Grafana 홈 화면)
6. browser_run_code → 쿠키 추출:
   async (page) => {
     const cookies = await page.context().cookies();
     const token = cookies.find(c => c.name === 'grafana_session');
     return token ? token.value : null;
   }
7. .env 파일의 GRAFANA_SESSION_COOKIE 값 업데이트 (값을 작은따옴표로 감싸서 저장: GRAFANA_SESSION_COOKIE='값')
8. browser_close → 브라우저 닫기
```

**참고**: Grafana 세션 쿠키는 10분마다 토큰이 회전되지만, 비활성 시 7일까지 유지된다. 브라우저에서 가끔 사용하면 세션이 유지된다.

---

## 명령 실행 방식

모든 Grafana API 호출은 curl로 수행한다:

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" "$GRAFANA_URL/api/{endpoint}" | python3 -m json.tool
```

---

## 사전 작업: 데이터소스 UID 확인

Loki/Prometheus 쿼리에는 **데이터소스 UID**가 필요하다. 먼저 데이터소스 목록을 조회하여 UID를 확인한다:

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" "$GRAFANA_URL/api/datasources" \
  | python3 -c "
import json, sys
ds_list = json.load(sys.stdin)
for ds in ds_list:
    print(f\"ID={ds['id']}  UID={ds['uid']}  type={ds['type']}  name={ds['name']}\")
"
```

---

## Loki 로그 쿼리

### 로그 조회 (POST /api/ds/query)

```bash
curl -s -X POST -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [{
      "refId": "A",
      "datasource": {"uid": "<LOKI_DS_UID>", "type": "loki"},
      "expr": "{app=\"myapp\"} |= \"error\"",
      "queryType": "range",
      "maxLines": 100
    }],
    "from": "now-1h",
    "to": "now"
  }' \
  "$GRAFANA_URL/api/ds/query"
```

**쿼리 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `expr` | string | LogQL 표현식 (필수) |
| `queryType` | string | `"range"` 또는 `"instant"` |
| `maxLines` | int | 반환할 최대 로그 줄 수 |
| `direction` | string | `"backward"` (기본, 최신순) 또는 `"forward"` |
| `resolution` | int | 1~10, 기본 1 |

**시간 범위 (`from`/`to`):**
- 상대 시간: `"now-1h"`, `"now-30m"`, `"now-7d"`
- 절대 시간 (epoch ms): `"1679900000000"`

### 라벨 목록 조회

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/datasources/uid/<LOKI_DS_UID>/resources/loki/api/v1/labels"
```

### 라벨 값 조회

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/datasources/uid/<LOKI_DS_UID>/resources/loki/api/v1/label/{라벨명}/values"
```

### 시리즈 조회

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/datasources/uid/<LOKI_DS_UID>/resources/loki/api/v1/series?match[]={app=~\".+\"}"
```

---

## Prometheus 메트릭 쿼리

### Range 쿼리 (POST /api/ds/query)

```bash
curl -s -X POST -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [{
      "refId": "A",
      "datasource": {"uid": "<PROM_DS_UID>", "type": "prometheus"},
      "expr": "rate(http_requests_total[5m])",
      "range": true,
      "instant": false,
      "intervalMs": 15000,
      "maxDataPoints": 1000
    }],
    "from": "now-1h",
    "to": "now"
  }' \
  "$GRAFANA_URL/api/ds/query"
```

### Instant 쿼리

```bash
curl -s -X POST -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [{
      "refId": "A",
      "datasource": {"uid": "<PROM_DS_UID>", "type": "prometheus"},
      "expr": "up",
      "instant": true,
      "range": false,
      "intervalMs": 15000,
      "maxDataPoints": 1
    }],
    "from": "now-5m",
    "to": "now"
  }' \
  "$GRAFANA_URL/api/ds/query"
```

**쿼리 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `expr` | string | PromQL 표현식 (필수) |
| `range` | bool | `true`이면 range 쿼리 |
| `instant` | bool | `true`이면 instant 쿼리 |
| `intervalMs` | int | 간격 (ms) |
| `maxDataPoints` | int | 최대 데이터 포인트 수 |
| `legendFormat` | string | 범례 템플릿 (예: `"{{instance}}"`) |

### Prometheus 메타데이터 (Raw Proxy)

```bash
# 라벨 목록
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/datasources/proxy/uid/<PROM_DS_UID>/api/v1/labels"

# 메트릭 메타데이터
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/datasources/proxy/uid/<PROM_DS_UID>/api/v1/metadata?metric=up"

# 라벨 값
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/datasources/proxy/uid/<PROM_DS_UID>/api/v1/label/{라벨명}/values"
```

---

## 대시보드

### 대시보드 검색

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/search?query=검색어&type=dash-db&limit=20"
```

**검색 파라미터:**

| 파라미터 | 설명 |
|----------|------|
| `query` | 검색어 |
| `type` | `dash-db` (대시보드), `dash-folder` (폴더) |
| `tag` | 태그로 필터 |
| `starred` | `true`이면 즐겨찾기만 |
| `folderIds` | 폴더 ID로 필터 |
| `limit` | 결과 수 제한 (기본 1000) |
| `page` | 페이지 번호 |

### 대시보드 상세 조회

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/dashboards/uid/{대시보드_UID}" | python3 -m json.tool
```

### 대시보드 태그 목록

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/dashboards/tags"
```

### 홈 대시보드

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/dashboards/home"
```

---

## 알림 (Alerting)

### 알림 규칙 전체 조회 (Ruler API)

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/ruler/grafana/api/v1/rules" | python3 -m json.tool
```

### 특정 알림 규칙 조회 (Provisioning API)

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/v1/provisioning/alert-rules/{UID}"
```

### 알림 연락처 조회

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/v1/provisioning/contact-points"
```

### 알림 정책 조회

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/v1/provisioning/policies"
```

---

## 기타 유용한 API

### 현재 사용자 정보 (인증 확인용)

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" "$GRAFANA_URL/api/user"
```

### 현재 조직 정보

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" "$GRAFANA_URL/api/org"
```

### 폴더 목록

```bash
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" "$GRAFANA_URL/api/folders"
```

### 어노테이션 조회

```bash
# 시간 범위로 조회 (from/to는 epoch ms)
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/annotations?from=1679900000000&to=1679986400000"

# 대시보드별 조회
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/annotations?dashboardId={id}"

# 태그로 조회
curl -s -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  "$GRAFANA_URL/api/annotations?tags=deploy"
```

### 서버 상태 확인

```bash
curl -s "$GRAFANA_URL/api/health"
```

---

## API 참조 및 도움말

모르는 API가 있거나 상세 파라미터를 확인하고 싶을 때:

- **공식 HTTP API 문서**: https://grafana.com/docs/grafana/v9.1/developers/http_api/
- **소스코드 라우트 정의** (v9.1.5): https://github.com/grafana/grafana/blob/v9.1.5/pkg/api/api.go
- **Loki LogQL 문법**: https://grafana.com/docs/loki/latest/logql/
- **PromQL 문법**: https://prometheus.io/docs/prometheus/latest/querying/basics/

### 주요 API 엔드포인트 카테고리

| 카테고리 | 기본 경로 | 설명 |
|----------|-----------|------|
| Health | `GET /api/health` | 서버 상태 확인 |
| User | `GET /api/user` | 현재 사용자 정보 |
| Org | `GET /api/org` | 현재 조직 정보 |
| Datasources | `GET /api/datasources` | 데이터소스 목록/상세 |
| DS Query | `POST /api/ds/query` | 통합 데이터 쿼리 (Loki, Prometheus 등) |
| DS Resources | `ANY /api/datasources/uid/:uid/resources/*` | 데이터소스 리소스 (메타데이터 등) |
| DS Proxy | `ANY /api/datasources/proxy/uid/:uid/*` | 데이터소스 raw 프록시 |
| Search | `GET /api/search` | 대시보드/폴더 검색 |
| Dashboards | `GET /api/dashboards/uid/:uid` | 대시보드 상세 |
| Folders | `GET /api/folders` | 폴더 목록 |
| Annotations | `GET /api/annotations` | 어노테이션 CRUD |
| Alerting (Ruler) | `GET /api/ruler/grafana/api/v1/rules` | 알림 규칙 전체 조회 |
| Alerting (Prov.) | `GET /api/v1/provisioning/alert-rules/:uid` | 알림 규칙 개별 조회 |
| Contact Points | `GET /api/v1/provisioning/contact-points` | 알림 연락처 |
| Policies | `GET /api/v1/provisioning/policies` | 알림 정책 |

---

## 로그 쿼리 결과 파싱 팁

`/api/ds/query` 응답은 중첩이 깊다. 로그 결과를 읽기 좋게 추출하는 패턴:

```bash
curl -s -X POST -b "grafana_session=$GRAFANA_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{...}' \
  "$GRAFANA_URL/api/ds/query" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', {})
for ref_id, result in results.items():
    frames = result.get('frames', [])
    for frame in frames:
        schema = frame.get('schema', {})
        field_data = frame.get('data', {}).get('values', [])
        fields = schema.get('fields', [])
        # 필드 이름 출력
        field_names = [f['name'] for f in fields]
        print('Fields:', field_names)
        # 데이터 출력 (첫 10개)
        if len(field_data) >= 2:
            labels_or_ts = field_data[0]
            values = field_data[1]
            for i, v in enumerate(values[:10]):
                print(v)
"
```

---

## 응답 원칙

1. **인증 확인을 먼저 한다** — 모든 작업 전 `GET /api/user`로 세션 유효성을 확인한다. 실패 시 재로그인 절차를 진행한다.
2. **데이터소스 UID를 먼저 확인한다** — Loki/Prometheus 쿼리 전에 `GET /api/datasources`로 UID를 조회한다. 캐시된 UID가 있으면 재사용한다.
3. **쿼리 실행은 반드시 사용자에게 확인받는다** — LogQL/PromQL 내용과 시간 범위를 보여주고 승인 후 실행한다. (단순 조회는 예외)
4. **조회 명령은 바로 실행한다** — 대시보드 검색, 데이터소스 목록, 알림 조회 등은 확인 없이 실행한다.
5. **결과를 읽기 좋게 정리한다** — JSON을 그대로 보여주지 않고 핵심 정보만 표 또는 목록으로 정리한다.
6. **에러 발생 시 원인을 분석한다** — 인증 만료, 권한 부족, 쿼리 문법 오류 등 원인을 파악하여 안내한다.
7. **재로그인 후 브라우저를 닫는다** — Playwright로 로그인한 뒤에는 반드시 `browser_close`로 브라우저를 정리한다.

---

보고서는 한국어로 작성한다. 기술 용어나 고유명사는 원문 그대로 사용한다.
