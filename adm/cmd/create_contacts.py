"""Contact__c가 없는 Opportunity에 대해 SF Contact를 생성.

Usage:
    python -m adm.cmd.create_contacts [YYYY-MM] [--dry-run]

Adscenter__c는 있지만 Contact__c가 없는 Opportunity를 조회하고,
DB(livecam/coad_campaign) → businessgroup_member → S3 info + Dash email
→ SF Account 매핑을 거쳐 Contact를 생성한 뒤 Opportunity에 연결합니다.

tsh proxy가 localhost:13306에서 실행 중이어야 합니다.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import struct
import subprocess
import sys
import time
from base64 import b32decode
from calendar import monthrange
from dataclasses import dataclass
from datetime import date

import pymysql
import requests
from simple_salesforce import Salesforce

from adm.cmd.settlement import (
    get_db_connection,
    get_salesforce,
    load_env,
    run_soql,
)

# ── 상수 ────────────────────────────────────────────────

_ADSCENTER_RE = re.compile(
    r"\[광고센터-(?:자동|수동)\](collaborative_campaign|livecommerce_campaign)_(\d+)"
)

_BIZ_TYPE_TO_SF_TYPE: dict[str, str] = {
    "advertiser": "Advertiser",
    "adagency": "Agency",
}


# ── 유틸리티 ────────────────────────────────────────────


def parse_month(arg: str | None) -> tuple[str, str]:
    """YYYY-MM → (start_date, last_day)"""
    if arg:
        y, m = arg.split("-")
        year, month = int(y), int(m)
    else:
        today = date.today()
        year, month = today.year, today.month
    last = monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last}"


def format_reg_num(num: int) -> str:
    s = str(num).zfill(10)
    return f"{s[:3]}-{s[3:5]}-{s[5:]}"


def generate_totp(secret_b32: str) -> str:
    """TOTP 6자리 코드 생성."""
    secret = b32decode(secret_b32)
    counter = int(time.time()) // 30
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


# ── 데이터 모델 ─────────────────────────────────────────


@dataclass
class ContactCandidate:
    """Contact 생성 후보."""

    user_id: int
    name: str  # S3 info의 이름
    phone: str  # S3 info의 전화번호
    email: str  # Dash에서 가져온 이메일
    businessgroup_id: int
    register_number: int
    business_type: str  # advertiser / adagency
    sf_account_id: str  # SF Account Id
    sf_account_name: str
    opportunity_ids: list[str]  # 연결할 Opportunity Id 목록


# ── Step 1: SF Opportunity 조회 ─────────────────────────


def fetch_opportunities(
    sf: Salesforce, start_date: str, last_day: str
) -> list[dict]:
    """Adscenter__c 있고 Contact__c 없는 Opportunity 조회."""
    return run_soql(
        sf,
        "SELECT Id, Name, AdType__c, StageName, CloseDate, Amount, Adscenter__c "
        "FROM Opportunity "
        f"WHERE CloseDate >= {start_date} AND CloseDate <= {last_day} "
        "AND Adscenter__c != null AND Contact__c = null "
        "ORDER BY CloseDate, Name",
    )


def parse_adscenter(value: str) -> tuple[str, int] | None:
    """Adscenter__c → (campaign_type, campaign_id). 실패 시 None."""
    m = _ADSCENTER_RE.search(value)
    if m:
        return m.group(1), int(m.group(2))
    return None


# ── Step 2: DB에서 campaign → user_id 매핑 ──────────────


def fetch_campaign_user_map(
    conn: pymysql.Connection,
    livecam_ids: set[int],
    coad_ids: set[int],
) -> dict[tuple[str, int], int]:
    """(campaign_type, campaign_id) → user_id 맵."""
    result: dict[tuple[str, int], int] = {}

    if livecam_ids:
        ph = ",".join(["%s"] * len(livecam_ids))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, owner_id FROM livecam WHERE id IN ({ph})",
                tuple(livecam_ids),
            )
            for r in cur.fetchall():
                result[("livecommerce_campaign", r["id"])] = r["owner_id"]

    if coad_ids:
        ph = ",".join(["%s"] * len(coad_ids))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, user_id FROM coad_campaign WHERE id IN ({ph}) "
                f"AND deleted_at IS NULL",
                tuple(coad_ids),
            )
            for r in cur.fetchall():
                result[("collaborative_campaign", r["id"])] = r["user_id"]

    return result


# ── Step 3: businessgroup_member + businessgroup 조회 ───


@dataclass
class BgMemberInfo:
    businessgroup_id: int
    info_file_uri: str
    register_number: int
    business_type: str


def fetch_bg_member_info(
    conn: pymysql.Connection, user_ids: set[int]
) -> dict[int, BgMemberInfo]:
    """user_id → BgMemberInfo."""
    if not user_ids:
        return {}

    ph = ",".join(["%s"] * len(user_ids))
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT bm.user_id, bm.businessgroup_id, bm.info_file_uri, "
            f"bg.register_number, bg.business_type "
            f"FROM businessgroup_member bm "
            f"JOIN businessgroup bg ON bg.id = bm.businessgroup_id "
            f"WHERE bm.user_id IN ({ph})",
            tuple(user_ids),
        )
        rows = cur.fetchall()

    result: dict[int, BgMemberInfo] = {}
    for r in rows:
        result[r["user_id"]] = BgMemberInfo(
            businessgroup_id=r["businessgroup_id"],
            info_file_uri=r["info_file_uri"],
            register_number=r["register_number"],
            business_type=r["business_type"],
        )
    return result


# ── Step 4: S3 info JSON → name, phone ─────────────────


def fetch_s3_info(uris: list[str]) -> dict[str, dict]:
    """S3 URI 목록 → {uri: {name, phone_number}} 맵."""
    result: dict[str, dict] = {}
    for uri in uris:
        try:
            out = subprocess.run(
                [
                    "aws-vault",
                    "exec",
                    "adfit-backend-591756927972",
                    "--",
                    "aws",
                    "s3",
                    "cp",
                    uri,
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if out.returncode == 0:
                result[uri] = json.loads(out.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            continue
    return result


# ── Step 5: Dash 유저 조회 (email) ──────────────────────


def get_dash_session() -> tuple[str, str]:
    """Dash 로그인 + MFA → (base_url, cookie)."""
    base_url = os.environ["DASH_API_GATEWAY_URL"]
    dash_id = os.environ["DASH_ID"]
    dash_pw = os.environ["DASH_PW"]

    # 기존 쿠키 시도
    cookie = os.environ.get("DASH_PROD_SESSION_COOKIE", "")
    if cookie:
        r = requests.get(
            f"{base_url}/ba/campaign/service/units?page_size=1",
            cookies={"connect.sid": cookie},
            timeout=10,
        )
        if r.status_code == 200:
            return base_url, cookie

    # 로그인
    r = requests.post(
        f"{base_url}/user/login",
        json={"username": dash_id, "password": dash_pw},
        timeout=10,
    )
    r.raise_for_status()
    cookie = r.cookies.get("connect.sid", "")
    if not cookie:
        raise RuntimeError("Dash 로그인 실패: connect.sid 쿠키 없음")

    # MFA
    totp_secret = os.environ.get("DASH_TOTP", "")
    if totp_secret:
        code = generate_totp(totp_secret)
    else:
        code = input("Dash MFA 6자리 코드를 입력하세요: ").strip()

    r = requests.post(
        f"{base_url}/user/mfa/verify",
        json={"code": code},
        cookies={"connect.sid": cookie},
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Dash MFA 인증 실패: {r.status_code} {r.text}")

    return base_url, cookie


def fetch_dash_emails(
    base_url: str, cookie: str, user_ids: set[int]
) -> dict[int, str]:
    """user_id → email 맵."""
    result: dict[int, str] = {}
    for uid in user_ids:
        try:
            r = requests.get(
                f"{base_url}/ba/users/{uid}",
                cookies={"connect.sid": cookie},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                email = data.get("email", "")
                if email:
                    result[uid] = email
        except requests.RequestException:
            continue
    return result


# ── Step 6: SF Account 매핑 ─────────────────────────────


def fetch_sf_accounts(
    sf: Salesforce,
    pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    """(formatted_reg_num, sf_type) → {id, name} 맵."""
    if not pairs:
        return {}

    result: dict[tuple[str, str], dict[str, str]] = {}
    by_type: dict[str, list[str]] = {}
    for reg, sf_type in pairs:
        by_type.setdefault(sf_type, []).append(reg)

    for sf_type, regs in by_type.items():
        for i in range(0, len(regs), 100):
            batch = regs[i : i + 100]
            in_clause = ",".join(f"'{rn}'" for rn in batch)
            type_filter = f" AND Type = '{sf_type}'" if sf_type else ""
            records = run_soql(
                sf,
                f"SELECT Id, Name, CorpRegNum__c FROM Account "
                f"WHERE CorpRegNum__c IN ({in_clause}){type_filter}",
            )
            for r in records:
                key = (r["CorpRegNum__c"], sf_type)
                if key not in result:
                    result[key] = {"id": r["Id"], "name": r["Name"]}

    return result


# ── Step 7: Contact 생성 + Opportunity 연결 ─────────────


def create_contacts(
    sf: Salesforce,
    candidates: list[ContactCandidate],
    dry_run: bool = True,
) -> list[dict]:
    """Contact 생성 후 Opportunity.Contact__c 업데이트."""
    results: list[dict] = []

    for c in candidates:
        # 중복 체크: 같은 Email + AccountId의 Contact 존재 여부
        existing = run_soql(
            sf,
            f"SELECT Id FROM Contact "
            f"WHERE Email = '{c.email}' AND AccountId = '{c.sf_account_id}' "
            f"LIMIT 1",
        )
        if existing:
            contact_id = existing[0]["Id"]
            action = "existing"
        elif dry_run:
            contact_id = None
            action = "dry_run"
        else:
            # Contact 생성
            resp = sf.Contact.create(
                {
                    "LastName": c.name,
                    "Email": c.email,
                    "Phone": c.phone,
                    "AccountId": c.sf_account_id,
                }
            )
            contact_id = resp["id"]
            action = "created"

        # Opportunity 연결
        linked_opps = []
        if contact_id and not dry_run:
            for opp_id in c.opportunity_ids:
                sf.Opportunity.update(opp_id, {"Contact__c": contact_id})
                linked_opps.append(opp_id)

        results.append(
            {
                "user_id": c.user_id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "account": c.sf_account_name,
                "account_id": c.sf_account_id,
                "contact_id": contact_id,
                "action": action,
                "opportunities": c.opportunity_ids,
                "linked": linked_opps,
            }
        )

    return results


# ── main ────────────────────────────────────────────────


def main(month_arg: str | None = None, dry_run: bool = True) -> None:
    load_env()

    start_date, last_day = parse_month(month_arg)
    year_month = start_date[:7]

    print(f"=== {year_month} Contact 생성 {'(DRY RUN)' if dry_run else ''} ===")
    print(f"기간: {start_date} ~ {last_day}")
    print()

    sf = get_salesforce()

    # Step 1: SF Opportunity 조회
    print("[1/7] Opportunity 조회 (Adscenter O, Contact X)...")
    opps = fetch_opportunities(sf, start_date, last_day)
    print(f"  {len(opps)}건")
    if not opps:
        print("  대상 Opportunity가 없습니다.")
        return

    # Adscenter__c 파싱 → campaign 분류
    livecam_ids: set[int] = set()
    coad_ids: set[int] = set()
    opp_by_campaign: dict[tuple[str, int], list[str]] = {}  # campaign_key → opp_ids

    for opp in opps:
        parsed = parse_adscenter(opp["Adscenter__c"])
        if not parsed:
            continue
        ctype, cid = parsed
        opp_by_campaign.setdefault((ctype, cid), []).append(opp["Id"])
        if ctype == "livecommerce_campaign":
            livecam_ids.add(cid)
        else:
            coad_ids.add(cid)

    print(f"  livecam: {len(livecam_ids)}건, coad_campaign: {len(coad_ids)}건")
    print()

    # Step 2: DB campaign → user_id
    print("[2/7] DB campaign → user_id 매핑...")
    conn = get_db_connection()
    try:
        campaign_user_map = fetch_campaign_user_map(conn, livecam_ids, coad_ids)
        print(f"  {len(campaign_user_map)}건 매핑")

        # user_id → opportunity_ids 집계
        user_opp_map: dict[int, list[str]] = {}
        for campaign_key, user_id in campaign_user_map.items():
            opp_ids = opp_by_campaign.get(campaign_key, [])
            user_opp_map.setdefault(user_id, []).extend(opp_ids)

        unique_user_ids = set(user_opp_map.keys())
        print(f"  고유 유저: {len(unique_user_ids)}명")
        print()

        # Step 3: businessgroup_member + businessgroup
        print("[3/7] businessgroup_member 조회...")
        bg_info_map = fetch_bg_member_info(conn, unique_user_ids)
        print(f"  {len(bg_info_map)}명 매핑")
        print()

    finally:
        conn.close()

    # Step 4: S3 info JSON
    print("[4/7] S3 info JSON 다운로드...")
    s3_uris = [bg.info_file_uri for bg in bg_info_map.values() if bg.info_file_uri]
    s3_info_map = fetch_s3_info(s3_uris)
    print(f"  {len(s3_info_map)}/{len(s3_uris)}건 다운로드")
    print()

    # Step 5: Dash email
    print("[5/7] Dash 유저 email 조회...")
    dash_url, dash_cookie = get_dash_session()
    email_map = fetch_dash_emails(dash_url, dash_cookie, unique_user_ids)
    print(f"  {len(email_map)}/{len(unique_user_ids)}명 이메일 확보")
    print()

    # Step 6: SF Account 매핑
    print("[6/7] SF Account 매핑...")
    reg_type_pairs: set[tuple[str, str]] = set()
    for uid in unique_user_ids:
        bg = bg_info_map.get(uid)
        if bg and bg.register_number:
            sf_type = _BIZ_TYPE_TO_SF_TYPE.get(bg.business_type, "")
            reg_type_pairs.add((format_reg_num(bg.register_number), sf_type))

    account_map = fetch_sf_accounts(sf, reg_type_pairs)
    print(f"  {len(account_map)}개 Account 매핑")
    print()

    # 후보 조합
    candidates: list[ContactCandidate] = []
    skipped: list[dict] = []

    for uid in sorted(unique_user_ids):
        bg = bg_info_map.get(uid)
        if not bg:
            skipped.append({"user_id": uid, "reason": "businessgroup_member 없음"})
            continue

        # S3 info
        s3_data = s3_info_map.get(bg.info_file_uri, {})
        name = s3_data.get("name", "")
        phone = s3_data.get("phone_number", "")

        # Email
        email = email_map.get(uid, "")

        # SF Account
        sf_type = _BIZ_TYPE_TO_SF_TYPE.get(bg.business_type, "")
        reg_formatted = format_reg_num(bg.register_number)
        account = account_map.get((reg_formatted, sf_type))

        if not name:
            skipped.append({"user_id": uid, "reason": "이름 없음 (S3 info)"})
            continue
        if not email:
            skipped.append({"user_id": uid, "reason": "이메일 없음 (Dash)"})
            continue
        if not account:
            skipped.append(
                {
                    "user_id": uid,
                    "reason": f"SF Account 없음 (reg={reg_formatted}, type={sf_type})",
                }
            )
            continue

        candidates.append(
            ContactCandidate(
                user_id=uid,
                name=name,
                phone=phone,
                email=email,
                businessgroup_id=bg.businessgroup_id,
                register_number=bg.register_number,
                business_type=bg.business_type,
                sf_account_id=account["id"],
                sf_account_name=account["name"],
                opportunity_ids=user_opp_map[uid],
            )
        )

    # Step 7: Contact 생성
    print(f"[7/7] Contact 생성 {'(DRY RUN)' if dry_run else ''}...")
    print(f"  후보: {len(candidates)}명, 스킵: {len(skipped)}명")

    if skipped:
        print()
        print("  [스킵 목록]")
        for s in skipped:
            print(f"    user_id={s['user_id']}: {s['reason']}")

    print()
    results = create_contacts(sf, candidates, dry_run=dry_run)

    # 결과 출력
    print("=== 결과 ===")
    for r in results:
        opp_count = len(r["opportunities"])
        linked_count = len(r["linked"])
        status = {
            "existing": "기존 Contact 사용",
            "created": "신규 생성",
            "dry_run": "생성 예정 (dry-run)",
        }[r["action"]]

        print(
            f"  {r['name']} ({r['email']}) → {r['account']} | "
            f"{status} | Opp {opp_count}건"
            + (f" (연결 {linked_count}건)" if linked_count else "")
        )
        if r["contact_id"]:
            print(f"    Contact: {r['contact_id']}")

    # 요약
    print()
    created = sum(1 for r in results if r["action"] == "created")
    existing = sum(1 for r in results if r["action"] == "existing")
    dry = sum(1 for r in results if r["action"] == "dry_run")
    total_opps = sum(len(r["opportunities"]) for r in results)

    print(f"=== 요약 ===")
    print(f"  신규 생성: {created}명")
    print(f"  기존 사용: {existing}명")
    if dry:
        print(f"  생성 예정: {dry}명 (--dry-run 해제 시 생성)")
    print(f"  스킵: {len(skipped)}명")
    print(f"  연결 대상 Opportunity: {total_opps}건")


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry-run" in args
    month = next((a for a in args if a != "--dry-run"), None)
    main(month, dry_run=dry)
