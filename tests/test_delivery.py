"""Exercise real Telegram update routing without making network requests."""
import os
import unittest
from unittest.mock import AsyncMock, patch

from telegram import Update, User
from telegram.ext import ExtBot
from bot import build_bot, REFINE
from matching import load_profiles


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': '123456:TEST_ONLY_NOT_A_REAL_TOKEN'}):
            self.app = build_bot(load_profiles())
        self.app.bot._bot_user = User(123456, 'Test bot', True, username='hackaton_Bags_bot')
        self.app._initialized = True
        self.sender = patch.object(ExtBot, 'send_message', new_callable=AsyncMock)
        self.sent = self.sender.start()
        self.addCleanup(self.sender.stop)
        self.errors = AsyncMock()
        self.app.add_error_handler(self.errors)
        self.sequence = 0

    async def deliver(self, text, *, chat_type='private', edited=False):
        self.sequence += 1
        message = {
            'message_id': self.sequence, 'date': 1790164800,
            'from': {'id': 777, 'first_name': 'Tester', 'is_bot': False},
            'chat': {'id': 777 if chat_type == 'private' else -777, 'type': chat_type},
            'text': text,
        }
        if text.startswith('/'):
            message['entities'] = [{'type': 'bot_command', 'offset': 0, 'length': len(text.split()[0])}]
        update = Update.de_json({'update_id': self.sequence, 'edited_message' if edited else 'message': message}, self.app.bot)
        await self.app.process_update(update)

    async def basic(self):
        for text in ['/start', 'Алматы', 'свадьба', 'Фотограф', '10.10.2026', '600000']:
            await self.deliver(text)
        self.assertEqual(self.app.user_data[777]['step'], 'result')
        self.errors.assert_not_awaited()

    async def test_group_cancel_does_not_clear_private_order(self):
        await self.deliver('/start')
        await self.deliver('Алматы')
        await self.deliver('/cancel@hackaton_Bags_bot', chat_type='group')
        await self.deliver('свадьба')
        self.errors.assert_not_awaited()
        self.assertEqual(self.app.user_data[777]['city'], 'Алматы')
        self.assertEqual(self.app.user_data[777]['step'], 'category')

    async def test_edited_messages_do_not_advance_conversation(self):
        await self.deliver('/start')
        await self.deliver('Алматы', edited=True)
        await self.deliver('/start', edited=True)
        self.errors.assert_not_awaited()
        self.assertEqual(self.app.user_data[777]['step'], 'city')
        await self.deliver('Алматы')
        self.assertEqual(self.app.user_data[777]['step'], 'format')

    async def test_qualified_skip_command(self):
        await self.basic()
        await self.deliver(REFINE)
        await self.deliver('/skip@hackaton_Bags_bot')
        self.assertEqual(self.app.user_data[777]['step'], 'language')
        self.assertIsNone(self.app.user_data[777]['duration_hours'])

    async def test_pasted_budget_with_narrow_spaces(self):
        for text in ['/start', 'Алматы', 'свадьба', 'Фотограф', '10.10.2026', '600\u202f000 ₸']:
            await self.deliver(text)
        self.assertEqual(self.app.user_data[777]['step'], 'result')
        self.assertEqual(self.app.user_data[777]['budget_kzt'], 600000)
        self.errors.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
