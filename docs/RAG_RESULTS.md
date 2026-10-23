# PokéField 과거 RAG 검증 기록

> 이 문서는 당시 실행 결과를 보존한 과거 기록이다. 최신 판정은 [현재 검증 요약](VERIFICATION_SUMMARY.md)과 [요구사항 현황](requirements.md)을 따른다. 아래 모델·테스트 수·미구현 설명은 현재 설정을 뜻하지 않는다.

# Pokémon Lab 구현 및 검증 결과

작업 경로: `C:\SSAFY\pennant_race_ai_core_2`

2026-10-21 실제 GMS API로 실행·검증했습니다. 기존 데이터 재수집은 수행하지 않았습니다.

## 구현한 기능

- LangGraph retrieve → generate 챗봇과 실제 인용 근거 표시. 선택 포켓몬 메타데이터 필수 포함, species_id로 외부 문서 필터, 세대 비교와 진화 데이터 근거 제공.
- 문서별 원문 URL·출처 유형·본문·이용 조건을 표시. 인용 번호 범위와 알려진 다른 종 이름 혼입을 검사.
- 자연어 조건 추출 → Python 정확 필터 → AI 후보 선별 → 후보 ID 재검증 → 이미지 카드. 선택형 필터와 기존 도감·세대 비교·이미지·한글 특성을 유지.

## 색인 및 수집 범위

| 컬렉션 | 레코드/청크 수 |
|---|---:|
| pokemon_meta | 6,260 |
| pokemon_docs | 64 |

메타데이터는 전체 1,025종·1,351형태를 포함합니다. 외부 문서는 대표 10종, 15개 문서(종 연결별 저장 수)를 수집했습니다. 나머지 1,015종은 외부 문서 미수집 상태입니다. 전체 외부 문서 수집 완료로 간주하지 않습니다.

| 종 ID | 이름 | 문서 수 | 자체 문서 확인 |
|---|---|---:|---|
| 25 | 피카츄 | 1 | True |
| 35 | 삐삐 | 1 | True |
| 94 | 팬텀 | 2 | True |
| 133 | 이브이 | 1 | True |
| 1 | 이상해씨 | 2 | True |
| 4 | 파이리 | 2 | True |
| 7 | 꼬부기 | 1 | True |
| 39 | 푸린 | 2 | True |
| 52 | 나옹 | 2 | True |
| 150 | 뮤츠 | 1 | True |

### 실제 외부 문서 출처

