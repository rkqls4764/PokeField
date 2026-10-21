# 개발 구조와 연결 순서

UI(app.py) → 데이터 조회(src/catalog.py) / RAG(src/rag.py). 설정(src/settings.py), 프롬프트(prompts/), 기존 수집(pokemon-rag/scripts/)을 분리합니다.

1. `pokemon_meta`: 세대별 record_id를 고정 문서 ID로 사용. 필터는 species_id/pokemon_id/generation 정수. 배열/객체는 텍스트로 변환하고 메타데이터에는 스칼라만 저장합니다.
2. `pokemon_docs`: 외부 문서의 species_id/pokemon_id/title/source_url/source_type/collected_at/license를 보존. 청크 ID는 `pokemon_id:문서ID:청크설정해시:순번`. 설정 변경 시 기존 동일 문서 청크를 정리한 뒤 upsert해 오래된 청크가 남지 않게 합니다.
3. 검색어 추출 → 후보 수집 → LLM 선별 → 본문 저장 → 청킹/임베딩. 선택 포켓몬 자체 문서는 항상 포함합니다. 영화 팩은 구조만 참고하며 포켓몬의 근거로 사용하지 않습니다.
4. 캐시 키는 정규화한 검색어와 언어. 문서 캐시와 검색/선별 이력을 분리합니다. 네트워크 재시도/간격과 Wikimedia의 실제 최신 정책을 연결 시 확인합니다.
5. retrieve는 선택 항목·세대의 메타데이터를 필수로 포함하고, 항목 필터를 적용해 pokemon_docs를 의미 검색합니다. 근거를 병합·ID 중복 제거 후 번호를 부여합니다.
6. generate는 번호가 붙은 근거만 모델에 전달합니다. 실제 인용 번호를 파싱해 사용된 근거만 UI에 표시합니다. 근거가 없거나 부족하면 확인되지 않는다고 답합니다.

세대 레코드는 게임별 등장 여부를 증명하지 않습니다. `game_presence=null`은 미확인이며 특수 폼이 후속 모든 게임에서 사용 가능하다는 뜻으로 표시하면 안 됩니다. 프롬프트 전문·키·예외 추적은 사용자 화면에 표시하지 않습니다.
