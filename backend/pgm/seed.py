"""개발 환경 전용 시연 데이터. 모든 날짜는 실행 시점 기준 상대 날짜다.

운영 환경에서는 manage.py 가 이 함수를 호출하지 않는다.
"""

from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session, select

from . import config
from .models import (
    COND_NORMAL,
    ITEM_REPAIR,
    ITEM_RETIRED,
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
    DamageReport,
    Item,
    Reservation,
    User,
)
from .security import hash_password
from .timeutil import SEOUL, now_utc

DEMO_PASSWORD_ADMIN = "admin1234!"
DEMO_PASSWORD_USER = "user1234!"

USERS = [
    ("admin@pgm.test", "관리자 정하윤", ROLE_ADMIN, DEMO_PASSWORD_ADMIN),
    ("student1@pgm.test", "김하늘", "user", DEMO_PASSWORD_USER),
    ("student2@pgm.test", "이바다", "user", DEMO_PASSWORD_USER),
    ("student3@pgm.test", "박솔", "user", DEMO_PASSWORD_USER),
]

MIC_DESC = "UHF 무선 핸드 마이크. 수신기·AA 건전지 2개 포함."
MIC_CAUTION = "사용 후 건전지를 빼서 반납해 주세요. 떨어뜨리지 않도록 주의하세요."
ITEMS = [
    ("MIC-001", "무선 마이크", "음향", MIC_DESC, MIC_CAUTION, "학생회실 A캐비닛 1단"),
    ("MIC-002", "무선 마이크", "음향", MIC_DESC, MIC_CAUTION, "학생회실 A캐비닛 1단"),
    ("MIC-003", "무선 마이크", "음향", MIC_DESC, MIC_CAUTION, "학생회실 A캐비닛 1단"),
    ("SPK-001", "블루투스 스피커", "음향", "충전식 휴대용 스피커 (최대 8시간).", "완충 후 반납해 주세요. 물기 주의.", "학생회실 A캐비닛 2단"),
    ("SPK-002", "블루투스 스피커", "음향", "충전식 휴대용 스피커 (최대 8시간).", "완충 후 반납해 주세요. 물기 주의.", "학생회실 A캐비닛 2단"),
    ("TRI-001", "카메라 삼각대", "촬영", "최대 높이 160cm, 스마트폰 거치대 포함.", "다리 잠금을 확인한 뒤 장비를 올려 주세요.", "방송실 장비장"),
    ("TRI-002", "카메라 삼각대", "촬영", "최대 높이 160cm, 스마트폰 거치대 포함.", "다리 잠금을 확인한 뒤 장비를 올려 주세요.", "방송실 장비장"),
    ("CAM-001", "디지털 카메라", "촬영", "미러리스 카메라, 렌즈 1개, 배터리 2개, SD카드 64GB.", "렌즈 캡을 꼭 닫아 반납해 주세요. 사진은 반납 전 백업 후 삭제.", "방송실 잠금 서랍"),
    ("PRJ-001", "빔프로젝터", "영상", "3,500안시 프로젝터. HDMI 케이블·리모컨 포함.", "전원을 끈 뒤 팬이 멈출 때까지 기다렸다가 분리해 주세요.", "교무실 옆 비품실"),
    ("PRJ-002", "빔프로젝터", "영상", "3,500안시 프로젝터. HDMI 케이블·리모컨 포함.", "전원을 끈 뒤 팬이 멈출 때까지 기다렸다가 분리해 주세요.", "교무실 옆 비품실"),
    ("PWR-001", "멀티탭 (5구, 5m)", "전기·전원", "개별 스위치 5구 멀티탭.", "정격 용량(16A)을 넘지 않게 사용하세요.", "학생회실 B선반"),
    ("PWR-002", "멀티탭 (5구, 5m)", "전기·전원", "개별 스위치 5구 멀티탭.", "정격 용량(16A)을 넘지 않게 사용하세요.", "학생회실 B선반"),
    ("PWR-003", "멀티탭 (3구, 구형)", "전기·전원", "구형 3구 멀티탭.", "노후로 사용 중지.", "학생회실 B선반"),
    ("EXT-001", "전선 릴 (20m)", "전기·전원", "야외 행사용 전선 릴.", "완전히 풀어서 사용하세요 (과열 방지).", "체육창고"),
]


