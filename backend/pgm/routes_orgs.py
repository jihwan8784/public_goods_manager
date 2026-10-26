"""기관 검색·지도·관리, 공공데이터 동기화."""

import hmac

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from . import config, orgsync
from .access import can_manage, eligibility
from .db import engine
from .models import (
    ACCESS_MEMBERS,
    ITEM_NORMAL,
    ITEM_RETIRED,
    ORG_KINDS,
    UNRETURNED,
    Item,
    Organization,
    OrgAdmin,
    Reservation,
    SyncRun,
    User,
)
from .schemas import OrgAdminIn, OrgIn, OrgUpdateIn, org_brief, org_full
from .security import AdminUser, CurrentUser, SessionDep
from .timeutil import now_utc

router = APIRouter()


def _org_or_404(session, org_id: int) -> Organization:
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "기관을 찾을 수 없습니다.")
    return org


def _item_counts(session, org_ids: list[int]) -> dict[int, dict]:
    """기관별 물품 수, 지금 바로 빌릴 수 있는 수, 소속 전용 물품 수."""
    if not org_ids:
        return {}
    rented = select(Reservation.item_id).where(col(Reservation.status).in_(UNRETURNED))
    rows = session.exec(
        select(
            Item.org_id,
            func.count(),
            func.sum(case((((Item.status == ITEM_NORMAL) & col(Item.id).not_in(rented)), 1), else_=0)),
            func.sum(case((Item.access == ACCESS_MEMBERS, 1), else_=0)),
        )
        .where(col(Item.org_id).in_(org_ids), Item.status != ITEM_RETIRED)
        .group_by(Item.org_id)
    ).all()
    return {r[0]: {"items": int(r[1]), "available_now": int(r[2] or 0), "members_only": int(r[3] or 0)} for r in rows}


# ================================================================ 공개: 기관 검색 (회원가입에서 학교 찾기)


@router.get("/orgs/search")
def search_orgs(
    session: SessionDep,
    q: str = Query(min_length=1, max_length=60),
    kind: str | None = Query(default=None, pattern="^(school|community_center|other)$"),
    limit: int = Query(default=20, ge=1, le=50),
):
    query = select(Organization).where(Organization.active == True)  # noqa: E712
    if kind:
        query = query.where(Organization.kind == kind)
    for word in q.split()[:4]:
        like = f"%{word}%"
        query = query.where(col(Organization.name).ilike(like) | col(Organization.address).ilike(like))
    rows = session.exec(query.order_by(func.length(Organization.name), Organization.name).limit(limit)).all()
    return {"orgs": [{**org_brief(o), "address": o.address} for o in rows]}


# ================================================================ 로그인 사용자: 지도 / 기관 상세


@router.get("/orgs/map")
def orgs_map(
    user: CurrentUser,
    session: SessionDep,
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    kind: str | None = Query(default=None, pattern="^(school|community_center|other)$"),
    with_items: bool = True,
    limit: int = Query(default=300, ge=1, le=3000),
):
    if sw_lat > ne_lat or sw_lng > ne_lng:
        raise HTTPException(422, "지도 범위가 올바르지 않습니다.")
    base = select(Organization).where(
        Organization.active == True,  # noqa: E712
        Organization.lat.is_not(None),
        Organization.lat.between(sw_lat, ne_lat),
        Organization.lng.between(sw_lng, ne_lng),
    )
    if kind:
        base = base.where(Organization.kind == kind)
    if with_items:
        has_items = select(Item.org_id).where(Item.status != ITEM_RETIRED)
        base = base.where(col(Organization.id).in_(has_items))
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    orgs = list(session.exec(base.order_by(Organization.name).limit(limit)).all())
    counts = _item_counts(session, [o.id for o in orgs])
    out = []
    for o in orgs:
        c = counts.get(o.id, {"items": 0, "available_now": 0, "members_only": 0})
        out.append(
            {
                **org_brief(o),
                "address": o.address,
                "lat": o.lat,
                "lng": o.lng,
                **c,
                "my_school": bool(user.is_student and user.school_id == o.id),
            }
        )
    return {"orgs": out, "total": total, "truncated": total > len(out), "updated_at": now_utc()}


@router.get("/orgs/{org_id}")
def org_detail(org_id: int, user: CurrentUser, session: SessionDep):
    org = _org_or_404(session, org_id)
    c = _item_counts(session, [org.id]).get(org.id, {"items": 0, "available_now": 0, "members_only": 0})
    probe = Item(org_id=org.id, access=ACCESS_MEMBERS, asset_code="", name="", category="")
    members_ok, members_reason = eligibility(user, probe, org)
    return {
        "org": org_full(org),
        **c,
        "can_manage": can_manage(session, user, org.id),
        "members_eligible": members_ok,
        "members_reason": members_reason,
    }


