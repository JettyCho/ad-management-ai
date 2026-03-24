# Team

## 코드베이스

각 프로젝트의 로컬 경로는 팀원마다 다르므로 `.env` 파일에서 해당 환경 변수를 읽어서 사용한다.

### adserver (buzzad)

buzzad라고도 불린다. 대시(dash)와 광고센터(ads-center)의 백엔드. 광고 할당, 송출, 통계, 정산 등 광고 비즈니스의 핵심 로직을 담당한다.
Python(Django) 기반이며, MySQL, Redis, Kafka, DynamoDB 등 다양한 인프라와 연동된다.

- GitHub: https://github.com/Buzzvil/adserver
- 로컬 경로: `.env`의 `ADSERVER_PATH`
- **인프라 식별자**: Kubernetes namespace, container, Loki/Grafana 라벨 등 인프라에서는 `buzzad`를 사용한다. 로그 조회, 메트릭 쿼리, 모니터링 등에서는 `adserver`가 아닌 **`buzzad`**로 검색해야 한다.

### ads-center (광고센터)

광고주용 셀프서빙 플랫폼의 프론트엔드. 광고 캠페인 생성, 관리, 리포트 등의 UI를 제공한다.
Next.js(App Router) + shadcn/ui 기반이며, 백엔드는 adserver를 사용한다.

- GitHub: https://github.com/Buzzvil/ads-center
- 웹사이트: https://ads.buzzvil.com
- 로컬 경로: `.env`의 `ADS_CENTER_PATH`
- 로그인 정보 `.env`의 `ADS_CENTER_ID`, `ADS_CENTER_PW`
- 사용 가이드: https://buzzvil.gitbook.io/guide
  - 광고주/대행사 대상의 광고센터 이용 가이드. 회원가입, 비즈니스 그룹·운영 그룹 설정, 광고 상품별 캠페인 생성 및 운영 방법, 소재 가이드, 리포트 확인, 정산까지의 전체 플로우를 다룬다.
  - 주요 섹션: 시작하기(그룹 구조·생성·관리) / 광고 상품(라이브커머스, 협력광고, 웹 리타겟팅) / UA 가이드(MMP 연동) / 연동(Pixel SDK, 스크립트) / 정책(소재 심사, 블록체인) / 정산

### dash (대시)

Buzzvil 내부 운영 대시보드의 프론트엔드. 광고 운영, 매체 관리 등 내부 업무용 UI를 제공한다.
Vue 기반이며, 백엔드는 adserver를 사용한다.

- GitHub: https://github.com/Buzzvil/dash
- 웹사이트: https://dashboard.buzzvil.com
- 로컬 경로: `.env`의 `DASH_PATH`

### dash-api-gateway

Dash의 BFF(Backend For Frontend). Dash 프론트엔드와 백엔드 서비스 사이의 API 게이트웨이 역할을 한다.
Node.js 기반이다.

- GitHub: https://github.com/Buzzvil/dash-api-gateway
- 로컬 경로: `.env`의 `DASH_API_GATEWAY_PATH`

## 문서자료

팀 문서는 Confluence에서 관리된다. cloudId는 `buzzvil.atlassian.net`을 사용한다.

### Demand 스페이스

ADM 팀이 속한 Demand 그룹 전체의 문서 공간이다. 그룹 차원의 미션, 비전, OKR, 사업계획, QBR/MBR, 업종 리포트 등이 관리된다. 팀의 업무 맥락을 이해하려면 이 스페이스의 문서도 함께 참고해야 한다.

- 스페이스 키: `DEM` (스페이스 ID: `1374945760`)
- 홈페이지 ID: `1374945812`
- URL: https://buzzvil.atlassian.net/wiki/spaces/DEM

### Ad Management 팀 페이지

Demand 스페이스 안에 있는 ADM 팀 전용 페이지이다. 팀의 일하는 방식, OKR, PRD, 스프린트, 런북, 회의록, 회고 등 팀 운영에 필요한 모든 문서가 이 페이지 하위에 정리되어 있다.

- 페이지 ID: `1427013947`
- URL: https://buzzvil.atlassian.net/wiki/spaces/DEM/pages/1427013947/Ad+Management

