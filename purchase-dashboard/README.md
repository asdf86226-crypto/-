# 구매요청 대시보드

개발 · 자재 · 생산 · 품질 팀의 구매요청을 한 곳에서 접수하고 정리하는 단일 파일 대시보드입니다.
별도 설치나 서버 없이 `index.html` 을 브라우저로 열면 바로 동작합니다.

## 실행

```bash
# 파일을 더블클릭하거나, 로컬 서버로 열기
python -m http.server -d purchase-dashboard 8080
# → http://localhost:8080
```

## 주요 기능

- **팀 공유(클라우드)**: Supabase 무료 DB에 연결하면 팀원 모두가 같은 링크에서 서로의 요청을 실시간(약 7초 주기 동기화)으로 확인. 미연결 시 자동으로 로컬 모드로 동작
- **직접 입력**: 요청팀, 품목코드, 품명, 수량, 입고요청일, 기타사항(+요청자)을 폼으로 입력
- **엑셀 붙여넣기**: 엑셀에서 표를 복사해 붙여넣으면 자동으로 여러 건을 일괄 등록
  - 인식 열 순서: `품목코드 · 품명 · 수량 · 입고요청일 · 기타사항`
  - 맨 윗줄 헤더는 자동 감지하여 제외, 요청팀은 붙여넣기 화면에서 선택
  - 다양한 날짜 형식(`2026-08-25`, `2026.08.25`, `8/25/2026` 등) 자동 정규화
- **팀별 필터 · 검색 · 정렬**: 상단 탭으로 팀 필터, 열 머리글 클릭 정렬, 품목코드/품명 검색
- **상태 관리**: 접수 → 진행 → 완료 순환(행의 ↻ 버튼), 입고요청일 기한 초과/임박 자동 표시
- **요약 집계**: 총 요청 · 진행 중 · 지연 · 완료 건수 상단 표시
- **CSV 내보내기**: 현재 필터된 목록을 CSV(UTF-8)로 저장
- **자동 저장**: 브라우저 localStorage에 저장되어 새로고침해도 유지
- **라이트/다크 테마** 지원

## 팀 공유 설정 (Supabase)

우측 상단 **`로컬 저장`** 버튼(또는 상단 배너의 `공유 연결 설정`)을 눌러 설정합니다.

1. [supabase.com](https://supabase.com) 무료 가입 → 새 프로젝트 생성
2. 왼쪽 **SQL Editor** 에서 아래 SQL 실행 (테이블 1개 생성)
3. **Project Settings → API** 에서 **Project URL** 과 **anon public** 키 복사
4. 대시보드 설정 모달에 붙여넣고 **연결 테스트 → 저장하고 연결**

```sql
create table if not exists purchase_requests (
  id uuid primary key default gen_random_uuid(),
  team text not null,
  code text, item_name text, qty text,
  due_date date, note text, requester text,
  status text default '접수',
  created_at timestamptz default now()
);
alter table purchase_requests enable row level security;
create policy "team access" on purchase_requests
  for all using (true) with check (true);
```

연결 정보(URL·키)는 각 사용자 브라우저의 localStorage에만 저장되며, HTML 안에는 포함되지 않습니다.
따라서 `index.html` 을 GitHub Pages/Netlify 등 **공용 주소**에 올린 뒤, 팀원 각자가 한 번씩 위 설정을
입력하면 같은 데이터를 공유하게 됩니다.

## 데이터 저장 위치

- **로컬 모드(기본)**: 브라우저 localStorage(키 `purchase_requests_v1`) — 내 브라우저에만 저장
- **클라우드 모드**: Supabase 데이터베이스 — 팀원 전체 공유

> ⚠️ 위 RLS 정책은 anon 키를 아는 누구나 읽고 쓸 수 있는 **사내용 간이 설정**입니다.
> 외부 공개 환경이라면 로그인(Supabase Auth) 기반으로 정책을 강화하세요.

## 다음 단계 아이디어

- 로그인/권한(팀별 수정 제한), Supabase Auth 연동
- 실시간 반영(현재 폴링 → Supabase Realtime 구독)
- `.xlsx` 파일 업로드(현재는 복사-붙여넣기 방식)
- 승인 워크플로우(요청 → 팀장 승인 → 구매 발주)
- 발주/입고 연계 및 알림
