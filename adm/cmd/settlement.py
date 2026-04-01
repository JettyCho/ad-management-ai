"""adscenter 정산 통계 생성.

Usage:
    python -m adm.cmd.settlement [YYYY-MM]

월을 지정하지 않으면 현재 월을 사용합니다.
tsh proxy가 localhost:13306에서 실행 중이어야 합니다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymysql
from simple_salesforce import Salesforce

from adm.cmd.gsheet import GoogleSheet

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_NAME = "prod-buzzad-replica-rds-ap-northeast-1-591756927972"
DB_PROXY_PORT = 13306


# ── 유틸리티 ──────────────────────────────────────────────


def load_env() -> None:
    """프로젝트 루트의 .env 파일을 환경변수로 로드."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            val = val.strip("'\"")
            os.environ.setdefault(key.strip(), val)


def parse_month(arg: str | None) -> tuple[str, str, str, str, str]:
    """YYYY-MM → (year_month, start_date, end_date, last_day, month_label)"""
    if arg:
        y, m = arg.split("-")
        year, month = int(y), int(m)
    else:
        today = date.today()
        year, month = today.year, today.month

    last = monthrange(year, month)[1]
    year_month = f"{year}-{month:02d}"
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"
    last_day = f"{year}-{month:02d}-{last}"
    month_label = f"{month}월"
    return year_month, start_date, end_date, last_day, month_label


def get_user_email() -> str:
    """team/{ME}/README.md에서 이메일 추출."""
    me = os.environ.get("ME", "")
    readme = PROJECT_ROOT / "team" / me / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            if "이메일" in line and "@" in line:
                match = re.search(r"[\w.+-]+@[\w.-]+", line)
                if match:
                    return match.group()
    return ""


# ── Salesforce ────────────────────────────────────────────


