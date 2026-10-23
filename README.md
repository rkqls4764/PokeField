# PokéField

포켓몬을 만나고 포획하는 전체 화면 필드와, 구조화 데이터·외부 문서에 근거해 질문에 답하는 오박사 RAG를 결합한 Streamlit 프로젝트다. 현재 프로젝트 경로는 `C:\SSAFY\pennant_race_ai_core_2`이다.

문서 기준일: **2026-10-23**. 필수 기능 F2001~F2012는 재검증 범위에서 12개 통과했다. 최신 회귀 테스트는 155개 통과다. 다만 실제 세대 비교 답변의 모순된 확인 불가 문구, 운영 연락처 미설정, 이미지 권리 미확인은 남아 있다. “모든 품질·권리·운영 검증 완료”를 뜻하지 않는다.

## 문서 안내

- [요구사항 정의 및 충족 현황](docs/requirements.md): F2001~F2016, NF2001~NF2007, 미실행 범위
- [RAG 파이프라인 설계서](docs/architecture.md): 컬렉션·프롬프트·LangGraph·검색/병합·설정 비교
- [실행·색인 운영 안내](docs/RAG_IMPLEMENTATION.md)
- [현재 검증 결과](docs/VERIFICATION_SUMMARY.md) 및 [검증 수치](docs/verification/current-results.json)
- [출처 및 이용 조건](docs/SOURCES_AND_LICENSES.md), [이미지별 출처 상태](docs/asset_provenance.json), [Wikipedia 문서별 이용 조건](docs/wikipedia_sources.json)
- [비기능 요구사항 보완 결과](docs/NF_VERIFICATION.md)

`docs/RAG_RESULTS.md`, `docs/RAG_VERIFICATION.json`, `docs/UNIT_TEST_RESULTS.json`은 과거 실행 기록이다. 최신 판정은 위 문서를 따른다.

## 기술 스택과 실제 설정

Python 3.11, Streamlit **1.62.0** Component v2, JavaScript/HTML/CSS, LangGraph **1.2.10**, LangChain OpenAI, ChromaDB **1.5.9**, Pydantic, SQLite를 사용한다. 패키지 고정 버전은 [requirements.txt](requirements.txt)에 있다.

현재 확인된 실행 설정은 GMS / `gpt-6.1-sol`, 임베딩 `text-embedding-3-small`, Top-k=5, 청크 1000자/중복 200자다. 환경변수 `CHAT_MODEL`이 기본값보다 우선한다. `src/settings.py`·`.env.example`의 기본 모델은 `gpt-5.4-nano`이므로 새 설치가 현재 운영 설정과 자동으로 같아지는 것은 아니다. 이번 문서 작업은 모델이나 실제 `.env`를 바꾸지 않았다.

## 실행

Windows PowerShell, 기존 프로젝트 기준:

