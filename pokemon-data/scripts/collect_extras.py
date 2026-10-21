
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
IMAGES = DATA / "images"

session = requests.Session()


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def download_image(url, path):
    if not url or path.exists():
        return False

    try:
        response = session.get(url, timeout=20)

        if response.status_code != 200:
            return False

        if "image/" not in response.headers.get(
            "Content-Type", ""
        ):
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)

        time.sleep(0.1)
        return True

    except requests.RequestException as e:
        print(f"이미지 오류: {url} - {e}")
        return False


# ----------------------------------
# 1. 포켓몬 이미지 추가 다운로드
# ----------------------------------
varieties = read_jsonl(
    PROCESSED / "pokemon_varieties.jsonl"
)

for pokemon in varieties:
    pid = pokemon["pokemon_id"]
    normal_url = pokemon.get("image_url")

    if not normal_url:
        print(f"공식 이미지 URL 없음: {pid}")
        continue

    download_image(
        normal_url,
        IMAGES / "official" / f"{pid}.png"
    )

    # 공식 일러스트 URL에서 이로치 주소 생성
    if "/official-artwork/" in normal_url:
        shiny_url = normal_url.replace(
            "/official-artwork/",
            "/official-artwork/shiny/"
        )

        download_image(
            shiny_url,
            IMAGES / "shiny" / f"{pid}.png"
        )

print("이미지 수집 처리 완료")


# ----------------------------------
# 2. 기존 데이터에서 특성 목록 추출
# ----------------------------------
generations = read_jsonl(
    PROCESSED / "pokemon_generations.jsonl"
)

ability_names = set()

for pokemon in generations:
    for ability in pokemon.get("abilities") or []:
        name = ability.get("name")

        if name:
            ability_names.add(name)


# ----------------------------------
# 3. 특성 한국어 이름 수집
# ----------------------------------
translations = {}
missing = []

for name in sorted(ability_names):
    url = f"https://pokeapi.co/api/v2/ability/{name}/"

    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()

        korean = next(
            (
                item["name"]
                for item in data.get("names", [])
                if item["language"]["name"] == "ko"
            ),
            None
        )

        if korean:
            translations[name] = korean
        else:
            missing.append(name)

        time.sleep(0.1)

    except requests.RequestException as e:
        print(f"특성 수집 오류: {name} - {e}")
        missing.append(name)


# ----------------------------------
# 4. 한국어 매핑 JSON 저장
# ----------------------------------
output = PROCESSED / "ability_names_ko.json"

output.write_text(
    json.dumps(
        translations,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

print(f"한국어 특성 수집: {len(translations)}개")
print(f"미확인 특성: {len(missing)}개")
print(f"미확인 목록: {missing}")
print("완료!")