def get_salesforce() -> Salesforce:
    """sf CLI의 인증 세션을 활용하여 Salesforce 클라이언트 반환."""
    result = subprocess.run(
        ["sf", "org", "display", "-o", "my-org", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sf org display 실패: {result.stderr}")
    info = json.loads(result.stdout)["result"]
    return Salesforce(
        instance_url=info["instanceUrl"],
        session_id=info["accessToken"],
    )


def run_soql(sf: Salesforce, query: str) -> list[dict]:
    """SOQL 실행 후 records 반환."""
    result = sf.query_all(query)
    return result["records"]


# ── DB 연결 ───────────────────────────────────────────────


def get_tsh_ssl_config() -> dict[str, str]:
    """tsh db config에서 CA/Cert/Key 경로 파싱."""
    result = subprocess.run(
        ["tsh", "db", "config", DB_NAME],
        capture_output=True,
        text=True,
    )
    cfg = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        for key in ("CA:", "Cert:", "Key:"):
            if line.startswith(key):
                cfg[key.rstrip(":")] = line.split(None, 1)[1]
    return cfg


def get_db_connection() -> pymysql.Connection:
    """tsh 프록시(localhost:13306)를 통한 MySQL 연결."""
    cfg = get_tsh_ssl_config()
    return pymysql.connect(
        host="127.0.0.1",
        port=DB_PROXY_PORT,
        user="viewer",
        database="lockjoyUS",
        ssl={"ca": cfg["CA"], "cert": cfg["Cert"], "key": cfg["Key"]},
        cursorclass=pymysql.cursors.DictCursor,
    )


# ── Step 1: 스프레드시트 생성 ─────────────────────────────


def step1_create_sheet(gs: GoogleSheet, year_month: str, email: str) -> str:
    sid = gs.create(
        title=f"{year_month} 정산 통계",
        sheet_names=["AdType × Stage × Adscenter", "Campaign", "Operationsgroup", "Opportunity x Campaign", "Settlement"],
        share_email=email,
    )
    return sid


# ── Step 2: AdType × Stage × Adscenter ───────────────────


def step2_adtype_stage(
    gs: GoogleSheet, sid: str, sf: Salesforce, start_date: str, last_day: str
) -> int:
    query = (
        "SELECT AdType__c, StageName, COUNT(Id) total, COUNT(Adscenter__c) adscenter_cnt "
        "FROM Opportunity "
        f"WHERE CloseDate >= {start_date} AND CloseDate <= {last_day} "
        "GROUP BY AdType__c, StageName "
        "ORDER BY AdType__c, COUNT(Id) DESC"
    )
    records = run_soql(sf, query)

    grand_total = sum(r["total"] for r in records)
    grand_adscenter = sum(r["adscenter_cnt"] for r in records)
    grand_ratio = f"{grand_adscenter / grand_total * 100:.1f}%" if grand_total > 0 else "0%"

    rows: list[list[str]] = [
        ["전체 Opportunity", str(grand_total), "Adscenter 있음", str(grand_adscenter), grand_ratio],
        [],
        ["AdType", "StageName", "전체", "Adscenter 있음", "Adscenter 비율"],
    ]
    for r in records:
        total = r["total"]
        ac = r["adscenter_cnt"]
        ratio = f"{ac / total * 100:.1f}%" if total > 0 else "0%"
        rows.append([
            r["AdType__c"] or "(없음)",
            r["StageName"],
            str(total),
            str(ac),
            ratio,
        ])

    gs.write(sid, "AdType × Stage × Adscenter!A1", rows)
    return len(records)


# ── Step 3: Campaign ─────────────────────────────────────


def step3_campaign(
    gs: GoogleSheet,
    sid: str,
    conn: pymysql.Connection,
    og_map: dict[int, OgInfo],
    start_date: str,
    end_date: str,
    last_day: str,
    month_label: str,
) -> tuple[list[dict], list[dict]]:
    # adserver 로직 기준: broadcast_at은 UTC, KST로 변환하여 월 범위 판정
    # KST start(00:00) → UTC: -9h, KST end(23:59:59) → UTC: -9h
    # 예: 3월 KST = 2월28일 15:00 UTC ~ 3월31일 14:59:59 UTC
    kst_start_utc = f"{start_date} 00:00:00"   # placeholder
    kst_end_utc = f"{last_day} 23:59:59"        # placeholder — 아래에서 정확히 계산

    with conn.cursor() as cur:
        # livecam: status_type='close', broadcast_end를 KST 월 범위로 필터
        # broadcast_at은 UTC 저장 → KST = UTC+9
        # KST 월초 00:00 = UTC 전월말 15:00, KST 월말 23:59:59 = UTC 월말 14:59:59
        cur.execute(
            "SELECT id, name, operationsgroup_id, status_type, budget, "
            "broadcast_at, broadcast_minute, lineitem_set_id, "
            "DATE_ADD(broadcast_at, INTERVAL broadcast_minute MINUTE) AS broadcast_end, "
            "CONVERT_TZ(DATE_ADD(broadcast_at, INTERVAL broadcast_minute MINUTE), '+00:00', '+09:00') AS broadcast_end_kst "
            "FROM livecam "
            "WHERE DATE_ADD(broadcast_at, INTERVAL broadcast_minute MINUTE) >= CONVERT_TZ(%s, '+09:00', '+00:00') "
            "AND DATE_ADD(broadcast_at, INTERVAL broadcast_minute MINUTE) <= CONVERT_TZ(%s, '+09:00', '+00:00') "
            "ORDER BY broadcast_at",
            (f"{start_date} 00:00:00", f"{last_day} 23:59:59"),
        )
        livecams = cur.fetchall()

        # coad_campaign: end_date 범위 + deleted_at IS NULL + closed_at IS NOT NULL
        cur.execute(
            "SELECT id, name, operationsgroup_id, ad_group_id, partner_type, "
            "total_budget, start_date, end_date "
            "FROM coad_campaign "
            "WHERE end_date >= %s AND end_date <= %s "
            "AND deleted_at IS NULL "
            "ORDER BY end_date",
            (start_date, last_day),
        )
        coad_campaigns = cur.fetchall()

    def _og_label(og_id: int) -> str:
        og = og_map.get(og_id)
        return og.display_label if og else str(og_id)

    rows: list[list[str]] = [
        ["livecam", str(len(livecams)), "coad_campaign", str(len(coad_campaigns)), "합계", str(len(livecams) + len(coad_campaigns))],
        [],
    ]

    # livecam
    rows.append([f"[livecam] {month_label} broadcast_end(KST) 기준 - {len(livecams)}건"])
    rows.append([
        "id", "name", "operationsgroup", "status_type",
        "budget", "broadcast_at(UTC)", "broadcast_minute",
        "broadcast_end(UTC)", "broadcast_end(KST)", "lineitem_set_id",
    ])
    for r in livecams:
        rows.append([
            str(r["id"]), r["name"], _og_label(r["operationsgroup_id"]),
            r["status_type"], str(r["budget"]), str(r["broadcast_at"]),
            str(r["broadcast_minute"]), str(r["broadcast_end"]),
            str(r["broadcast_end_kst"]), str(r["lineitem_set_id"]),
        ])

    rows.append([])  # 구분 빈 행

    # coad_campaign
    rows.append([f"[coad_campaign] {month_label} end_date 기준 - {len(coad_campaigns)}건"])
    rows.append([
        "id", "name", "operationsgroup", "ad_group_id",
        "partner_type", "total_budget", "start_date", "end_date",
    ])
    for r in coad_campaigns:
        rows.append([
            str(r["id"]), r["name"], _og_label(r["operationsgroup_id"]),
            str(r["ad_group_id"]), r["partner_type"], str(r["total_budget"]),
            str(r["start_date"]), str(r["end_date"]),
        ])

    gs.write(sid, "Campaign!A1", rows)
    return livecams, coad_campaigns


# ── OG 조회 (공통) ───────────────────────────────────────


def _parse_json_field(val) -> any:
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
    return val


def _format_reg_num(num) -> str:
    s = str(num).zfill(10)
    return f"{s[:3]}-{s[3:5]}-{s[5:]}"


@dataclass
class OgInfo:
    """operationsgroup 조회 결과."""
    id: int
    name: str
    operations_type: str
    owner_bg_id: int
    owner_name: str
    operator_bg_ids: list[int]
    operator_names: list[str]
    billing_json: str
    has_billing_manager: bool
    has_va: bool  # 모든 연관 BG의 SF Account에 VirtualAccountNumber__c가 있으면 True

    @property
    def display_label(self) -> str:
        """Campaign 시트에 표시할 라벨: og_name(owner, op1, op2)"""
        names = [n for n in [self.owner_name] + self.operator_names if n]
        if names:
            return f"{self.name}({', '.join(names)})"
        return self.name


def build_og_info_map(
    sf: Salesforce,
    conn: pymysql.Connection,
    og_ids: set[int],
) -> dict[int, OgInfo]:
    """operationsgroup ID 집합 → OgInfo 맵 (BG + SF Account 포함)."""
    og_ids = og_ids - {0}
    if not og_ids:
        return {}

    # 1. operationsgroup 조회
    ph = ",".join(["%s"] * len(og_ids))
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, name, operations_type, businessgroup_id_owner, "
            f"businessgroup_id_operator_json, billing_json "
            f"FROM operationsgroup WHERE id IN ({ph}) ORDER BY id",
            tuple(og_ids),
        )
        og_list = cur.fetchall()

    # 2. businessgroup ID 수집
    bg_ids: set[int] = set()
    for og in og_list:
        if og["businessgroup_id_owner"]:
            bg_ids.add(og["businessgroup_id_owner"])
        op_ids = _parse_json_field(og.get("businessgroup_id_operator_json"))
        if isinstance(op_ids, list):
            bg_ids.update(op_ids)
    bg_ids.discard(0)

    # 3. businessgroup 조회 (register_number + business_type)
    # bg_map: bg_id → {register_number, business_type}
    bg_map: dict[int, dict] = {}
    if bg_ids:
        ph = ",".join(["%s"] * len(bg_ids))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, register_number, business_type FROM businessgroup WHERE id IN ({ph})",
                tuple(bg_ids),
            )
            for row in cur.fetchall():
                bg_map[row["id"]] = {
                    "register_number": row["register_number"],
                    "business_type": row.get("business_type", ""),
                }

    # 4. 사업자번호 + Type → SF Account (Name + VirtualAccountNumber__c)
    # adserver와 동일: business_type → SF Account Type 매핑
    _BIZ_TYPE_TO_SF_TYPE = {"advertiser": "Advertiser", "adagency": "Agency"}

    # account_map: (reg_num, sf_type) → {name, va}
    account_map: dict[tuple[str, str], dict[str, str]] = {}

    # 사업자번호+타입 조합 수집
    reg_type_pairs: set[tuple[str, str]] = set()
    for bg in bg_map.values():
        rn = bg["register_number"]
        bt = bg["business_type"]
        if rn:
            sf_type = _BIZ_TYPE_TO_SF_TYPE.get(bt, "")
            reg_type_pairs.add((_format_reg_num(rn), sf_type))

    if reg_type_pairs:
        # SF Type별로 묶어서 조회
        by_sf_type: dict[str, list[str]] = {}
        for reg, sf_type in reg_type_pairs:
            by_sf_type.setdefault(sf_type, []).append(reg)

        for sf_type, regs in by_sf_type.items():
            for i in range(0, len(regs), 100):
                batch = regs[i : i + 100]
                in_clause = ",".join(f"'{rn}'" for rn in batch)
                type_filter = f" AND Type = '{sf_type}'" if sf_type else ""
                records = run_soql(
                    sf,
                    f"SELECT CorpRegNum__c, Name, VirtualAccountNumber__c FROM Account "
                    f"WHERE CorpRegNum__c IN ({in_clause}){type_filter}",
                )
                for r in records:
                    crn = r.get("CorpRegNum__c")
                    key = (crn, sf_type)
                    if crn and key not in account_map:
                        account_map[key] = {
                            "name": r["Name"],
                            "va": r.get("VirtualAccountNumber__c") or "",
                        }

    def _account_info(bg_id: int) -> dict[str, str] | None:
        bg = bg_map.get(bg_id)
        if not bg or not bg["register_number"]:
            return None
        sf_type = _BIZ_TYPE_TO_SF_TYPE.get(bg["business_type"], "")
        return account_map.get((_format_reg_num(bg["register_number"]), sf_type))

    def _account_name(bg_id: int) -> str:
        info = _account_info(bg_id)
        return info["name"] if info else ""

    def _account_has_va(bg_id: int) -> bool:
        info = _account_info(bg_id)
        return bool(info and info["va"].strip()) if info else False

    # 5. OgInfo 조합
    result: dict[int, OgInfo] = {}
    for og in og_list:
        owner_id = og["businessgroup_id_owner"] or 0
        owner_name = _account_name(owner_id)

        op_id_list: list[int] = []
        op_names: list[str] = []
        op_json = _parse_json_field(og.get("businessgroup_id_operator_json"))
        if isinstance(op_json, list):
            op_id_list = op_json
            for oid in op_json:
                op_names.append(_account_name(oid))

        billing = _parse_json_field(og.get("billing_json"))
        billing_raw = og.get("billing_json") or ""
        has_billing_manager = False
        if isinstance(billing, dict):
            bm = billing.get("billing_manager_user_id")
            has_billing_manager = bool(bm and str(bm).strip())

        # has_va: operator가 있으면 operator 전원 확인, 없으면 owner 확인
        if op_id_list:
            has_va = all(_account_has_va(oid) for oid in op_id_list)
        else:
            has_va = _account_has_va(owner_id)

        result[og["id"]] = OgInfo(
            id=og["id"],
            name=og["name"],
            operations_type=str(og.get("operations_type", "")),
            owner_bg_id=owner_id,
            owner_name=owner_name,
            operator_bg_ids=op_id_list,
            operator_names=op_names,
            billing_json=billing_raw if isinstance(billing_raw, str) else json.dumps(billing_raw),
            has_billing_manager=has_billing_manager,
            has_va=has_va,
        )

    return result


