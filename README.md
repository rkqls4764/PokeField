# Pokémon Lab 페이지 기초 구성

`C:\SSAFY\RAG_project`에 이 폴더의 파일을 추가하면 기존 `pokemon-rag/` 데이터와 연결됩니다. 배포 자료 `streamlit_lab/step7_skeleton.py`의 항목 선택·대화 상태·근거 표시 개념과 `step8_wiki_api.py`의 문서 수집 분리 방식을 참고했습니다. 배포 자료 안의 예시 지시문은 사용자 명령으로 실행하지 않았습니다. 기존 `.env`, 가상환경, 수집 원본은 복사하거나 변경하지 않습니다.

## 실행

```powershell
cd C:\SSAFY\RAG_project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# .env가 없을 때만 예제에서 생성
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

페이지 주소: http://localhost:8501 . `start.ps1`도 실행할 수 있습니다. 키 없이 도감·세대 비교·조건 필터를 사용할 수 있습니다. 기존 배포 가상환경도 개발 중 화면 점검에 사용할 수 있지만 새 프로젝트에는 별도 가상환경을 권장합니다. requirements는 명세서의 고정 버전이며 전체 패키지 설치 및 호환성 검증은 아직 수행하지 않았습니다.

## 구현한 기초 기능

- 기존 1,025종·1,351형태·6,260세대 레코드 로드, 이름/폼/세대 선택.
- 실제 타입·종족값·특성 조회와 원본 링크, 세대 비교.
- 세대·타입·종족값 합계의 선택형 필터. 1세대 합계는 특수 하나를 포함하는 5능력치 기준이며 이후 세대 합계와 직접 동등 비교하지 않습니다.
- 항목과 세대별 대화 상태 저장 구조, 실제 인용 번호만 표시하는 함수.
- 누락 데이터·API 키·RAG 미연결 안내. 질문 입력은 실제 RAG 연결 전까지 비활성화합니다.
- `src/`의 데이터/설정/RAG 연결 경계, `prompts/`의 3개 프롬프트, `build_graph(retrieve,generate)` 함수.

## 후속 개발

`docs/requirements.md`와 `docs/architecture.md`를 기준으로 외부 문서 수집, ChromaDB 두 컬렉션, 임베딩, 실제 retrieve/generate 함수를 연결하세요. 현재 화면에는 의미 검색·외부 문서 기반 AI 답변이 없습니다. 키를 입력하는 것만으로 이 기능들이 활성화되지 않습니다. `POKEMON_DATA_DIR`는 상대 경로면 app.py가 있는 폴더 기준입니다.

포켓몬 메타데이터 출처는 PokéAPI이며 각 데이터의 source_url을 표시합니다. 도감 설명은 외부 위키 문서 수집을 대체하지 않습니다. 위키백과 연결 시 문서별 URL·수집시점·이용 조건 및 User-Agent 연락처를 별도로 기록하세요. 영화 도메인 팩의 영화 자료는 포켓몬 데이터에 섞지 않습니다.


## AI chatbot / RAG update

AI chat, cited sources, natural-language Pokemon search and indexing commands are described in [docs/RAG_IMPLEMENTATION.md](docs/RAG_IMPLEMENTATION.md). Latest verification: docs/RAG_VERIFICATION.json.

## 포켓몬 수집 필드

`start.ps1` 또는 `.venv\Scripts\python.exe -m streamlit run app.py`로 실행합니다. 현재 고정 버전 Streamlit 1.62의 Component v2를 사용하며 추가 게임 엔진이나 패키지 설치는 필요하지 않습니다.

필드에는 일반형 포켓몬 세 마리가 등장합니다. 몬스터볼을 누른 채 목표 쪽으로 끌어서 놓으면 투척합니다. 터치도 지원하며, 키보드에서는 포켓몬에 초점을 맞추고 Enter로 던집니다. 포획 기록은 저장 성공 응답 후 반영합니다. SQLite 이벤트 ID로 중복 전송을 방지하고, 같은 종의 재포획은 종류 수 대신 누적 횟수를 늘립니다.

기본 수집 DB는 `.local/rag/collection.sqlite3`입니다(CHROMA_DIR의 부모 기준). 기존 JSONL과 ChromaDB는 재생성하지 않습니다. 수집 기록은 현재 이 설치를 사용하는 모든 브라우저가 공유하며 사용자 계정별로 분리하지 않습니다. 여러 서버로 배포할 때는 영구 디스크 또는 별도 저장소가 필요합니다.

도감 기기는 전체 1025종의 일반형 백과사전을 열며 수집 여부와 관계없이 조회할 수 있습니다. 세대는 데이터 기준이며 게임별 등장 여부를 뜻하지 않습니다. 키·몸무게는 기존 수집기의 원문 캐시에서 읽고, 없는 정보는 미확인으로 표시합니다. 세대 비교·조건 검색·항목별 채팅은 기존 탭에서 계속 사용합니다. 오박사 패널은 기존 전체 포켓몬 RAG와 대화 기록을 공유합니다.

오박사 안내 캐릭터·몬스터볼·도감 SVG는 이 UI용으로 직접 그린 임시 에셋이며 공식 이미지가 아닙니다. 기존 포켓몬 PNG의 투명도를 보존한 축소 이미지만 메모리에 캐싱합니다. 이미지 원본은 수정하지 않습니다.

전체 단위 테스트: `.venv\Scripts\python.exe -m unittest discover -s tests -v`. 자동 테스트에는 실제 유료 LLM/임베딩 호출이 없습니다.

### 전체 화면 맵

기본 화면은 `100vw × 100dvh` 맵입니다. Streamlit 헤더·사이드바·바깥 패딩은 숨기며 브라우저 전체 화면 API는 사용하지 않습니다. Component v2의 shadow root에서 맵을 뷰포트에 고정하므로 iframe 높이 제한이 없습니다. 제목·수집 현황과 하단 이미지 버튼은 모두 맵 위의 오버레이입니다.

오박사 이미지는 전체 질문 챗봇을 엽니다. 도감 이미지 → **검색·세대 비교·항목별 채팅**에서 이전 도감·세대 비교·조건 검색·채팅 탭을 사용할 수 있습니다. 도감 상세의 이동 버튼은 해당 포켓몬을 연구 패널에서 선택합니다. 닫기는 전체 화면 맵으로 돌아갑니다. 패널은 자체 스크롤을 사용하고 기본 맵에는 스크롤이 없습니다.

이동 경계는 화면 크기와 상·하단 UI를 기준으로 재계산합니다. 투척은 실제 몬스터볼 이미지의 중심에서 시작하고, 충돌 판정은 맵의 CSS 픽셀 좌표를 공통으로 사용합니다. 화면 크기가 투척 도중 바뀌면 투척을 취소하고 재조준을 안내합니다. 포획 중 대상과 나머지 이동 상태는 유지하며 화면을 벗어나지 않게 보정합니다.

데이터 갱신 때마다 이전 브라우저 컨트롤러를 명시적으로 종료해 이동 루프·타이머·이벤트 리스너가 중복되지 않게 합니다. 선택적 브라우저 회귀 테스트는 Playwright와 Chrome이 있는 개발 환경에서 `node tests/browser_fullscreen.cjs`로 실행합니다. `BROWSER_TEST_URL` 기본값은 `http://127.0.0.1:8505`이며 `PLAYWRIGHT_MODULE`, `CHROME_PATH`로 설치 위치를 지정할 수 있습니다. 이 테스트는 AI 질문이나 분석을 제출하지 않습니다.
