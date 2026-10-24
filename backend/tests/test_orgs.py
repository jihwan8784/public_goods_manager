"""회원가입·학생 인증, 기관별 권한, 지도, 공공데이터 동기화 테스트."""

import urllib.parse

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from pgm import config, orgsync
from pgm.app import create_app
from pgm.models import Organization

from .conftest import future, iso, login, make_item, make_org, make_org_admin, make_user


def anon():
    return TestClient(create_app(run_startup=False))


def signup(client, email, **kw):
    body = {"email": email, "name": "새 회원", "password": "password123", **kw}
    return client.post("/auth/signup", json=body)


def reserve(client, item_id, h1=1, h2=2):
    return client.post(
        "/reservations",
        json={"item_id": item_id, "start_at": iso(future(h1)), "end_at": iso(future(h2)), "purpose": "동아리 활동"},
    )


@pytest.fixture
def world(db, users):
    """학교 두 곳 + 주민센터 하나, 각 기관 관리자, 물품"""
    gaon = make_org(db, "s-gaon", "가온고등학교", "school", 37.55, 126.92)
    hanbit = make_org(db, "s-hanbit", "한빛중학교", "school", 37.58, 126.94)
    center = make_org(db, "c-seogyo", "서교동 행정복지센터", "community_center", 37.556, 126.918)
    far = make_org(db, "s-busan", "부산누리고등학교", "school", 35.15, 129.05)
    gaon_admin = make_user(db, "gaon.admin@t.test")
    hanbit_admin = make_user(db, "hanbit.admin@t.test")
    make_org_admin(db, gaon, gaon_admin)
    make_org_admin(db, hanbit, hanbit_admin)
    return {
        "gaon": gaon,
        "hanbit": hanbit,
        "center": center,
        "far": far,
        "gaon_item": make_item(db, "MIC-001", "무선 마이크", org=gaon, access="members"),
        "hanbit_item": make_item(db, "MIC-001", "무선 마이크", org=hanbit, access="members"),
        "center_item": make_item(db, "TBL-001", "접이식 테이블", org=center, access="public"),
        "gaon_admin": login(gaon_admin.email),
        "hanbit_admin": login(hanbit_admin.email),
    }


# ---------------------------------------------------------------- 회원가입


def test_signup_general_user_logs_in(world):
    c = anon()
    r = signup(c, "Resident@T.test")
    assert r.status_code == 201, r.text
    me = c.get("/auth/me").json()["user"]
    assert me["email"] == "resident@t.test" and me["student"]["status"] == "none" and not me["is_staff"]
    assert signup(anon(), "resident@t.test").status_code == 409
    assert signup(anon(), "not-an-email").status_code == 422
    assert anon().post("/auth/signup", json={"email": "a@b.cd", "name": "x", "password": "short"}).status_code == 422


def test_student_signup_requires_school_and_number(world):
    assert signup(anon(), "s1@t.test", is_student=True).status_code == 422
    assert signup(anon(), "s1@t.test", is_student=True, school_id=world["center"].id, student_no="1").status_code == 422
    assert signup(anon(), "s1@t.test", is_student=True, school_id=world["gaon"].id).status_code == 422
    c = anon()
    r = signup(c, "s1@t.test", is_student=True, school_id=world["gaon"].id, student_no="10203")
    assert r.status_code == 201
    st = r.json()["user"]["student"]
    assert st["status"] == "pending" and st["school"]["name"] == "가온고등학교"


def test_school_items_need_approved_student_of_that_school(world):
    c = anon()
    uid = signup(c, "s1@t.test", is_student=True, school_id=world["gaon"].id, student_no="10203").json()["user"]["id"]
    # 승인 전: 학교 물품 불가, 주민센터 물품 가능
    r = reserve(c, world["gaon_item"].id)
    assert r.status_code == 403 and "승인" in r.json()["detail"]
    assert reserve(c, world["center_item"].id).status_code == 201
    # 목록에서 자격 표시
    rows = {i["id"]: i for i in c.get("/items").json()["items"]}
    assert rows[world["gaon_item"].id]["eligible"] is False
    assert rows[world["center_item"].id]["eligible"] is True
    # 다른 학교 관리자는 승인 불가, 일반 사용자는 접근 불가
    assert world["hanbit_admin"].post(f"/admin/students/{uid}/approve").status_code == 404
    assert c.get("/admin/students").status_code == 403
    # 자기 학교 관리자가 승인
    pending = world["gaon_admin"].get("/admin/students").json()["students"]
    assert [s["id"] for s in pending] == [uid]
    assert world["gaon_admin"].post(f"/admin/students/{uid}/approve").status_code == 200
    assert reserve(c, world["gaon_item"].id).status_code == 201
    # 다른 학교 물품은 여전히 불가
    assert reserve(c, world["hanbit_item"].id).status_code == 403
    # 일반 회원(학생 아님)은 학교 물품 불가
    g = anon()
    signup(g, "g@t.test")
    assert reserve(g, world["gaon_item"].id).status_code == 403