# ── Step 4: Operationsgroup ──────────────────────────────


def step4_operationsgroup(
    gs: GoogleSheet,
    sid: str,
    og_map: dict[int, OgInfo],
) -> tuple[int, int]:
    if not og_map:
        gs.write(sid, "Operationsgroup!A1", [["데이터 없음"]])
        return 0, 0

    no_va_count = 0
    rows: list[list[str]] = [[
        "id", "name", "operations_type", "owner_bg_id", "owner_name",
        "operator_bg_ids", "operator_names",
        "has_billing_manager", "has_va(SF)", "billing_json",
    ]]

    for og in sorted(og_map.values(), key=lambda o: o.id):
        has_va_str = "O" if og.has_va else "X"
        has_bm_str = "O" if og.has_billing_manager else "X"
        if not og.has_va:
            no_va_count += 1
        rows.append([
            str(og.id),
            og.name,
            og.operations_type,
            str(og.owner_bg_id),
            og.owner_name,
            json.dumps(og.operator_bg_ids),
            ", ".join(og.operator_names),
            has_bm_str,
            has_va_str,
            og.billing_json,
        ])

    gs.write(sid, "Operationsgroup!A1", rows)
    return len(og_map), no_va_count


# ── Step 5: Opportunity x Campaign ────────────────────────

