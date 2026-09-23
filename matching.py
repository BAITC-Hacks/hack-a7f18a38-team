"""Deterministic matching against an editable JSON contractor catalog."""
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path


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


def load_profiles(path=None) -> list[dict]:
    path = Path(path) if path else Path(__file__).with_name("catalog.json")
    profiles = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("Каталог должен содержать непустой список подрядчиков.")
    ids = set()
    for p in profiles:
        for key in ("id", "name", "city", "category"):
            if not isinstance(p.get(key), str) or not p[key].strip():
                raise ValueError(f"В каталоге не заполнено поле {key}.")
        if p["id"] in ids:
            raise ValueError("В каталоге повторяется id.")
        ids.add(p["id"])
        for key in ("formats", "languages", "busy_dates"):
            if not isinstance(p.get(key), list) or any(not isinstance(v, str) for v in p[key]):
                raise ValueError(f"Поле {key} должно быть списком строк.")
        if not p["formats"] or not p["languages"]:
            raise ValueError("Укажите форматы и языки подрядчика.")
        for key in ("price_kzt", "max_hours"):
            if type(p.get(key)) is not int or p[key] <= 0:
                raise ValueError(f"Поле {key} должно быть положительным целым числом.")
        for value in p["busy_dates"]:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError("Неверная дата занятости в каталоге.")
    return profiles


def catalog_options(profiles):
    return {
        "cities": sorted({p["city"] for p in profiles}),
        "categories": sorted({p["category"] for p in profiles}),
        "formats": sorted({v for p in profiles for v in p["formats"]}),
        "languages": sorted({v for p in profiles for v in p["languages"]}),
    }


def recommend(request: Request, profiles: list[dict]) -> Result:
    try:
        if date.fromisoformat(request.event_date).isoformat() != request.event_date:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Введите существующую дату в формате ГГГГ-ММ-ДД.") from None
    if request.budget_kzt < 0:
        raise ValueError("Бюджет не может быть отрицательным.")
    if request.duration_hours is not None and request.duration_hours <= 0:
        raise ValueError("Длительность должна быть больше нуля.")
    counts = dict.fromkeys(("city", "format", "busy", "budget", "duration", "language"), 0)
    category = [p for p in profiles if p["category"] == request.category]
    matches = []
    for p in category:
        failures = {
            "city": p["city"] != request.city,
            "format": request.event_format not in p["formats"],
            "busy": request.event_date in p["busy_dates"],
            "budget": p["price_kzt"] > request.budget_kzt,
            "duration": request.duration_hours is not None and request.duration_hours > p["max_hours"],
            "language": request.language is not None and request.language not in p["languages"],
        }
        for key, failed in failures.items():
            counts[key] += int(failed)
        if not any(failures.values()):
            matches.append(p)
    matches.sort(key=lambda p: (p["price_kzt"], p["id"]))
    message = "Подходящие варианты (сначала дешевле):" if matches else (
        "Совпадений нет. Попробуйте изменить город, дату, категорию, бюджет, длительность или язык."
    )
    return Result(matches[:3], "ok" if matches else "no_matches", message, counts, len(category))


def format_result(result: Result, request: Request) -> str:
    lines = [result.message]
    for i, p in enumerate(result.profiles, 1):
        label = " [ДЕМО]" if p.get("demo", False) else ""
        lines.append(
            f"\n{i}. {p['name']}{label}\n{p['city']} · {p['category']}\n"
            f"Пакет: {p['price_kzt']:,} ₸, до {p['max_hours']} ч.\n"
            f"Языки: {', '.join(p['languages'])}\n"
            + ("Учебная карточка, реального исполнителя нет." if p.get("demo", False)
               else f"Контакт: {p.get('contact', 'не указан')}")
        )
    lines.append("\nПодбор по каталогу не является бронированием; цену и доступность нужно подтвердить.")
    return "\n".join(lines)
