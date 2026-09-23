"""Rebuild both bot and website catalogs from the supplied CSV, without dependencies."""
import csv
import json
from pathlib import Path
from matching import ROOT, CALENDAR_START, CALENDAR_END, validate_profiles


def boolean(value):
    if value not in ("True", "False"):
        raise ValueError(f"Неверное логическое значение: {value!r}")
    return value == "True"


def read_dataset(path):
    profiles = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            split = lambda key: [v.strip() for v in row[key].split("|") if v.strip()]
            profiles.append({
                "id": row["id"], "name": row["anon_name"], "categories": split("categories"),
                "city": row["city"], "price_kzt": int(row["price_from_kzt"]),
                "formats": split("event_formats"), "languages": split("languages"),
                "max_hours": int(row["max_hours"]) if row["max_hours"].strip() else None,
                "busy_dates": split("busy_dates"), "description": row["description"],
                **{key: boolean(row[key]) for key in ("synthetic", "price_imputed", "city_imputed")},
            })
    return validate_profiles(profiles)


def main():
    profiles = read_dataset(ROOT / "data" / "contractors.csv")
    (ROOT / "catalog.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload = {"profiles": profiles, "calendarStart": CALENDAR_START, "calendarEnd": CALENDAR_END}
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (ROOT / "catalog-data.js").write_text("window.HACKALEM_DATA = " + encoded + ";\n", encoding="utf-8")
    print(f"Каталог обновлён: {len(profiles)} анкет. Бот и сайт используют одинаковые данные.")


if __name__ == "__main__":
    main()