_ADSCENTER_RE = re.compile(
    r"\[광고센터-(?:자동|수동)\](collaborative_campaign|livecommerce_campaign)_(\d+)"
)


def _parse_adscenter(value: str | None) -> tuple[str, int] | None:
    """Adscenter__c 값에서 (campaign_type, id) 추출."""
    if not value:
        return None
    m = _ADSCENTER_RE.search(value)
    if m:
        return m.group(1), int(m.group(2))
    return None


def step5_opportunity_campaign(
    gs: GoogleSheet,
    sid: str,
    sf: Salesforce,
    livecams: list[dict],
    coad_campaigns: list[dict],
    start_date: str,
    last_day: str,
) -> tuple[dict[str, int], dict[tuple[str, int], list[dict]]]:
    """Opportunity ↔ Campaign 매핑 정합성 시트. 매칭 맵도 반환."""

    # 1. DB 캠페인 ID → 이름 맵 구축
    livecam_map = {r["id"]: r["name"] for r in livecams}
    coad_map = {r["id"]: r["name"] for r in coad_campaigns}

    # 2. SF Opportunity 조회 (Adscenter__c 있는 것, Amount 포함)
    sf_opps = run_soql(
        sf,
        "SELECT Id, Name, AdType__c, StageName, CloseDate, Amount, Adscenter__c "
        "FROM Opportunity "
        f"WHERE CloseDate >= {start_date} AND CloseDate <= {last_day} "
        "AND Adscenter__c != null",
    )

    # 3. SF 매핑: (campaign_type, campaign_id) → Opportunity 목록
    sf_by_campaign: dict[tuple[str, int], list[dict]] = {}
    for opp in sf_opps:
        parsed = _parse_adscenter(opp.get("Adscenter__c"))
        if parsed:
            sf_by_campaign.setdefault(parsed, []).append(opp)

    # 4. 결과 행 구축
    rows: list[list[str]] = [[
        "match", "campaign_type", "campaign_id", "campaign_name",
        "sf_opportunity_id", "sf_opportunity_name", "sf_adtype",
        "sf_stage", "sf_adscenter",
    ]]

    counts = {"O": 0, "X": 0, "SF만": 0}
    matched_keys: set[tuple[str, int]] = set()

    # 4-1. livecam 기준
    for cid, cname in sorted(livecam_map.items()):
        key = ("livecommerce_campaign", cid)
        opps = sf_by_campaign.get(key, [])
        if opps:
            for opp in opps:
                rows.append([
                    "O", "livecam", str(cid), cname,
                    opp["Id"], opp["Name"], opp.get("AdType__c", ""),
                    opp.get("StageName", ""), opp.get("Adscenter__c", ""),
                ])
            counts["O"] += 1
            matched_keys.add(key)
        else:
            rows.append(["X", "livecam", str(cid), cname, "", "", "", "", ""])
            counts["X"] += 1

    # 4-2. coad_campaign 기준
    for cid, cname in sorted(coad_map.items()):
        key = ("collaborative_campaign", cid)
        opps = sf_by_campaign.get(key, [])
        if opps:
            for opp in opps:
                rows.append([
                    "O", "coad_campaign", str(cid), cname,
                    opp["Id"], opp["Name"], opp.get("AdType__c", ""),
                    opp.get("StageName", ""), opp.get("Adscenter__c", ""),
                ])
            counts["O"] += 1
            matched_keys.add(key)
        else:
            rows.append(["X", "coad_campaign", str(cid), cname, "", "", "", "", ""])
            counts["X"] += 1

    # 4-3. SF에만 있는 것 (DB 3월 범위에 없음)
    for key, opps in sorted(sf_by_campaign.items()):
        if key in matched_keys:
            continue
        ctype, cid = key
        db_type = "livecam" if ctype == "livecommerce_campaign" else "coad_campaign"
        for opp in opps:
            rows.append([
                "SF만", db_type, str(cid), "",
                opp["Id"], opp["Name"], opp.get("AdType__c", ""),
                opp.get("StageName", ""), opp.get("Adscenter__c", ""),
            ])
        counts["SF만"] += 1

    gs.write(sid, "Opportunity x Campaign!A1", rows)
    return counts, sf_by_campaign


