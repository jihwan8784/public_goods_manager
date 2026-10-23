"""개발 환경 전용 시연 데이터. 모든 날짜는 실행 시점 기준 상대 날짜다.

기관·사용자는 모두 가상이다. 운영 환경에서는 manage.py 가 이 함수를 호출하지 않는다.
"""

from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session, select

from . import config
from .models import (
    ACCESS_MEMBERS,
    ACCESS_PUBLIC,
    COND_NORMAL,
    ITEM_REPAIR,
    ITEM_RETIRED,
    ORG_CENTER,
    ORG_SCHOOL,
    R_APPROVED,
    R_CANCELLED,
    R_IN_USE,
    R_PENDING,
    R_REJECTED,
    R_RETURN_REQUESTED,
    R_RETURNED,
    REPORT_IN_PROGRESS,
    REPORT_RECEIVED,
    REPORT_RESOLVED,
    ROLE_ADMIN,
    STUDENT_APPROVED,
    STUDENT_PENDING,
    DamageReport,
    Item,
    Organization,
    OrgAdmin,
    Reservation,
    User,
)
from .security import hash_password
from .timeutil import SEOUL, now_utc

DEMO_PASSWORD_ADMIN = "admin1234!"
DEMO_PASSWORD_USER = "user1234!"

# (key, 종류, 이름, 세부, 주소, 위도, 경도)  — 가상의 기관, 좌표는 서울 서부 일대
ORGS = [
    ("gaon", ORG_SCHOOL, "가온고등학교", "고등학교", "서울특별시 마포구 가온로 10 (가상)", 37.5563, 126.9236),
    ("hanbit", ORG_SCHOOL, "한빛중학교", "중학교", "서울특별시 서대문구 한빛길 22 (가상)", 37.5791, 126.9368),
    ("nuri", ORG_SCHOOL, "누리초등학교", "초등학교", "서울특별시 마포구 누리로 5 (가상)", 37.5502, 126.9145),
    ("seogyo", ORG_CENTER, "서교동 행정복지센터 (시연)", "", "서울특별시 마포구 서교로 1 (가상)", 37.5555, 126.9180),
    ("yeonhui", ORG_CENTER, "연희동 행정복지센터 (시연)", "", "서울특별시 서대문구 연희로 2 (가상)", 37.5680, 126.9300),
]

# (email, 이름, 역할, 비밀번호, 학생 학교 key, 학생 상태, 관리 기관 key 목록)
USERS = [
    ("admin@pgm.test", "서비스 관리자", ROLE_ADMIN, DEMO_PASSWORD_ADMIN, None, None, []),
    ("gaon.admin@pgm.test", "정하윤 (가온고 담당)", "user", DEMO_PASSWORD_ADMIN, None, None, ["gaon"]),
    ("center.admin@pgm.test", "오세린 (서교동 센터)", "user", DEMO_PASSWORD_ADMIN, None, None, ["seogyo", "yeonhui"]),
    ("student1@pgm.test", "김하늘", "user", DEMO_PASSWORD_USER, "gaon", STUDENT_APPROVED, []),
    ("student2@pgm.test", "이바다", "user", DEMO_PASSWORD_USER, "gaon", STUDENT_APPROVED, []),
    ("student3@pgm.test", "박솔", "user", DEMO_PASSWORD_USER, "gaon", STUDENT_PENDING, []),
    ("student4@pgm.test", "최유진", "user", DEMO_PASSWORD_USER, "hanbit", STUDENT_APPROVED, []),
    ("resident@pgm.test", "한결 (주민)", "user", DEMO_PASSWORD_USER, None, None, []),
]

