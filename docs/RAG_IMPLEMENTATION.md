# PokéField RAG 실행·색인 운영 안내

> 제출 문서 보완 기준: 2026-10-23의 기존 실행 기록과 공식 셀프 점검 결과입니다. 기존 검증 이력은 보존합니다. 이번 갱신에서는 브라우저 저장 관련 8개 테스트와 Cloud 읽기 검사만 수행했으며, 유료 API·재색인은 실행하지 않았습니다. 실제 GMS, 로컬 Python, 응답 캐시, 저장 응답 재생, FakeLLM/FakeEmbeddings를 구분합니다. 심화 F2013~F2016은 **미선택**입니다.

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
- runtime: RAG용 `cache.sqlite3`, `documents`, `document_status`, `usage.jsonl`, 색인/수집 보고서입니다. 기존 `collection.sqlite3`는 남아 있을 수 있으나 공개 필드는 읽거나 자동 이관하지 않습니다.
- 프롬프트: `extract_query.txt`, `select_documents.txt`, `generate_answer.txt`, `extract_filters.txt`, `select_candidates.txt`.
- UI 재실행은 새 질문 제출과 구분합니다. 수집 버튼/질문 제출/AI 변화 분석 버튼 등 사용자 동작에서 작업을 수행합니다.
- 상성·기술 등 로컬 근거 생성과 일반 설명 LLM 경로는 다릅니다. 선택형 질문은 해당 pid/세대 색인이 필요하며 로컬 질문은 키 없이 가능합니다.

## 안전한 검증과 배포 전 확인

전체 테스트 명령은 `python -m unittest discover -s tests -v`입니다. 기존 155개와 브라우저 저장 보완 후 163개 회귀는 격리 저장소를 사용했습니다. 최신 상세 범위는 검증 요약을 따릅니다. 원본 SQLite/Chroma에 테스트 이벤트를 기록하지 않습니다. `scripts/verify_live.py`는 실제 API를 사용할 수 있어 별도 호출 예산으로 실행해야 합니다.

소스/문서/.env.example에는 키를 쓰지 않습니다. `.env`, `.local`, 원본 캐시, 가상환경은 제출 대상에서 제외합니다. 정적 파일 공개 설정은 `static/`의 자산에 한정합니다. Wikipedia/포켓몬/이미지 이용 조건은 [출처 문서](SOURCES_AND_LICENSES.md)에 따르고, 권리 미확인을 해결된 것으로 표기하지 않습니다.

## 제출 폴더 경로

이 문서와 [검증 결과](VERIFICATION_SUMMARY.md)는 docs 기준 `evidence/screenshots/`, `evidence/logs/`, `evidence/checklists/`의 상대경로를 사용합니다. PDF는 docs/pdf 기준 `../evidence/`를 사용합니다. 셀프 XLSX의 원래 H열은 감사 이력을 위해 보존하고 [경로 대조표](evidence/path-map.json)를 함께 제공합니다. 실행 환경의 개인 절대경로와 제출용 파일 위치를 혼동하지 않습니다.

신규 Wikipedia 수집은 실제 운영 연락처 확인이 남아 있습니다. 아래 화면을 확보한 것으로 간주하지 않습니다.

[추가 증빙 필요: 실제 운영 연락처가 설정된 격리 환경에서 외부 문서 수집·색인 진행과 완료를 확인한 화면입니다. 실행에는 별도 승인·비용 판단이 필요하며 이번 작업에서는 수행하지 않았습니다.]

## 실제 UI에서 확인된 흐름

조건 검색 결과에서 선택한 포켓몬·세대를 질문 화면에 넘기는 동작은 [기존 Chrome 검사](evidence/logs/browser-results.json)로 확인했습니다. 기술 검색 첫 페이지와 추가 페이지를 포함합니다. 전체/선택별 대화 분리는 [기존 게임·기록 검사](evidence/logs/game-results.json)에 있습니다.

[기존 화면 원본: 기존 특성 검색 결과의 선택→질문 연결 화면입니다. 로컬 답변을 사용했습니다.](evidence/screenshots/ability-chat.png)

[기존 화면 원본: 기존 답변 생성 진행 화면입니다. FakeLLM UI이며 실제 GMS 지연 측정 화면은 아닙니다.](evidence/screenshots/03-progress-FakeLLM-current.png)

## Cloud 배포와 현재 확인 상태