- [피카츄](https://ko.wikipedia.org/wiki/%ED%94%BC%EC%B9%B4%EC%B8%84) · Creative Commons Attribution-Share Alike 4.0
- [삐삐](https://ko.wikipedia.org/wiki/%EC%82%90%EC%82%90) · Creative Commons Attribution-Share Alike 4.0
- [팬텀 (포켓몬)](https://ko.wikipedia.org/wiki/%ED%8C%AC%ED%85%80_(%ED%8F%AC%EC%BC%93%EB%AA%AC)) · Creative Commons Attribution-Share Alike 4.0
- [팬텀](https://ko.wikipedia.org/wiki/%ED%8C%AC%ED%85%80) · Creative Commons Attribution-Share Alike 4.0
- [이브이](https://ko.wikipedia.org/wiki/%EC%9D%B4%EB%B8%8C%EC%9D%B4) · Creative Commons Attribution-Share Alike 4.0
- [이상해씨](https://ko.wikipedia.org/wiki/%EC%9D%B4%EC%83%81%ED%95%B4%EC%94%A8) · Creative Commons Attribution-Share Alike 4.0
- [이상해풀](https://ko.wikipedia.org/wiki/%EC%9D%B4%EC%83%81%ED%95%B4%ED%92%80) · Creative Commons Attribution-Share Alike 4.0
- [파이리](https://ko.wikipedia.org/wiki/%ED%8C%8C%EC%9D%B4%EB%A6%AC) · Creative Commons Attribution-Share Alike 4.0
- [리자드](https://ko.wikipedia.org/wiki/%EB%A6%AC%EC%9E%90%EB%93%9C) · Creative Commons Attribution-Share Alike 4.0
- [꼬부기](https://ko.wikipedia.org/wiki/%EA%BC%AC%EB%B6%80%EA%B8%B0) · Creative Commons Attribution-Share Alike 4.0
- [푸린 (포켓몬)](https://ko.wikipedia.org/wiki/%ED%91%B8%EB%A6%B0_(%ED%8F%AC%EC%BC%93%EB%AA%AC)) · Creative Commons Attribution-Share Alike 4.0
- [푸린](https://ko.wikipedia.org/wiki/%ED%91%B8%EB%A6%B0) · Creative Commons Attribution-Share Alike 4.0
- [나옹](https://ko.wikipedia.org/wiki/%EB%82%98%EC%98%B9) · Creative Commons Attribution-Share Alike 4.0
- [나옹 (포켓몬)](https://ko.wikipedia.org/wiki/%EB%82%98%EC%98%B9_(%ED%8F%AC%EC%BC%93%EB%AA%AC)) · Creative Commons Attribution-Share Alike 4.0
- [뮤츠](https://ko.wikipedia.org/wiki/%EB%AE%A4%EC%B8%A0) · Creative Commons Attribution-Share Alike 4.0

## 검증

- 회귀 테스트 23개 통과: 실제 JSONL/Chroma, 모의 LLM/임베딩을 사용하는 논리·무결성 검사.
- 실제 GMS 챗봇 질문 5개 통과: 피카츄 특성, 팬텀 6·7세대 특성, 이브이 진화, 삐삐 타입 변경, 문서에 없는 가상 특성 거절.
- 실제 GMS 자연어 검색 예제 4개 통과: 전기/공격/스피드, 9세대 공격 120 이상, 물/높은 방어, 불꽃/스피드 100 이상.
- Streamlit AppTest: 실제 채팅·근거 펼침, 포켓몬별 대화 분리, 자연어 카드·이동, 기존 도감/세대 전환, 빈 검색, 키/색인 누락 안내 모두 통과.
- 메타데이터 재색인: changed=0, skipped=6260. 문서 재색인: changed_chunks=0, 문서 청크 64 유지.
- 보호 대상 7,247개 파일 해시 비교: 기존 .env·데이터·이미지 변경 0개.

## API 및 토큰 사용

기록된 이벤트: {'embedding': 217, 'wiki_http': 58, 'llm': 51, 'schema_error': 1}
기록된 토큰 합계: {'input_tokens': 1337804, 'output_tokens': 6088, 'total_tokens': 1343892}
이 수치는 구현 중 재검증 호출까지 포함합니다. 실제 과금액은 추정하지 않았습니다. 키·프롬프트·본문은 사용량 로그에 기록하지 않습니다. 기존 .env는 Git에 추적되지 않는 것을 확인했습니다.

## 실행

```powershell
cd C:\SSAFY\pennant_race_ai_core_2
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

로컬 서버를 http://127.0.0.1:8502 에서 실행했습니다. 8501의 기존 프로세스는 유지했습니다. 서버 시작 로그와 AppTest 실행은 확인했으나 별도 HTTP health 검사는 권한이 허용되지 않아 미검증입니다. 브라우저 화면의 픽셀 단위 시각 검사는 수행하지 않았습니다.

## 수정·추가 파일과 역할

- app.py: 기존 네 탭 유지, 검색 카드 선택과 RAG 화면 연결.
- src/catalog.py, src/settings.py: 기존 로더 확장, 한글 특성·진화 근거·서비스/청킹/임계값 설정.
- src/rag.py: 실제 LangGraph, 근거 병합/번호 부여/답변 검증.
- src/llm.py, src/storage.py: API 클라이언트, 구조 검증, 캐시와 사용량 로그.
- src/vector_store.py: 두 Chroma 컬렉션, 고정 ID/content hash upsert.
- src/document_service.py: 위키 API 수집/선별/청킹/색인과 이용 조건 기록.
- src/natural_search.py, src/ui_rag.py: 자연어 조건·후보 검증, 채팅·출처·검색 카드 UI.
- scripts/index_pokemon.py, scripts/index_documents.py, scripts/verify_live.py: 실제 색인·수집·검증 명령.
- prompts/extract_query.txt, select_documents.txt, generate_answer.txt, extract_filters.txt, select_candidates.txt: 기능별 프롬프트.
- tests/test_services.py: 23개 회귀 테스트.
- .env.example, .gitignore, requirements.txt, README.md, docs/: 설정 예제·의존성·실행/설계/검증 문서.

## 남은 사항

- 외부 문서는 10종만 확보했습니다. 추가 종은 index_documents.py --species로 단계 확장하세요.
- WIKI_CONTACT가 비어 있습니다. 실제 연락처를 설정하면 서비스 운영자가 요청자를 식별할 수 있습니다. 현재 앱 식별자와 6.2초 간격으로 호출합니다.
- 자연어 필터는 타입 AND, 최소값(이상), 높은/빠른 조건, 한 개 세대를 지원합니다. 이하/제외/OR는 지원하지 않으며 추정 검색 대신 안내합니다.
- 원본 진화 조건은 API 기준입니다. 버전 그룹별 조건을 다른 게임에 일반화하지 않습니다. 실제 게임 등장 여부도 미확인입니다.
- LLM 문장의 의미적 정확성까지 코드로 완전히 보장할 수 없습니다. 숫자·타입·ID·인용을 검증하고 실제 근거를 함께 제공합니다.
- 자동 답변 테스트는 키워드·인용/데이터 검사이며 독립적인 게임 공략 검수는 아닙니다. 이전 검증 중 발견된 구조 제한·인용 중복·잘못된 이름 표기 문제를 수정하고 최종 테스트를 다시 통과했습니다.