# ── Step 6: Settlement ───────────────────────────────────

_EXCLUDE_STAGES = {"제안", "수주실패_광고미진행"}


_EXCLUDE_OG_IDS = {0, 2}  # 0: 미지정, 2: 버즈빌 내부 테스트


def step6_settlement(
    gs: GoogleSheet,
    sid: str,
    livecams: list[dict],
    coad_campaigns: list[dict],
    sf_by_campaign: dict[tuple[str, int], list[dict]],
    og_map: dict[int, OgInfo],
    sf_instance_url: str,
) -> dict:
    """Settlement 시트: match=O이면서 제외 단계/테스트 OG가 아닌 건의 정산 요약."""

    livecam_budget_map = {r["id"]: r["budget"] for r in livecams}
    coad_budget_map = {r["id"]: r["total_budget"] for r in coad_campaigns}
    livecam_og_map = {r["id"]: r["operationsgroup_id"] for r in livecams}
    coad_og_map = {r["id"]: r["operationsgroup_id"] for r in coad_campaigns}

    def _og_label(og_id: int) -> str:
        og = og_map.get(og_id)
        return og.display_label if og else str(og_id)

    total_db_count = len(livecams) + len(coad_campaigns)

    # 정산 대상 수집
    all_matched: list[dict] = []  # stage 필터 전
    settlement_rows: list[dict] = []

    for key, opps in sf_by_campaign.items():
        ctype, cid = key
        for opp in opps:
            if ctype == "livecommerce_campaign":
                db_type = "livecam"
                db_budget = livecam_budget_map.get(cid)
                og_id = livecam_og_map.get(cid, 0)
            else:
                db_type = "coad_campaign"
                db_budget = coad_budget_map.get(cid)
                og_id = coad_og_map.get(cid, 0)

            if db_budget is None:
                continue  # DB에 없는 건 (SF만) 제외

            stage = opp.get("StageName", "")
            sf_amount = opp.get("Amount") or 0
            sf_id = opp["Id"]
            sf_url = f"{sf_instance_url}/{sf_id}"

            row = {
                "campaign_type": db_type,
                "campaign_id": cid,
                "campaign_name": opp["Name"],
                "og_id": og_id,
                "operationsgroup": _og_label(og_id),
                "sf_stage": stage,
                "sf_adtype": opp.get("AdType__c", ""),
                "sf_amount": sf_amount,
                "db_budget": db_budget,
                "diff": sf_amount - db_budget,
                "sf_url": sf_url,
            }
            all_matched.append(row)

            if stage in _EXCLUDE_STAGES:
                continue
            if og_id in _EXCLUDE_OG_IDS:
                continue
            settlement_rows.append(row)

    # 통계 계산
    excluded_stage_count = sum(1 for r in all_matched if r["sf_stage"] in _EXCLUDE_STAGES)
    excluded_test_count = sum(
        1 for r in all_matched
        if r["sf_stage"] not in _EXCLUDE_STAGES and r["og_id"] in _EXCLUDE_OG_IDS
    )

    lc_rows = [r for r in settlement_rows if r["campaign_type"] == "livecam"]
    cc_rows = [r for r in settlement_rows if r["campaign_type"] == "coad_campaign"]

    stats = {
        "total_db_count": total_db_count,
        "matched_count": len(all_matched),
        "excluded_stage_count": excluded_stage_count,
        "excluded_test_count": excluded_test_count,
        "livecam_count": len(lc_rows),
        "coad_count": len(cc_rows),
        "total_count": len(settlement_rows),
        "livecam_sf_amount": sum(r["sf_amount"] for r in lc_rows),
        "livecam_db_budget": sum(r["db_budget"] for r in lc_rows),
        "coad_sf_amount": sum(r["sf_amount"] for r in cc_rows),
        "coad_db_budget": sum(r["db_budget"] for r in cc_rows),
        "total_sf_amount": sum(r["sf_amount"] for r in settlement_rows),
        "total_db_budget": sum(r["db_budget"] for r in settlement_rows),
    }

    # 시트 작성
    rows: list[list[str]] = [
        ["[필터링 과정]"],
        [
            "DB 캠페인 합계", str(total_db_count),
            "→ SF 매칭(O)", str(len(all_matched)),
            f"→ 제안/수주실패 제외(-{excluded_stage_count})",
            f"→ 제외 OG(0,2) 제외(-{excluded_test_count})",
            "→ 정산 대상", str(len(settlement_rows)),
        ],
        [],
        ["[유형별 통계]"],
        ["", "건수", "SF Amount (수주)", "DB Budget (예산)", "차이"],
        [
            "livecam",
            str(stats["livecam_count"]),
            str(stats["livecam_sf_amount"]),
            str(stats["livecam_db_budget"]),
            str(stats["livecam_sf_amount"] - stats["livecam_db_budget"]),
        ],
        [
            "coad_campaign",
            str(stats["coad_count"]),
            str(stats["coad_sf_amount"]),
            str(stats["coad_db_budget"]),
            str(stats["coad_sf_amount"] - stats["coad_db_budget"]),
        ],
        [
            "합계",
            str(stats["total_count"]),
            str(stats["total_sf_amount"]),
            str(stats["total_db_budget"]),
            str(stats["total_sf_amount"] - stats["total_db_budget"]),
        ],
        [],
        [
            "campaign_type", "campaign_id", "campaign_name", "operationsgroup",
            "sf_stage", "sf_adtype", "sf_amount", "db_budget", "diff", "sf_link",
        ],
    ]

    for r in sorted(settlement_rows, key=lambda x: (x["campaign_type"], x["campaign_id"])):
        rows.append([
            r["campaign_type"],
            str(r["campaign_id"]),
            r["campaign_name"],
            r["operationsgroup"],
            r["sf_stage"],
            r["sf_adtype"],
            str(r["sf_amount"]),
            str(r["db_budget"]),
            str(r["diff"]),
            r["sf_url"],
        ])

    gs.write(sid, "Settlement!A1", rows)
    return stats


