"""공공기관 목록 동기화.

- 학교: 교육청 NEIS 학교기본정보 Open API (https://open.neis.go.kr) — NEIS_API_KEY 필요(무료)
- 주민센터 등: 공공데이터포털에서 받은 CSV 파일 가져오기
- 좌표: 카카오 로컬 API 주소 검색 — KAKAO_REST_API_KEY 필요(무료)

네트워크 호출은 http_get 으로 주입받아 테스트에서 가짜 응답을 쓸 수 있게 했다.
"""

import csv
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from sqlmodel import Session, select

from . import config
from .models import ORG_CENTER, ORG_SCHOOL, Organization, SyncRun
from .timeutil import now_utc

HttpGet = Callable[[str, dict[str, str]], dict]

NEIS_URL = "https://open.neis.go.kr/hub/schoolInfo"
KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class SyncError(Exception):
    pass


def default_http_get(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "public-goods-manage", **headers})
    with urllib.request.urlopen(req, timeout=20) as res:  # noqa: S310 (고정된 공공 API 주소)
        return json.loads(res.read().decode("utf-8"))


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    geocoded: int = 0
    messages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 학교 (NEIS)


def fetch_neis_schools(api_key: str, http_get: HttpGet = default_http_get, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        qs = urllib.parse.urlencode({"KEY": api_key, "Type": "json", "pIndex": page, "pSize": page_size})
        data = http_get(f"{NEIS_URL}?{qs}", {})
        if "schoolInfo" not in data:
            result = data.get("RESULT", {})
            if result.get("CODE") == "INFO-200":  # 데이터 없음
                break
            raise SyncError(f"NEIS 응답 오류: {result.get('CODE')} {result.get('MESSAGE')}")
        head, body = data["schoolInfo"][0]["head"], data["schoolInfo"][1]
        total = int(head[0]["list_total_count"])
        rows.extend(body.get("row", []))
        if len(rows) >= total or not body.get("row"):
            break
        page += 1
    return rows


def _school_values(row: dict) -> dict:
    address = " ".join(x for x in [row.get("ORG_RDNMA") or "", row.get("ORG_RDNDA") or ""] if x).strip()
    return {
        "code": str(row["SD_SCHUL_CODE"]),
        "name": (row.get("SCHUL_NM") or "").strip(),
        "subtype": (row.get("SCHUL_KND_SC_NM") or "").strip(),
        "region": (row.get("LCTN_SC_NM") or "").strip(),
        "address": address[:255],
        "phone": (row.get("ORG_TELNO") or "").strip()[:40],
    }


def upsert_orgs(session: Session, kind: str, source: str, values: list[dict], deactivate_missing: bool) -> SyncResult:
    """code 기준으로 추가·수정. 주소가 바뀌면 좌표를 다시 찾도록 표시한다."""
    res = SyncResult()
    existing = {o.code: o for o in session.exec(select(Organization).where(Organization.kind == kind)).all()}
    now = now_utc()
    seen: set[str] = set()
    for v in values:
        if not v.get("code") or not v.get("name"):
            continue
        seen.add(v["code"])
        org = existing.get(v["code"])
        if org is None:
            org = Organization(kind=kind, source=source, synced_at=now, **{k: v[k] for k in v if k in _ORG_FIELDS})
            if org.lat is not None and org.lng is not None:
                org.geocode_status = "ok"
            session.add(org)
            existing[v["code"]] = org
            res.created += 1
            continue
        changed = False
        for k in ("name", "subtype", "region", "address", "phone"):
            if k in v and v[k] != getattr(org, k):
                if k == "address" and org.geocode_status != "manual":
                    org.geocode_status = "pending"
                    org.lat = org.lng = None
                setattr(org, k, v[k])
                changed = True
        if v.get("lat") is not None and v.get("lng") is not None and org.geocode_status != "manual":
            if (org.lat, org.lng) != (v["lat"], v["lng"]):
                org.lat, org.lng, org.geocode_status = v["lat"], v["lng"], "ok"
                changed = True
        if not org.active:
            org.active = True
            changed = True
        org.synced_at = now
        if changed:
            res.updated += 1
    if deactivate_missing:
        for code, org in existing.items():
            if code not in seen and org.active and org.source == source:
                org.active = False  # 폐교 등. 기록 보존을 위해 지우지 않는다
                res.deactivated += 1
    session.commit()
    return res


_ORG_FIELDS = {"code", "name", "subtype", "region", "address", "phone", "lat", "lng"}


def sync_schools(session: Session, http_get: HttpGet = default_http_get) -> SyncResult:
    if not config.NEIS_API_KEY:
        raise SyncError("NEIS_API_KEY 가 설정되지 않아 학교 목록을 가져올 수 없습니다.")
    rows = fetch_neis_schools(config.NEIS_API_KEY, http_get)
    if not rows:
        raise SyncError("NEIS 에서 받은 학교가 없습니다.")
    return upsert_orgs(session, ORG_SCHOOL, "neis", [_school_values(r) for r in rows], deactivate_missing=True)


# ---------------------------------------------------------------- CSV (주민센터 등)

_NAME_COLS = ("기관명", "주민센터명", "행정복지센터명", "시설명", "명칭", "읍면동명", "name")
_ADDR_COLS = ("도로명주소", "소재지도로명주소", "주소", "소재지지번주소", "지번주소", "address")
_LAT_COLS = ("위도", "lat", "latitude")
_LNG_COLS = ("경도", "lng", "lon", "longitude")
_CODE_COLS = ("기관코드", "행정기관코드", "행정동코드", "code")
_PHONE_COLS = ("전화번호", "대표전화", "phone")
_REGION_COLS = ("시도명", "시도", "region")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SyncError("파일 인코딩을 알 수 없습니다. UTF-8 또는 CP949 CSV 를 올려 주세요.")


def _pick(row: dict, cols: tuple[str, ...]) -> str:
    for c in cols:
        if c in row and row[c] and str(row[c]).strip():
            return str(row[c]).strip()
    return ""


def parse_org_csv(raw: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    if not any(h in headers for h in _NAME_COLS):
        raise SyncError(f"기관 이름 열을 찾지 못했습니다. 다음 중 하나가 필요합니다: {', '.join(_NAME_COLS[:5])}")
    out = []
    for row in reader:
        name = _pick(row, _NAME_COLS)
        address = _pick(row, _ADDR_COLS)
        if not name:
            continue
        code = _pick(row, _CODE_COLS) or "h" + hashlib.sha1(f"{name}|{address}".encode()).hexdigest()[:16]
        v = {
            "code": code[:60],
            "name": name[:120],
            "address": address[:255],
            "phone": _pick(row, _PHONE_COLS)[:40],
            "region": _pick(row, _REGION_COLS)[:40] or (address.split(" ")[0] if address else ""),
            "subtype": "",
        }
        try:
            lat, lng = float(_pick(row, _LAT_COLS)), float(_pick(row, _LNG_COLS))
            if 33 <= lat <= 39 and 124 <= lng <= 132:  # 대한민국 범위
                v["lat"], v["lng"] = lat, lng
        except ValueError:
            pass
        out.append(v)
    if not out:
        raise SyncError("가져올 기관이 없습니다.")
    return out


def import_csv(session: Session, raw: bytes, kind: str = ORG_CENTER, replace: bool = False) -> SyncResult:
    return upsert_orgs(session, kind, "csv", parse_org_csv(raw), deactivate_missing=replace)


# ---------------------------------------------------------------- 좌표 (카카오)


def geocode_one(org: Organization, http_get: HttpGet) -> tuple[float, float] | None:
    headers = {"Authorization": f"KakaoAK {config.KAKAO_REST_API_KEY}"}
    if org.address:
        q = urllib.parse.urlencode({"query": org.address})
        docs = http_get(f"{KAKAO_ADDRESS_URL}?{q}", headers).get("documents", [])
        if docs:
            return float(docs[0]["y"]), float(docs[0]["x"])
    q = urllib.parse.urlencode({"query": f"{org.region} {org.name}".strip()})
    docs = http_get(f"{KAKAO_KEYWORD_URL}?{q}", headers).get("documents", [])
    if docs:
        return float(docs[0]["y"]), float(docs[0]["x"])
    return None


def geocode_pending(
    session: Session, limit: int = 500, time_budget: float = 40.0, http_get: HttpGet = default_http_get
) -> int:
    """좌표가 없는 기관의 좌표를 찾는다. 시간 제한이 있는 서버리스 환경을 위해 나눠서 처리한다."""
    if not config.KAKAO_REST_API_KEY:
        return 0
    deadline = time.monotonic() + time_budget
    orgs = session.exec(
        select(Organization)
        .where(Organization.geocode_status == "pending", Organization.active == True)  # noqa: E712
        .limit(limit)
    ).all()
    done = 0
    for org in orgs:
        if time.monotonic() > deadline:
            break
        try:
            point = geocode_one(org, http_get)
        except Exception:  # 일시적 오류는 다음 실행에서 다시 시도
            continue
        if point:
            org.lat, org.lng, org.geocode_status = point[0], point[1], "ok"
            done += 1
        else:
            org.geocode_status = "failed"
        if done % 50 == 0:
            session.commit()
    session.commit()
    return done


# ---------------------------------------------------------------- 실행 기록


def run_sync(
    session: Session,
    schools: bool = True,
    geocode_limit: int = 500,
    time_budget: float = 40.0,
    http_get: HttpGet = default_http_get,
) -> SyncRun:
    # 동시에 두 번 실행되지 않게: 10분 안에 시작된 진행 중 기록이 있으면 거절
    busy = session.exec(
        select(SyncRun).where(SyncRun.status == "running", SyncRun.started_at > now_utc() - timedelta(minutes=10))
    ).first()
    if busy:
        raise SyncError("이미 동기화가 진행 중입니다. 잠시 후 다시 시도해 주세요.")
    run = SyncRun(kind="schools" if schools else "geocode")
    session.add(run)
    session.commit()
    try:
        started = time.monotonic()
        msgs = []
        if schools:
            res = sync_schools(session, http_get)
            run.created, run.updated, run.deactivated = res.created, res.updated, res.deactivated
            msgs.append(f"학교 추가 {res.created} · 변경 {res.updated} · 폐교 처리 {res.deactivated}")
        remaining = max(5.0, time_budget - (time.monotonic() - started))
        run.geocoded = geocode_pending(session, geocode_limit, remaining, http_get)
        if not config.KAKAO_REST_API_KEY:
            msgs.append("KAKAO_REST_API_KEY 가 없어 좌표를 찾지 않았습니다.")
        else:
            msgs.append(f"좌표 확인 {run.geocoded}곳")
        run.status, run.message = "ok", " / ".join(msgs)
    except Exception as e:  # 기록을 남기고 다시 알린다
        session.rollback()
        run.status, run.message = "error", str(e)[:1000]
    finally:
        run.finished_at = now_utc()
        session.add(run)
        session.commit()
    session.refresh(run)
    return run
