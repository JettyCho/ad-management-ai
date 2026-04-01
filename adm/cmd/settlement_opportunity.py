"""정산 예정 기회 상태 조회.

Usage:
    python -m adm.cmd.settlement_opportunity [YYYY-MM-DD]

start_date를 지정하지 않으면 현재 월의 1일을 사용합니다.
tsh proxy가 localhost:13306에서 실행 중이어야 합니다.

시트 구성:
  - 정산 예정: billingstatement.status_type = 'pending'
  - 정산 확정: billingstatement.status_type != 'pending' (confirm, auto 등)
"""

from __future__ import annotations

import re
import sys
from datetime import date

from simple_salesforce import Salesforce

from adm.cmd.gsheet import GoogleSheet
from adm.cmd.settlement import (
    OgInfo,
    build_og_info_map,
    get_db_connection,
    get_salesforce,
    get_user_email,
    load_env,
    run_soql,
)

# Adscenter__c 값에서 campaign_type, campaign_id 추출
_ADSCENTER_RE = re.compile(
    r"\[광고센터-(?:자동|수동)\](collaborative_campaign|livecommerce_campaign)_(\d+)"
)

# campaign_type 매핑: DB enum → SF Adscenter 값
_CAMPAIGN_TYPE_TO_SF = {
    "livecam": "livecommerce_campaign",
    "coad_campaign": "collaborative_campaign",
}


def parse_start_date(arg: str | None) -> str:
    """인자 → start_date 문자열. 없으면 현재 월 1일."""
    if arg:
        return arg
    today = date.today()
    return f"{today.year}-{today.month:02d}-01"


