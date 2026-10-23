# PokéField RAG 실행·색인 운영 안내

> 제출 문서 보완 기준: 2026-10-23의 기존 실행 기록과 공식 셀프 점검 결과입니다. 이번 문서 보완에서는 테스트·유료 API·재색인을 실행하지 않았습니다. 실제 GMS, 로컬 Python, 응답 캐시, 저장 응답 재생, FakeLLM/FakeEmbeddings를 구분합니다. 심화 F2013~F2016은 **미선택**입니다.

기준일 2026-10-23. 상세 설계는 [파이프라인 설계서](architecture.md), 현재 판정은 [요구사항](requirements.md), 실제 검증은 [검증 요약](VERIFICATION_SUMMARY.md)을 따릅니다.

## 실행 환경 구분

이 문서의 Windows 명령은 `.venv`, 데이터, 이미지와 색인이 이미 준비된 기존 환경을 기준으로 합니다. 신규 환경의 가상환경 생성·패키지 설치·환경변수 준비는 [README 실행 방법](../README.md#start)을 먼저 따릅니다. 데이터 준비와 색인 생성은 앱 실행과 별도 작업이며, 기존 자료가 있으면 다시 수행하지 않습니다.

## 기존 환경 실행

**아래 명령은 실행 안내이며 이번 문서 보완에서 실행하지 않았습니다.** 소스·.env·운영 DB는 그대로 유지했습니다.

```powershell
cd C:\SSAFY\pennant_race_ai_core_2
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`./start.ps1`도 같은 루트에서 앱을 시작합니다. 현재 실행 모델은 `.env`/환경변수 우선이며 확인값은 GMS `gpt-6.1-sol`입니다. `.env.example`의 기본값과 같다고 가정하지 않습니다. 기존 설정은 덮어쓰지 않습니다.

## 색인 준비 (필요할 때만)

[기존 화면 원본: 기존 데이터로 표시한 도감 화면입니다. 신규 색인·신규 수집 성공의 증거는 아닙니다.](evidence/screenshots/02-dex-current.png)

기존 `pokemon-data/data/processed`, 이미지와 ChromaDB가 있으면 재수집하지 않습니다. 메타데이터가 없거나 바뀐 경우:

```powershell
# 소량 검증
.\.venv\Scripts\python.exe scripts\index_pokemon.py --pilot
# 전체 필요 시
.\.venv\Scripts\python.exe scripts\index_pokemon.py
# 운영자가 실제 WIKI_CONTACT 및 모델/임베딩 키를 준비한 뒤 선택적 문서 수집
.\.venv\Scripts\python.exe scripts\index_documents.py --species 25 94
```

메타데이터 upsert는 변경 없는 ID/해시를 생략합니다. 외부 문서 재실행은 수집 캐시를 재사용하고 `--refresh`는 재평가를 요청합니다. 기본 외부 수집은 PILOT 10종입니다. 연락처 미설정 시 새 Wikipedia 요청은 보내지 않으며 기존 HTTP/문서 캐시는 이용합니다. 실제 운영자 연락처를 문서 예시로 대체하지 않습니다.

모델/임베딩 공급자·모델을 바꿀 때 기존 벡터 signature를 무시하지 않습니다. 필요하면 별도 CHROMA_DIR에 검증 색인을 만듭니다. 색인/수집은 LLM·임베딩 비용이 발생할 수 있으며 자동 검증에 넣지 않습니다.

## 경로와 동작 구분

- 데이터: `pokemon-data/data/processed`; 원본: `pokemon-data/data/raw`; 이미지: `pokemon-data/data/images`.
- Vector DB: CHROMA_DIR(기본 `chroma_db`). runtime은 그 부모의 `.local/rag`.
- runtime: `cache.sqlite3`, `collection.sqlite3`, `documents`, `document_status`, `usage.jsonl`, 색인/수집 보고서.
- 프롬프트: `extract_query.txt`, `select_documents.txt`, `generate_answer.txt`, `extract_filters.txt`, `select_candidates.txt`.
- UI 재실행은 새 질문 제출과 구분합니다. 수집 버튼/질문 제출/AI 변화 분석 버튼 등 사용자 동작에서 작업을 수행합니다.
- 상성·기술 등 로컬 근거 생성과 일반 설명 LLM 경로는 다릅니다. 선택형 질문은 해당 pid/세대 색인이 필요하며 로컬 질문은 키 없이 가능합니다.

## 안전한 검증과 배포 전 확인

전체 테스트 명령은 `python -m unittest discover -s tests -v`입니다. 실제 완료된 155개 검증은 Settings의 기본 저장 경로를 임시 위치로 대체하고 유료 모델/임베딩 호출을 차단한 실행입니다. 원본 SQLite/Chroma에 테스트 이벤트를 기록하지 않습니다. `scripts/verify_live.py`는 실제 API를 사용할 수 있어 별도 호출 예산으로 실행해야 합니다.

소스/문서/.env.example에는 키를 쓰지 않습니다. `.env`, `.local`, 원본 캐시, 가상환경은 제출 대상에서 제외합니다. 정적 파일 공개 설정은 `static/`의 자산에 한정합니다. Wikipedia/포켓몬/이미지 이용 조건은 [출처 문서](SOURCES_AND_LICENSES.md)에 따르고, 권리 미확인을 해결된 것으로 표기하지 않습니다.

## 제출 폴더 경로

이 문서와 [검증 결과](VERIFICATION_SUMMARY.md)는 docs 기준 `evidence/screenshots/`, `evidence/logs/`, `evidence/checklists/`의 상대경로를 사용합니다. PDF는 docs/pdf 기준 `../evidence/`를 사용합니다. 셀프 XLSX의 원래 H열은 감사 이력을 위해 보존하고 [경로 대조표](evidence/path-map.json)를 함께 제공합니다. 실행 환경의 개인 절대경로와 제출용 파일 위치를 혼동하지 않습니다.

신규 Wikipedia 수집은 실제 운영 연락처 확인이 남아 있습니다. 아래 화면을 확보한 것으로 간주하지 않습니다.

[추가 증빙 필요: 실제 운영 연락처가 설정된 격리 환경에서 외부 문서 수집·색인 진행과 완료를 확인한 화면입니다. 실행에는 별도 승인·비용 판단이 필요하며 이번 작업에서는 수행하지 않았습니다.]

## 실제 UI에서 확인된 흐름

조건 검색 결과에서 선택한 포켓몬·세대를 질문 화면에 넘기는 동작은 [기존 Chrome 검사](evidence/logs/browser-results.json)로 확인했습니다. 기술 검색 첫 페이지와 추가 페이지를 포함합니다. 전체/선택별 대화 분리는 [기존 게임·기록 검사](evidence/logs/game-results.json)에 있습니다.

[기존 화면 원본: 기존 특성 검색 결과의 선택→질문 연결 화면입니다. 로컬 답변을 사용했습니다.](evidence/screenshots/ability-chat.png)

[기존 화면 원본: 기존 답변 생성 진행 화면입니다. FakeLLM UI이며 실제 GMS 지연 측정 화면은 아닙니다.](evidence/screenshots/03-progress-FakeLLM-current.png)