def test_reject_requires_reason_and_reapply(world):
    c = anon()
    uid = signup(c, "s1@t.test", is_student=True, school_id=world["gaon"].id, student_no="1").json()["user"]["id"]
    assert world["gaon_admin"].post(f"/admin/students/{uid}/reject", json={"reason": ""}).status_code == 422
    r = world["gaon_admin"].post(f"/admin/students/{uid}/reject", json={"reason": "학번 불일치"})
    assert r.json()["student"]["status"] == "rejected"
    assert "거절" in reserve(c, world["gaon_item"].id).json()["detail"]
    # 다시 신청하면 승인 대기
    r = c.put("/me/student", json={"school_id": world["gaon"].id, "student_no": "10203"})
    assert r.json()["user"]["student"]["status"] == "pending"


def test_approval_rechecks_borrower_eligibility(world, db):
    c = anon()
    uid = signup(c, "s1@t.test", is_student=True, school_id=world["gaon"].id, student_no="1").json()["user"]["id"]
    world["gaon_admin"].post(f"/admin/students/{uid}/approve")
    rid = reserve(c, world["gaon_item"].id).json()["reservation"]["id"]
    # 신청 후 전학 신청 → 승인 대기로 바뀜 → 예약 승인 불가
    c.put("/me/student", json={"school_id": world["hanbit"].id, "student_no": "2"})
    r = world["gaon_admin"].post(f"/admin/reservations/{rid}/approve")
    assert r.status_code == 409 and "자격" in r.json()["detail"]


# ---------------------------------------------------------------- 기관별 관리 범위


def test_org_admin_scope(world, db, users):
    c = anon()
    uid = signup(c, "s4@t.test", is_student=True, school_id=world["hanbit"].id, student_no="1").json()["user"]["id"]
    world["hanbit_admin"].post(f"/admin/students/{uid}/approve")
    rid = reserve(c, world["hanbit_item"].id).json()["reservation"]["id"]
    ga = world["gaon_admin"]
    # 가온고 관리자에게 한빛중 예약이 보이지 않고 처리할 수 없음
    assert all(r["id"] != rid for r in ga.get("/admin/reservations").json()["reservations"])
    assert ga.post(f"/admin/reservations/{rid}/approve").status_code == 403
    assert ga.post(f"/admin/reservations/{rid}/reject", json={"reason": "x"}).status_code == 403
    assert ga.post(f"/admin/reservations/{rid}/cancel", json={"reason": "x"}).status_code == 404
    assert ga.get(f"/reservations/{rid}").status_code == 404
    # 물품도 자기 기관만
    codes = {(i["org_id"], i["asset_code"]) for i in ga.get("/admin/items").json()["items"]}
    assert codes == {(world["gaon"].id, "MIC-001")}
    body = {"org_id": world["hanbit"].id, "asset_code": "X-1", "name": "x", "category": "x"}
    assert ga.post("/admin/items", json=body).status_code == 403
    upd = {**body, "status": "repair"}
    assert ga.put(f"/admin/items/{world['hanbit_item'].id}", json=upd).status_code == 404
    # 자기 기관에는 등록 가능, 관리번호는 기관마다 따로
    ok = ga.post("/admin/items", json={**body, "org_id": world["gaon"].id, "asset_code": "MIC-002"})
    assert ok.status_code == 201
    dup = ga.post("/admin/items", json={**body, "org_id": world["gaon"].id, "asset_code": "mic-001"})
    assert dup.status_code == 409
    # 기관 관리자는 서비스 관리자 기능(회원·기관) 사용 불가
    assert ga.get("/admin/users").status_code == 403
    assert ga.get("/admin/orgs").status_code == 403
    assert ga.post("/admin/sync").status_code == 403
    # 담당 기관 관리자는 승인 가능
    assert world["hanbit_admin"].post(f"/admin/reservations/{rid}/approve").status_code == 200


def test_super_admin_assigns_org_admin(world, clients):
    c = anon()
    signup(c, "teacher@t.test")
    assert c.get("/admin/reservations").status_code == 403
    r = clients["admin"].post(f"/admin/orgs/{world['center'].id}/admins", json={"email": "teacher@t.test"})
    assert r.status_code == 201
    me = c.get("/auth/me").json()["user"]
    assert me["is_staff"] and me["managed_orgs"][0]["name"] == "서교동 행정복지센터"
    assert c.get("/admin/reservations").status_code == 200
    assert clients["admin"].post(f"/admin/orgs/{world['center'].id}/admins", json={"email": "nobody@t.test"}).status_code == 404


