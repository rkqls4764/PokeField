# 🎮 PokéField

**PokéField**는 포켓몬을 직접 만나고 수집할 수 있는 웹 애플리케이션입니다.

포켓몬이 돌아다니는 필드에서 몬스터볼로 포켓몬을 포획하고, 수집한 포켓몬의 정보를 도감에서 확인할 수 있는 서비스입니다. 또한 RAG(Retrieval-Augmented Generation) 기술을 활용한 오박사 챗봇을 통해 포켓몬에 대한 다양한 질문을 할 수 있는 프로젝트입니다.

단순히 포켓몬 정보를 조회하는 데 그치지 않고, 검색한 포켓몬을 필드에서 직접 찾아 포획하는 경험까지 연결한 것이 특징입니다.

## 🧭 목차

| | 바로가기 |
|:--:|---|
| 🛠️ | [기술 스택](#tech) |
| ✨ | [주요 기능](#features) |
| 🧠 | [RAG 시스템 구조](#rag) |
| 🚀 | [실행 방법](#start) |
| 🗂️ | [데이터 및 색인 준비](#data) |
| ✅ | [테스트](#test) |
| 📌 | [참고 사항](#notes) |
| 📚 | [관련 문서](#documents) |

---

<a id="tech"></a>

## 🛠️ 기술 스택

| 구분 | 기술 |
|---|---|
| Language | Python 3.11, JavaScript |
| Frontend | Streamlit, HTML, CSS, JavaScript |
| RAG | LangChain, LangGraph |
| Vector DB | ChromaDB |
| LLM | GMS (OpenAI 호환 API) |
| Embedding | text-embedding-3-small |
| 저장 | 브라우저 localStorage(포획), SQLite(RAG 캐시·기존 오프라인 기록) |
| Data | PokéAPI, Wikipedia |

자세한 패키지 버전은 [requirements.txt](requirements.txt)에 정리되어 있습니다.

---

<a id="features"></a>

## ✨ 주요 기능

### 🌿 1. 포켓몬 필드

포켓몬이 자유롭게 돌아다니는 필드에서 직접 포켓몬을 포획할 수 있는 기능입니다.

- 초원, 바다, 하늘, 사막 등 총 9개 지역으로 구성된 필드
- 지역별 타입에 맞는 포켓몬 등장
- 포켓몬의 이동 및 대기 애니메이션
- 몬스터볼을 이용한 포획 기능
- 포획 이펙트와 수집 기록 저장

각 지역에서는 해당 환경과 관련된 타입의 포켓몬이 등장하며, 한 번에 3~10마리의 포켓몬이 나타나는 방식입니다.

공개 필드의 포획 기록은 브라우저 `localStorage`에 저장합니다. 브라우저 프로필·사이트(origin)별로 분리되며 같은 프로필의 탭은 공유합니다. 새로고침 시 복원하고 수집 수·도감·중복 포획 횟수에 반영합니다. 기존 공용 SQLite 포획 기록은 자동으로 가져오지 않습니다.

### 📖 2. 포켓몬 도감

포켓몬의 정보를 검색하고 확인할 수 있는 도감 기능입니다.

- 포켓몬 이름 및 도감 번호 검색
- 타입과 세대별 필터링
- 포켓몬 이미지 및 상세 정보 확인
- 종족값, 특성, 진화 정보 제공
- 수집 여부와 포획 기록 확인
- 선택한 포켓몬에 대한 질문 기능

로토무 도감 형태의 UI를 사용하며, 아직 포획하지 않은 포켓몬도 정보를 확인할 수 있는 방식입니다.

### 🤖 3. 오박사 RAG 챗봇

포켓몬 데이터를 바탕으로 질문에 답변하는 RAG 챗봇입니다.

포켓몬 메타데이터와 외부 문서를 검색한 뒤 관련 근거를 활용하여 답변을 생성하는 구조입니다. 답변에는 사용한 근거의 번호와 출처를 함께 표시합니다.

주요 질문 예시는 다음과 같습니다.

- 피카츄의 특성은 무엇인가?
- 피카츄의 약점 타입은 무엇인가?
- 파이리의 진화 과정은 어떻게 되는가?
- 몸통박치기를 배우는 포켓몬은 무엇인가?
- 팬텀의 6세대와 7세대 차이는 무엇인가?

전체 포켓몬을 대상으로 질문하거나, 도감에서 특정 포켓몬을 선택한 뒤 질문할 수 있는 기능입니다.

오박사 캐릭터에 맞는 말투를 적용했으며, 전체 질문과 포켓몬별 대화 기록을 구분하여 관리하는 방식입니다.

### 🔎 4. 자연어 포켓몬 검색

자연어로 원하는 조건을 입력하여 포켓몬을 찾는 기능입니다.

타입, 특성, 세대, 종족값, 습득 기술 등의 조건을 활용할 수 있으며, 실제 데이터에 맞는 포켓몬만 검색 결과로 제공하는 방식입니다.

검색한 포켓몬을 선택하면 해당 포켓몬에 대한 질문으로 이어갈 수 있는 구조입니다.

### ⚡ 5. 타입 상성 및 기술 검색

포켓몬의 타입 상성과 기술 습득 정보를 검색할 수 있는 기능입니다.

타입 상성은 18개 타입의 공격·방어 배율을 기반으로 계산하며, 복합 타입의 약점과 저항도 확인할 수 있는 방식입니다.

기술 검색은 포켓몬별 기술 습득 데이터를 바탕으로 기술명, 세대, 습득 방법 등을 조회하는 기능입니다.

### 🎯 6. 추천 포켓몬 찾기

오박사 챗봇에서 답변한 포켓몬을 필드에서 직접 찾아볼 수 있는 기능입니다.

챗봇에서 포켓몬을 선택하면 해당 포켓몬이 등장할 수 있는 지역으로 이동하며, 대상 포켓몬을 강조하여 표시하는 방식입니다.

---

<a id="rag"></a>

## 🧠 RAG 시스템 구조

PokéField의 RAG 시스템은 포켓몬 메타데이터와 외부 문서를 활용하는 구조입니다.

### 📦 데이터 수집 및 색인

1. PokéAPI 기반 포켓몬 메타데이터를 JSONL 형태로 구성합니다.
2. 포켓몬별 검색 텍스트를 생성하고 임베딩하여 ChromaDB에 저장하는 방식입니다.
3. 질문과 관련된 외부 문서를 검색하고 LLM 프롬프트로 문서를 선별합니다.
4. 선별한 문서를 청킹한 뒤 별도의 ChromaDB 컬렉션에 색인합니다.

현재 사용 중인 주요 컬렉션은 다음과 같습니다.

| 컬렉션 | 내용 |
|---|---|
| `pokemon_meta` | 포켓몬 메타데이터 |
| `pokemon_docs` | 외부 문서 청크 |

### 🔄 질문 처리 과정

```text
사용자 질문
    ↓
질문 분석 및 검색어 추출
    ↓
포켓몬 메타데이터 검색
    +
외부 문서 검색
    ↓
검색 결과 병합 및 중복 제거
    ↓
근거 문서 구성
    ↓
LangGraph (retrieve → generate)
    ↓
근거 기반 답변 생성
    ↓
답변 및 출처 표시
```

LangGraph의 `retrieve`와 `generate` 노드를 분리하여 검색과 답변 생성을 처리하는 구조입니다.

기술 검색과 타입 상성처럼 정확한 데이터 조회가 필요한 기능은 Python으로 계산하거나 필터링한 결과를 활용하는 방식입니다.

청크 크기, 중복 길이, Top-k는 설정으로 관리하며, Top-k는 사용자 화면에서도 변경할 수 있는 기능입니다.

자세한 구현 내용은 [RAG 파이프라인 설계서](docs/pdf/architecture.pdf)에 정리되어 있습니다.

---

<a id="start"></a>

## 🚀 실행 방법

### ① 프로젝트 준비

Python 3.11 환경을 기준으로 작성한 프로젝트입니다.

프로젝트 폴더에서 PowerShell을 실행한 뒤 다음 명령어로 가상환경을 생성하고 라이브러리를 설치합니다.

```powershell
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### ② 환경변수 설정

`.env.example` 파일을 복사하여 `.env` 파일을 생성합니다.

```powershell
Copy-Item .env.example .env
```

`.env` 파일에는 사용하는 LLM 제공자와 API 키를 설정해야 합니다.

- `LLM_PROVIDER`: LLM 제공자
- `GMS_KEY` 또는 `OPENAI_API_KEY`: API 인증 키
- `CHAT_MODEL`: 사용할 채팅 모델
- `POKEMON_DATA_DIR`: 포켓몬 데이터 경로
- `CHROMA_DIR`: Vector DB 저장 경로
- `WIKI_CONTACT`: Wikipedia API 요청에 사용하는 운영자 연락처

API 키는 GitHub에 업로드하지 않고 환경변수로 관리하는 방식입니다.

기본 모델과 현재 실행 모델은 환경변수에 따라 다를 수 있으므로 실제 설정을 확인해야 합니다.

### ③ 실행 환경 확인

```powershell
.\.venv\Scripts\python.exe scripts\check_setup.py
```

프로젝트의 데이터와 기본 설정 상태를 확인하는 명령어입니다.

### ④ 웹 애플리케이션 실행

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

실행 후 브라우저에서 다음 주소로 접속할 수 있습니다.

`http://localhost:8501`

기존 가상환경이 준비된 Windows 환경에서는 `start.ps1` 스크립트로 실행할 수도 있습니다.

---

## Cloud 배포와 현재 확인 상태

서비스 주소는 [PokéField](https://pokefield.streamlit.app/)입니다. 2026-10-23 실제 읽기 검사에서 새 독립 프로필 A·B 모두 최초·새로고침 후 `22 / 1025`를 표시했고, 앱 프레임의 개인 포획 저장 키는 없었습니다. **로컬 수정본의 사용자별 저장이 Cloud에 적용됐다고 판정하지 않습니다.** 배포 커밋·Cloud Python 버전·Secrets·색인 로드는 [추가 검증 필요]입니다. 운영 기록 보존을 위해 Cloud에서는 포획·채팅을 하지 않았습니다.

배포 진입점은 `app.py`이며 의존성은 루트 `requirements.txt`, 정적 제공은 `.streamlit/config.toml`을 사용합니다. Python은 로컬 검증 환경 3.11과 맞춰 확인합니다. Linux의 설치·실행 예시는 아래와 같으며 이번에 Linux 설치를 실행한 결과는 아닙니다.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Cloud의 App settings → Secrets에 기존 환경변수 이름을 최상위 TOML 키로 설정합니다. 공급자와 모델은 기존 값을 유지하고 인증 키 값은 문서·Git에 기록하지 않습니다. `Settings.load()`는 환경변수를 읽으므로 임의 중첩 테이블을 사용하지 않습니다. Linux 경로는 다음처럼 프로젝트 기준 상대경로를 사용합니다.

```toml
POKEMON_DATA_DIR = "pokemon-data/data/processed"
CHROMA_DIR = "chroma_db"
```

`chroma_db/`는 ignore 규칙과 별개로 현재 Git 추적 파일에 SQLite·HNSW 파일이 포함됩니다. 앱은 기존 디렉터리를 직접 로드하며 자동 다운로드·자동 색인 코드는 없습니다. 로컬 추적 상태가 원격 배포 완료를 뜻하지는 않습니다. 일관된 전체 색인 디렉터리, 임베딩 signature 및 Linux 호환성 확인은 [Cloud 운영·색인 절차](docs/RAG_IMPLEMENTATION.md#cloud-배포와-현재-확인-상태)를 따릅니다. 설정 원칙은 [공식 Cloud 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)를 참고합니다.

---

<a id="data"></a>

## 🗂️ 데이터 및 색인 준비

프로젝트는 PokéAPI 기반의 포켓몬 데이터를 사용합니다.

현재 검증된 데이터 규모는 다음과 같습니다.

| 데이터 | 개수 |
|---|---:|
| 포켓몬 종 | 1,025 |
| 포켓몬 형태 | 1,351 |
| 세대별 레코드 | 6,260 |
| 메타데이터 색인 | 6,260 |
| 외부 문서 청크 | 64 |

> 외부 문서 색인은 현재 일부 포켓몬을 대상으로 구성된 상태이며, 전체 포켓몬의 설명 문서를 모두 수집한 상태는 아닙니다.

기존 데이터와 색인이 준비되어 있다면 다시 수집하거나 임베딩할 필요는 없습니다.

색인을 새로 생성해야 하는 경우 다음 명령어를 사용할 수 있습니다.

```powershell
# 일부 데이터 색인
.\.venv\Scripts\python.exe scripts\index_pokemon.py --pilot

# 특정 포켓몬의 외부 문서 수집 및 색인
.\.venv\Scripts\python.exe scripts\index_documents.py --species 25 94
```

전체 메타데이터 색인은 `--pilot` 옵션을 제외하여 실행하는 방식입니다.

> 새로운 문서 수집과 임베딩 과정에서는 API 호출 비용이 발생할 수 있습니다.

포켓몬 원본 데이터와 이미지 준비 과정은 [데이터 README](pokemon-data/README.md)에 정리되어 있습니다.

---

<a id="test"></a>

## ✅ 테스트

프로젝트의 단위 테스트는 다음 명령어로 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

2026년 10월 23일 기존 격리 회귀는 155개이며, 브라우저 저장 보완 후 전체 163개가 45.941초에 통과했습니다. 이번 문서 갱신에서는 관련 8개 테스트만 다시 통과했습니다. 전체 회귀는 FakeLLM·격리 저장소를 사용했고 실제 LLM 호출 결과가 아닙니다.

> 필수 요구사항 F2001~F2012는 검증 및 재검증을 통해 모두 통과한 상태입니다. 다만 실제 외부 LLM을 사용하는 전체 사용자 흐름과 모바일 실기기 환경까지 모두 검증한 결과는 아닙니다.

테스트 결과는 [검증 결과 문서](docs/pdf/VERIFICATION_SUMMARY.pdf)에 정리되어 있습니다.

---

<a id="notes"></a>

## 📌 참고 사항

- 공개 필드의 포획 기록은 브라우저 `localStorage`에 저장합니다. 브라우저 프로필·사이트(origin)별로 분리되며 같은 프로필의 탭은 공유합니다. 새로고침 시 복원하고 수집 수·도감·중복 포획 횟수에 반영합니다. 기존 공용 SQLite 포획 기록은 자동으로 가져오지 않습니다. 로그인·계정·기기 간 동기화는 없습니다. 사이트 데이터 삭제, 주소 변경, 시크릿 창 종료 시 기록이 사라질 수 있습니다. 저장소가 차단되거나 가득 차면 안내 후 포획 저장을 중단하며 공용 DB로 대체하지 않습니다.
- 채팅 기록은 Streamlit 세션 상태를 사용하므로 장기 보관을 위한 계정별 대화 저장 기능은 제공하지 않습니다.
- RAG 답변에는 API 키가 필요하지만, 도감과 로컬 타입 상성·기술 검색 등은 LLM 호출 없이 사용할 수 있는 기능입니다.
- 외부 문서 수집에는 Wikipedia API를 사용하며, 새로운 요청에는 운영자 연락처 설정이 필요합니다.
- 포켓몬 데이터와 이미지의 출처 및 이용 조건은 공개 배포 전에 추가 확인이 필요한 상태입니다.

---

<a id="documents"></a>

## 📚 관련 문서

- [요구사항 정의서](docs/pdf/requirements.pdf)
- [RAG 파이프라인 설계서](docs/pdf/architecture.pdf)
- [RAG 구현 및 색인 안내](docs/pdf/RAG_IMPLEMENTATION.pdf)
- [프로젝트 검증 결과](docs/pdf/VERIFICATION_SUMMARY.pdf)
- [비기능 요구사항 검증](docs/pdf/NF_VERIFICATION.pdf)
- [데이터 출처 및 이용 조건](docs/pdf/SOURCES_AND_LICENSES.pdf)
