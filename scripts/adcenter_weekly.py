"""
광고센터 주간 문의 자동 분석 스크립트.
GitHub Actions에서 매주 금요일 08:30 KST에 실행.

환경변수 (GitHub Secrets):
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN
    ANTHROPIC_API_KEY
"""

import base64
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

REPO_ROOT = Path(__file__).parent.parent
DATA_FILE = REPO_ROOT / "out" / "jetty" / "adcenter_weekly_data.json"
KEYWORDS_FILE = REPO_ROOT / ".claude" / "skills" / "adcenter-weekly" / "keywords.json"


# ── Gmail 인증 ──────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


# ── 날짜 계산 ────────────────────────────────────────────────────────────────

def get_week_range():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    iso = today.isocalendar()
    week_label = f"{iso[0]}-W{iso[1]:02d}"
    return monday, friday, week_label


# ── Gmail 검색 ───────────────────────────────────────────────────────────────

def search_threads(service, query, max_results=30):
    result = service.users().threads().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    return result.get("threads", [])


def get_thread_text(service, thread_id):
    thread = service.users().threads().get(
        userId="me", threadId=thread_id, format="full"
    ).execute()
    texts = []
    for msg in thread.get("messages", []):
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "")
        sender = headers.get("From", "")
        date_str = headers.get("Date", "")
        body = _extract_body(msg["payload"])
        texts.append(f"[{date_str}] From: {sender}\nSubject: {subject}\n{body[:1500]}")
    return "\n\n---\n\n".join(texts)


def _extract_body(payload):
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


# ── Claude 분류 ──────────────────────────────────────────────────────────────

CATEGORIES = [
    "소재/캠페인 삭제 불가",
    "계정/멤버 관리 오류",
    "협력광고 구조/온보딩 불명확",
    "성과 지표 정의 불명확",
    "소재 검수 속도/절차",
    "정산/가상계좌 시스템",
    "기타 (신규 패턴)",
]

SYSTEM_PROMPT = """
당신은 버즈빌 광고센터(셀프서빙 플랫폼) 관련 고객 문의를 분류하는 분석가입니다.

[포함 기준 - 광고센터 셀프서빙 이슈]
- 소재/캠페인 삭제·숨김 요청
- 멤버 초대 오류, 계정 접근 오류
- 협력광고 등록 방법, 셀프서빙 구조 질문
- 비즈니스 정보/심사 관련 문의
- 성과 지표·데이터 정의 질문
- 광고머니 충전, 가상계좌 오류
- 쿠폰 사용법, 라이브커머스 취소 방법
- 예산 배분/소진 로직 불명확 (광고센터 UI/UX 관련)

[제외 기준]
- 에이전시가 버즈빌 매니저에게 캠페인 세팅/소재 교체/예산 변경을 요청하는 이메일
- 미디어믹스 제안, 계약서, 정산 청구 등 순수 B2B 영업 이메일
- 버즈빌 담당자가 외부에 먼저 제안을 보내는 outbound 영업 이메일
- 내부 테스트(staging/TEST 표기), 자동 알림 메일

카테고리:
1. 소재/캠페인 삭제 불가
2. 계정/멤버 관리 오류
3. 협력광고 구조/온보딩 불명확
4. 성과 지표 정의 불명확
5. 소재 검수 속도/절차
6. 정산/가상계좌 시스템
7. 기타 (신규 패턴)
""".strip()


def classify_thread(client, thread_text):
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""아래 이메일 스레드가 광고센터 이슈인지 판단하고, 맞다면 분류해주세요.

{thread_text}

