# Pokémon Lab RAG 구현

## 실행

프로젝트 폴더에서 다음 명령을 실행합니다. 기존 `.env`와 다운로드 데이터/이미지는 유지합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\index_pokemon.py --pilot
.\.venv\Scripts\python.exe scripts\index_documents.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

전체 메타데이터 색인은 `scripts/index_pokemon.py`에서 --pilot을 빼면 됩니다. 외부 문서는 기본 10종이며 --species 25 35 처럼 확대합니다. PokéAPI JSONL과 이미지는 다시 다운로드하지 않습니다. 기존 .env의 값은 그대로 사용하고 새 설정은 .env.example을 참고해 추가하세요.

## 동작

- `catalog.py`: JSONL 로드와 정확한 수치/타입 필터. 한국어 특성 파일 두 개를 병합. 진화 질문에는 실제 진화 데이터도 근거로 제공.
- `vector_store.py`: Chroma의 pokemon_meta와 pokemon_docs. 명시적인 임베딩 사용으로 자동 모델 다운로드를 막음. 고정 ID와 내용 해시로 변경 없는 항목을 건너뜀.
- `llm.py`: GMS/OpenAI를 분리한 LangChain ChatOpenAI, Pydantic 결과 검증, OpenAI 임베딩 엔드포인트. 캐시는 서비스/모델/본문 해시 단위. 키와 원문 프롬프트를 로그에 남기지 않음.
- `document_service.py`: 한국어 위키백과 Action API. 검색어 추출→후보 선별→본문/이용조건/리비전 저장→청킹→색인. 자체 문서는 후보 선별 결과보다 우선. 관련 포켓몬명이 본문에 없는 문서는 제외. 원문 URL과 이용 조건은 API 응답을 사용.
- `rag.py`: 실제 LangGraph retrieve→generate. 선택 포켓몬 메타데이터를 필수로 넣고 세대 비교 질문에는 해당 이력도 넣음. 외부 문서는 species_id로 제한해 의미 검색하고 중복 ID를 제거. 인용 번호가 없거나 범위 밖이면 답변을 표시하지 않음.
- `natural_search.py`: JSON 조건 추출→Python 정확 필터→AI 후보 선별→후보 ID/실제 데이터 재검증. 추천 수치는 JSONL로 표시. 상대 조건은 기본 100 이상이며 .env에서 변경.
- `ui_rag.py`: 기존 네 탭과 이미지/한글 특성을 유지하며 채팅/근거/검색 카드를 연결. 항목+세대 단위 대화 분리. 결과 선택 시 포켓몬과 세대를 바꾸고 질문하기 탭으로 이동.

## 캐시와 비용

페이지를 열거나 다시 그릴 때 전체 색인·수집·임베딩을 수행하지 않습니다. 색인은 명령 실행 시에만 진행합니다. 문서 버튼과 질문 입력/자연어 검색 제출 시에만 API를 호출합니다. 질문별 추가 수집은 체크박스로 선택합니다. 기본값은 꺼짐이며 캐시된 문서로 검색합니다.

`.local/rag/cache.sqlite3`에 검색 API 응답·LLM 조건/선별 결과·임베딩을 캐시합니다. `.local/rag/usage.jsonl`은 실제 LLM/임베딩 요청과 제공된 토큰 사용량, 위키 HTTP 상태를 기록합니다. 임베딩은 32개 단위, 자연어 후보는 기본 25개만 LLM에 전달합니다. GMS 사용량/과금은 실제 계정 정책에 따르므로 금액을 추정 보고하지 않습니다.

## 출처/이용 조건

위키백과 정책을 확인한 뒤 Action API만 사용합니다. robots.txt에서 제한된 HTML 대량 수집이나 다른 포켓몬 위키 크롤링은 하지 않습니다. WIKI_CONTACT에는 실제 영문 연락처를 설정하세요. 연락처가 없으면 앱 식별자만 보내고 요청 간격 6.2초를 적용합니다. 429/503 및 Retry-After를 처리하며 30초를 넘는 대기 지시는 조기 재시도 대신 중단합니다.

- https://www.mediawiki.org/wiki/API:Etiquette
- https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
- https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use
- https://ko.wikipedia.org/robots.txt

문서별 실제 라이선스 문구/URL·제목·원문 URL·수집일·리비전을 저장합니다. 원문 링크에서 문서 이력/기여자를 확인할 수 있습니다. 수정·배포 시 해당 이용 조건을 따라야 합니다. API 도감 설명을 외부 문서로 간주하지 않습니다.

## 한계

숫자·타입·후보 ID·인용 번호는 Python으로 검사합니다. LLM이 문장을 근거에서 올바르게 해석했는지의 의미적 정확성까지 코드가 보장하지는 않습니다. 실제 답변과 근거를 함께 확인하세요. 자연어 검색은 최소값(이상), 높은/빠른 상대 조건, 타입 AND, 한 개 세대를 지원합니다. 이하/제외/복합 OR 등은 별도 스키마 확장이 필요합니다. 외부 문서의 게임 세대 정보는 일부 누락될 수 있어 세대별 구조화 메타데이터를 우선하고 등장 여부는 추정하지 않습니다.

최신 검증 결과와 수집 범위는 `.local/rag/` 보고서 및 `docs/RAG_VERIFICATION.json`에 기록됩니다. 외부 문서가 미수집인 종도 메타데이터가 색인돼 있으면 그 근거만으로 답변할 수 있습니다. 임베딩 모델/서비스를 바꿀 때는 새 CHROMA_DIR를 사용하세요.

## 공식 구현 참고

https://docs.trychroma.com/docs/collections/add-data
https://docs.langchain.com/oss/python/langgraph/graph-api
https://developers.openai.com/api/docs/guides/structured-outputs
https://developers.openai.com/api/reference/resources/embeddings/methods/create
