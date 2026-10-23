# public goods manage

학교·동아리·학생회에서 쓰는 **공동 물품 대여 관리 웹**입니다. 물품 보유 현황, 예약, 대여, 반납, 고장 신고를 한곳에서 관리합니다.

- 프론트엔드: Next.js 16 + Tailwind CSS (`frontend/`)
- 백엔드: FastAPI + SQLModel + PostgreSQL (`backend/`)
- 배포: Vercel (web / api 두 프로젝트), DB: Neon

## 로컬 실행

1. PostgreSQL 준비 — `docker compose -f backend/docker-compose.yml up -d` (DB `pgm`, 테스트용 `pgm_test` 자동 생성)
2. 백엔드
   ```bash
   cd backend
   python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
   cp .env.example .env
   .venv/bin/python -m pgm.manage seed-demo --reset   # 시연 데이터 (개발 환경 전용)
   .venv/bin/uvicorn main:app --reload --port 8000
   ```
3. 프론트엔드
   ```bash
   cd frontend
   cp .env.example .env.local && npm install && npm run dev
   ```
4. http://localhost:3000 접속

### 개발용 테스트 계정 (seed-demo 로 생성, 가상 인물)
| 역할 | 아이디 | 비밀번호 |
|---|---|---|
| 관리자 | admin@pgm.test | admin1234! |
| 일반 사용자 | student1@pgm.test (김하늘), student2@pgm.test (이바다), student3@pgm.test (박솔) | user1234! |

## 테스트
```bash
cd backend && .venv/bin/python -m pytest -q
```

## Vercel 배포 시 환경변수
**API 프로젝트 (donga-shop-api)**
- `DATABASE_URL` (Neon, 기존 값)
- `SECRET_KEY` — 필수. `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` — 최초 관리자 (관리자가 없을 때 한 번만 생성)
- `ALLOWED_ORIGINS` (기존 값)

**웹 프로젝트 (donga-shop-web)**
- `NEXT_PUBLIC_API_URL` 또는 `API_URL` — API 주소 (기존 값 그대로 사용 가능)
- `NEXT_PUBLIC_SITE_URL` — QR 에 넣을 주소 (선택, 예: https://donga-shop-web.vercel.app)

자세한 규칙과 구조는 `CLAUDE.md` 참고.
