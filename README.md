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
