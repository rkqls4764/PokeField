# PokéField RAG 실행·색인 운영 안내

기준일 2026-10-23. 상세 설계는 [파이프라인 설계서](architecture.md), 현재 판정은 [요구사항](requirements.md), 실제 검증은 [검증 요약](VERIFICATION_SUMMARY.md)을 따른다.

## 기존 환경 실행

```powershell
cd C:\SSAFY\pennant_race_ai_core_2
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`./start.ps1`도 같은 루트에서 앱을 시작한다. 현재 실행 모델은 `.env`/환경변수 우선이며 확인값은 GMS `gpt-6.1-sol`이다. `.env.example`의 기본값과 같다고 가정하지 않는다. 기존 설정은 덮어쓰지 않는다.

## 색인 준비 (필요할 때만)

기존 `pokemon-data/data/processed`, 이미지와 ChromaDB가 있으면 재수집하지 않는다. 메타데이터가 없거나 바뀐 경우:

```powershell
# 소량 검증
.\.venv\Scripts\python.exe scripts\index_pokemon.py --pilot
# 전체 필요 시
.\.venv\Scripts\python.exe scripts\index_pokemon.py
# 운영자가 실제 WIKI_CONTACT 및 모델/임베딩 키를 준비한 뒤 선택적 문서 수집
.\.venv\Scripts\python.exe scripts\index_documents.py --species 25 94
```

메타데이터 upsert는 변경 없는 ID/해시를 생략한다. 외부 문서 재실행은 수집 캐시를 재사용하고 `--refresh`는 재평가를 요청한다. 기본 외부 수집은 PILOT 10종이다. 연락처 미설정 시 새 Wikipedia 요청은 보내지 않으며 기존 HTTP/문서 캐시는 이용한다. 실제 운영자 연락처를 문서 예시로 대체하지 않는다.

모델/임베딩 공급자·모델을 바꿀 때 기존 벡터 signature를 무시하지 않는다. 필요하면 별도 CHROMA_DIR에 검증 색인을 만든다. 색인/수집은 LLM·임베딩 비용이 발생할 수 있으며 자동 검증에 넣지 않는다.

## 경로와 동작 구분

- 데이터: `pokemon-data/data/processed`; 원본: `pokemon-data/data/raw`; 이미지: `pokemon-data/data/images`.
- Vector DB: CHROMA_DIR(기본 `chroma_db`). runtime은 그 부모의 `.local/rag`.
- runtime: `cache.sqlite3`, `collection.sqlite3`, `documents`, `document_status`, `usage.jsonl`, 색인/수집 보고서.
- 프롬프트: `extract_query.txt`, `select_documents.txt`, `generate_answer.txt`, `extract_filters.txt`, `select_candidates.txt`.
- UI 재실행은 새 질문 제출과 구분한다. 수집 버튼/질문 제출/AI 변화 분석 버튼 등 사용자 동작에서 작업을 수행한다.
- 상성·기술 등 로컬 근거 생성과 일반 설명 LLM 경로는 다르다. 선택형 질문은 해당 pid/세대 색인이 필요하며 로컬 질문은 키 없이 가능하다.

## 안전한 검증과 배포 전 확인

전체 테스트 명령은 `python -m unittest discover -s tests -v`이다. 실제 완료된 155개 검증은 Settings의 기본 저장 경로를 임시 위치로 대체하고 유료 모델/임베딩 호출을 차단한 실행이다. 원본 SQLite/Chroma에 테스트 이벤트를 기록하지 않는다. `scripts/verify_live.py`는 실제 API를 사용할 수 있어 별도 호출 예산으로 실행해야 한다.

소스/문서/.env.example에는 키를 쓰지 않는다. `.env`, `.local`, 원본 캐시, 가상환경은 제출 대상에서 제외한다. 정적 파일 공개 설정은 `static/`의 자산에 한정한다. Wikipedia/포켓몬/이미지 이용 조건은 [출처 문서](SOURCES_AND_LICENSES.md)에 따르고, 권리 미확인을 해결된 것으로 표기하지 않는다.