# ================================================================ 서비스 관리자: 기관 관리


def _admins_of(session, org_ids: list[int]) -> dict[int, list[dict]]:
    if not org_ids:
        return {}
    rows = session.exec(
        select(OrgAdmin.org_id, User).join(User, User.id == OrgAdmin.user_id).where(col(OrgAdmin.org_id).in_(org_ids))
    ).all()
    out: dict[int, list[dict]] = {}
    for org_id, u in rows:
        out.setdefault(org_id, []).append({"id": u.id, "name": u.name, "email": u.email})
    return out


@router.get("/admin/orgs")
def admin_orgs(
    admin: AdminUser,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=60),
    kind: str | None = Query(default=None, pattern="^(school|community_center|other)$"),
    has_items: bool = False,
    geocode: str | None = Query(default=None, pattern="^(pending|ok|failed|manual)$"),
    limit: int = Query(default=50, ge=1, le=200),
):
    query = select(Organization)
    if kind:
        query = query.where(Organization.kind == kind)
    if geocode:
        query = query.where(Organization.geocode_status == geocode)
    if has_items:
        query = query.where(col(Organization.id).in_(select(Item.org_id)))
    if q and q.strip():
        for word in q.split()[:4]:
            like = f"%{word}%"
            query = query.where(col(Organization.name).ilike(like) | col(Organization.address).ilike(like))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    orgs = list(session.exec(query.order_by(Organization.name).limit(limit)).all())
    ids = [o.id for o in orgs]
    counts = _item_counts(session, ids)
    admins = _admins_of(session, ids)
    return {
        "total": total,
        "orgs": [
            {**org_full(o), **counts.get(o.id, {"items": 0, "available_now": 0, "members_only": 0}), "admins": admins.get(o.id, [])}
            for o in orgs
        ],
    }


@router.post("/admin/orgs", status_code=201)
def admin_create_org(body: OrgIn, admin: AdminUser, session: SessionDep):
    if body.kind not in ORG_KINDS:
        raise HTTPException(422, "기관 종류가 올바르지 않습니다.")
    org = Organization(
        kind=body.kind,
        code=f"manual-{now_utc().strftime('%Y%m%d%H%M%S%f')}",
        name=body.name.strip(),
        address=body.address.strip(),
        subtype=body.subtype.strip(),
        region=body.region.strip() or (body.address.split(" ")[0] if body.address else ""),
        phone=body.phone.strip(),
        lat=body.lat,
        lng=body.lng,
        geocode_status="manual" if body.lat is not None and body.lng is not None else "pending",
        source="manual",
    )
    session.add(org)
    session.commit()
    session.refresh(org)
    return {"org": org_full(org)}


@router.patch("/admin/orgs/{org_id}")
def admin_update_org(org_id: int, body: OrgUpdateIn, admin: AdminUser, session: SessionDep):
    org = _org_or_404(session, org_id)
    if body.name is not None:
        org.name = body.name.strip()
    if body.address is not None and body.address.strip() != org.address:
        org.address = body.address.strip()
        if body.lat is None:
            org.lat = org.lng = None
            org.geocode_status = "pending"
    if body.lat is not None and body.lng is not None:
        org.lat, org.lng, org.geocode_status = body.lat, body.lng, "manual"  # 직접 지정한 좌표는 동기화가 덮어쓰지 않음
    if body.active is not None:
        org.active = body.active
    session.commit()
    session.refresh(org)
    return {"org": org_full(org)}


