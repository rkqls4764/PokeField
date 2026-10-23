# 출처와 이용 조건 — PokéField

확인일: 2026-10-23. 접근 가능한 API·저장소라는 사실과 콘텐츠의 재배포 허락은 별개다. 아래의 미확인을 자유 이용 허락으로 해석하지 않는다. 이 문서는 법적 이용 허락을 새로 부여하지 않는다.

## 출처별 기록

| 대상 / 프로젝트 위치 | 확인된 출처 | 이용 조건과 조치 | 판정 |
|---|---|---|---|
| 포켓몬·종·진화·타입·특성 JSONL, 한국어 이름 / `pokemon-data/data/processed` | [PokéAPI v2](https://pokeapi.co/docs/v2), 레코드별 `source_url`; 수집 정보 `pokemon-data/reports/collection_manifest.json` | API 공정 사용 정책은 로컬 캐시와 절제된 요청을 요구한다. 현재 기존 JSON·원본 캐시 재사용. 서버 코드의 [LICENSE.md](https://raw.githubusercontent.com/PokeAPI/pokeapi/master/LICENSE.md)는 저작권 고지 유지·보증 부인·보증/홍보 금지 조건을 둔다. 이 소프트웨어 조건을 포켓몬 원작 콘텐츠 전체의 이용 허락으로 확대하지 않는다. | 출처 확인, 원작 콘텐츠 재배포 권한은 별도 확인 필요 |
| 기술명·위력·명중률·버전·타입 상성 / `move_catalog.json`, `type_chart.json` | [PokéAPI CSV](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv); `battle_data_manifest.json`에 파일별 URL·CSV SHA-256 | `scripts/build_battle_data.py`는 move_names/moves/version_groups/versions/version_names/type_efficacy/type_efficacy_past/move_changelog CSV를 변환한다. 현재 저장본은 브랜치 URL과 해시로 식별되며 수집 당시 커밋 SHA는 별도로 기록되지 않았다. 코드 라이선스와 게임 데이터 권리는 구분한다. | 실제 데이터 출처 확인, 포괄적 콘텐츠 허락 미확인 |
| 포켓몬별 습득 기술 / `pokemon_learnsets.jsonl` (기존 `pokemon_moves.jsonl` 별도 보존) | 기존 PokéAPI pokemon 원본 캐시의 `moves` → 레코드별 `source_url` (파일명은 실제 처리 데이터 목록 참고) | 세대·버전·레벨·방법은 수집 캐시에 있는 정보만 사용한다. CSV와 JSON 변환은 원작 권리를 제거하지 않는다. 현재 버전 기록 누락을 습득 불가로 단정하지 않는다. | 출처 확인, 별도 콘텐츠 허락 미확인 |
| 검색·RAG 외부 설명 / `.local/rag/documents` 및 Chroma `pokemon_docs` | [한국어 Wikipedia Action API](https://ko.wikipedia.org/w/api.php), 문서별 URL·revision_id·revision_timestamp·collected_at | API에서 조회한 rightsinfo의 `license`·`license_url`을 저장한다. [Wikimedia 이용약관 §7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en#7._Licensing_of_Content)에 따라 문서 링크/기여자 이력 등으로 저작자 표시, 적용 라이선스 링크 보존, 변형 시 변경 사실 표시와 적용되는 동일조건 준수. 현재 RAG는 원문 일부 검색·청킹·요약을 사용하며 원문 자체와 구분한다. 원문 배포 시 문서별 라이선스/별도 고지를 함께 제공해야 한다. 이미지에는 텍스트 라이선스를 일괄 적용하지 않는다. | 문서별 저장 라이선스·원문 링크 확인; 배포물 구성은 제출 전 재점검 |
| 포켓몬 공식 일러스트·스프라이트 / `pokemon-data/data/images` | PokéAPI pokemon 응답의 `sprites` URL; [PokeAPI/sprites](https://github.com/PokeAPI/sprites) | [sprites/LICENCE.txt](https://raw.githubusercontent.com/PokeAPI/sprites/master/LICENCE.txt)는 저장소의 CC0 표기와 함께 이미지 콘텐츠의 The Pokémon Company 저작권을 명시한다. 저장소 CC0만으로 제3자 캐릭터 이미지 권리가 모두 해소됐다고 판단하지 않는다. 상표·캐릭터·개별 이미지 이용 가능 범위는 별도 확인해야 한다. | 공급 경로 확인, 포괄적 이미지 이용 허락 미확인 |
| 배경 9개 / `static/regions/{grassland,sky,sea,electric,volcano,snow,city,cave,desert}.png` | 사용자가 Downloads의 `배경_초원/하늘/바다/전기/화산/눈/도시/동굴/사막.png`로 제공 | 원게시 URL·저작자·제작 도구·라이선스·사용 허락 증빙 없음. AI 생성 여부도 단정하지 않는다. | 원출처·이용 조건 미확인 |
| 몬스터볼·오박사 / `static/regions/{ball,professor}.jpg` | 사용자가 Downloads의 `몬스터볼.jpg`, `오박사.jpg`로 제공 | 원게시 URL·작가·편집 허락·재배포 허락 미확인. 포켓몬 캐릭터 권리를 오픈소스 코드 라이선스로 대체하지 않는다. | 미확인 |
| 로토무 도감 / `static/rotom/{closed,open}.png` | 사용자가 Desktop의 `도감_닫힘.png`, `도감_열림.png`로 제공 | 원게시 URL·작가·사용 허락 미확인. 배경 제거/변환이 원작 권리를 소멸시키지 않는다. | 미확인 |
| `rotom-landscape.png`, `rotom-mobile.png` | 프로젝트 루트의 도감 화면 이미지. 제작·원출처 증빙 없음 | 원작 이미지가 포함된 화면 캡처인지 별도 원본인지 확정하지 않는다. 기존 파일을 삭제·대체하지 않았다. | 미확인 |

사용자 제공 경로는 전달 경로이며 저작권자 또는 게시 출처라는 뜻이 아니다. `docs/wikipedia_sources.json`은 현재 저장된 15개 문서의 URL·라이선스·수정판·수집 시점·기여자 이력 링크를 기록한다. `docs/asset_provenance.json`은 파일별 상대 경로·SHA-256·원출처 확인 상태를 기록한다. 캐릭터 명칭/상표는 각 권리자에게 귀속되며, 본 프로젝트의 공식 제휴·승인을 주장하지 않는다.

## Wikipedia 운영자 연락처 (NF2006)

[User-Agent 정책](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy/en)은 클라이언트 식별자와 연락 가능한 운영자 정보를 요구한다. [API 사용 지침](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines), [API 예절](https://www.mediawiki.org/wiki/API:Etiquette)도 확인했다.

- 위치: 프로젝트 `.env` 또는 실행 환경의 `WIKI_CONTACT`. `Settings.load()`가 환경변수에서 읽는다. 실제 `.env`는 이번 작업에서 변경하지 않는다.
- 값: 운영자가 실제 소유·관리하는 영문 이메일, 연락 가능한 URL 또는 위키 사용자 식별자. 이 문서나 테스트의 예시 주소를 운영 연락처로 복사하지 않는다.
- 비어 있거나 비 ASCII/제어문자가 포함되면 새 Wikipedia HTTP 요청 전에 안전한 설정 안내를 반환한다. 기존 응답·문서 캐시는 계속 사용한다.
- 전송 형식: `PokemonLab/1.0 (<설정한 실제 연락처>)`. 내부 클라이언트 식별자이며 화면 프로젝트명 변경과 무관하다.
- 기존 간격 6.2초 기본값, 최대 3회 시도, 429/503·Retry-After·maxlag 처리는 유지한다. 30초 초과 대기 지시는 재시도하지 않고 안내한다.
- 테스트는 예약 도메인 `example.org`를 가짜 연락처로 사용한 모의 HTTP만 실행한다. 실제 연락처를 확인하거나 Wikipedia 신규 수집 성공을 검증했다는 뜻이 아니다.

## 사용자가 확인할 사항

1. 실제 운영자 연락처를 결정하여 WIKI_CONTACT에 설정한다.
2. 배경·오박사·몬스터볼·로토무 이미지의 원게시 URL, 작가, 적용 라이선스 또는 허락 증빙을 제공한다. 생성 이미지라면 사용 도구·약관과 생성/편집 기록도 확인한다.
3. 포켓몬 이미지·명칭·게임 데이터에 대한 배포 형태의 허용 범위를 확인한다. 확인 전 공개·상업 배포의 권리 문제가 해결됐다고 표시하지 않는다.
4. 실제 제출 ZIP에서 `.env`, API 키, `.local` 진단/캐시, 가상환경을 제외하고 필요한 출처·이용 조건 고지는 포함한다. 원문 재배포 시 문서 URL·라이선스와 변형 고지를 함께 제공한다.

NF2007의 기록 보완은 완료할 수 있으나, 위 미확인 권리의 실제 허락까지 자동으로 충족시킬 수는 없다.


## 제출 문서 연결

구현 범위는 [요구사항 현황](requirements.md), 실제 검증은 [현재 검증 요약](VERIFICATION_SUMMARY.md)을 따른다. 이 출처 조사 문서와 [이미지별 기록](asset_provenance.json), [위키 문서별 기록](wikipedia_sources.json)은 미확인 권리를 보존한 채 함께 제출한다.