# ── main ──────────────────────────────────────────────────


def main(year_month_arg: str | None = None) -> None:
    load_env()

    year_month, start_date, end_date, last_day, month_label = parse_month(year_month_arg)
    email = get_user_email()

    print(f"=== {year_month} 정산 통계 생성 ===")
    print(f"기간: {start_date} ~ {last_day}")
    print(f"이메일: {email}")
    print()

    gs = GoogleSheet()
    sf = get_salesforce()

    # Step 1
    print("[1/4] 스프레드시트 생성...")
    sid = step1_create_sheet(gs, year_month, email)
    url = f"https://docs.google.com/spreadsheets/d/{sid}"
    print(f"  URL: {url}")
    print()

    # Step 2
    print("[2/4] Salesforce Opportunity 조회...")
    sf_count = step2_adtype_stage(gs, sid, sf, start_date, last_day)
    print(f"  {sf_count}건")
    print()

    # Step 3 + 4 (DB 사용)
    conn = get_db_connection()
    try:
        # OG 정보를 먼저 조회 (step3, step4 공통 사용)
        print("[3/4] buzzad DB 조회 + OG 정보 수집...")
        # 먼저 livecam/coad_campaign에서 og_id 수집을 위해 raw 조회
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT operationsgroup_id FROM livecam "
                "WHERE status_type = 'close' "
                "AND DATE_ADD(broadcast_at, INTERVAL broadcast_minute MINUTE) >= CONVERT_TZ(%s, '+09:00', '+00:00') "
                "AND DATE_ADD(broadcast_at, INTERVAL broadcast_minute MINUTE) <= CONVERT_TZ(%s, '+09:00', '+00:00')",
                (f"{start_date} 00:00:00", f"{last_day} 23:59:59"),
            )
            og_ids = {r["operationsgroup_id"] for r in cur.fetchall()}
            cur.execute(
                "SELECT DISTINCT operationsgroup_id FROM coad_campaign "
                "WHERE end_date >= %s AND end_date <= %s "
                "AND deleted_at IS NULL",
                (start_date, last_day),
            )
            og_ids |= {r["operationsgroup_id"] for r in cur.fetchall()}

        og_map = build_og_info_map(sf, conn, og_ids)
        print(f"  {len(og_map)}개 운영그룹 조회 완료")

        livecams, coad_campaigns = step3_campaign(
            gs, sid, conn, og_map, start_date, end_date, last_day, month_label
        )
        print(f"  livecam: {len(livecams)}건, coad_campaign: {len(coad_campaigns)}건")
        print()

        print("[4/6] Operationsgroup 시트 입력...")
        og_count, no_va_count = step4_operationsgroup(gs, sid, og_map)
        print(f"  {og_count}개 운영그룹 (가상계좌 없음: {no_va_count}개)")
        print()

        print("[5/6] Opportunity x Campaign 매핑...")
        match_counts, sf_by_campaign = step5_opportunity_campaign(
            gs, sid, sf, livecams, coad_campaigns, start_date, last_day
        )
        print(f"  O: {match_counts['O']}, X: {match_counts['X']}, SF만: {match_counts['SF만']}")
        print()

        print("[6/6] Settlement 시트 작성...")
        settle_stats = step6_settlement(
            gs, sid, livecams, coad_campaigns, sf_by_campaign, og_map,
            sf_instance_url=f"https://{sf.sf_instance}",
        )
        print(f"  정산 대상: {settle_stats['total_count']}건 (livecam {settle_stats['livecam_count']}, coad {settle_stats['coad_count']})")
        print(f"  SF Amount: {settle_stats['total_sf_amount']:,}, DB Budget: {settle_stats['total_db_budget']:,}")
    finally:
        conn.close()

    print()
    print(f"=== 완료 ===")
    print(f"{year_month} 정산 통계 생성 완료")
    print(f"스프레드시트: {url}")
    print(f"시트 구성:")
    print(f"  - AdType × Stage × Adscenter: Salesforce Opportunity {sf_count}건")
    print(f"  - Campaign: livecam {len(livecams)}건 + coad_campaign {len(coad_campaigns)}건")
    print(f"  - Operationsgroup: {og_count}개 운영그룹 (가상계좌 없음: {no_va_count}개)")
    print(f"  - Opportunity x Campaign: O={match_counts['O']}, X={match_counts['X']}, SF만={match_counts['SF만']}")
    print(f"  - Settlement: {settle_stats['total_count']}건, SF={settle_stats['total_sf_amount']:,}, DB={settle_stats['total_db_budget']:,}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