JSON으로만 응답:
{{
  "is_adcenter_issue": true/false,
  "category": "카테고리명 또는 null",
  "company": "회사명",
  "summary": "1줄 요약"
}}"""
        }]
    )
    text = response.content[0].text.strip()
    # JSON 블록 추출
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return None


# ── HTML 생성 ────────────────────────────────────────────────────────────────

BADGE_CLASS = {
    "소재/캠페인 삭제 불가": "badge-red",
    "계정/멤버 관리 오류": "badge-blue",
    "협력광고 구조/온보딩 불명확": "badge-green",
    "성과 지표 정의 불명확": "badge-orange",
    "소재 검수 속도/절차": "badge-purple",
    "정산/가상계좌 시스템": "badge-gray",
    "기타 (신규 패턴)": "badge-teal",
}


def generate_html(data, week_label, period, this_week_total, cumulative_total):
    weeks = data["weeks"]
    monday_str, friday_str = period.split("~")

    tab_buttons = ""
    tab_panes = ""

    for w in weeks:
        wk = w["week"]
        if wk == "pre-analysis":
            tab_id = "pre"
            btn_label = "사전 분석 (2025-11~2026-05-11)"
        else:
            tab_id = wk.replace("-", "").replace("W", "w").lower()
            parts = w["period"].split("~")
            btn_label = f"{wk.split('-')[1]} · {parts[0][5:]}~{parts[1][5:]}"

        is_current = wk == week_label
        active_cls = " active" if is_current else ""
        tab_buttons += f'<button class="tab-btn{active_cls}" onclick="switchTab(\'{tab_id}\', event)">{btn_label}</button>\n'

        if wk == "pre-analysis":
            cards = ""
            for iss in w["issues"]:
                cat = iss["category"]
                bc = BADGE_CLASS.get(cat, "badge-gray")
                extra = ""
                if iss.get("count_one_time"):
                    extra = f'<span class="one-time-tag">일회성 {iss["count_one_time"]}건 별도</span>'
                    note = iss.get("one_time_note", "")
                    extra += f'<div style="color:#b45309;font-size:10px;margin-top:4px">* {note}</div>'
                examples_str = ", ".join(iss.get("examples", []))
                cards += f"""
        <div class="pre-card">
          <div class="cat-name"><span class="badge {bc}">{cat}</span></div>
          <div class="cat-count">{iss["count"]} {extra}</div>
          <div class="cat-examples">{examples_str}</div>
        </div>"""
            tab_panes += f"""
    <div id="tab-{tab_id}" class="tab-pane">
      <div class="pre-summary">{cards}
      </div>
      <p class="pre-note">사전 분석 기간(2025-11-01~2026-05-11)은 수동 집계. 일회성 이벤트(4/1 정산 오류)는 반복 이슈 집계에서 제외.</p>
    </div>"""
        else:
            rows = ""
            for iss in w["issues"]:
                cat = iss["category"]
                bc = BADGE_CLASS.get(cat, "badge-gray")
                for ex in iss.get("examples", []):
                    parts_ex = ex.split(" — ", 1)
                    company = parts_ex[0] if parts_ex else ex
                    summary = parts_ex[1] if len(parts_ex) > 1 else ""
                    rows += f"""
          <tr>
            <td><span class="badge {bc}">{cat}</span></td>
            <td>{company}</td>
            <td>{summary}</td>
          </tr>"""
            if not rows:
                rows = '<tr><td colspan="3" style="text-align:center;color:#aaa;padding:24px">이번 주 광고센터 관련 문의 없음</td></tr>'
            tab_panes += f"""
    <div id="tab-{tab_id}" class="tab-pane{active_cls}">
      <table class="issue-table">
        <thead><tr><th style="width:200px">카테고리</th><th style="width:160px">회사</th><th>내용 요약</th></tr></thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div>"""

    # 트렌드 테이블
    all_cats = [c for c in CATEGORIES]
    week_cols = [w for w in weeks if w["week"] != "pre-analysis"]
    week_cols_sorted = sorted(week_cols, key=lambda x: x["week"])

    def get_count(week_data, cat):
        for iss in week_data.get("issues", []):
            if iss["category"] == cat:
                return iss["count"], iss.get("count_one_time", 0)
        return 0, 0

    def get_pre_count(cat):
        pre = next((w for w in weeks if w["week"] == "pre-analysis"), None)
        if not pre:
            return 0, 0
        for iss in pre.get("issues", []):
            if iss["category"] == cat:
                return iss["count"], iss.get("count_one_time", 0)
        return 0, 0

    th_cols = '<th>pre</th>' + "".join(f'<th{"  class=\"current-week\"" if w["week"] == week_label else ""}>{w["week"].split("-")[1]}</th>' for w in week_cols_sorted) + '<th class="total-col">누적 합계</th>'
    tbody_rows = ""
    footnote_needed = False
    foot_totals = {"pre": 0}
    for w in week_cols_sorted:
        foot_totals[w["week"]] = 0
    foot_totals["total"] = 0

    for cat in all_cats:
        bc = BADGE_CLASS.get(cat, "badge-gray")
        pre_cnt, pre_one = get_pre_count(cat)
        foot_totals["pre"] += pre_cnt
        pre_cell = f'{pre_cnt} <sup>*</sup>' if pre_one > 0 else str(pre_cnt) if pre_cnt > 0 else "0"
        if pre_one > 0:
            footnote_needed = True
        row_total = pre_cnt
        week_cells = ""
        for w in week_cols_sorted:
            cnt, _ = get_count(w, cat)
            foot_totals[w["week"]] += cnt
            row_total += cnt
            is_cur = w["week"] == week_label
            hl = " highlight" if cnt > 0 and is_cur else ""
            cur_cls = " current-week" if is_cur else ""
            week_cells += f'<td class="{(cur_cls + hl).strip()}">{cnt if cnt > 0 else "0"}</td>'
        foot_totals["total"] += row_total
        tbody_rows += f"""
        <tr>
          <td><span class="badge {bc}" style="font-size:11px">{cat}</span></td>
          <td>{pre_cell}</td>
          {week_cells}
          <td class="total-col">{row_total}</td>
        </tr>"""

    foot_week_cells = ""
    for w in week_cols_sorted:
        is_cur = w["week"] == week_label
        cur_cls = ' class="current-week highlight"' if is_cur else ""
        foot_week_cells += f'<td{cur_cls}>{foot_totals[w["week"]]}</td>'

    footnote_html = ""
    if footnote_needed:
        footnote_html = '<p class="footnote"><sup>*</sup> 일회성 4건 별도 집계 제외 — 2026-04-01 수수료율 일괄 오류로 인한 드림인사이트 외 4개사 동시 발생. 반복 패턴 아님.</p>'

    period_label = f"{monday_str} ~ {friday_str[5:]}"
    next_friday = (datetime.strptime(friday_str, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>광고센터 주간 문의 분석 — {week_label}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif; background: #f5f6f8; color: #1a1a2e; line-height: 1.65; font-size: 15px; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 40px 24px 80px; }}
  .page-header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%); color: #fff; border-radius: 16px; padding: 40px 48px; margin-bottom: 32px; }}
  .page-header h1 {{ font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }}
  .page-header p {{ margin-top: 8px; color: #a0aec0; font-size: 14px; }}
  .meta-row {{ display: flex; gap: 32px; margin-top: 24px; flex-wrap: wrap; }}
  .meta-item {{ text-align: center; }}
  .meta-item .num {{ font-size: 36px; font-weight: 800; color: #e94560; }}
  .meta-item .lbl {{ font-size: 12px; color: #a0aec0; margin-top: 2px; }}
  h2 {{ font-size: 20px; font-weight: 700; margin-bottom: 16px; color: #1a1a2e; }}
  .section {{ background: #fff; border-radius: 12px; padding: 28px 32px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  .badge {{ display: inline-block; border-radius: 4px; font-size: 11px; font-weight: 600; padding: 3px 8px; white-space: nowrap; }}
  .badge-red    {{ background: #fee2e2; color: #b91c1c; }}
  .badge-blue   {{ background: #dbeafe; color: #1d4ed8; }}
  .badge-green  {{ background: #dcfce7; color: #15803d; }}
  .badge-orange {{ background: #ffedd5; color: #c2410c; }}
  .badge-purple {{ background: #ede9fe; color: #6d28d9; }}
  .badge-gray   {{ background: #f1f5f9; color: #475569; }}
  .badge-teal   {{ background: #ccfbf1; color: #0f766e; }}
  .issue-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  .issue-table th {{ background: #f8f9fc; padding: 10px 14px; text-align: left; font-weight: 700; color: #666; font-size: 12px; border-bottom: 2px solid #e8eaf0; }}
  .issue-table td {{ padding: 12px 14px; border-bottom: 1px solid #f0f2f5; vertical-align: top; }}
  .issue-table tr:last-child td {{ border-bottom: none; }}
  .issue-table tr:hover td {{ background: #fafbfc; }}
  .trend-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .trend-table th {{ background: #f8f9fc; padding: 10px 12px; text-align: center; font-weight: 700; color: #666; font-size: 12px; border-bottom: 2px solid #e8eaf0; border-right: 1px solid #e8eaf0; }}
  .trend-table th:first-child {{ text-align: left; }}
  .trend-table td {{ padding: 10px 12px; border-bottom: 1px solid #f0f2f5; border-right: 1px solid #f5f6f8; text-align: center; }}
  .trend-table td:first-child {{ text-align: left; font-weight: 500; }}
  .trend-table tr:last-child td {{ border-bottom: none; }}
  .trend-table .highlight {{ font-weight: 800; color: #e94560; }}
  .trend-table .current-week {{ background: #fff8f9; }}
  .trend-table .total-col {{ font-weight: 700; background: #f8f9fc; }}
  .trend-table tfoot td {{ background: #f8f9fc; font-weight: 700; }}
  .footnote {{ font-size: 12px; color: #888; margin-top: 10px; }}
  .footnote sup {{ color: #e94560; font-weight: 700; }}
  .tab-bar {{ display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }}
  .tab-btn {{ padding: 7px 16px; border-radius: 20px; border: 1.5px solid #e8eaf0; background: #fff; font-size: 13px; font-weight: 600; color: #666; cursor: pointer; transition: all 0.15s; }}
  .tab-btn:hover {{ border-color: #0f3460; color: #0f3460; }}
  .tab-btn.active {{ background: #0f3460; border-color: #0f3460; color: #fff; }}
  .tab-pane {{ display: none; }}
  .tab-pane.active {{ display: block; }}
  .pre-summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  @media (max-width: 600px) {{ .pre-summary {{ grid-template-columns: 1fr 1fr; }} }}
  .pre-card {{ background: #f8f9fc; border-radius: 8px; padding: 14px 16px; }}
  .pre-card .cat-name {{ font-size: 12px; color: #555; margin-bottom: 6px; }}
  .pre-card .cat-count {{ font-size: 24px; font-weight: 800; color: #1a1a2e; }}
  .pre-card .cat-examples {{ font-size: 11px; color: #888; margin-top: 4px; line-height: 1.5; }}
  .pre-note {{ font-size: 12px; color: #888; margin-top: 14px; }}
  .one-time-tag {{ background: #fef3c7; color: #92400e; border-radius: 3px; font-size: 10px; padding: 1px 5px; margin-left: 4px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="page-header">
    <h1>광고센터 주간 문의 분석</h1>
    <p>sales@buzzvil.com 수신 이메일 기준 · 광고센터(셀프서빙) 관련 이슈만 집계</p>
    <div class="meta-row">
      <div class="meta-item">
        <div class="num">{this_week_total}</div>
        <div class="lbl">이번 주 문의 ({week_label.split("-")[1]})</div>
      </div>
      <div class="meta-item">
        <div class="num">{cumulative_total}</div>
        <div class="lbl">누적 문의 (일회성 제외)</div>
      </div>
      <div class="meta-item">
        <div class="num" style="font-size:22px;letter-spacing:-1px">{period_label}</div>
        <div class="lbl">분석 기간</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>주별 문의 현황</h2>
    <div class="tab-bar">
      {tab_buttons}
    </div>
    {tab_panes}
  </div>

  <div class="section">
    <h2>카테고리별 누적 트렌드</h2>
    <table class="trend-table">
      <thead>
        <tr>
          <th>카테고리</th>
          {th_cols}
        </tr>
      </thead>
      <tbody>
        {tbody_rows}
      </tbody>
      <tfoot>
        <tr>
          <td>합계</td>
          <td>{foot_totals["pre"]}</td>
          {foot_week_cells}
          <td class="total-col">{foot_totals["total"]}</td>
        </tr>
      </tfoot>
    </table>
    {footnote_html}
  </div>

  <p style="text-align:center;font-size:12px;color:#aaa;margin-top:8px">
    자동 생성: {date.today().strftime("%Y-%m-%d")} · 다음 리포트: {next_friday} (금 08:30 KST)
  </p>
</div>
<script>
function switchTab(id, e) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  e.currentTarget.classList.add('active');
}}
</script>
</body>
</html>"""
    return html


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    monday, friday, week_label = get_week_range()
    period = f"{monday}~{friday}"
    print(f"분석 기간: {period} ({week_label})")

    keywords = json.loads(KEYWORDS_FILE.read_text())["terms"]
    kw_query = " OR ".join(keywords)

    print("Gmail 연결 중...")
    service = get_gmail_service()

    query_a = "from:ads.noreply@buzzvil.com newer_than:7d"
    query_b = f"to:sales@buzzvil.com newer_than:7d -from:ads.noreply@buzzvil.com ({kw_query})"

    print("이메일 수집 중...")
    threads_a = search_threads(service, query_a)
    threads_b = search_threads(service, query_b)

    all_thread_ids = list({t["id"] for t in threads_a + threads_b})
    print(f"수집된 스레드: {len(all_thread_ids)}건")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    issues_by_category = {}
    for tid in all_thread_ids:
        text = get_thread_text(service, tid)
        result = classify_thread(client, text)
        if result and result.get("is_adcenter_issue"):
            cat = result.get("category", "기타 (신규 패턴)")
            company = result.get("company", "")
            summary = result.get("summary", "")
            example = f"{company} — {summary}" if summary else company
            if cat not in issues_by_category:
                issues_by_category[cat] = []
            issues_by_category[cat].append(example)
            print(f"  [포함] {cat}: {example}")
        else:
            print(f"  [제외] 스레드 {tid}")

    this_week_issues = [
        {"category": cat, "count": len(examples), "examples": examples}
        for cat, examples in issues_by_category.items()
    ]
    this_week_total = sum(i["count"] for i in this_week_issues)
    print(f"\n이번 주 광고센터 문의: {this_week_total}건")

    data = json.loads(DATA_FILE.read_text())
    data["weeks"] = [w for w in data["weeks"] if w.get("week") != week_label]
    data["weeks"].insert(0, {
        "week": week_label,
        "period": period,
        "issues": this_week_issues,
        "total": this_week_total,
    })
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print("adcenter_weekly_data.json 업데이트 완료")

    cumulative_total = sum(
        i["count"]
        for w in data["weeks"]
        for i in w.get("issues", [])
    )

    html = generate_html(data, week_label, period, this_week_total, cumulative_total)
    out_file = REPO_ROOT / "out" / "jetty" / f"adcenter_weekly_{friday.strftime('%Y%m%d')}.html"
    out_file.write_text(html)

    print(f"HTML 생성: {out_file.name}")


if __name__ == "__main__":
    main()
