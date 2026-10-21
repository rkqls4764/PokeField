import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

main_path = DATA / "ability_names_ko.json"
manual_path = DATA / "ability_names_manual_ko.json"

# 기존 한국어 데이터 로드
with open(main_path, encoding="utf-8") as f:
    translations = json.load(f)

# 수동 번역 데이터 로드
with open(manual_path, encoding="utf-8") as f:
    manual = json.load(f)

# 기존 번역이 없는 특성만 추가
added = {}

for key, value in manual.items():
    if key not in translations:
        translations[key] = value
        added[key] = value

# 기존 JSON 파일에 병합 결과 저장
with open(main_path, "w", encoding="utf-8") as f:
    json.dump(translations, f, ensure_ascii=False, indent=2)

print(f"추가된 특성: {len(added)}개")
print(f"전체 한국어 특성: {len(translations)}개")

for key, value in added.items():
    print(f"{key} → {value}")