서비스 주소는 [PokéField](https://pokefield.streamlit.app/)입니다. **2026-10-23 실제 Cloud 읽기 검사에서 새 독립 프로필 A·B 모두 `22 / 1025`를 표시했고, 앱 프레임의 `pokefield:` localStorage 키는 없었습니다. 새로고침 후에도 같았습니다.** 로컬 수정본과 다른 표시이므로 사용자별 저장 수정이 배포됐다고 판정하지 않습니다. 배포 브랜치·커밋·Secrets·Cloud Python 버전은 관리 화면 확인이 필요합니다. 운영 기록 보존을 위해 Cloud에서 포획·채팅·색인을 실행하지 않았습니다.

현재 저장소는 `app.py`, `requirements.txt`, `.streamlit/config.toml`, `src/`, `prompts/`, 가공 데이터·이미지·`static/` 및 기존 `chroma_db/` 파일을 사용합니다. `chroma_db/`는 `.gitignore`에 있으나 현재 Git 추적 파일에는 SQLite와 HNSW 파일이 포함됩니다. ignore만으로 추적이 해제되지는 않습니다. 로컬 추적 상태는 원격 배포 완료의 증거가 아닙니다. `.github/` 배포 워크플로와 색인 자동 다운로드·압축 해제 코드는 확인되지 않았습니다.

Cloud는 Linux 환경이므로 Windows 절대경로를 사용하지 않습니다. 배포 시 진입점은 `app.py`, Python은 기존 로컬 검증 환경인 3.11과 맞춰 확인합니다. 새 환경의 실행 예시는 다음과 같으며 이번 작업에서 Linux 설치를 실행한 결과는 아닙니다.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Community Cloud의 App settings → Secrets에 **최상위 TOML 키**로 기존 환경변수 이름을 설정합니다. `Settings.load()`는 `os.getenv`를 읽고 별도의 중첩 `st.secrets` 변환은 하지 않습니다. 필요한 이름은 `LLM_PROVIDER`, 공급자에 따른 `GMS_KEY` 또는 `OPENAI_API_KEY`, `CHAT_MODEL`, `EMBEDDING_MODEL`, `POKEMON_DATA_DIR`, `CHROMA_DIR`, 선택적 `WIKI_CONTACT`입니다. 실제 비밀값·연락처를 문서에 적지 않습니다. 기존 모델·공급자 설정을 그대로 사용하고 변경하지 않습니다.

경로는 `POKEMON_DATA_DIR = "pokemon-data/data/processed"`, `CHROMA_DIR = "chroma_db"`처럼 저장소 루트 기준 상대경로를 사용합니다. `Settings.ROOT`는 `src/settings.py`의 부모 프로젝트 경로입니다. 경로의 대소문자와 이미지 파일 포함 여부를 확인합니다. 실제 Cloud Secrets는 열람하지 않았으며 설정 완료로 표시하지 않습니다. `.streamlit/config.toml`의 정적 제공은 켜져 있고 주소는 현재 `127.0.0.1`입니다. 이 설정을 수정하지 않았으며 Cloud의 실제 실행 옵션 우선순위는 운영 화면에서 확인해야 합니다.

ChromaDB는 `VectorStore`에서 `PersistentClient(CHROMA_DIR)`로 기존 두 컬렉션을 엽니다. 빈 폴더면 컬렉션을 만들지만 자동으로 기존 벡터를 채우지는 않습니다. 같은 공급자·API base URL·임베딩 모델의 signature가 필요합니다. 준비된 색인은 앱을 중지한 일관된 전체 디렉터리(SQLite와 HNSW 파일)를 배포 대상으로 준비하고, Linux·고정 패키지 버전에서 호환성과 컬렉션 수를 확인해야 합니다. 이번에는 운영 색인을 열거나 재생성하지 않았습니다. 재시작 뒤 서버 파일 보존을 개인 기록의 영속성으로 간주하지 않습니다.

[추가 검증 필요: Cloud 관리 화면에서 실제 배포 브랜치·커밋과 Python 버전, 비밀값을 가린 설정명, 메타/문서 컬렉션 로드 상태를 확인합니다. 수정본 배포 후 새 프로필 A·B의 최초 수집 수 0, 각각 포획·새로고침·도감 표시·상호 격리를 확인합니다.]

운영 참고: [공식 배포 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [의존성·Linux 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [Secrets 관리](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)입니다. 실제 배포 설정을 확인했다는 의미는 아닙니다.
