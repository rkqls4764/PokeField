# Pokémon RAG 데이터 수집기

Python 3.10 이상, 외부 라이브러리 없이 실행합니다. PokéAPI 전체 종 목록을 페이지별로 읽고 종 → variety → form 및 진화 체인을 수집합니다. 이 작업 범위는 데이터 준비입니다. 외부 위키 문서, ChromaDB 및 LangGraph 구현은 포함하지 않습니다.

## 실제 실행 결과 (2026-10-21 한국시간)

소량 5종 테스트 후 전체 수집을 실행했습니다. API 목록 기준 전체 1,025종을 확보했습니다. API 실패 0건, 한국어 이름 누락 0건, 중복 및 참조 오류 0건입니다. 삐삐 타입 변경과 팬텀 특성 변경 검증, 1세대 특수 능력치 구조 검사, 이력 복원 단위 테스트 3개를 통과했습니다.

| 가공 파일 | 레코드 수 |
|---|---:|
| pokemon_species.jsonl | 1,025 |
| pokemon_varieties.jsonl | 1,351 |
| pokemon_forms.jsonl | 1,579 |
| pokemon_generations.jsonl | 6,260 |
| pokemon_moves.jsonl | 638,321 |
| pokemon_evolutions.jsonl | 677 |
| generations.json | 9 |
| version_groups.json | 32 |

세대별 레코드 수: 1세대 151, 2세대 251, 3세대 392, 4세대 508, 5세대 673, 6세대 811, 7세대 969, 8세대 1,154, 9세대 1,351. 특수 형태를 포함한 역학 레코드 수이며 각 세대 게임의 실제 등장 포켓몬 수가 아닙니다.

API 이력 필드 누락 및 최초 세대 미확인 형태는 0건입니다. 독립 게임 자료와의 대조는 하지 않았으며, 게임별 등장 여부 6,260행은 미확인 null로 남겼습니다. 버전별 진화 조건 대조, 외부 위키 수집 및 색인은 추가 작업입니다.

```powershell
python scripts/test_history.py
# 독립 디렉터리에 소량 테스트
python scripts/collect_pokemon.py --root sample --ids 25 35 94 6 19
python scripts/process_pokemon.py --root sample
python scripts/validate_pokemon.py --root sample
# 전체 수집 및 검증
python scripts/collect_pokemon.py
python scripts/process_pokemon.py
python scripts/validate_pokemon.py
# 한 번에 수집 → 가공 → 분석 → 검증 (재실행 시 캐시 사용)
python scripts/run_pipeline.py
```

`--workers 6`으로 동시 요청 수를 조정합니다. 전역 요청 시작 간격은 0.08초, 타임아웃은 45초, 최대 4회 시도하며 1/2/4초 후 재시도합니다. 실패는 보고서에 기록하고 다른 항목은 계속 수집합니다. 재실행은 캐시를 사용합니다. 새로운 시점의 전체 스냅샷은 `--root 새폴더`로 수집하세요. 동일 캐시에서 갱신 수집은 제공하지 않으므로 기존 캐시와 새 데이터의 혼합에 주의하세요.

## 파일

- `data/raw/*.json`: URL의 SHA-256을 파일명으로 사용하는 원본 캐시. `source_url`, UTC `collected_at`, 변경하지 않은 API `response`를 함께 저장합니다.
- `data/processed/pokemon_species.jsonl`: 한국어/영어 이름, 종 ID, 최초 세대, 전설/환상/베이비 구분, 한국어 도감 설명과 버전, variety 참조.
- `pokemon_varieties.jsonl`: 독립 능력치를 가진 Pokemon ID, 종 ID, form ID, 등장 세대와 확인 근거, 이미지 URL.
- `pokemon_forms.jsonl`: 세부 form ID, 이름/다국어 이름, 버전 그룹, 메가/배틀 전용 여부.
- `pokemon_generations.jsonl`: `pokemon:{pokemon_id}:gen:{generation}` 고유 키. 세대별 타입/능력치/특성과 필드별 복원 상태.
- `pokemon_moves.jsonl`: Pokemon ID·버전 그룹·기술·습득 방법·레벨 조합으로 중복 제거한 기술 정보.
- `pokemon_evolutions.jsonl`: 진화 조건마다 한 행. 원본 evolution_details를 details에 보존. 종을 하나만 가진 체인은 간선이 없어 행이 없습니다.
- `generations.json`, `version_groups.json`: 동적으로 조회한 세대 및 버전 그룹 상세.
- `reports/collection_manifest.json`: 전체 목록의 예상 수, 수집 범위, API 실패.
- `reports/collection_report.json`: 실제 파일별 행 수, 무결성 검사, 대표 사례 검증, 미확인 수.
- `reports/api_analysis.json`: 대표 실제 응답 구조와 이력 분석.