def seed_demo(engine, reset: bool = False) -> None:
    if config.IS_PRODUCTION:
        raise RuntimeError("운영 환경에서는 시연 데이터를 만들 수 없습니다.")
    with Session(engine) as s:
        if s.exec(select(User)).first() or s.exec(select(Item)).first():
            if not reset:
                print("이미 데이터가 있습니다. 지우고 다시 만들려면 --reset 을 붙이세요.")
                return
            s.exec(
                text(
                    "TRUNCATE pgm_damage_report, pgm_reservation, pgm_item, pgm_user RESTART IDENTITY CASCADE"
                )
            )
            s.commit()

        users = {}
        for email, name, role, pw in USERS:
            u = User(email=email, name=name, role=role, password_hash=hash_password(pw))
            s.add(u)
            users[email] = u
        items = {}
        for code, name, cat, desc, caution, loc in ITEMS:
            i = Item(asset_code=code, name=name, category=cat, description=desc, caution=caution, location=loc)
            s.add(i)
            items[code] = i
        s.flush()

        admin = users["admin@pgm.test"]
        u1, u2, u3 = users["student1@pgm.test"], users["student2@pgm.test"], users["student3@pgm.test"]
        now = now_utc()
        # 서울 기준 정시로 맞춘 기준 시각
        base = now.astimezone(SEOUL).replace(minute=0, second=0, microsecond=0)
        day = base.replace(hour=0)

        def at(days: int, hour: int):
            return day + timedelta(days=days, hours=hour)

        def res(code, user, start, end, purpose, status, **kw):
            r = Reservation(
                item_id=items[code].id,
                user_id=user.id,
                start_at=start,
                end_at=end,
                purpose=purpose,
                status=status,
                created_at=min(start, now) - timedelta(days=1),
                updated_at=now,
                **kw,
            )
            s.add(r)
            return r

        # 승인 대기 (서로 겹치는 신청 2건 → 승인 시 충돌 확인용)
        res("MIC-001", u1, at(1, 10), at(1, 12), "학생회 정기 회의 발표", R_PENDING)
        res("MIC-001", u2, at(1, 11), at(1, 13), "방송부 인터뷰 촬영", R_PENDING)
        res("TRI-002", u3, at(2, 14), at(2, 17), "사진 동아리 야외 출사", R_PENDING)
        # 예약 확정 (인계 전)
        res("PRJ-001", u1, at(2, 13), at(2, 17), "동아리 홍보 영상 상영", R_APPROVED, decided_by=admin.id, decided_at=now)
        res("MIC-002", u3, at(3, 9), at(3, 12), "축제 사회", R_APPROVED, decided_by=admin.id, decided_at=now)
        # 대여 중
        res("TRI-001", u2, at(-1, 9), at(1, 18), "졸업 앨범 촬영", R_IN_USE,
            decided_by=admin.id, decided_at=now - timedelta(days=2), checked_out_at=at(-1, 9), checked_out_by=admin.id)
        res("CAM-001", u3, base - timedelta(hours=2), base + timedelta(hours=5), "체육대회 사진 촬영", R_IN_USE,
            decided_by=admin.id, decided_at=now - timedelta(days=1), checked_out_at=base - timedelta(hours=2), checked_out_by=admin.id)
        # 연체 (반납 기한 지남, 미반납) + 곧 시작하는 다음 확정 예약 → 인계 차단 경고
        res("SPK-001", u1, at(-5, 13), at(-2, 18), "체육대회 응원 음악", R_IN_USE,
            decided_by=admin.id, decided_at=now - timedelta(days=6), checked_out_at=at(-5, 13), checked_out_by=admin.id)
        res("SPK-001", u2, base + timedelta(hours=1), base + timedelta(hours=4), "점심 버스킹 공연", R_APPROVED,
            decided_by=admin.id, decided_at=now - timedelta(days=1))
        # 반납 요청 (관리자 확인 전)
        res("PWR-001", u2, at(-1, 13), base + timedelta(hours=3), "부스 운영 전원 연결", R_RETURN_REQUESTED,
            decided_by=admin.id, decided_at=now - timedelta(days=2), checked_out_at=at(-1, 13), checked_out_by=admin.id,
            return_requested_at=now - timedelta(minutes=30), return_request_note="학생회실 B선반 앞에 두었습니다.")
        # 반납 완료
        res("MIC-002", u1, at(-7, 10), at(-7, 12), "학급 회의", R_RETURNED,
            decided_by=admin.id, decided_at=at(-8, 9), checked_out_at=at(-7, 10), checked_out_by=admin.id,
            returned_at=at(-7, 12), returned_by=admin.id, return_condition=COND_NORMAL)
        res("PRJ-001", u3, at(-4, 13), at(-4, 16), "수학 동아리 발표", R_RETURNED,
            decided_by=admin.id, decided_at=at(-5, 9), checked_out_at=at(-4, 13), checked_out_by=admin.id,
            returned_at=at(-4, 16), returned_by=admin.id, return_condition=COND_NORMAL)
        # 거절 / 취소
        res("PRJ-002", u2, at(1, 15), at(1, 17), "영화 감상회", R_REJECTED,
            reject_reason="해당 물품이 수리 중이라 PRJ-001로 다시 신청해 주세요.", decided_by=admin.id, decided_at=now)
        res("SPK-002", u1, at(2, 12), at(2, 13), "점심 방송", R_CANCELLED, cancelled_at=now)
        # 수리 중인 물품에 남아 있는 확정 예약 → 영향받는 예약 표시 확인용
        res("PRJ-002", u3, at(4, 13), at(4, 15), "과학 동아리 발표", R_APPROVED, decided_by=admin.id, decided_at=now - timedelta(days=3))

        items["PRJ-002"].status = ITEM_REPAIR
        items["PWR-003"].status = ITEM_RETIRED
        s.add(DamageReport(item_id=items["PRJ-002"].id, reporter_id=u2.id, description="전원을 켜면 램프가 계속 깜빡이고 화면이 꺼집니다.",
                           status=REPORT_IN_PROGRESS, admin_note="램프 교체 부품 주문함 (도착 예정 3일).", handled_by=admin.id,
                           created_at=now - timedelta(days=2)))
        s.add(DamageReport(item_id=items["MIC-003"].id, reporter_id=u1.id, description="말할 때 지직거리는 잡음이 납니다.",
                           status=REPORT_RECEIVED, created_at=now - timedelta(hours=5)))
        s.add(DamageReport(item_id=items["TRI-002"].id, reporter_id=u3.id, description="다리 한쪽 잠금이 헐거워요.",
                           status=REPORT_RESOLVED, admin_note="잠금 나사 조임 완료.", handled_by=admin.id,
                           created_at=now - timedelta(days=10)))
        s.commit()

    print("시연 데이터 생성 완료")
    print(f"  관리자: admin@pgm.test / {DEMO_PASSWORD_ADMIN}")
    print(f"  사용자: student1@pgm.test, student2@pgm.test, student3@pgm.test / {DEMO_PASSWORD_USER}")