```powershell
cd C:\SSAFY\pennant_race_ai_core_2
# 최초 설치 때만 실행. 기존 .venv와 .env는 덮어쓰지 않는다.
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

기본 주소는 http://localhost:8501 이다. 기존 가상환경에서는 `./start.ps1`로도 실행한다. 새 장치에서의 전체 신규 설치는 이번 문서 작업에서 실행하지 않았다. `check_setup.py`는 데이터/메타데이터 텍스트 확인이며 유료 API 연결 시험은 아니다.

`.env` 또는 환경변수에 사용할 `LLM_PROVIDER`와 해당 `GMS_KEY`/`OPENAI_API_KEY`를 설정한다. 키를 문서·소스에 쓰지 않는다. `POKEMON_DATA_DIR`, `CHROMA_DIR`의 상대 경로는 프로젝트 루트 기준이다. Wikipedia 새 수집에는 실제 운영자가 제공한 `WIKI_CONTACT`가 필요하다. 현재 공란이며 새 요청은 설정 안내 후 중단된다. 기존 캐시는 계속 사용한다.

도감·필드·로컬 상성·기술 검색은 유료 LLM 없이 동작한다. 선택형 RAG는 해당 포켓몬/세대의 메타데이터 색인이 필요하며 설명 생성에는 키가 필요하다. 일반 자연어 조건 검색은 입력에 따라 추출·후보 선별 API가 발생할 수 있다.

## 기능과 사용 흐름

- **필드:** 9개 지역에서 타입 규칙에 맞는 포켓몬 3~10마리가 등장한다. 몬스터볼 드래그/터치 투척 또는 이동 중인 포켓몬에 키보드 초점 후 Enter로 포획한다. SQLite 저장 성공 후 팝업·수집 수가 반영된다.
- **도감:** 우측 하단 로토무로 열고 이름/번호·타입·세대·수집 필터와 상세 정보를 본다. 미수집 포켓몬도 조회한다. 포획 팝업의 도감 버튼은 해당 포켓몬을 선택한다. 상세 하단 질문 버튼은 항목 문맥을 전달한다.
- **오박사:** 기본 전체 포켓몬 질문과 선택형 질문을 지원한다. 전체 기록과 `pokemon_id:generation`별 기록은 분리한다. 실제 인용된 근거 번호·제목·링크만 표시한다. 포켓몬 이름/조건을 인식하지 못했다고 임의로 대상을 선택하지 않는다.
- **자연어 탐색:** 타입·특성·숨겨진 특성·세대·최소 능력치 조건을 실제 데이터로 필터링한다. 결과에서 포켓몬을 선택하면 질문 탭으로 전환한다. 기술 검색도 첫/추가 페이지에서 질문 연결을 지원한다. 이하/제외/OR 등 지원하지 않는 조건은 안내한다.
- **세대 비교·진화·상성·기술:** 수치와 변경 여부·상성 배율·습득 조건은 Python/JSON으로 처리한다. 진화 경로는 순환 방지 탐색을 사용한다. 변경 이유는 외부 문서에 명시된 경우만 설명한다.
- **추천 포켓몬 추적:** 답변에서 인식한 이름을 실제 인용 근거와 대조한 대상만 잡으러 가기 버튼으로 연결한다. 출현 타입이 맞는 지역 이동·목표 강조·취소를 지원한다. 이번 최신 서비스 테스트가 추천 추적의 모든 경계를 실제 브라우저로 다시 실행한 것은 아니다.

## 데이터 준비와 색인

기존 데이터가 있으면 재다운로드·전체 재임베딩하지 않는다. 현재 검증 스냅샷은 1,025종·1,351형태·6,260세대 레코드, Chroma `pokemon_meta` 6,260건·`pokemon_docs` 64청크다. 외부 문서는 15개 문서-종 연결/10종 범위이며 전체 종의 외부 설명이 확보된 것은 아니다.

1. `pokemon-data/data/processed`의 기존 JSONL과 `pokemon-data/data/images`를 준비한다. 원본은 `pokemon-data/data/raw`, 데이터 준비 명령은 [데이터 문서](pokemon-data/README.md)에 있다. 새 수집이 꼭 필요하면 별도 `--root`에서 검증한다.
2. 색인이 없거나 내용이 바뀐 경우만 다음 명령을 사용한다. 비용이 발생할 수 있다.

```powershell
# 소량 메타데이터 먼저, 전체는 --pilot을 생략
.\.venv\Scripts\python.exe scripts\index_pokemon.py --pilot
# 필요할 때 선택한 종의 외부 문서 수집·색인
.\.venv\Scripts\python.exe scripts\index_documents.py --species 25 94
```

메타데이터의 ID·내용 해시가 같으면 건너뛴다. 외부 문서는 캐시된 수집 결과를 재사용하며 `--refresh`는 재평가를 요청한다. 기본 외부 수집 범위는 스크립트의 10종 PILOT이다. 새 수집에는 연락처와 모델/임베딩 키가 필요하며 검색어 추출·선별·임베딩 비용이 발생한다.

타입 상성/기술 검색용 `type_chart.json`, `move_catalog.json`, `pokemon_learnsets.jsonl`과 manifest는 이미 준비되어 있다. `scripts/build_battle_data.py`는 기존 pokemon 원본 캐시와 PokéAPI CSV로 만드는 별도 준비 도구이며 첫 실행 시 CSV를 요청할 수 있다. 웹 실행 시 자동 재생성하지 않는다.

## 저장·검증·제한

`CHROMA_DIR`는 Vector DB, 그 부모의 `.local/rag`는 API/임베딩/답변 캐시·문서·사용량·`collection.sqlite3`이다. 수집 기록은 이 설치의 브라우저 간 공유이며 로그인 사용자별 저장소가 아니다. 채팅 기록은 Streamlit 세션 상태이며 계정 기반 장기 저장을 제공하지 않는다. `server.enableStaticServing=true` 설정을 유지한다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

최신 검증은 운영 DB를 복사하거나 임시 저장소로 대체하고 실제 유료 API를 차단한 155개 테스트다. 위 일반 명령은 테스트 자체가 사용하는 임시 저장소 외에도 앱 초기화 경로를 실행할 수 있으므로 제출 전 검증은 별도 `CHROMA_DIR` 환경에서 수행한다. 실제 API를 호출하는 `scripts/verify_live.py`는 일반 테스트와 별개이며 비용 한도를 자체 보장한다고 안내하지 않는다.

실제 유료 답변 테스트는 2026-10-23 GMS 4회(총 14,665토큰)였으며 특성·진화·비교·근거 없는 질문을 확인했다. 약점·기술은 로컬, 반복 비교는 응답 캐시다. 브라우저 검증은 실제 JS/SQLite와 로컬 답변을 사용했고 FakeLLM이 장착된 격리 앱이었다. 실제 API를 연결한 전체 UI 흐름을 모두 완료했다고 표시하지 않는다.

세대 비교 답변에서 변경 사실 뒤에 일반적인 “확인하기 어렵다” 문장이 붙는 품질 문제가 남아 있다. 모바일은 Chrome 화면 크기 모의이며 실기기 검증은 미실행이다. 이미지 권리·Wikipedia 운영자 연락처·운영 부하 목표는 사용자 확인이 필요하다. 공용 배포/상업 사용 권리가 확보됐다고 보장하지 않는다.