가공 파일명은 모두 `data/processed/` 기준입니다. 파일은 UTF-8로 쓰며 한국어를 보존합니다. 임시 파일을 완성한 후 교체하므로 기존 원본 캐시는 가공 실패의 영향을 받지 않습니다. 출력은 메모리/스트리밍을 혼용합니다. 대용량 기술 파일은 생성과 검증 모두 행 단위로 처리합니다.

## 세대 이력 해석과 한계

공식 문서: https://pokeapi.co/docs/v2

`past_types`, `past_stats`, `past_abilities`의 generation은 이전 값이 마지막으로 유효한 세대(포함)입니다. 현재 상태에서 큰 경계부터 역순 적용합니다. 타입은 목록을 교체하고, 능력치는 stat 이름별로, 특성은 slot별로 부분 변경합니다. null 특성은 빈 슬롯입니다. 필드 자체가 없으면 해당 값은 미확인으로 처리합니다. 필드가 존재하며 이력이 비어 있으면 API가 변경 이력을 제공하지 않은 것으로 해석합니다. 이는 독립적인 게임별 역사 검증을 뜻하지 않습니다.

1세대 special은 원본 이력에서만 읽고, special_attack/special_defense는 null로 둡니다. 2세대 이후 special은 null입니다. 1~2세대 특성은 빈 목록이고, 숨겨진 특성은 5세대부터 허용합니다. 특수 형태의 최초 세대는 연결된 모든 form의 version_group → generation 중 최솟값으로 확인하며 종의 최초 세대보다 빠를 수 없습니다. 이 근거는 API 메타데이터이며 모든 게임의 실제 이용 가능성까지 증명하지 않습니다. 확인되지 않는 variety는 최초 세대를 null로 두고 세대 행 생성을 보류합니다.

`history_status=api_history_reconstructed`는 API 이력 규칙에 따라 복원했다는 의미입니다. 게임별 등장 여부는 기술 습득 목록이나 game_indices만으로 확정하지 않으며 모두 `game_presence=null`로 유지합니다. 메가진화처럼 일부 후속 게임에 없는 형태도 세대별 역학 레코드가 존재할 수 있습니다. 실제 게임 등장 조회에는 별도 버전별 근거가 필요합니다. 진화 조건에도 게임 버전을 임의 부여하지 않습니다.

## RAG 연결

`pokemon_meta`는 세대 행의 record_id를 문서 ID로, species_id/pokemon_id/generation을 정수 필터로 사용하세요. name_ko, types, stats, abilities를 자연어 텍스트로 만들고 미확인 값을 명시하세요. 배열/객체는 Chroma 메타데이터에 바로 넣지 말고 텍스트/스칼라로 변환합니다. `pokemon_docs`에는 추후 외부 문서의 title/body/source_url/species_id/pokemon_id를 저장하고 청킹합니다. API 한국어 도감 설명은 외부 위키 문서 수집을 대체하지 않습니다.

## 출처 및 이용 조건

PokéAPI https://pokeapi.co/ 및 API v2를 사용합니다. 공식 Fair Use 정책의 로컬 캐시 및 절제된 호출 원칙을 적용했습니다. 포켓몬 명칭/이미지의 권리는 각 권리자에게 있습니다. API 접근 가능 여부와 콘텐츠 재배포 권한은 구분되므로 공개 서비스/상업 이용 전 원 출처의 최신 조건을 확인하세요. 이미지는 URL만 저장합니다.

참고 PDF의 RAG 서비스 전체 명세 중 이번 요청은 데이터 수집 부분만 구현합니다. 이후 외부 문서 수집과 이용 조건 기록, 두 컬렉션 색인, 검색/생성/UI, RAG 품질 비교를 별도로 진행해야 합니다.