MIC = ("무선 마이크", "음향", "UHF 무선 핸드 마이크. 수신기·AA 건전지 2개 포함.", "사용 후 건전지를 빼서 반납해 주세요.")
SPK = ("블루투스 스피커", "음향", "충전식 휴대용 스피커 (최대 8시간).", "완충 후 반납해 주세요. 물기 주의.")
TRI = ("카메라 삼각대", "촬영", "최대 높이 160cm, 스마트폰 거치대 포함.", "다리 잠금을 확인한 뒤 장비를 올려 주세요.")
CAM = ("디지털 카메라", "촬영", "미러리스 카메라, 렌즈 1개, 배터리 2개, SD카드 64GB.", "렌즈 캡을 꼭 닫아 반납해 주세요.")
PRJ = ("빔프로젝터", "영상", "3,500안시 프로젝터. HDMI 케이블·리모컨 포함.", "전원을 끈 뒤 팬이 멈출 때까지 기다렸다가 분리해 주세요.")
PWR = ("멀티탭 (5구, 5m)", "전기·전원", "개별 스위치 5구 멀티탭.", "정격 용량(16A)을 넘지 않게 사용하세요.")
EXT = ("전선 릴 (20m)", "전기·전원", "야외 행사용 전선 릴.", "완전히 풀어서 사용하세요 (과열 방지).")
TBL = ("접이식 테이블", "행사", "180×60cm 접이식 테이블.", "접을 때 손가락 끼임 주의.")
TNT = ("행사용 천막 (3×3m)", "행사", "원터치 천막, 모래주머니 4개 포함.", "강풍 시 사용하지 마세요.")

# (기관 key, 관리번호, 종류, 보관 장소, 이용 대상)
ITEMS = [
    ("gaon", "MIC-001", MIC, "학생회실 A캐비닛 1단", ACCESS_MEMBERS),
    ("gaon", "MIC-002", MIC, "학생회실 A캐비닛 1단", ACCESS_MEMBERS),
    ("gaon", "MIC-003", MIC, "학생회실 A캐비닛 1단", ACCESS_MEMBERS),
    ("gaon", "SPK-001", SPK, "학생회실 A캐비닛 2단", ACCESS_MEMBERS),
    ("gaon", "SPK-002", SPK, "학생회실 A캐비닛 2단", ACCESS_MEMBERS),
    ("gaon", "TRI-001", TRI, "방송실 장비장", ACCESS_MEMBERS),
    ("gaon", "TRI-002", TRI, "방송실 장비장", ACCESS_MEMBERS),
    ("gaon", "CAM-001", CAM, "방송실 잠금 서랍", ACCESS_MEMBERS),
    ("gaon", "PRJ-001", PRJ, "교무실 옆 비품실", ACCESS_MEMBERS),
    ("gaon", "PRJ-002", PRJ, "교무실 옆 비품실", ACCESS_MEMBERS),
    ("hanbit", "PRJ-001", PRJ, "과학실", ACCESS_MEMBERS),
    ("hanbit", "MIC-001", MIC, "방송실", ACCESS_MEMBERS),
    ("seogyo", "PWR-001", PWR, "민원실 뒤 창고", ACCESS_PUBLIC),
    ("seogyo", "PWR-002", PWR, "민원실 뒤 창고", ACCESS_PUBLIC),
    ("seogyo", "PWR-003", ("멀티탭 (3구, 구형)", "전기·전원", "구형 3구 멀티탭.", "노후로 사용 중지."), "민원실 뒤 창고", ACCESS_PUBLIC),
    ("seogyo", "EXT-001", EXT, "지하 창고", ACCESS_PUBLIC),
    ("seogyo", "TBL-001", TBL, "지하 창고", ACCESS_PUBLIC),
    ("yeonhui", "TNT-001", TNT, "주차장 옆 창고", ACCESS_PUBLIC),
    ("yeonhui", "TBL-001", TBL, "주차장 옆 창고", ACCESS_PUBLIC),
]

TABLES = "pgm_damage_report, pgm_reservation, pgm_item, pgm_org_admin, pgm_user, pgm_sync_run, pgm_org"


