---
name: adcenter-weekly
description: 매주 sales@buzzvil.com 이메일에서 광고센터(셀프서빙 플랫폼) 관련 고객 불편/문의를 자동 분석하고 HTML 리포트를 생성합니다. TRIGGER when: Cron 자동 실행 또는 사용자가 "광고센터 주간 분석", "이번 주 광고센터 문의" 등을 요청할 때.
argument-hint: (선택) 분석할 주의 날짜 범위 (예: "2026-05-12~2026-05-15"). 생략 시 이번 주 자동 계산.
disable-model-invocation: false
context: compress
allowed-tools: mcp__google_workspace__search_gmail_messages, mcp__google_workspace__get_gmail_messages_content_batch, mcp__google_workspace__get_gmail_message_content, Read, Write
---

# 광고센터 주간 문의 분석

## 광고센터 문의 정의

**포함 (광고센터 셀프서빙 플랫폼 이슈)**:
- 소재/캠페인 삭제·숨김 요청
- 멤버 초대 오류, 계정 접근 오류
- 협력광고 등록 방법, 셀프서빙 구조 질문
- 비즈니스 정보/심사 관련 문의
- 성과 지표·데이터 정의 질문
- 광고머니 충전, 가상계좌 오류
- 쿠폰 사용법, 라이브커머스 취소 방법

**제외 (매니지드 운영 이메일)**:
- 에이전시가 버즈빌 매니저에게 캠페인 세팅/소재 교체/예산 변경을 요청하는 이메일
- 검수 요청 중 "빨리 해주세요" 등 매니저에게 처리를 부탁하는 이메일
- 미디어믹스 제안, 계약서, 정산 청구 등 순수 B2B 영업 이메일

---

## Step 1 — 기간 및 데이터 로드

**날짜 범위 계산**:
- 인자가 주어지면 해당 범위 사용
- 없으면 오늘(`$TODAY`) 기준으로 이번 주 월요일~오늘(금요일)을 계산
- Gmail `newer_than` 파라미터용 일수(days) 산출 (월요일 기준 최대 7d)

**파일 로드** (병렬):
1. `.claude/skills/adcenter-weekly/keywords.json` → `terms` 배열 추출
2. `out/jetty/adcenter_weekly_data.json` → 이전 주차 누적 데이터 확보

---

## Step 2 — Gmail 수집

두 쿼리를 **병렬** 실행:

**쿼리 A — 직접 접수 문의**:
```
from:ads.noreply@buzzvil.com newer_than:7d
```
광고센터 문의하기 폼으로 접수된 이메일 전부.

**쿼리 B — 영업팀 이메일 중 키워드 포함 건**:
keywords.json의 terms를 OR로 연결하여 동적 생성:
```
to:sales@buzzvil.com newer_than:7d -from:ads.noreply@buzzvil.com (광고센터 OR 셀프서빙 OR 협력광고 OR ...)
```

각 쿼리로 최대 30건 수집. 스레드 ID 목록 확보 후 본문 읽기.

---

## Step 3 — 이슈 필터링 및 분류

수집된 각 스레드를 읽고 아래를 판단:

1. **광고센터 이슈 여부**: 위 정의 기준으로 포함/제외 결정
2. **카테고리 분류** (해당되는 것 모두):
   - `소재/캠페인 삭제 불가`
   - `계정/멤버 관리 오류`
   - `협력광고 구조/온보딩 불명확`
   - `성과 지표 정의 불명확`
   - `소재 검수 속도/절차`
   - `정산/가상계좌 시스템`
   - `기타 (신규 패턴)` — 위 카테고리에 해당하지 않는 새로운 유형

3. **요약 추출**: 회사명, 1줄 요약, 핵심 인용 문구 (있으면)

---

## Step 4 — 데이터 업데이트

`out/jetty/adcenter_weekly_data.json`을 읽고, 이번 주 항목을 추가하여 덮어쓰기.

이미 해당 `week` 키가 존재하면 덮어쓴다 (재실행 대비).

추가할 항목 구조:
```json
{
  "week": "2026-W{N}",
  "period": "YYYY-MM-DD~YYYY-MM-DD",
  "issues": [
    {
      "category": "카테고리명",
      "count": N,
      "examples": ["회사명 — 1줄 요약"]
    }
  ],
  "total": N
}
```

---

## Step 5 — HTML 리포트 생성

**저장 경로**: `out/jetty/adcenter_weekly_YYYYMMDD.html` (오늘 날짜)

**리포트 구성**:

### 헤더 섹션
- 분석 기간 (이번 주 날짜 범위)
- 이번 주 광고센터 문의 건수
- 누적 건수 (adcenter_weekly_data.json의 `count` 합산 — `count_one_time` 제외)

### 주별 문의 탭 섹션
JavaScript 탭으로 구성. `adcenter_weekly_data.json`의 모든 주차를 탭 버튼으로 렌더링.
- **pre 탭**: 카테고리별 요약 카드 그리드. `count_one_time > 0`인 카테고리에는 "일회성 N건 별도" 태그와 `one_time_note` 표시.
- **주차 탭 (W20, W21, …)**: 카테고리 배지 + 회사명 + 1줄 요약 테이블. 건수 0이면 "이번 주 광고센터 관련 문의 없음" 표시.

### 카테고리별 누적 트렌드 테이블
행: 카테고리, 열: 전체 주차 + 누적 합계.
- `count_one_time > 0`인 셀은 `N *` 형태로 표시하고 테이블 하단에 각주 출력.
- 이번 주에 새로 발생한 카테고리 강조.
- 누적 합계는 `count`만 사용 (`count_one_time` 제외).

### 주요 대화 발췌
이번 주 대표 케이스 2~3건. 실제 메일 인용 포함.

**스타일**: `out/jetty/sales_email_analysis.html`의 CSS 스타일 참고하여 동일한 디자인 언어 적용.

---

## 완료 보고

실행 완료 후 아래를 출력:
- 생성된 HTML 파일 경로
- 이번 주 광고센터 문의 건수 및 카테고리 분포 요약
- 누적 건수 기준 가장 많이 발생한 TOP 3 카테고리