@router.post("/admin/orgs/{org_id}/admins", status_code=201)
def admin_add_org_admin(org_id: int, body: OrgAdminIn, admin: AdminUser, session: SessionDep):
    org = _org_or_404(session, org_id)
    u = session.exec(select(User).where(User.email == body.email.strip().lower())).first()
    if not u:
        raise HTTPException(404, "그 이메일로 가입한 회원이 없습니다. 먼저 회원가입을 해야 합니다.")
    session.add(OrgAdmin(org_id=org.id, user_id=u.id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "이미 이 기관의 관리자입니다.")
    return {"admins": _admins_of(session, [org.id]).get(org.id, [])}


@router.delete("/admin/orgs/{org_id}/admins/{user_id}")
def admin_remove_org_admin(org_id: int, user_id: int, admin: AdminUser, session: SessionDep):
    link = session.get(OrgAdmin, (org_id, user_id))
    if not link:
        raise HTTPException(404, "관리자 지정 기록이 없습니다.")
    session.delete(link)
    session.commit()
    return {"admins": _admins_of(session, [org_id]).get(org_id, [])}


# ================================================================ 동기화


def _run_out(r: SyncRun | None) -> dict | None:
    if not r:
        return None
    return {
        "id": r.id,
        "kind": r.kind,
        "status": r.status,
        "message": r.message,
        "created": r.created,
        "updated": r.updated,
        "deactivated": r.deactivated,
        "geocoded": r.geocoded,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
    }


@router.get("/admin/sync")
def sync_status(admin: AdminUser, session: SessionDep):
    runs = session.exec(select(SyncRun).order_by(col(SyncRun.started_at).desc()).limit(10)).all()
    by_kind = dict(
        session.exec(
            select(Organization.kind, func.count()).where(Organization.active == True).group_by(Organization.kind)  # noqa: E712
        ).all()
    )
    by_geo = dict(
        session.exec(
            select(Organization.geocode_status, func.count())
            .where(Organization.active == True)  # noqa: E712
            .group_by(Organization.geocode_status)
        ).all()
    )
    return {
        "runs": [_run_out(r) for r in runs],
        "orgs_by_kind": by_kind,
        "geocode": by_geo,
        "neis_key": bool(config.NEIS_API_KEY),
        "kakao_key": bool(config.KAKAO_REST_API_KEY),
        "cron_secret": bool(config.CRON_SECRET),
        "admin_code": bool(config.ADMIN_ACCESS_CODE),
    }


@router.post("/admin/sync")
def sync_now(admin: AdminUser, session: SessionDep, schools: bool = True):
    try:
        run = orgsync.run_sync(session, schools=schools, time_budget=40.0)
    except orgsync.SyncError as e:
        raise HTTPException(409, str(e))
    return {"run": _run_out(run)}


@router.post("/admin/orgs/import")
async def import_orgs(
    admin: AdminUser,
    session: SessionDep,
    file: UploadFile = File(...),
    kind: str = Form(default="community_center"),
    replace: bool = Form(default=False),
    coords_only: bool = Form(default=False),
):
    if kind not in ORG_KINDS:
        raise HTTPException(422, "기관 종류가 올바르지 않습니다.")
    raw = await file.read(20 * 1024 * 1024 + 1)
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "파일은 20MB 이하로 올려 주세요.")
    is_school_file = orgsync.looks_like_school_file(raw)
    if is_school_file and kind != "school":
        raise HTTPException(
            422, "학교 목록 파일입니다. 기관 종류를 '학교'로 고르고 '좌표만 채우기'로 올려 주세요."
        )
    if kind == "school" and not coords_only:
        has_neis = session.exec(select(Organization.id).where(Organization.source == "neis").limit(1)).first()
        if has_neis:
            coords_only = True  # NEIS 학교가 있으면 중복을 만들지 않고 좌표만 채운다
    try:
        if coords_only:
            res = orgsync.fill_coordinates(session, kind, orgsync.parse_org_csv(raw))
        else:
            res = orgsync.import_csv(session, raw, kind=kind, replace=replace)
    except orgsync.SyncError as e:
        raise HTTPException(422, str(e))
    run = SyncRun(
        kind=f"csv-coords:{kind}" if coords_only else f"csv:{kind}",
        status="ok",
        created=res.created,
        updated=res.updated,
        deactivated=res.deactivated,
        message=f"파일 {file.filename} " + ("좌표 채우기 · 좌표 갱신 " + str(res.updated) + "곳 · " + " ".join(res.messages) if coords_only else "가져오기"),
        finished_at=now_utc(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return {"run": _run_out(run)}


@router.post("/admin/orgs/cleanup-csv")
def cleanup_csv(
    admin: AdminUser,
    session: SessionDep,
    kind: str = Query(pattern="^(school|community_center|other)$"),
):
    """CSV 로 잘못 가져온 기관을 정리 (쓰이지 않으면 삭제, 쓰이면 비활성)."""
    res = orgsync.cleanup_csv_orgs(session, kind)
    return {"deleted": res.updated, "deactivated": res.deactivated}


@router.get("/cron/sync")
def cron_sync(authorization: str | None = Header(default=None)):
    """Vercel Cron 이 매일 호출 (Authorization: Bearer CRON_SECRET)."""
    if not config.CRON_SECRET:
        raise HTTPException(503, "CRON_SECRET 이 설정되지 않았습니다.")
    expected = f"Bearer {config.CRON_SECRET}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(401, "인증 실패")
    from sqlmodel import Session

    with Session(engine) as session:
        try:
            run = orgsync.run_sync(session, schools=bool(config.NEIS_API_KEY), time_budget=50.0)
        except orgsync.SyncError as e:
            raise HTTPException(409, str(e))
        return {"run": _run_out(run)}
