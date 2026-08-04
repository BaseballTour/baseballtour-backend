# Week 2 담당자 B 진행 현황

## 완료

- TourAPI 위치 기반 조회, 상세·소개·이미지 Adapter와 Place 변환
- 카테고리 매핑, 중복 제거, 이미지·영업시간 fallback
- 잘못된 좌표, 빈 응답, timeout, 업무 오류 처리
- 프로세스 메모리 TTL 캐시(기본 5분)
- 구장 9개, 개발 경기 5개, Firestore 초기 JSON
- ODsay 우선·직선거리 fallback 방식 결정
- 이동시간 Matrix와 동일 node ID 중복 제거
- 도착·출발·숙소·경기장 Anchor 기반 greedy 일정 생성 v0.1
- 체류시간·영업시간·경기 40분 전·출발 1시간 전 조건
- 필수 장소와 가까운 장소 우선, 방문 불가 장소 제외 사유
- 가짜 Matrix 일정 생성 테스트와 요청·응답 모델 계약

## 부분 완료

- KBO 경기 확보: 개발 Seed 완료, 실제 확정 일정 수집원 미정
- ODsay Server Key 실호출 및 실제 대중교통 Matrix 일정 생성 검증 완료
- TourAPI 상세 Adapter는 다양한 contentType의 추가 실데이터 검증 필요
- 캐시: 단일 프로세스 방식, 운영 다중 인스턴스에서는 Redis 검토
- 알고리즘: 규칙 기반 v0.1, 실제 교통시간과 다양한 여행 조건 검증 필요

## 담당자 A 선행 또는 공동 연결 필요

- Trip·Game·Stadium을 `TripInput`으로 조합하는 Application Service
- 일정 생성 API의 Trip 상태 전환과 UID 소유권 검증
- ItineraryPlanRepository 및 Firestore transaction/batch 저장
- 새 ACTIVE Plan 생성, 이전 Plan ARCHIVED 처리
- Swagger 최종 예시와 프론트엔드 검토

## 외부 작업 필요

- Kakao 애플리케이션 등록과 Local API Key 발급
- 실제 KBO 확정 경기 데이터의 공식 제공처·갱신 주기 결정
