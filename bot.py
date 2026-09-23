"""Five-step Telegram search with optional refinements and back navigation."""
from datetime import date, timedelta
from pathlib import Path
import logging
import os
import sys

from matching import (Request, load_profiles, catalog_options, recommend, parse_date,
                      format_card, format_result, money, CALENDAR_END, CALENDAR_START)

ROOT = Path(__file__).parent
STATES = {name: i for i, name in enumerate(("city", "format", "category", "date", "budget", "result", "duration", "language"))}
BACK = "← Назад"
NEW = "🔎 Новый подбор"
REFINE = "⚙️ Уточнить подбор"
SKIP = "Не важно"


def _load_local_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_bot(profiles):
    from telegram import ReplyKeyboardMarkup, Update
    from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

    options = catalog_options(profiles)

    def keyboard(values, back=True):
        rows = [values[i:i + 2] for i in range(0, len(values), 2)]
        if back:
            rows.append([BACK])
        return ReplyKeyboardMarkup(rows, resize_keyboard=True)

    def choices(step, data):
        if step == "city":
            return options["cities"]
        if step == "format":
            return catalog_options([p for p in profiles if p["city"] == data["city"]])["formats"]
        if step == "category":
            return catalog_options([p for p in profiles if p["city"] == data["city"] and data["event_format"] in p["formats"]])["categories"]
        if step == "budget":
            return ["300 000 ₸", "500 000 ₸", "1 000 000 ₸", "3 000 000 ₸"]
        if step == "duration":
            return [SKIP, "4", "6", "8", "10", "12"]
        if step == "language":
            return [SKIP, *options["languages"]]
        if step == "date":
            today = date.today()
            values = [today, today + timedelta(days=1), today + timedelta(days=(5 - today.weekday()) % 7)]
            return list(dict.fromkeys(d.strftime("%d.%m.%Y") for d in values if CALENDAR_START <= d.isoformat() <= CALENDAR_END))
        return [NEW, REFINE]

    async def ask(update, context, step):
        data = context.user_data
        data["step"] = step
        prompts = {
            "city": f"✨ HackAlem\n\nНайдём подрядчика за пять шагов. В каталоге {len(profiles)} анонимных анкет хакатона, включая синтетические. Контактов в базе нет.\n\n1 / 5 · Где пройдёт мероприятие?",
            "format": "2 / 5 · Что планируете?\nВыберите формат мероприятия.",
            "category": "3 / 5 · Кто вам нужен?\nПоказываю категории для вашего города и мероприятия.",
            "date": "4 / 5 · Когда мероприятие?\nНапишите дату: 10.10.2026, или выберите кнопку.\nКалендарь базы: 23.09–31.12.2026.",
            "budget": "5 / 5 · Какой бюджет на одного подрядчика?\nВыберите сумму или напишите свою в тенге. Сравним с начальной ценой в базе.",
            "duration": "Уточним подбор · Сколько часов?\nВыберите длительность или «Не важно».",
            "language": "Уточним подбор · Какой язык нужен?",
            "result": "Что делаем дальше?",
        }
        await update.message.reply_text(prompts[step], reply_markup=keyboard(choices(step, data), step not in ("city", "result")))
        return STATES[step]

    async def start(update, context):
        context.user_data.clear()
        context.user_data.update(duration_hours=None, language=None)
        return await ask(update, context, "city")

    async def results(update, context):
        data = context.user_data
        request = Request(**{k: data[k] for k in ("city", "event_date", "event_format", "category", "budget_kzt", "duration_hours", "language")})
        result = recommend(request, profiles)
        summary = f"{request.city} · {request.event_format}\n{request.category} · {date.fromisoformat(request.event_date).strftime('%d.%m.%Y')}\nБюджет: {money(request.budget_kzt)}"
        if request.duration_hours:
            summary += f" · {request.duration_hours} ч."
        if request.language:
            summary += f" · {request.language}"
        await update.message.reply_text("✨ Ваш подбор\n\n" + summary + "\n\n" + result.message, reply_markup=keyboard([NEW, REFINE, "✏️ Изменить бюджет", "📅 Изменить дату"], False))
        for i, profile in enumerate(result.profiles, 1):
            await update.message.reply_text(format_card(profile, i))
        if result.profiles:
            await update.message.reply_text("По учебному календарю эти даты не заняты. Начальную цену и доступность нужно подтвердить; это не бронирование.")
        data["step"] = "result"
        return STATES["result"]

    async def handle(update, context):
        data = context.user_data
        step = data.get("step", "city")
        text = update.message.text.strip()
        if text == NEW:
            return await start(update, context)
        if text == BACK:
            data.pop("editing", None)
            previous = {"format":"city", "category":"format", "date":"category", "budget":"date", "duration":"result", "language":"duration"}.get(step, "city")
            if previous == "result":
                return await results(update, context)
            return await ask(update, context, previous)
        if step == "result":
            target = {REFINE:"duration", "✏️ Изменить бюджет":"budget", "📅 Изменить дату":"date"}.get(text)
            if target:
                data["editing"] = target in ("budget", "date")
                return await ask(update, context, target)
            await update.message.reply_text("Выберите действие кнопкой ниже или отправьте /start.")
            return STATES[step]
        if step in ("city", "format", "category", "language"):
            if text not in choices(step, data):
                await update.message.reply_text("Выберите один из вариантов на клавиатуре.")
                return STATES[step]
            key = "event_format" if step == "format" else step
            data[key] = None if step == "language" and text == SKIP else text
            if step == "language":
                return await results(update, context)
            return await ask(update, context, {"city":"format", "format":"category", "category":"date"}[step])
        if step == "date":
            try:
                data["event_date"] = parse_date(text)
            except ValueError as exc:
                await update.message.reply_text(str(exc))
                return STATES[step]
            if data.pop("editing", False):
                return await results(update, context)
            return await ask(update, context, "budget")
        if step == "budget":
            try:
                amount = int("".join(text.replace("₸", "").split()))
                if amount <= 0 or amount > 1_000_000_000:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Введите сумму от 1 до 1 000 000 000 ₸, например 500000.")
                return STATES[step]
            data["budget_kzt"] = amount
            data.pop("editing", None)
            return await results(update, context)
        if step == "duration":
            try:
                command = text.split()[0].split("@", 1)[0].casefold() if text else ""
                hours = None if text == SKIP or command == "/skip" else int(text)
                if hours is not None and not 1 <= hours <= 1000:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Введите целое число часов от 1 до 1000 или выберите «Не важно».")
                return STATES[step]
            data["duration_hours"] = hours
            return await ask(update, context, "language")

    async def cancel(update, context):
        context.user_data.clear()
        await update.message.reply_text("Подбор отменён. Начнём, когда будете готовы.", reply_markup=keyboard([NEW], False))
        return ConversationHandler.END

    async def help_message(update, context):
        if update.effective_message:
            await update.effective_message.reply_text("/start — новый подбор\n/cancel — отменить\n← Назад — вернуться на шаг\n\nБаза анонимизирована. Цены указаны «от», контактов нет. Календарь: 23.09–31.12.2026.")

    async def error(update, context):
        logging.error("Ошибка: %s", type(context.error).__name__)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Не удалось обработать запрос. Начните заново: /start")

    async def setup(app):
        await app.bot.set_my_commands([("start", "Найти подрядчика"), ("help", "Как это работает"), ("cancel", "Отменить")])
        print(f"Бот подключён: @{app.bot.username}", flush=True)

    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).concurrent_updates(False).post_init(setup).build()
    # Only new private messages may change an order. Edited messages have no
    # update.message, and context.user_data is shared with the same user's groups.
    private_message = filters.ChatType.PRIVATE & filters.UpdateType.MESSAGE
    private_text = private_message & filters.TEXT & ~filters.COMMAND
    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start, private_message), MessageHandler(private_text & filters.Regex("^" + NEW + "$"), start)],
        states={value: [MessageHandler(private_text, handle)] + ([CommandHandler("skip", handle, private_message)] if key == "duration" else []) for key, value in STATES.items()},
        fallbacks=[CommandHandler("cancel", cancel, private_message), CommandHandler("help", help_message, private_message)], allow_reentry=True,
    )
    app.add_handler(conversation)
    app.add_handler(CommandHandler("cancel", cancel, private_message))
    app.add_handler(MessageHandler(private_message, help_message))
    app.add_error_handler(error)
    return app


def run_demo(profiles):
    request = Request("Алматы", "2026-10-10", "свадьба", "Фотограф", 600000)
    result = recommend(request, profiles)
    print(format_result(result, request))
    return bool(result.profiles)


def main():
    try:
        profiles = load_profiles()
        if "--demo" in sys.argv:
            return 0 if run_demo(profiles) else 1
        _load_local_env()
        if not os.environ.get("TELEGRAM_BOT_TOKEN"):
            print("Вставьте токен в .env после TELEGRAM_BOT_TOKEN= и запустите start.bat.")
            return 1
        logging.basicConfig(level=logging.ERROR)
        app = build_bot(profiles)
        print("Подключаюсь к Telegram…", flush=True)
        app.run_polling(bootstrap_retries=0)
    except Exception as exc:
        print(f"Ошибка запуска: {type(exc).__name__}. Проверьте каталог, интернет и .env. Токен не отправляйте в чат.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
