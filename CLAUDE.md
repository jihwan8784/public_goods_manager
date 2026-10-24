# public goods manage

학교·주민센터 등 여러 공공기관의 공동 물품 대여 관리 웹. 회원가입·학생 인증·지도 지원. 화면은 모두 한국어.

## 구조
- `frontend/` Next.js 16 (App Router, Tailwind 4) — Vercel `public-goods-manager`
  - 브라우저는 같은 도메인 `/api/*` 만 호출하고 `next.config.ts` rewrites 가 API 서버로 전달 (httpOnly 쿠키를 같은 사이트 쿠키로 사용)
  - `app/(main)/` 로그인 후 화면 (AppShell 이 로그인·관리자 여부 확인), `app/login/`
  - `frontend/AGENTS.md`: 이 Next.js 버전은 학습 데이터와 다르니 `node_modules/next/dist/docs/` 를 먼저 확인
- `backend/` FastAPI + SQLModel + PostgreSQL(Neon) — Vercel `public-goods-manager-api`
  - `main.py` 진입점, `pgm/services.py` 예약·대여 규칙(모든 상태 변경은 여기서만), `pgm/models.py` 테이블(`pgm_*`)
  - `pgm/access.py` 기관별 권한·대여 자격, `pgm/routes.py` 물품·예약·관리 API, `pgm/people.py` 회원가입·학생 승인·회원, `pgm/routes_orgs.py` 기관·지도·동기화
  - `pgm/orgsync.py` 공공데이터 동기화 (NEIS 학교, CSV 주민센터, 카카오 좌표). `vercel.json` 이 매일 `/cron/sync` 호출
  - `pgm/db.py` 의 `_migrate_v2` 가 1차(단일 조직) DB 를 자동으로 여러 기관 구조로 올림
  - `pgm/seed.py` 개발용 시연 데이터, `pgm/manage.py` 관리 명령

## 명령어
```bash
# DB (로컬): docker compose -f backend/docker-compose.yml up -d   (또는 로컬 PostgreSQL 16 + DB pgm, pgm_test)
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python -m pgm.manage init-db            # 테이블·제약조건 생성 (API 첫 요청 때도 자동 실행)
.venv/bin/python -m pgm.manage seed-demo --reset  # 개발용 시연 데이터 (APP_ENV=production 이면 거부)
.venv/bin/python -m pgm.manage create-admin EMAIL 이름
.venv/bin/uvicorn main:app --reload --port 8000
.venv/bin/python -m pytest -q                     # pgm_test DB 사용 (TEST_DATABASE_URL 로 변경 가능)

cd frontend && cp .env.example .env.local && npm install
npm run dev | npm run build | npx tsc --noEmit | npm run lint
```

## 핵심 대여 규칙 (반드시 유지)
- 상태: `pending`(승인 대기) → `approved`(예약 확정) → `in_use`(대여 중) → `return_requested`(반납 요청) → `returned`(반납 완료). `rejected`/`cancelled` 는 종료 상태. 단계 건너뛰기·반복 처리 불가(409).
- 승인 ≠ 대여 시작. 관리자가 실물 인계 시 `checkout` 해야 `in_use`. 반납 요청 ≠ 반납 완료 (관리자 실물 확인 필요).
- 기간 점유 상태: `approved`, `in_use`, `return_requested`. 같은 물품의 점유 기간은 겹칠 수 없음. 구간은 `[start, end)` → 끝 시각 == 다음 시작 허용.
- 승인 대기끼리는 겹쳐도 됨. 승인 시 재검사. 취소·거절은 점유 안 함.
- 동시성: 상태 변경 시 예약 행 `FOR UPDATE` → 물품 행 `FOR UPDATE` (항상 이 순서). DB 배제 제약 `pgm_reservation_no_overlap`(btree_gist) 이 최종 안전장치.
- 수리 중(`repair`)·보관 종료(`retired`) 물품: 신규 신청·승인·인계 불가. 수리 전환 시 영향받는 예약(대기·확정) 목록을 관리자에게 반환.
- 미반납(`in_use`/`return_requested`) 대여가 있으면 다음 예약 인계 불가 + 관리자 대시보드 경고. 연체 = 미반납이고 `end_at <= now`.
- 인계는 시작 30분 전부터 종료 전까지. 신규 예약은 과거 불가, 최대 14일, 180일 이내.
- 대여·신고 기록 있는 물품은 삭제 불가 → 보관 종료. 반납 시 "수리 필요" 선택하면 물품 수리 중 + 고장 신고 자동 생성.
- 시간: DB 는 `timestamptz`(UTC). 시간대 없는 입력은 Asia/Seoul 로 해석. 프론트는 `+09:00` 붙여 전송, 표시는 `lib/time.ts` (Asia/Seoul).
- 권한: 서버에서 매 요청 DB 역할 확인(토큰에 역할 없음). 다른 사람 예약은 404 로 숨김. `/admin/*` 는 관리자만.
- QR 은 `/items/{id}` 주소만 담음. 로그인 필요, 상태 변경 없음.
- 알림은 화면 표시만. 문자·이메일·푸시를 보냈다고 표시하지 말 것.

## 기관·회원 규칙
- 역할: `role=admin` 은 서비스 관리자(전체 + 기관·회원 관리). 기관 관리자는 `pgm_org_admin` 으로 지정, 자기 기관 물품·예약·신고·학생 승인만.
- 관리 범위 검사는 서버에서: 목록은 `managed_org_ids` 로 필터, 상태 변경은 services 의 `_ensure_manager`.
- 물품 `access`: `public`(로그인 회원 누구나) / `members`(그 학교의 승인된 학생만). 자격은 `access.eligibility` 한 곳에서 판단. 신청 때와 승인 때 모두 검사.
- 회원가입은 누구나. 학생이면 학교(NEIS 목록) + 학번 → `pending` → 그 학교 관리자가 승인/거절(사유 필수). 학교를 바꾸면 다시 `pending`.
- 관리번호는 기관별 고유 (`uq_pgm_item_org_code`).
- 기관 목록: 학교는 NEIS(`NEIS_API_KEY`) 매일 동기화, 목록에서 빠진 학교는 비활성(삭제 안 함). 주민센터는 CSV 가져오기. 좌표는 카카오(`KAKAO_REST_API_KEY`), 직접 지정한 좌표(`manual`)는 동기화가 덮어쓰지 않음.
- 실시간: 서버리스라 웹소켓 대신 화면별 15~20초 자동 갱신(`useLoad(path, { refreshMs })`, 탭 숨김 시 중지).
- 지도: 기본은 키가 필요 없는 OpenStreetMap(Leaflet, `components/OsmMap.tsx`). `NEXT_PUBLIC_KAKAO_MAP_KEY` 가 있으면 카카오맵, 불러오기 실패 시 OSM 으로 대체.
- 좌표 없이 카카오 REST 키가 없을 때: 공공데이터포털 위치 CSV 를 '좌표만 채우기'로 올려 기존 기관(이름+시도 일치)에 위도·경도 입력 (`orgsync.fill_coordinates`).

## 환경
- 운영(Vercel, 또는 `APP_ENV=production`): `SECRET_KEY` 필수, 쿠키 Secure, 시연 데이터 생성 거부. 최초 서비스 관리자는 `BOOTSTRAP_ADMIN_EMAIL/PASSWORD` 또는 `create-admin`.
- 외부 API 는 테스트에서 `http_get` 주입으로 가짜 응답 사용 (실제 호출 없음).
- 기존 쇼핑몰 `customer` 테이블은 건드리지 않음.
