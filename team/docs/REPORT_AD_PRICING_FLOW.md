# 광고 금액 체계 분석 리포트

> **작성일**: 2026-03-24
> **목적**: Dash UI에서 보여지는 광고 금액이 어떤 로직을 거쳐 계산되고 표시되는지, 전체 흐름을 추적한다.
> **대상 독자**: 주니어 개발자 포함 누구나. 복잡하지만 한 단계씩 따라갈 수 있도록 근거와 코드 위치를 명시한다.

---

## 목차

1. [전체 조감도](#1-전체-조감도)
2. [핵심 용어 정의](#2-핵심-용어-정의)
3. [Phase 1: 금액 입력 — Dash UI에서 사람이 설정하는 값](#3-phase-1-금액-입력--dash-ui에서-사람이-설정하는-값)
4. [Phase 2: 전환 시 금액 자동 계산 — CurrencyManager](#4-phase-2-전환-시-금액-자동-계산--currencymanager)
5. [Phase 3: 리포트 금액 — Dash UI에 표시되는 cost](#5-phase-3-리포트-금액--dash-ui에-표시되는-cost)
6. [Phase 4: 정산 — Salesforce 양방향 연동](#6-phase-4-정산--salesforce-양방향-연동)
7. [직영업(A) vs 네트워크(E) 차이](#7-직영업a-vs-네트워크e-차이)
8. [부록: is_forced_conversion, sales, unit_sales 필드 상세](#8-부록-is_forced_conversion-sales-unit_sales-필드-상세)
9. [참조 파일 색인](#9-참조-파일-색인)

---

## 1. 전체 조감도

광고 금액은 **"누가 얼마를 주고받는가"**라는 세 가지 관점으로 나뉜다.

```
광고주(Advertiser)         버즈빌(Buzzvil)           매체(Publisher/Unit)
      │                        │                         │
      │   unit_price 지불      │    unit_sales 지급       │
      ├───────────────────────>│────────────────────────>│
      │                        │                         │
      │                   마진(take rate)                 │
      │               = sales - unit_sales               │
      │                        │                         │
```

- **`unit_price`**: 광고주가 전환 1건당 지불하는 단가. 모든 금액 계산의 출발점이다.
- **`sales`**: 전환 발생 시 광고주에게 청구되는 금액. 대부분 `unit_price`와 같다.
- **`unit_sales`**: 전환 발생 시 매체(퍼블리셔)에게 지급되는 금액. 환율, 수익 배분율 등을 적용하여 계산된다.
- **`cost`**: 리포트에서 보이는 비용. revenue_type(CPM/CPC/CPA)에 따라 `unit_price × 성과 지표`로 StatsService가 계산한다.

이 금액들이 설정되고, 계산되고, 표시되고, 정산되는 전체 과정을 아래에서 단계별로 설명한다.

---

## 2. 핵심 용어 정의

아래 용어들은 이 리포트 전체에서 반복적으로 사용된다. 먼저 정확한 의미를 정리한다.

| 용어 | 의미 | 코드 위치 (대표) |
|------|------|-----------------|
| **unit_price** | 라인아이템의 광고 단가. 광고주가 전환 1건당 지불하는 금액 | `adserver/orders/models/models.py` DecimalField(18,9) |
| **revenue** | unit_price의 구버전 이름. **deprecated**, unit_price를 사용해야 한다 | 동일 파일 DecimalField(12,4) |
| **sales** | 전환(conversion) 발생 시 기록되는 광고주 정산 금액. 라인아이템 화폐 기준 | `adserver/orders/models/models.py` RawDataConversions 모델 |
| **unit_sales** | 전환 발생 시 기록되는 매체 정산 금액. 유닛 화폐 기준 | 동일 모델 |
| **cost** | 리포트에 표시되는 비용. StatsService가 revenue_type별로 사전 계산 | `adserver/ddd/domain/statssvc_values.py` PerformanceReport |
| **target_unit_sales** | 특정 유닛에 대해 개별 설정한 매체 단가. JSON 형태 `{"unit_id": price}` | `adserver/orders/models/models.py` JSONField |
| **unit_group_sales** | 유닛그룹에 대해 설정한 매체 단가. JSON 형태 `{"group_id": price}` | 동일 파일 JSONField |
| **action_point** | 전환 시 유저가 받는 포인트. 설정하지 않으면 unit_sales에서 자동 계산 | 동일 파일 DecimalField(18,9) |
| **revenue_type** | 과금 방식: cpm(노출), cpc(클릭), cpa(전환), cpk, cpe, cps 등 | 동일 파일 CharField |
| **item_type** | 라인아이템 유형: `A`(직영업/direct_sales), `E`(네트워크/static_networks) | 동일 파일 CharField |
| **is_forced_conversion** | 관리자가 수동으로 강제 생성한 전환인지 여부 (True/False) | RawDataConversions 모델 BooleanField |

---

## 3. Phase 1: 금액 입력 — Dash UI에서 사람이 설정하는 값

### 3.1 애드그룹 생성/편집 화면

세일즈 담당자가 애드그룹을 만들 때 입력하는 금액 필드들이다.

| 필드 | 편집 가능 | 의미 | UI 위치 |
|------|----------|------|---------|
| `budget` (BOOKING_BUDGET) | Yes | 예약 예산. Salesforce Opportunity의 Amount와 연동된다 | 예산 섹션 |
| `agent_fee_rate` | Yes | 대행사 수수료율 (%). 정산 시 차감에 사용 | 예산 섹션 |
| `extra_budgets` | 읽기 전용 | 이월(O), 보상(C), 추가(A), 프로모션(P), 수수료(M) 예산의 합계 | 예산 섹션 |

> **출처**: Dash 프론트엔드 `dash/src/modules/campaign/views/direct_sales/detail/adgroup/form/create-edit-section/budget.vue`

### 3.2 라인아이템 생성/편집 화면

가장 중요한 금액 입력이 이루어지는 곳이다.

| 필드 | 편집 가능 | 의미 | 비고 |
|------|----------|------|------|
| **`unit_price`** | **Yes** | **광고 단가 — 모든 금액 계산의 출발점** | revenue_type별로 최소/최대값 제한 |
| `budget_v2` | Yes | 라인아이템 예산. unit_price 이상이어야 한다 | 필수 |
| `daily_budget_v2` | Yes | 일 예산 상한 | 선택 |
| `currency` | 생성 시만 | 통화 (KRW, USD 등). 생성 후 변경 불가 | 잠금 |
| `alloc_cap_budget` | Yes | 안전 예산 (daily_budget_v2 이하) | 선택 |
| `alloc_cap_rate` | Yes | 안전 비율 (0~100%) | 선택 |

> **출처**: Dash 프론트엔드 `dash/src/modules/campaign/views/direct_sales/detail/lineitem/budget.vue`
> **모델 정의**: `adserver/orders/models/models.py` 라인 486-640

### 3.3 유닛 타겟팅 (Placement) 화면

매체별로 지급할 단가를 개별 override할 수 있는 화면이다. 이 값을 설정하면 Phase 2의 자동 계산을 덮어쓴다.

| 필드 | 편집 가능 | 의미 | 저장 위치 |
|------|----------|------|----------|
| `group.payout` | Yes | 유닛그룹별 매체 단가 | `UnitGroupLineitemMappings.sales` |
| `unit.sales` | Yes | 특정 유닛별 매체 단가 | `lineitem.target_unit_sales` JSON |
| `group.base_alloc_cap` | Yes | 유닛그룹 할당 비율 (1~100%) | 매핑 테이블 |
| `unit.base_alloc_cap` | Yes | 유닛 할당 비율 (1~100%) | 매핑 테이블 |

> **출처**: Dash 프론트엔드 `dash/src/component/forms/inputs/target/units/field-group-unit.vue`
> **시리얼라이저**: `adserver/cms/serializers/serializers.py` UnitGroupLineitemMappingsSerializer (라인 160-198)

### 3.4 입력값 요약

결국 담당자가 실제로 입력하는 핵심 금액은 다음 세 가지다:

1. **`unit_price`** — 광고 단가 (필수)
2. **`budget`** — 예산 (필수)
3. **유닛별/그룹별 매체 단가** — override (선택)

나머지 모든 금액(`sales`, `unit_sales`, `cost`, `action_reward` 등)은 이 입력값들로부터 **시스템이 자동 계산**한다.

---

## 4. Phase 2: 전환 시 금액 자동 계산 — CurrencyManager

전환(conversion)이 발생하면, 시스템은 세 가지 금액을 계산하여 `RawDataConversions` 테이블에 기록한다:
- `sales` (광고주 정산 금액)
- `unit_sales` (매체 정산 금액)
- `action_reward` (유저 보상 포인트)

이 계산의 핵심은 `CurrencyManager` 클래스이다.

> **핵심 파일**: `adserver/common/currency.py`

### 4.1 sales (광고주 정산 금액) 결정

sales는 대부분의 경우 `unit_price`와 동일하다.

```python
# adserver/action/ddd/service/conversion_strategies.py
# ConversionService._create_conversion() 내부

sales = lineitem.unit_price  # 기본값
```

**예외 케이스:**

| 상황 | sales 값 | 근거 |
|------|----------|------|
| 일반 전환 | `lineitem.unit_price` | 기본 동작 |
| 멀티리워드 캠페인 | `0` | 광고주 정산 없음 |
| 실험군(experiment) | `recent_click.forced_unit_sales` | 실험 설정값 적용 |

> **출처**: `adserver/action/ddd/service/conversion_strategies.py` ConversionService._create_conversion()

### 4.2 unit_sales (매체 정산 금액) 결정 — 핵심 로직

매체에 지급할 금액을 결정하는 과정이다. **우선순위가 있으며, 위에서부터 순서대로 체크**한다.

> **핵심 함수**: `CurrencyManager.get_unit_lineitem_sales(unit, lineitem)`
> **파일**: `adserver/common/currency.py` 라인 439-507

#### 우선순위 1: ADN Fixed Revenue Share

네트워크 라인아이템(`item_type=E`)이고, 특정 유닛그룹에 고정 수익 배분율이 설정된 경우:

```
unit_sales = unit_price × FIXED_REVENUE_SHARE(%) × 환율
```

> 이 값은 코드에 상수로 정의되어 있다.

#### 우선순위 2: 유닛별/그룹별 Override 단가

Dash UI에서 담당자가 직접 입력한 단가가 있는 경우 (CPA, CPE, CPS, CPCQUIZ, CPQ 타입):

```
# 특정 유닛에 대한 단가가 있으면
unit_sales = target_unit_sales[unit.id] × 환율

# 없으면, 유닛그룹 단가 중 최대값
unit_sales = max(unit_group_sales.values()) × 환율
```

> `target_unit_sales`는 라인아이템 모델의 JSON 필드로, `{"unit_id": price}` 형태이다.
> `unit_group_sales`도 동일 형태: `{"group_id": price}`

#### 우선순위 3: 매체 기본 단가 (KR, 비자사)

한국(KR) 지역의 비자사 매체에 대해, 유닛에 revenue_type별 기본 단가가 설정되어 있는 경우:

```
unit_sales = unit.default_unit_prices[revenue_type] × 환율
```

#### 우선순위 4: 기본 공식 (Fallback)

위 어떤 조건에도 해당하지 않으면, 수익 배분율(revenue_rate)을 적용한 기본 공식을 사용한다:

```
unit_sales = unit_price × get_revenue_rate(unit, lineitem) × 환율
```

`get_revenue_rate()`는 유닛의 `reward_rate` 속성에서 가져온다. CPS/CPY 타입은 별도의 배분율(`reward_rate_cps`, `reward_rate_cpy`)을 사용한다.

#### 환율 계산

통화가 다른 경우 (예: 라인아이템은 KRW, 유닛은 USD), 환율을 적용한다:

```python
# adserver/common/currency.py 라인 363-420
rate = CurrencyManager.new_currency_rate(src_currency, dst_currency)

# 통화별 반올림 규칙
# KRW: 정수 단위 (소수점 없음)
# USD: 소수점 2자리
# 기타: 그대로
```

#### unit_sales 계산 흐름 다이어그램

```
전환 발생
  │
  ├─ ADN Fixed Revenue Share 있음? ──Yes──> unit_price × RS% × 환율
  │                                         (네트워크 광고 전용)
  │
  ├─ target_unit_sales[unit_id] 있음? ──Yes──> 해당 값 × 환율
  │   (Dash에서 유닛별 단가 입력)
  │
  ├─ unit_group_sales 있음? ──Yes──> max(values) × 환율
  │   (Dash에서 그룹별 단가 입력)
  │
  ├─ default_unit_prices[rev_type] 있음? ──Yes──> 기본 단가 × 환율
  │   (KR 비자사 매체)
  │
  └─ Fallback ──> unit_price × revenue_rate × 환율
```

> **출처**: `adserver/common/currency.py` 라인 439-507 `get_unit_lineitem_sales()`

### 4.3 action_reward (유저 보상 포인트) 결정

유저가 전환 시 받는 포인트를 계산한다. 이것도 우선순위가 있다.

> **핵심 함수**: `CurrencyManager.get_action_reward()`
> **파일**: `adserver/common/currency.py` 라인 692-762

| 우선순위 | 조건 | 계산 |
|---------|------|------|
| 1 | 비인센티브 광고 | `settings.NON_INCENTIVE_REWARD` (고정값) |
| 2 | ADN 고정 action point | `ADNETWORK_FIXED_ACTION_POINT[adnetwork_id]` |
| 3 | 카카오페이 전용 | `KakaopayPointAssignmentManager.decide_action_point()` |
| 4 | action_point 필드가 설정됨 | `action_point × 환율 × POINT_RATE[통화]` |
| 5 | Fallback | `unit_sales × reward_rate × POINT_RATE[통화]` |

**POINT_RATE** (통화별 포인트 배율):

| 통화 | 배율 | 의미 |
|------|------|------|
| KRW | 1 | 1원 = 1포인트 |
| USD | 1000 | 1달러 = 1000포인트 |
| JPY | 10 | 1엔 = 10포인트 |
| IDR | 1 | 1루피아 = 1포인트 |

### 4.4 전환 기록 전체 흐름

```
전환 이벤트 발생
  │
  ▼
ConversionService._add_conversion()
  │  (adserver/action/ddd/service/conversion_strategies.py)
  │
  ├─ sales = lineitem.unit_price
  ├─ unit_sales = CurrencyManager.get_unit_lineitem_sales(unit, lineitem)
  ├─ action_reward = CurrencyManager.get_action_reward(...)
  │
  ▼
ConversionService._create_conversion()
  │
  ├─ RawDataConversions 레코드 생성
  │   - sales, unit_sales, is_forced_conversion 기록
  │
  ├─ Kafka에 전환 데이터 발행
  │   - produce_conversion_topic()
  │
  └─ 유저에게 포인트 지급
      - action_reward만큼
```

> **출처**: `adserver/action/ddd/service/conversion_strategies.py` ConversionService._add_conversion() 라인 319

---

## 5. Phase 3: 리포트 금액 — Dash UI에 표시되는 cost

Dash의 라인아이템/애드그룹 리포트 탭에서 담당자가 보는 **"비용"** 컬럼은 `cost`라는 단일 필드이다.

### 5.1 revenue_type별 cost 계산

`cost`는 StatsService(gRPC)에서 revenue_type에 따라 **사전 계산**되어 반환된다. Python 코드에서는 이미 계산된 값을 받아서 합산만 한다.

| revenue_type | cost 계산 공식 | 예시 (unit_price=100) |
|---|---|---|
| **CPM** (노출 기반) | impression ÷ 1000 × unit_price | 10,000 노출 → cost = 1,000 |
| **CPC** (클릭 기반) | click × unit_price | 50 클릭 → cost = 5,000 |
| **CPA** (전환 기반) | action(전환) × unit_price | 10 전환 → cost = 1,000 |
| **CPK/CPE/CPS** | action × unit_price | CPA와 동일 방식 |

> **출처**: `adserver/ddd/adapters/repos/remote_report_repo.py` 라인 236-246
> CPA 라인아이템은 `action` 기반, 나머지는 `click` 기반으로 식별된다.

### 5.2 데이터 소스와 병합

리포트 데이터는 두 가지 소스에서 가져와 병합된다:

```
StatsService (gRPC)
  ├─ MySQL: 2일 이전 확정 데이터
  └─ Redis: 최근 2일 실시간 캐시
      │
      ▼
  _make_merged_report()    ← MySQL + Redis 병합
      │
      ▼
  _make_total_report()     ← 기간 전체 합산
      │
      ▼
  BaseReportSerializer     ← API 응답으로 직렬화
      │
      ▼
  Dash UI "비용" 컬럼     ← 프론트엔드 표시
```

> **출처**: `adserver/services.py` 라인 210-272 (`_make_merged_report`, `_make_total_report`)

### 5.3 PerformanceReport 합산 로직

리포트 데이터의 합산은 `PerformanceReport` Value Object의 `__add__` 연산자로 수행된다. 단순 더하기이다.

```python
# adserver/ddd/domain/statssvc_values.py

@dataclass(kw_only=True)
class PerformanceReport:
    impression: int = 0
    click: int = 0
    action: int = 0        # 전환 수
    cost: int = 0          # 비용 (단일 통합 필드)

    def __add__(self, vo: PerformanceReport) -> PerformanceReport:
        return PerformanceReport(
            impression=self.impression + vo.impression,
            click=self.click + vo.click,
            action=self.action + vo.action,
            cost=self.cost + vo.cost,  # 단순 합산
        )
```

> **출처**: `adserver/ddd/domain/statssvc_values.py`

### 5.4 API 응답 직렬화

API가 Dash 프론트엔드에 반환하는 리포트 필드들이다:

```python
# adserver/api/views/serializers.py 라인 224-256

class BaseReportSerializer(serializers.Serializer):
    conversion = IntegerField(source='action')  # 전환 수
    click = IntegerField()
    impression = IntegerField()
    cost = IntegerField()                        # ← Dash에 표시되는 금액
    unique_impression = IntegerField()
    unique_click = IntegerField()
    dna = DictField()                            # DNA(Dynamic Ads) 이벤트
    cs_action = IntegerField()                   # 강제 전환 수
```

> **출처**: `adserver/api/views/serializers.py` 라인 224-256

### 5.5 Dash 프론트엔드에서의 표시

프론트엔드에서 `cost`는 통화에 따라 반올림 방식이 다르다:

| 통화 | 반올림 | 예시 |
|------|--------|------|
| KRW | `Math.ceil` (올림) | 123.4 → 124 |
| 기타 | `Math.floor` (내림) | 1.234 → 1.23 |

리포트에서 추가로 **계산되는 지표들** (프론트엔드에서 계산):

| 지표 | 공식 | 출처 |
|------|------|------|
| CTR | click ÷ impression × 100 | 프론트엔드 계산 |
| CVR | conversion ÷ click × 100 | 프론트엔드 계산 |
| ROAS | dna.sales ÷ cost × 100 | 프론트엔드 계산 |
| CPP | cost ÷ dna.purchase | 프론트엔드 계산 |

> **출처**: Dash 프론트엔드 `dash/src/modules/campaign/views/direct_sales/detail/lineitem/lineitem-report.vue`
> 및 `dash/src/model/baAnalyticsAdGroup.js`

### 5.6 데이터 흐름 전체 경로 (API 엔드포인트 추적)

```
Dash 프론트엔드
  GET /ba/ads/{id}/reports?start_date=...&end_date=...
      │
      ▼
dash-api-gateway (순수 프록시, 금액 로직 없음)
  proxyBA("/api/service/lineitems/{id}/report")
      │   (dash-api-gateway/routers/ba.js 라인 633)
      ▼
adserver API
  ServiceLineitemDetailSerializer
      │   (api/views/serializers.py 라인 471)
      ▼
  LineitemReportFieldSerializer._get_report_data()
      │
      ▼
  get_full_lineitem_report()
      │   (adserver/services.py 라인 795-885)
      ▼
  PerformanceReportRepository.get_lineitem_report_from_statssvc_mysql_and_redis()
      │
      ▼
  StatsProvider (gRPC) → MySQL/Redis에서 cost 조회
```

> **출처**: `dash-api-gateway/routers/ba.js` 라인 633, `dash-api-gateway/proxy/ba.js`, `adserver/services.py` 라인 795-885

---

## 6. Phase 4: 정산 — Salesforce 양방향 연동

직영업 광고의 정산은 Salesforce와 자동으로 연동된다. 캠페인 생명주기에 따라 3단계로 동작한다.

### 6.1 캠페인 생성 시: adserver → Salesforce

Collaborative 캠페인이 생성되면, `_sync_salesforce()` 메서드가 Salesforce에 Opportunity를 자동 생성한다.

**전달되는 주요 필드:**

| Salesforce 필드 | 값 | 설명 |
|-----------------|----|----|
| `Amount` | `entity.total_budget` | 캠페인 총 예산 |
| `Unit_Price__c` | `20` (하드코딩) | 기본 단가 |
| `Adscenter__c` | `"[광고센터-자동]collaborative_campaign_{id}"` | 연결 키 |
| `Start_Date__c` | 캠페인 시작일 | |
| `End_Date__c` | 캠페인 종료일 | |
| `StageName` | `"제안"` | 초기 단계 |
| `SalesChannel__c` | `"OC"` 또는 `"OA"` | 광고주 직접/대행사 경유 |

> **출처**: `adserver/adscenter/collaborative/application/campaign_create_use_case.py` `_sync_salesforce()`

### 6.2 캠페인 종료 다음날: adserver → Salesforce (매일 배치)

`CampaignSFUploadUseCase`가 매일 실행되어, **어제 종료된 캠페인의 실제 소진 금액**으로 SF Opportunity의 `Amount`를 덮어쓴다.

| 캠페인 유형 | 소진 금액 계산 | 조건 |
|---|---|---|
| LiveCommerce | `unique_click_count × unit_price` | 소진 < 예산일 때만 업데이트 |
| Collaborative | `report.cost` | 소진 < total_budget일 때만 업데이트 |

> **출처**: `adserver/adscenter/billing/application/usecases/campaign_sf_upload_usecase.py`

### 6.3 정산 기간 (매월 1~10일): Salesforce → adserver (매일 배치)

`BillingStatementSFDownloadUseCase`가 정산기간에 실행되어, SF Opportunity의 금액을 adserver로 역동기화한다.

**가져오는 필드:**

| Salesforce 필드 | adserver 필드 | 용도 |
|-----------------|--------------|------|
| `Amount` | `spent_budget` | 소진 금액 (정산 기준) |
| `Agency_Rep_FeeRate__c` | `agency_fee_rate` | 대행사 수수료율 (100으로 나눔) |

> **출처**: `adserver/adscenter/billing/application/usecases/billing_statement_sf_download_usecase.py`

### 6.4 최종 정산 금액 계산

```
spent_budget  = SF Amount (실제 소진금액, source of truth)
vat           = spent_budget × 10%
agency_fee    = (spent_budget + vat) × agency_fee_rate
payment       = spent_budget + vat - agency_fee
```

**예시** (spent_budget = 1,000원, agency_fee_rate = 20%):
```
spent_budget  = 1,000원
vat           =   100원  (1,000 × 10%)
agency_fee    =   220원  ((1,000 + 100) × 20%)
payment       =   880원  (1,000 + 100 - 220)
```

> **출처**: `adserver/docs/specs/billing-statement-implementation.md`

### 6.5 연결 키

Salesforce Opportunity와 adserver 캠페인을 연결하는 키는 `Adscenter__c` 커스텀 필드이다:
- LiveCommerce: `livecommerce_campaign_{campaign_id}`
- Collaborative: `collaborative_campaign_{campaign_id}`

> **출처**: `adserver/adscenter/salesforce/utils.py`

### 6.6 정산 흐름 다이어그램

```
[캠페인 생성]
  adserver ──Amount=total_budget──> SF Opportunity 생성
                                    (StageName="제안")

[캠페인 운영 중]
  Dash UI에서 cost(리포트) 확인
  세일즈가 SF에서 금액 수정 가능

[캠페인 종료 다음날] (배치)
  adserver ──Amount=실제소진금액──> SF Opportunity 업데이트

[정산 기간 매월 1~10일] (배치)
  SF Opportunity ──Amount, FeeRate──> adserver BillingStatement
                                       ├─ spent_budget 확정
                                       ├─ VAT 계산
                                       ├─ agency_fee 차감
                                       └─ payment_amount 산출
```

---

## 7. 직영업(A) vs 네트워크(E) 차이

라인아이템의 `item_type`에 따라 금액 처리 방식이 크게 달라진다.

| 구분 | 직영업 (`item_type=A`) | 네트워크 (`item_type=E`) |
|------|----------------------|------------------------|
| **unit_price 설정** | 세일즈가 Dash에서 직접 입력 | 광고주/ADN이 설정 |
| **unit_sales 결정** | ① target_unit_sales ② unit_group_sales ③ revenue_rate × unit_price | ① **ADN fixed revenue share** (최우선) ② unit_group_sales (ADN 매핑) ③ revenue_rate × unit_price |
| **target_unit_sales** | 유닛 개별 단가 지정 가능 | 일반적으로 사용 안 함 |
| **자동화** | 수동 설정 | `StaticAutomationService` 자동 매핑 (platform/country/sales 검증) |
| **정산** | Salesforce 연동 (자동 배치) | unit_sales 기반 시스템 계산 |
| **Dash에서 보는 것** | unit_price, budget, cost(리포트) | unit_price, ADN 매핑 sales |

### 네트워크 자동화의 sales 검증

네트워크 라인아이템은 `StaticAutomationService`가 매핑 시 sales를 검증한다:

```python
# adserver/network/ddd/service/static_automation_service.py 라인 85-107

def _is_valid_sales(self, unit_group, mapping):
    convert_rate = CurrencyManager.new_currency_rate(
        unit_group.currency, lineitem.currency
    )
    # 매핑의 sales를 라인아이템 통화로 환산했을 때,
    # unit_price보다 크면 안 된다 (매체비 > 광고주 단가이면 적자)
    if mapping.sales and lineitem.unit_price < mapping.sales * convert_rate:
        return False
    return True
```

> **출처**: `adserver/network/ddd/service/static_automation_service.py` 라인 85-107, 153-158

---

## 8. 부록: is_forced_conversion, sales, unit_sales 필드 상세

### 8.1 is_forced_conversion (강제 전환)

| 항목 | 내용 |
|------|------|
| **테이블** | `buzzad.raw_data_conversions` (MySQL) |
| **Athena** | `prod_buzzad.l_cdc_raw_data_conversions`, `prod_buzzad.g_raw_data_conversion` |
| **타입** | BooleanField / tinyint(1) |
| **`False` (0)** | 시스템이 자동 감지한 정상 전환 |
| **`True` (1)** | 관리자가 `force_conversion()`으로 수동 적립한 전환 |

**비즈니스 로직에서의 역할:**

1. **검증 우회**: `True`이면 포스트백 윈도우, 유기 프로필 검증 등 자동 거절 로직을 **건너뛴다** (스탭이 강제로 적립한 건이므로 신뢰)

   > `adserver/action/ddd/service/multi_reward_service.py` process_mission_reward()

2. **멀티리워드 카운트 제외**: 정상 전환만 카운트할 때 `is_forced_conversion=False`로 필터링

   > `adserver/network/ddd/repos/django_raw_data_conversions_repo.py` has_succeeded_conversions_by_viewer_id_and_lineitem_id_without_forced_conversion() 라인 156-161

3. **CS 문의 처리**: 강제 적립 전환의 ID를 조회하여 포인트 로그 처리

   > `adserver/network/ddd/repos/django_adnetwork_cs_inquiry_repo.py`

4. **리포트 분리**: 대시보드에서 정상 전환과 강제 전환을 구분하여 집계

   > Redash 쿼리 #31868 "is_forced_conversion 기록 잘 되고 있는가" (Tiana Lee 작성)

**사용 시나리오**: CS 보상 지급, 이벤트 보상, 테스트 데이터 생성 등

### 8.2 sales (광고주 정산 금액) 상세

`sales`는 전환 테이블(`RawDataConversions`)뿐 아니라 여러 매핑 테이블에서도 사용된다. 문맥에 따라 의미가 약간 다르다.

| 테이블 | 의미 | 타입 |
|--------|------|------|
| `RawDataConversions.sales` | 전환 1건에 대한 광고주 정산 금액 | Decimal(18,9) |
| `UnitLineitemMappings.sales` | 유닛-라인아이템 매핑의 판매 단가 | Decimal(18,9) |
| `UnitGroupLineitemMappings.sales` | 유닛그룹-라인아이템 매핑의 판매 단가 | Decimal(18,9) |
| `UnitGroupAdnetworkMapping.sales` | ADN별 최소 판매 가격 기준값 | Decimal(18,9) |

> **출처**: `adserver/orders/models/models.py` 라인 1993, 2016, 2043, 2113
> **네트워크 모델**: `adserver/network/models.py` 라인 73

### 8.3 unit_sales (매체 정산 금액) 상세

| 항목 | 내용 |
|------|------|
| **테이블** | `RawDataConversions.unit_sales`, `IgnoredConversions.unit_sales` |
| **타입** | Decimal(18,9) / Decimal(12,4) |
| **계산** | `CurrencyManager.get_unit_lineitem_sales(unit, lineitem)` (4.2절 참조) |

**Redash 실무 사용 패턴** (Redash 쿼리 시리즈, sophie jang 작성):

```sql
-- 버즈빌 마진 계산
SELECT sum(c.sales - c.unit_sales) AS margin
FROM prod_buzzad.v_conversion c
```

`sales - unit_sales`가 버즈빌의 순수 마진(take rate)이다.

> **출처**: Redash 쿼리 "[4차]sales-unit_sales_CPK/CPInsta/CPYoutube/CPL", "[5차]sales-unit_sales_CPK" (ad-action 태그)

### 8.4 lockjoyUS.raw_data_conversions

DataHub에 `lockjoyUS`라는 별도 스키마는 등록되어 있지 않다. 실체는 **`buzzad.raw_data_conversions`** (MySQL)이며, `lockjoyUS`는 buzzad의 과거 이름 또는 US 리전 DB 인스턴스 별칭으로 추정된다. Athena CDC 복제본은 `prod_buzzad.l_cdc_raw_data_conversions`이다.

> **출처**: DataHub 검색 결과 — `prod_buzzad.l_cdc_raw_data_conversions` 엔티티

---

## 9. 참조 파일 색인

### adserver (백엔드)

| 파일 경로 | 역할 |
|----------|------|
| `adserver/orders/models/models.py` | 라인아이템, RawDataConversions 등 모델 정의. 모든 금액 필드의 원천 |
| `common/currency.py` | **CurrencyManager** — unit_sales, action_reward, 환율 계산의 핵심 |
| `action/ddd/service/conversion_strategies.py` | 전환 시 sales, unit_sales, action_reward 계산 및 기록 |
| `network/ddd/service/static_automation_service.py` | 네트워크 라인아이템의 자동 매핑 및 sales 검증 |
| `cms/serializers/serializers.py` | API 응답에서 금액 필드 직렬화 |
| `api/views/serializers.py` | BaseReportSerializer — 리포트 API 응답 |
| `adserver/services.py` (라인 210-885) | 리포트 데이터 조회, 병합, 합산 |
| `adserver/ddd/domain/statssvc_values.py` | PerformanceReport VO — cost 합산 로직 |
| `adserver/ddd/adapters/repos/remote_report_repo.py` | StatsService 연동, revenue_type별 분기 |
| `adscenter/collaborative/application/campaign_create_use_case.py` | Salesforce Opportunity 자동 생성 |
| `adscenter/billing/application/usecases/campaign_sf_upload_usecase.py` | 소진금액 SF 업로드 (매일 배치) |
| `adscenter/billing/application/usecases/billing_statement_sf_download_usecase.py` | SF 금액 역동기화 (정산 기간) |
| `adscenter/salesforce/utils.py` | SF 연결 키 (Adscenter__c) 생성 |
| `docs/specs/billing-statement-implementation.md` | 정산 금액 계산 명세 |

### dash-api-gateway (API 게이트웨이)

| 파일 경로 | 역할 |
|----------|------|
| `routers/ba.js` | BA 라우터 — 모든 광고 관련 API 경로 정의 |
| `proxy/ba.js` | 프록시 래퍼 (express-http-proxy) |
| `lib/payoutQuery.js` | 정산 쿼리 필터링 미들웨어 |

> dash-api-gateway는 **순수 프록시**이다. 금액 관련 비즈니스 로직은 없으며, 요청을 adserver로 전달하고 응답을 그대로 반환한다.

### dash (프론트엔드)

| 파일 경로 | 역할 |
|----------|------|
| `src/model/baAd.js` | 라인아이템 모델 — 금액 필드 매핑 |
| `src/model/baAnalyticsAdGroup.js` | 애드그룹 리포트 — cost 반올림, CTR/CVR/ROAS 계산 |
| `src/modules/campaign/views/direct_sales/detail/lineitem/budget.vue` | 라인아이템 예산/단가 입력 폼 |
| `src/modules/campaign/views/direct_sales/detail/lineitem/lineitem-report.vue` | 라인아이템 리포트 (cost 표시) |
| `src/modules/campaign/views/direct_sales/detail/adgroup/form/create-edit-section/budget.vue` | 애드그룹 예산 입력 폼 |
| `src/component/forms/inputs/target/units/field-group-unit.vue` | 유닛 타겟팅 폼 — 유닛별/그룹별 단가 입력 |

### 데이터 파이프라인 / 분석

| 리소스 | 역할 |
|--------|------|
| `prod_buzzad.v_conversion` (Athena) | 전환 데이터 뷰 — sales, unit_sales 컬럼 |
| `prod_buzzad.g_raw_data_conversion` (Athena) | 원본 전환 데이터 — is_forced_conversion 포함 |
| `prod_buzzad.v_statistics_unit_lineitem` (Athena) | 시간당 통계 뷰 — lineitem_sales_sum, unit_sales_sum |
| Redash 쿼리 #31868 | is_forced_conversion 검증 쿼리 (Tiana Lee) |
| Redash 쿼리 시리즈 "[4차]/[5차] sales-unit_sales" | 마진 분석 쿼리 (sophie jang) |
| `adpacingsvc/src/adpacing/entrypoints/unit_sales_aggregator.py` | unit_sales 집계 전용 서비스 |

---

> **면책**: 이 리포트는 2026-03-24 기준 코드베이스를 분석한 결과이다. 코드 변경에 따라 실제 동작과 다를 수 있다.
