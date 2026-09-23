"""Telegram polling bot and local demo runner for the HackAlem contractor catalog."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from matching import Request, catalog_options, format_result, load_profiles, recommend


ROOT = Path(__file__).parent
STATES = {"city": 1, "date": 2, "format": 3, "category": 4, "budget": 5, "duration": 6, "language": 7}


def _load_local_env() -> None:
    """Load simple KEY=value entries from .env without printing or exporting secrets."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value


def run_demo(profiles: list[dict[str, str]]) -> bool:
    """Run catalog-backed examples, date comparison, and a stable-order check."""
    dense = Request("Алматы", "2026-10-10", "свадьба", "Фотограф", 600_000)
    rare = Request("Алматы", "2026-10-10", "свадьба", "Фото и видеобудки", 500_000)
    empty = Request("Алматы", "2026-10-10", "свадьба", "Фотограф", 0)

    cases = [("1. Плотная категория: фотограф, Алматы, 10 октября", dense),
             ("2. Редкая категория: фото- и видеобудки, Алматы, 10 октября", rare),
             ("3. Нулевой результат: фотограф, бюджет 0 ₸", empty)]
    results = {}
    passed = True
    for title, request in cases:
        result = recommend(request, profiles)
        results[title] = result
        print(f"\n=== {title} ===")
        print(format_result(result, request))
    passed &= bool(results[cases[0][0]].profiles)
    passed &= bool(results[cases[1][0]].profiles)
    passed &= results[cases[2][0]].status == "no_matches"
    passed &= "бюджет" in results[cases[2][0]].message

    other_date = Request("Алматы", "2026-10-17", "свадьба", "Фотограф", 600_000)
    first = recommend(dense, profiles)
    second = recommend(other_date, profiles)
    print("\n=== Сравнение двух дат, один и тот же запрос ===")
    print(f"2026-10-10: {[p['id'] for p in first.profiles]}")
    print(f"2026-10-17: {[p['id'] for p in second.profiles]}")
    print(f"Занято в категории на даты: {first.rejection_counts['busy']} и {second.rejection_counts['busy']} из {first.category_count}")
    passed &= [p["id"] for p in first.profiles] != [p["id"] for p in second.profiles]

    repeated = recommend(dense, profiles)
    stable = [p["id"] for p in first.profiles] == [p["id"] for p in repeated.profiles]
    print(f"Повтор того же запроса: {'порядок совпал' if stable else 'ОШИБКА: порядок различается'}")
    passed &= stable
    print(f"\nИтог демо-проверки: {'ПРОЙДЕНА' if passed else 'ЕСТЬ ПРОБЛЕМА'}")
    return passed