# ---------------------------------------------------------------- 검색 / 지도


def test_org_search_is_public(world):
    r = anon().get("/orgs/search", params={"q": "가온", "kind": "school"})
    assert [o["name"] for o in r.json()["orgs"]] == ["가온고등학교"]
    assert anon().get("/orgs/search", params={"q": "가온", "kind": "community_center"}).json()["orgs"] == []


def test_map_bounds_and_counts(world, clients):
    seoul = {"sw_lat": 37.4, "sw_lng": 126.8, "ne_lat": 37.7, "ne_lng": 127.1}
    r = clients["alice"].get("/orgs/map", params=seoul).json()
    names = {o["name"]: o for o in r["orgs"]}
    assert set(names) == {"가온고등학교", "한빛중학교", "서교동 행정복지센터"}  # 물품 없는 기관·범위 밖 제외
    assert names["서교동 행정복지센터"]["available_now"] == 1
    r = clients["alice"].get("/orgs/map", params={**seoul, "kind": "community_center"}).json()
    assert [o["name"] for o in r["orgs"]] == ["서교동 행정복지센터"]
    whole = {"sw_lat": 33, "sw_lng": 124, "ne_lat": 39, "ne_lng": 132, "with_items": False}
    assert "부산누리고등학교" in {o["name"] for o in clients["alice"].get("/orgs/map", params=whole).json()["orgs"]}
    assert anon().get("/orgs/map", params=seoul).status_code == 401


# ---------------------------------------------------------------- 공공데이터 동기화


def neis_row(code, name, addr, kind="고등학교"):
    return {"SD_SCHUL_CODE": code, "SCHUL_NM": name, "SCHUL_KND_SC_NM": kind, "LCTN_SC_NM": "서울특별시",
            "ORG_RDNMA": addr, "ORG_RDNDA": "", "ORG_TELNO": "02-000-0000"}