def fetch_campaigns_by_status(conn, start_date: str) -> tuple[list[dict], list[dict]]:
    """billingstatement의 campaign 목록을 pending / 그 외로 분리 조회."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT bs.id AS bs_id, bs.operationsgroup_id, bs.start_date, "
            "bs.status_type, "
            "bsc.id AS bsc_id, bsc.campaign_type, bsc.campaign_id, "
            "bsc.spent_budget, bsc.agency_fee_rate "
            "FROM billingstatement bs "
            "JOIN billingstatement_campaign bsc ON bsc.billingstatement_id = bs.id "
            "WHERE bs.start_date = %s "
            "ORDER BY bs.operationsgroup_id, bsc.campaign_type, bsc.campaign_id",
            (start_date,),
        )
        all_rows = cur.fetchall()

    pending = [r for r in all_rows if r["status_type"] == "pending"]
    confirmed = [r for r in all_rows if r["status_type"] != "pending"]
    return pending, confirmed


def fetch_sf_opportunities(
    sf: Salesforce,
    campaigns: list[dict],
) -> dict[tuple[str, int], list[dict]]:
    """campaign 목록을 기반으로 SF Opportunity 조회. (campaign_type, campaign_id) → opps 맵."""

    # Adscenter__c LIKE 검색용 키워드 수집
    search_keys: set[str] = set()
    for c in campaigns:
        sf_type = _CAMPAIGN_TYPE_TO_SF.get(c["campaign_type"], "")
        if sf_type:
            search_keys.add(f"{sf_type}_{c['campaign_id']}")

    if not search_keys:
        return {}

    # 50개씩 배치 조회
    all_opps: list[dict] = []
    keys_list = sorted(search_keys)
    for i in range(0, len(keys_list), 50):
        batch = keys_list[i : i + 50]
        where_clauses = " OR ".join(
            f"Adscenter__c LIKE '%{k}%'" for k in batch
        )
        query = (
            "SELECT Id, Name, AdType__c, StageName, CloseDate, Amount, "
            "Agency_Rep_FeeRate__c, Agency_Rep_Fee2__c, Agency_Rep_Fee__c, "
            "Agency_Fee_Rate__c, Adscenter__c, OwnerId, Owner.Name "
            f"FROM Opportunity WHERE ({where_clauses})"
        )
        all_opps.extend(run_soql(sf, query))

    # (campaign_type, campaign_id) → opps 맵 구축
    result: dict[tuple[str, int], list[dict]] = {}
    for opp in all_opps:
        m = _ADSCENTER_RE.search(opp.get("Adscenter__c") or "")
        if m:
            sf_type = m.group(1)
            cid = int(m.group(2))
            db_type = "livecam" if sf_type == "livecommerce_campaign" else "coad_campaign"
            result.setdefault((db_type, cid), []).append(opp)

    return result


def build_sheet_rows(
    campaigns: list[dict],
    sf_map: dict[tuple[str, int], list[dict]],
    og_map: dict[int, OgInfo],
    sf_instance_url: str,
    label: str,
) -> list[list[str]]:
    """시트에 쓸 행 목록 생성."""

    def _og_label(og_id: int) -> str:
        og = og_map.get(og_id)
        return og.display_label if og else str(og_id)

    matched = sum(1 for c in campaigns if (c["campaign_type"], c["campaign_id"]) in sf_map)
    unmatched = len(campaigns) - matched

    rows: list[list[str]] = [
        [f"{label} — 전체: {len(campaigns)}건, SF 매칭: {matched}건, 미매칭: {unmatched}건"],
        [],
        [
            "campaign_type", "campaign_id", "operationsgroup",
            "spent_budget", "agency_fee_rate(%)",
            "match",
            "sf_id", "sf_name", "sf_owner", "sf_stage", "sf_adtype",
            "sf_close_date", "sf_amount",
            "sf_commission_rate(%)", "sf_commission_amount", "sf_commission_formula",
            "sf_adscenter", "sf_link",
        ],
    ]

    for c in campaigns:
        key = (c["campaign_type"], c["campaign_id"])
        og_label = _og_label(c["operationsgroup_id"])
        fee_rate_pct = f"{float(c['agency_fee_rate']) * 100:.1f}" if c["agency_fee_rate"] else "0"
        spent = str(c["spent_budget"])

        opps = sf_map.get(key, [])
        if opps:
            for opp in opps:
                owner = opp.get("Owner") or {}
                owner_name = owner.get("Name", "") if isinstance(owner, dict) else ""
                sf_fee_rate = opp.get("Agency_Rep_FeeRate__c")
                sf_fee_rate_str = f"{float(sf_fee_rate):.1f}" if sf_fee_rate else ""
                sf_fee_amount = opp.get("Agency_Rep_Fee2__c")
                sf_fee_amount_str = str(sf_fee_amount) if sf_fee_amount else ""
                sf_fee_formula = opp.get("Agency_Rep_Fee__c")
                sf_fee_formula_str = str(sf_fee_formula) if sf_fee_formula else ""
                sf_url = f"{sf_instance_url}/{opp['Id']}"

                rows.append([
                    c["campaign_type"],
                    str(c["campaign_id"]),
                    og_label,
                    spent,
                    fee_rate_pct,
                    "O",
                    opp["Id"],
                    opp["Name"],
                    owner_name,
                    opp.get("StageName", ""),
                    opp.get("AdType__c", ""),
                    str(opp.get("CloseDate", "")),
                    str(opp.get("Amount", "")),
                    sf_fee_rate_str,
                    sf_fee_amount_str,
                    sf_fee_formula_str,
                    opp.get("Adscenter__c", ""),
                    sf_url,
                ])
        else:
            rows.append([
                c["campaign_type"],
                str(c["campaign_id"]),
                og_label,
                spent,
                fee_rate_pct,
                "X",
                "", "", "", "", "", "", "", "", "", "", "", "",
            ])

    return rows


def main(start_date_arg: str | None = None) -> None:
    load_env()

    start_date = parse_start_date(start_date_arg)
    email = get_user_email()

    print(f"=== 정산 예정 기회 상태 ===")
    print(f"start_date: {start_date}")
    print(f"이메일: {email}")
    print()

    sf = get_salesforce()
    conn = get_db_connection()

    try:
        # 1. billingstatement_campaign 전체 조회 (pending / 그 외 분리)
        print("[1/4] billingstatement 캠페인 조회...")
        pending, confirmed = fetch_campaigns_by_status(conn, start_date)
        print(f"  정산 예정(pending): {len(pending)}건")
        print(f"  정산 확정(그 외):   {len(confirmed)}건")
        all_campaigns = pending + confirmed
        if not all_campaigns:
            print("  해당 start_date의 정산 데이터가 없습니다.")
            return
        print()

        # 2. OG 정보 수집
        print("[2/4] 운영그룹 정보 수집...")
        og_ids = {c["operationsgroup_id"] for c in all_campaigns}
        og_map = build_og_info_map(sf, conn, og_ids)
        print(f"  {len(og_map)}개 운영그룹")
        print()

        # 3. SF Opportunity 조회 (전체 캠페인 한 번에)
        print("[3/4] Salesforce Opportunity 조회...")
        sf_map = fetch_sf_opportunities(sf, all_campaigns)
        matched = sum(1 for c in all_campaigns if (c["campaign_type"], c["campaign_id"]) in sf_map)
        print(f"  매칭: {matched}/{len(all_campaigns)}건")
        print()

        # 4. 스프레드시트 생성 + 시트별 기록
        print("[4/4] 스프레드시트 생성...")
        gs = GoogleSheet()
        sheet_names = ["정산 예정", "정산 확정"]
        sid = gs.create(
            title=f"정산 예정 기회 상태 — {start_date}",
            sheet_names=sheet_names,
            share_email=email,
        )
        url = f"https://docs.google.com/spreadsheets/d/{sid}"
        print(f"  URL: {url}")

        sf_instance_url = f"https://{sf.sf_instance}"

        if pending:
            rows_pending = build_sheet_rows(pending, sf_map, og_map, sf_instance_url, "정산 예정")
            gs.write(sid, "정산 예정!A1", rows_pending)
            print(f"  [정산 예정] {len(rows_pending) - 3}건 기록")
        else:
            gs.write(sid, "정산 예정!A1", [["해당 기간 정산 예정 건이 없습니다."]])
            print(f"  [정산 예정] 0건")

        if confirmed:
            rows_confirmed = build_sheet_rows(confirmed, sf_map, og_map, sf_instance_url, "정산 확정")
            gs.write(sid, "정산 확정!A1", rows_confirmed)
            print(f"  [정산 확정] {len(rows_confirmed) - 3}건 기록")
        else:
            gs.write(sid, "정산 확정!A1", [["해당 기간 정산 확정 건이 없습니다."]])
            print(f"  [정산 확정] 0건")

    finally:
        conn.close()

    print()
    print(f"=== 완료 ===")
    print(f"스프레드시트: {url}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