팀 문서를 찾을 때는 이 페이지를 기준으로 하위 페이지를 탐색하면 된다.

## 슬랙 채널

### 버즈빌 전사 채널

- `#_the_buzzvil_times` (C3E2ZPUGP) — 업계 뉴스, 외부 기사, 버즈빌 관련 소식 공유
- `#announcement` (CJQGE9C07) — 전사 공지사항 및 Team Lead 미팅 노트 공유
- `#office-kr` (C07JHRX4L) — 한국 오피스 운영 안내 (보안 정책, 주차, 복지 등)

### Demand 그룹 채널

- `#demand-group` (C01HATVTX8U) — Demand 그룹 전체 소통. WBR 노트, 세일즈 회의록 등 공유
- `#demand-product` (C01HYJT0W7Q) — Demand 프로덕트 전반 논의. PRD 전달 등
- `#demand-product-managers` (C0583NV7C3T) — Demand PM들의 운영 채널. PPP 미팅, WBR 안건 조율
- `#demand-product-sales-strategy` (C06A2T67TLK) — 세일즈 자동화, 소재 프리뷰 발송, Salesforce 연동 등 세일즈-프로덕트 전략 논의

### Demand 그룹 내 타 팀 채널

- `#ad-expansion` (C087QNJP333) — Ad Expansion 팀. 협력광고, 세그먼트, CPK 등 광고 확장 관련
- `#ad-platform` (C01HKBNRS5D) — Ad Platform 팀. bidder, adserver 인프라, 배포 공유
- `#ad-product-action` (C01JGT46AG5) — Ad Product 팀. 액션형 광고(UA, 멀티미션 등) 운영 및 이슈 논의
- `#ad-spark` (C0AAF81D9ML) — Ad Spark 팀. buzzlib 내재화, UA 멀티미션 등 신규 기능 개발

### ADM 팀 운영

- `#ad-management` (C01HX8TMHAN) — ADM 팀 메인 채널. 팀 내 개발 논의, PR 리뷰 요청, 기술적 질의응답
- `#dash` (C4XAJEDEU) — 대시 관련 문의 인입. 권한 요청, dev 환경 이슈, CI 실패 등
- `#dash-bd` (CMKQDM4T0) — BDM팀이 대시보드 관련 문의를 올리는 채널. 매체사 계정 권한, 유닛 관련
- `#dash-sales-cm` (CM66H2142) — 세일즈/CM팀과 대시 운영 이슈 소통. 소재 예약, 라이브커머스 세팅 등
- `#세일즈포스` (C0AK8SWBKRB) — Salesforce 내재화 프로젝트 논의. 마이그레이션 계획, 유스케이스 정리

### ADM 팀 상품 채널

- `#라이브커머스` (C09BGG18Z39) — 라이브커머스 상품 운영. 캠페인 검수, 라이브 일정, 체류형 이슈
- `#협력광고` (C096UPT9D8A) — 협력광고 상품 운영. 소재 심사, 브랜드 인사이트 리포트, 인터랙션 전략
- `#광고센터` (C0ACRBATPT6) — 광고센터(ads-center) 관련. RMN 캠페인, 비즈니스그룹 심사, UI 개선

### 알림·모니터링 채널

- `#adm-emergency` (C02E9B935QQ) — ADM 긴급 알림. Datadog 모니터 알림 및 광고 운영 긴급 이슈
- `#adm-exception` (C01KZQL7KL2) — Sentry 에러 알림. Dashboard(대시) 프로젝트의 에러 자동 수집
- `#biz-emergency` (C04PWLNV9BL) — 비즈니스 긴급 알림. Datadog 기반 비즈니스 임팩트 모니터링
- `#dash-장애알림센터` (C087JMQ1R4J) — 대시 장애·공지사항 팝업 관련 문의 인입 채널

### 개발자 명령어 채널

- `#buzzad-commands` (C012H0JKRAM) — 프로덕션 환경 명령어 실행. kiki 봇을 통해 할당, 비활성화, 우선순위 변경 등 수행
- `#buzzad-commands-test` (C012FG9EDNW) — staging/prod-beta 환경 명령어 실행. 테스트용 명령어 및 검증