class FakeHttp:
    def __init__(self, schools):
        self.schools = schools
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        if url.startswith(orgsync.NEIS_URL):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            page, size = int(q["pIndex"][0]), int(q["pSize"][0])
            rows = self.schools[(page - 1) * size : page * size]
            if not rows:
                return {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
            return {"schoolInfo": [{"head": [{"list_total_count": len(self.schools)}, {"RESULT": {"CODE": "INFO-000"}}]}, {"row": rows}]}
        assert headers["Authorization"].startswith("KakaoAK ")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
        if "없는" in query:
            return {"documents": []}
        return {"documents": [{"x": "126.9", "y": "37.5"}]}


def test_neis_sync_upserts_deactivates_and_geocodes(db, monkeypatch):
    monkeypatch.setattr(config, "NEIS_API_KEY", "test-key")
    monkeypatch.setattr(config, "KAKAO_REST_API_KEY", "kakao-key")
    schools = [neis_row(f"7{i:06d}", f"테스트{i}고등학교", f"서울특별시 테스트로 {i}") for i in range(5)]
    schools.append(neis_row("7999999", "없는주소학교", "없는 주소"))
    http = FakeHttp(schools)
    run = orgsync.run_sync(db, http_get=http)
    assert run.status == "ok", run.message
    assert run.created == 6 and run.geocoded == 5
    orgs = {o.code: o for o in db.exec(select(Organization)).all()}
    assert orgs["7000001"].lat == 37.5 and orgs["7999999"].geocode_status == "failed"

    # 다음 날: 한 학교 폐교(목록에서 빠짐), 한 학교 주소 변경
    http.schools = [s for s in schools if s["SD_SCHUL_CODE"] != "7000004"]
    http.schools[0] = {**http.schools[0], "ORG_RDNMA": "서울특별시 새주소로 1"}
    run = orgsync.run_sync(db, http_get=http)
    assert (run.created, run.updated, run.deactivated) == (0, 1, 1)
    db.expire_all()
    assert db.exec(select(Organization).where(Organization.code == "7000004")).one().active is False
    moved = db.exec(select(Organization).where(Organization.code == "7000000")).one()
    assert moved.address == "서울특별시 새주소로 1" and moved.geocode_status == "ok"  # 다시 좌표를 찾음


def test_neis_paging(db, monkeypatch):
    monkeypatch.setattr(config, "NEIS_API_KEY", "k")
    http = FakeHttp([neis_row(f"8{i:06d}", f"학교{i}", "") for i in range(5)])
    rows = orgsync.fetch_neis_schools("k", http, page_size=2)
    assert len(rows) == 5 and sum(1 for c in http.calls if "pIndex" in c) == 3


def test_sync_without_key_is_reported(db, monkeypatch, clients):
    monkeypatch.setattr(config, "NEIS_API_KEY", "")
    run = clients["admin"].post("/admin/sync").json()["run"]
    assert run["status"] == "error" and "NEIS_API_KEY" in run["message"]
    status = clients["admin"].get("/admin/sync").json()
    assert status["neis_key"] is False and status["runs"][0]["status"] == "error"


def test_csv_import_cp949_with_and_without_coordinates(db, clients):
    content = "행정복지센터명,도로명주소,위도,경도,전화번호\n서교동 행정복지센터,서울특별시 마포구 서교로 1,37.555,126.918,02-1\n연희동 행정복지센터,서울특별시 서대문구 연희로 2,,,\n"
    r = clients["admin"].post(
        "/admin/orgs/import",
        files={"file": ("centers.csv", content.encode("cp949"), "text/csv")},
        data={"kind": "community_center"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["run"]["created"] == 2
    orgs = {o.name: o for o in db.exec(select(Organization)).all()}
    assert orgs["서교동 행정복지센터"].geocode_status == "ok" and orgs["서교동 행정복지센터"].lat == 37.555
    assert orgs["연희동 행정복지센터"].geocode_status == "pending"
    # 같은 파일을 다시 올리면 중복 생성되지 않음
    again = clients["admin"].post("/admin/orgs/import", files={"file": ("c.csv", content.encode("utf-8"), "text/csv")}, data={"kind": "community_center"})
    assert again.json()["run"]["created"] == 0
    bad = clients["admin"].post("/admin/orgs/import", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422


def test_cron_requires_secret(db, monkeypatch):
    c = anon()
    monkeypatch.setattr(config, "CRON_SECRET", "")
    assert c.get("/cron/sync").status_code == 503
    monkeypatch.setattr(config, "CRON_SECRET", "s3cret")
    monkeypatch.setattr(config, "NEIS_API_KEY", "")
    assert c.get("/cron/sync").status_code == 401
    assert c.get("/cron/sync", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = c.get("/cron/sync", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and r.json()["run"]["status"] == "ok"


def test_manual_coordinates_survive_sync(db, monkeypatch, clients):
    org = make_org(db, "7000000", "테스트0고등학교", "school", None, None)
    org.source, org.address = "neis", "서울특별시 테스트로 0"
    db.commit()
    r = clients["admin"].patch(f"/admin/orgs/{org.id}", json={"lat": 37.6, "lng": 127.0})
    assert r.json()["org"]["geocode_status"] == "manual"
    monkeypatch.setattr(config, "NEIS_API_KEY", "k")
    http = FakeHttp([neis_row("7000000", "테스트0고등학교", "서울특별시 바뀐로 9")])
    orgsync.run_sync(db, http_get=http)
    db.expire_all()
    o = db.get(Organization, org.id)
    assert (o.lat, o.lng, o.geocode_status, o.address) == (37.6, 127.0, "manual", "서울특별시 바뀐로 9")


def test_school_location_csv_fills_coordinates_only(db, clients):
    a = make_org(db, "7000001", "가온고등학교", "school", None, None)
    a.region, a.geocode_status = "서울특별시", "pending"
    b = make_org(db, "7000002", "누리초등학교", "school", None, None)
    b.region = "서울특별시"
    c = make_org(db, "7000003", "누리초등학교", "school", None, None)
    c.region = "부산광역시"
    for o in (a, b, c):
        o.geocode_status = "pending"
    db.commit()
    content = (
        "학교ID,학교명,시도명,소재지도로명주소,위도,경도\n"
        "B1,가온 고등학교,서울특별시,서울특별시 마포구,37.55,126.92\n"
        "B2,누리초등학교,부산광역시,부산광역시 해운대구,35.16,129.16\n"
        "B3,없는학교,서울특별시,서울특별시 어딘가,37.5,127.0\n"
    )
    r = clients["admin"].post(
        "/admin/orgs/import",
        files={"file": ("schools.csv", content.encode("cp949"), "text/csv")},
        data={"kind": "school", "coords_only": "true"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["run"]["created"] == 0 and "갱신 2곳" in r.json()["run"]["message"]
    db.expire_all()
    assert (db.get(type(a), a.id).lat, db.get(type(a), a.id).geocode_status) == (37.55, "ok")
    assert db.get(type(b), b.id).lat is None  # 서울 누리초는 그대로
    assert db.get(type(c), c.id).lat == 35.16  # 시도로 구분해 부산 누리초만
    assert db.exec(select(Organization).where(Organization.name == "없는학교")).first() is None