def build_bot(profiles: list[dict[str, str]]):
    """Create a guided, keyboard-based Telegram conversation."""
    try:
        from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
        from telegram.ext import (
            Application, CommandHandler, ContextTypes, ConversationHandler,
            MessageHandler, filters,
        )
    except ImportError as exc:
        raise RuntimeError("Не установлена библиотека. Выполните: python -m pip install -r requirements.txt") from exc

    options = catalog_options(profiles)

    def keyboard(values: list[str]):
        return ReplyKeyboardMarkup([[value] for value in values], resize_keyboard=True, one_time_keyboard=True)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        notice = "В каталоге есть учебные карточки с пометкой ДЕМО.\n" if any(p.get("demo") for p in profiles) else ""
        await update.message.reply_text(notice + "Подберу до трёх подрядчиков из каталога. Выберите город:", reply_markup=keyboard(options["cities"]))
        return STATES["city"]

    async def city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = update.message.text.strip()
        if value not in options["cities"]:
            await update.message.reply_text("Выберите город кнопкой ниже.", reply_markup=keyboard(options["cities"]))
            return STATES["city"]
        context.user_data["city"] = value
        await update.message.reply_text("Введите дату в формате ГГГГ-ММ-ДД, например 2026-10-10:", reply_markup=ReplyKeyboardRemove())
        return STATES["date"]

    async def event_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        from datetime import date
        value = update.message.text.strip()
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError
            if parsed < date.today():
                await update.message.reply_text("Эта дата уже прошла. Введите сегодняшнюю или будущую дату:")
                return STATES["date"]
        except ValueError:
            await update.message.reply_text("Введите существующую дату в формате ГГГГ-ММ-ДД:")
            return STATES["date"]
        context.user_data["event_date"] = value
        await update.message.reply_text("Выберите тип мероприятия:", reply_markup=keyboard(options["formats"]))
        return STATES["format"]

    async def event_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = update.message.text.strip()
        if value not in options["formats"]:
            await update.message.reply_text("Выберите тип мероприятия кнопкой ниже.", reply_markup=keyboard(options["formats"]))
            return STATES["format"]
        context.user_data["event_format"] = value
        await update.message.reply_text("Выберите категорию подрядчика:", reply_markup=keyboard(options["categories"]))
        return STATES["category"]

    async def category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = update.message.text.strip()
        if value not in options["categories"]:
            await update.message.reply_text("Выберите категорию кнопкой ниже.", reply_markup=keyboard(options["categories"]))
            return STATES["category"]
        context.user_data["category"] = value
        await update.message.reply_text("Укажите бюджет в тенге, например 500000:", reply_markup=ReplyKeyboardRemove())
        return STATES["budget"]

    async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            value = int(update.message.text.strip().replace(" ", "").replace("₸", ""))
            if value <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите бюджет целым числом больше нуля, например 500000:")
            return STATES["budget"]
        context.user_data["budget_kzt"] = value
        await update.message.reply_text("Длительность в часах? Введите целое число или /skip:")
        return STATES["duration"]

    async def duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = update.message.text.strip()
        if value == "/skip":
            context.user_data["duration_hours"] = None
        else:
            try:
                hours = int(value)
                if hours <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Введите целое число часов больше нуля или нажмите /skip:")
                return STATES["duration"]
            context.user_data["duration_hours"] = hours
        choices = ["Не важно", *options["languages"]]
        await update.message.reply_text("Выберите язык или «Не важно»:", reply_markup=keyboard(choices))
        return STATES["language"]

    async def language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = update.message.text.strip()
        choices = ["Не важно", *options["languages"]]
        if value not in choices:
            await update.message.reply_text("Выберите язык кнопкой ниже.", reply_markup=keyboard(choices))
            return STATES["language"]
        request = Request(
            city=context.user_data["city"], event_date=context.user_data["event_date"],
            event_format=context.user_data["event_format"], category=context.user_data["category"],
            budget_kzt=context.user_data["budget_kzt"], duration_hours=context.user_data["duration_hours"],
            language=None if value == "Не важно" else value,
        )
        result = recommend(request, profiles)
        await update.message.reply_text(format_result(result, request), reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text("Чтобы подобрать ещё раз, отправьте /start.")
        return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        await update.message.reply_text("Подбор остановлен. Чтобы начать заново, отправьте /start.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STATES["city"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, city)],
            STATES["date"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_date)],
            STATES["format"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_format)],
            STATES["category"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, category)],
            STATES["budget"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
            STATES["duration"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, duration), CommandHandler("skip", duration)],
            STATES["language"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, language)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_message:
            await update.effective_message.reply_text("/start — начать подбор заново\n/cancel — отменить подбор\n/skip — пропустить длительность\n/help — помощь")

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
        # Do not log exception strings: request URLs may include the token.
        logging.error("Ошибка обработки: %s", type(context.error).__name__)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Не удалось обработать запрос. Начните заново: /start")

    async def setup_commands(application):
        await application.bot.set_my_commands([
            ("start", "Подобрать подрядчика"), ("cancel", "Отменить подбор"), ("help", "Помощь"),
        ])

    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).concurrent_updates(False).post_init(setup_commands).build()
    application.add_handler(conversation)
    application.add_handler(CommandHandler("help", help_message))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.ALL, help_message))
    application.add_error_handler(on_error)
    return application


def main() -> int:
    try:
        profiles = load_profiles()
    except (OSError, ValueError) as exc:
        print(f"Не удалось загрузить catalog.json: {exc}")
        return 1
    if "--demo" in sys.argv:
        return 0 if run_demo(profiles) else 1
    _load_local_env()
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("Не найден TELEGRAM_BOT_TOKEN. Скопируйте .env.example в .env и вставьте токен в .env.")
        print("Для локальной проверки каталога запустите: python bot.py --demo")
        return 1
    logging.basicConfig(level=logging.ERROR)
    try:
        app = build_bot(profiles)
    except (RuntimeError, ValueError):
        print("Проверьте зависимости и токен в .env. Установка зависимостей: setup.bat")
        return 1
    print("Подключаюсь к Telegram. Остановить: Ctrl+C")
    try:
        app.run_polling(bootstrap_retries=0)
    except Exception as exc:
        print(f"Не удалось запустить бота ({type(exc).__name__}). Проверьте интернет и токен в .env; закройте другие копии бота.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
