import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from telegram.ext import ConversationHandler
from bot import build_bot, STATES, BACK, REFINE, NEW, SKIP
from matching import load_profiles


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN':'123456:TEST_ONLY_NOT_A_REAL_TOKEN'}):
            self.app = build_bot(load_profiles())
        self.conversation = self.app.handlers[0][0]
        self.message = SimpleNamespace(text='/start', reply_text=AsyncMock())
        self.update = SimpleNamespace(message=self.message)
        self.context = SimpleNamespace(user_data={})
        self.state = await self.conversation.entry_points[0].callback(self.update, self.context)

    async def send(self, text, expected):
        self.message.text = text
        self.state = await self.conversation.states[self.state][0].callback(self.update, self.context)
        self.assertEqual(self.state, STATES[expected], text)

    async def basic(self):
        for text, expected in [('Алматы','format'),('свадьба','category'),('Фотограф','date'),('10.10.2026','budget'),('600000','result')]:
            await self.send(text, expected)

    async def test_five_steps_refine_edit_and_restart(self):
        await self.basic()
        calls = [c.args[0] for c in self.message.reply_text.call_args_list]
        self.assertTrue(any('HK-53108' in c for c in calls))
        await self.send(REFINE,'duration')
        await self.send('10','language')
        await self.send('английский','result')
        await self.send('✏️ Изменить бюджет','budget')
        await self.send('1','result')
        self.assertTrue(any('Совпадений нет' in c.args[0] for c in self.message.reply_text.call_args_list))
        await self.send('📅 Изменить дату','date')
        await self.send('2026-10-17','result')
        await self.send(NEW,'city')
        self.assertIsNone(self.context.user_data['language'])

    async def test_validation_back_skip_cancel(self):
        await self.send('Нет города','city')
        await self.send('Алматы','format')
        await self.send(BACK,'city')
        await self.send('Алматы','format')
        await self.send('свадьба','category')
        await self.send('Фотограф','date')
        await self.send('2027-01-01','date')
        await self.send('10.10.2026','budget')
        await self.send('-1','budget')
        await self.send('500 000 ₸','result')
        await self.send(REFINE,'duration')
        await self.send('0','duration')
        await self.send('/skip','language')
        await self.send(SKIP,'result')
        self.assertEqual(await self.conversation.fallbacks[0].callback(self.update,self.context), ConversationHandler.END)
        self.assertEqual(self.context.user_data,{})


if __name__ == '__main__':
    unittest.main()
