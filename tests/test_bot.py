import os
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.ext import ConversationHandler
from bot import build_bot, STATES
from matching import load_profiles


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_conversation_and_validation(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123456:TEST_ONLY_NOT_A_REAL_TOKEN"}):
            app = build_bot(load_profiles())
        conversation = app.handlers[0][0]
        message = SimpleNamespace(text="/start", reply_text=AsyncMock())
        update = SimpleNamespace(message=message)
        context = SimpleNamespace(user_data={})
        state = await conversation.entry_points[0].callback(update, context)
        self.assertEqual(state, STATES["city"])
        for text, expected in [
            ("Нет города", "city"), ("Алматы", "date"),
            ("ошибка", "date"), ((date.today() + timedelta(days=30)).isoformat(), "format"),
            ("свадьба", "category"), ("Фотограф", "budget"),
            ("-5", "budget"), ("600 000 ₸", "duration"),
            ("0", "duration"), ("/skip", "language"),
        ]:
            message.text = text
            state = await conversation.states[state][0].callback(update, context)
            self.assertEqual(state, STATES[expected], text)
        message.text = "Не важно"
        state = await conversation.states[state][0].callback(update, context)
        self.assertEqual(state, ConversationHandler.END)
        self.assertTrue(any("ДЕМО" in call.args[0] for call in message.reply_text.call_args_list))
        state = await conversation.fallbacks[0].callback(update, context)
        self.assertEqual(state, ConversationHandler.END)
        self.assertEqual(context.user_data, {})


if __name__ == "__main__":
    unittest.main()