def seed_demo(engine, reset: bool = False) -> None:
    if config.IS_PRODUCTION:
        raise RuntimeError("운영 환경에서는 시연 데이터를 만들 수 없습니다.")
    with Session(engine) as s:
        if s.exec(select(User)).first() or s.exec(select(Item)).first():
            if not reset:
                print("이미 데이터가 있습니다. 지우고 다시 만들려면 --reset 을 붙이세요.")
                return
            s.exec(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
            s.commit()

        orgs: dict[str, Organization] = {}
        for key, kind, name, sub, addr, lat, lng in ORGS:
            o = Organization(
                kind=kind, code=f"demo-{key}", name=name, subtype=sub, region="서울특별시", address=addr,
                lat=lat, lng=lng, geocode_status="manual", source="manual",
            )
            s.add(o)
            orgs[key] = o
        s.flush()

        users: dict[str, User] = {}
        for email, name, role, pw, school, status, manages in USERS:
            u = User(email=email, name=name, role=role, password_hash=hash_password(pw))
            if school:
                u.is_student = True
                u.school_id = orgs[school].id
                u.student_no = f"2{len(users)}{len(users) + 3}0{len(users) + 1}"
                u.student_status = status
            s.add(u)
            users[email] = u
        s.flush()
        for email, *_rest, manages in USERS:
            for key in manages:
                s.add(OrgAdmin(org_id=orgs[key].id, user_id=users[email].id))

        items: dict[str, Item] = {}
        for key, code, (name, cat, desc, caution), loc, access in ITEMS:
            i = Item(org_id=orgs[key].id, access=access, asset_code=code, name=name, category=cat,
                     description=desc, caution=caution, location=loc)
            s.add(i)
            items[f"{key}:{code}"] = i
        s.flush()

        staff = users["gaon.admin@pgm.test"]
        center_staff = users["center.admin@pgm.test"]
        u1, u2 = users["student1@pgm.test"], users["student2@pgm.test"]
        u4, res_user = users["student4@pgm.test"], users["resident@pgm.test"]
        now = now_utc()
        base = now.astimezone(SEOUL).replace(minute=0, second=0, microsecond=0)
        day = base.replace(hour=0)

        def at(days: int, hour: int):
            return day + timedelta(days=days, hours=hour)

        def res(key, user, start, end, purpose, status, **kw):
            r = Reservation(
                item_id=items[key].id, user_id=user.id, start_at=start, end_at=end, purpose=purpose, status=status,
                created_at=min(start, now) - timedelta(days=1), updated_at=now, **kw,
            )
            s.add(r)
            return r

        A = {"decided_by": staff.id}
        # 승인 대기 (서로 겹치는 신청 2건 → 승인 시 충돌 확인용)
        res("gaon:MIC-001", u1, at(1, 10), at(1, 12), "학생회 정기 회의 발표", R_PENDING)
        res("gaon:MIC-001", u2, at(1, 11), at(1, 13), "방송부 인터뷰 촬영", R_PENDING)
        res("seogyo:TBL-001", res_user, at(2, 9), at(2, 18), "아파트 바자회 부스", R_PENDING)
        # 예약 확정 (인계 전)
        res("gaon:PRJ-001", u1, at(2, 13), at(2, 17), "동아리 홍보 영상 상영", R_APPROVED, decided_at=now, **A)
        res("gaon:MIC-002", u2, at(3, 9), at(3, 12), "축제 사회", R_APPROVED, decided_at=now, **A)
        res("hanbit:PRJ-001", u4, at(2, 9), at(2, 11), "과학 탐구 발표", R_APPROVED, decided_at=now)
        # 대여 중
        res("gaon:TRI-001", u2, at(-1, 9), at(1, 18), "졸업 앨범 촬영", R_IN_USE, decided_at=now - timedelta(days=2),
            checked_out_at=at(-1, 9), checked_out_by=staff.id, **A)
        res("gaon:CAM-001", u1, base - timedelta(hours=2), base + timedelta(hours=5), "체육대회 사진 촬영", R_IN_USE,
            decided_at=now - timedelta(days=1), checked_out_at=base - timedelta(hours=2), checked_out_by=staff.id, **A)
        # 연체 + 곧 시작하는 다음 확정 예약 → 인계 차단 경고
        res("gaon:SPK-001", u1, at(-5, 13), at(-2, 18), "체육대회 응원 음악", R_IN_USE, decided_at=now - timedelta(days=6),
            checked_out_at=at(-5, 13), checked_out_by=staff.id, **A)
        res("gaon:SPK-001", u2, base + timedelta(hours=1), base + timedelta(hours=4), "점심 버스킹 공연", R_APPROVED,
            decided_at=now - timedelta(days=1), **A)
        # 반납 요청 (주민센터 물품, 관리자 확인 전)
        res("seogyo:PWR-001", res_user, at(-1, 13), base + timedelta(hours=3), "마을 축제 부스 전원", R_RETURN_REQUESTED,
            decided_by=center_staff.id, decided_at=now - timedelta(days=2), checked_out_at=at(-1, 13),
            checked_out_by=center_staff.id, return_requested_at=now - timedelta(minutes=30),
            return_request_note="민원실 앞에 두었습니다.")
        # 반납 완료
        res("gaon:MIC-002", u1, at(-7, 10), at(-7, 12), "학급 회의", R_RETURNED, decided_at=at(-8, 9),
            checked_out_at=at(-7, 10), checked_out_by=staff.id, returned_at=at(-7, 12), returned_by=staff.id,
            return_condition=COND_NORMAL, **A)
        res("yeonhui:TNT-001", u2, at(-4, 9), at(-4, 18), "봉사활동 부스", R_RETURNED, decided_by=center_staff.id,
            decided_at=at(-5, 9), checked_out_at=at(-4, 9), checked_out_by=center_staff.id, returned_at=at(-4, 18),
            returned_by=center_staff.id, return_condition=COND_NORMAL)
        # 거절 / 취소
        res("gaon:PRJ-002", u2, at(1, 15), at(1, 17), "영화 감상회", R_REJECTED,
            reject_reason="해당 물품이 수리 중이라 PRJ-001로 다시 신청해 주세요.", decided_at=now, **A)
        res("gaon:SPK-002", u1, at(2, 12), at(2, 13), "점심 방송", R_CANCELLED, cancelled_at=now)
        # 수리 중인 물품에 남아 있는 확정 예약 → 영향받는 예약 표시 확인용
        res("gaon:PRJ-002", u1, at(4, 13), at(4, 15), "과학 동아리 발표", R_APPROVED, decided_at=now - timedelta(days=3), **A)

        items["gaon:PRJ-002"].status = ITEM_REPAIR
        items["seogyo:PWR-003"].status = ITEM_RETIRED
        s.add(DamageReport(item_id=items["gaon:PRJ-002"].id, reporter_id=u2.id,
                           description="전원을 켜면 램프가 계속 깜빡이고 화면이 꺼집니다.", status=REPORT_IN_PROGRESS,
                           admin_note="램프 교체 부품 주문함 (도착 예정 3일).", handled_by=staff.id,
                           created_at=now - timedelta(days=2)))
        s.add(DamageReport(item_id=items["gaon:MIC-003"].id, reporter_id=u1.id, description="말할 때 지직거리는 잡음이 납니다.",
                           status=REPORT_RECEIVED, created_at=now - timedelta(hours=5)))
        s.add(DamageReport(item_id=items["seogyo:EXT-001"].id, reporter_id=res_user.id, description="전선 피복이 일부 벗겨져 있어요.",
                           status=REPORT_RESOLVED, admin_note="절연 테이프 보수 후 점검 완료.", handled_by=center_staff.id,
                           created_at=now - timedelta(days=10)))
        s.commit()

    print("시연 데이터 생성 완료 (기관·사용자 모두 가상)")
    print(f"  서비스 관리자: admin@pgm.test / {DEMO_PASSWORD_ADMIN}")
    print(f"  기관 관리자: gaon.admin@pgm.test (가온고), center.admin@pgm.test (주민센터) / {DEMO_PASSWORD_ADMIN}")
    print(f"  학생: student1~2 (가온고 승인), student3 (가온고 승인 대기), student4 (한빛중) / {DEMO_PASSWORD_USER}")
    print(f"  주민(학생 아님): resident@pgm.test / {DEMO_PASSWORD_USER}")
