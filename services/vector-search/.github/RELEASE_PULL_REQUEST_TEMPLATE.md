## 📌 개요 (Overview)

- 원본 PR: #<번호> (`<source-branch>` → develop, merged)
- develop에서 검증 완료된 <기능명>을(를) main에 반영합니다.
- main 기준 diff: **N 커밋**

## 📝 변경 사항 (Changes)

- [ ]
- [ ]

## 📸 스크린샷 / 로그 / 응답 예시 (Optional)
<details>
<summary>펼쳐보기</summary>

<!-- dev 환경 검증 로그, trace id, 응답 예시 등 -->

</details>

## 🧪 테스트 계획 및 결과 (Test Plan)

- [x] 단위 테스트 수행 완료 (develop 기준)
- [x] 로컬(`uvicorn`) 환경 정상 작동 확인
- [x] dev 환경 통합 검증 완료
- [ ] **머지 후 prod 반영 체크리스트**:
  - [ ] Jenkins main 파이프라인으로 prod 이미지 빌드/푸시 성공
  - [ ] prod 컨테이너 기동 및 `/health` 정상
  - [ ] prod 스모크 테스트

## 🧐 리뷰 요청 사항 (Request for Review)

- 이 PR은 **기능 추가가 아닌 develop → main 머지**입니다. 코드는 원본 PR #<번호>에서 이미 리뷰/검증된 내용이며, 본 PR에서는 prod 반영 적정성 중심으로 봐주세요.
-

## ☑️ 체크리스트 (Checklist)

- [ ] PR 제목은 `[RELEASE] 기능명 (→ main)` 규칙을 따랐나요?
- [ ] 본문에 에픽/스토리/내부 작업 메모 등은 포함하지 않았나요?
- [ ] 브랜치는 develop 기준 검증 완료 상태인가요?
- [ ] base 브랜치가 `main`으로 설정되어 있나요?
