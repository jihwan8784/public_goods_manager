"""관리 명령.

  python -m pgm.manage init-db                     # 테이블·제약조건 생성
  python -m pgm.manage create-admin EMAIL 이름      # 관리자 계정 생성 (비밀번호는 입력받음)
  python -m pgm.manage seed-demo [--reset]         # 개발용 시연 데이터 (운영 환경에서는 거부)
"""

import getpass
import sys

from sqlmodel import Session, select

from . import config
from .db import engine, init_db
from .models import ROLE_ADMIN, User
from .security import hash_password


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "init-db":
        init_db()
        print("데이터베이스 초기화 완료")
        return 0
    if cmd == "create-admin":
        if len(argv) < 3:
            print("사용법: python -m pgm.manage create-admin EMAIL 이름")
            return 1
        email, name = argv[1].strip().lower(), argv[2]
        pw = getpass.getpass("비밀번호(8자 이상): ")
        if len(pw) < 8:
            print("비밀번호는 8자 이상이어야 합니다.")
            return 1
        init_db()
        with Session(engine) as s:
            if s.exec(select(User).where(User.email == email)).first():
                print("이미 존재하는 아이디입니다.")
                return 1
            s.add(User(email=email, name=name, password_hash=hash_password(pw), role=ROLE_ADMIN))
            s.commit()
        print(f"관리자 {email} 생성 완료")
        return 0
    if cmd == "seed-demo":
        from .seed import seed_demo

        if config.IS_PRODUCTION:
            print("운영 환경(APP_ENV=production)에서는 시연 데이터를 만들 수 없습니다.")
            return 2
        init_db()
        seed_demo(engine, reset="--reset" in argv)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
