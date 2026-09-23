"""Shared catalog contract and deterministic matching for HackAlem."""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import json

ROOT = Path(__file__).parent
CALENDAR_START = "2026-09-23"
CALENDAR_END = "2026-12-31"


@dataclass(frozen=True)
class Request:
    city: str
    event_date: str
    event_format: str
    category: str
    budget_kzt: int
    duration_hours: int | None = None
    language: str | None = None


@dataclass
class Result:
    profiles: list[dict]
    status: str
    message: str
    rejection_counts: dict[str, int]
    category_count: int
    total: int = 0


def parse_date(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(value.strip(), fmt).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError("Введите дату, например 10.10.2026.")
    if not CALENDAR_START <= parsed.isoformat() <= CALENDAR_END:
        raise ValueError("В базе есть расписание только с 23.09 по 31.12.2026. Выберите дату в этом периоде.")
    return parsed.isoformat()


def validate_profiles(profiles):
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("Каталог пуст или имеет неверный формат.")
    ids = set()
    for p in profiles:
        for key in ("id", "name", "city", "description"):
            if not isinstance(p.get(key), str) or not p[key].strip():
                raise ValueError(f"Не заполнено поле {key}.")
        if p["id"] in ids:
            raise ValueError(f"Повторяющийся id: {p['id']}")
        ids.add(p["id"])
        for key in ("categories", "formats", "languages", "busy_dates"):
            values = p.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"Неверное поле {key}: {p['id']}")
            if key != "busy_dates" and not values:
                raise ValueError(f"Пустое поле {key}: {p['id']}")
        if type(p.get("price_kzt")) is not int or p["price_kzt"] <= 0:
            raise ValueError("Цена должна быть положительным целым числом.")
        hours = p.get("max_hours")
        if hours is not None and (type(hours) is not int or hours <= 0):
            raise ValueError("Неверная длительность.")
        for key in ("synthetic", "price_imputed", "city_imputed"):
            if type(p.get(key)) is not bool:
                raise ValueError(f"Неверный флаг {key}.")
        for value in p["busy_dates"]:
            if date.fromisoformat(value).isoformat() != value or not CALENDAR_START <= value <= CALENDAR_END:
                raise ValueError("Дата занятости вне календаря базы.")
    return profiles


def load_profiles(path=None):
    return validate_profiles(json.loads((Path(path) if path else ROOT / "catalog.json").read_text(encoding="utf-8-sig")))


def catalog_options(profiles):
    return {
        "cities": sorted({p["city"] for p in profiles}),
        "categories": sorted({v for p in profiles for v in p["categories"]}),
        "formats": sorted({v for p in profiles for v in p["formats"]}),
        "languages": sorted({v for p in profiles for v in p["languages"]}),
    }


def recommend(request: Request, profiles: list[dict]) -> Result:
    event_date = parse_date(request.event_date)
    if request.budget_kzt < 0:
        raise ValueError("Бюджет не может быть отрицательным.")
    if request.duration_hours is not None and request.duration_hours <= 0:
        raise ValueError("Длительность должна быть больше нуля.")
    candidates = [p for p in profiles if request.category in p["categories"]]
    counts = dict.fromkeys(("city", "format", "busy", "budget", "duration", "language"), 0)
    matches = []
    for p in candidates:
        failures = {
            "city": p["city"] != request.city,
            "format": request.event_format not in p["formats"],
            "busy": event_date in p["busy_dates"],
            "budget": p["price_kzt"] > request.budget_kzt,
            # Empty max_hours is 'not applicable' in the supplied preview, not zero.
            "duration": request.duration_hours is not None and p["max_hours"] is not None and request.duration_hours > p["max_hours"],
            "language": request.language is not None and request.language not in p["languages"],
        }
        for key, failed in failures.items():
            counts[key] += int(failed)
        if not any(failures.values()):
            matches.append(p)
    matches.sort(key=lambda p: (p["price_kzt"], p["id"]))
    message = f"Найдено: {len(matches)}. Показываю до трёх вариантов, сначала дешевле." if matches else "Совпадений нет. Увеличьте бюджет или измените дату и параметры."
    return Result(matches[:3], "ok" if matches else "no_matches", message, counts, len(candidates), len(matches))


def money(value):
    return f"{value:,}".replace(",", " ") + " ₸"


def format_card(p, index=None):
    title = f"{index}. " if index else ""
    lines = [title + p["name"], " · ".join(p["categories"]), f"📍 {p['city']}   •   от {money(p['price_kzt'])}"]
    if p["max_hours"] is not None:
        lines.append(f"🕒 До {p['max_hours']} ч.   •   {', '.join(p['languages'])}")
    else:
        lines.append(f"Языки: {', '.join(p['languages'])}. Лимит часов не применим.")
    description = " ".join(p["description"].split())
    lines.append("\n" + (description[:317] + "…" if len(description) > 320 else description))
    flags = []
    if p["synthetic"]:
        flags.append("Синтетический профиль")
    if p["price_imputed"]:
        flags.append("Цена заполнена при подготовке базы")
    if p["city_imputed"]:
        flags.append("Город заполнен при подготовке базы")
    if flags:
        lines.append("\nℹ️ " + ". ".join(flags))
    lines.append(f"ID: {p['id']} · Анонимная анкета, контактов в базе нет.")
    return "\n".join(lines)


def format_result(result, request):
    return "\n\n".join([result.message, *(format_card(p, i) for i, p in enumerate(result.profiles, 1)), "Начальная цена и календарь взяты из учебной базы; это не подтверждённое бронирование."])
