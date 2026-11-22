"""Test tương thích, chuẩn hóa model và chatbot (tools, fallback, rate limit, history)."""

import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from chatbot.models import ChatbotSetting, ChatConversation
from chatbot.services import tools
from core.tests.factories import make_customer, make_model, make_product, verify
from products.models import Product
from products.selectors import compatibility_lookup
from products.services import resolve_iphone_model

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest', 'content_type': 'application/json'}


class CompatibilityTests(TestCase):
    def setUp(self):
        for name, series in [('iPhone 13', 13), ('iPhone 13 mini', 13), ('iPhone 13 Pro', 13), ('iPhone 13 Pro Max', 13),
                             ('iPhone 11', 11), ('iPhone 11 Pro', 11), ('iPhone XS Max', 10)]:
            make_model(name, series)

    def test_resolve_variants(self):
        cases = {'ip13 pro': 'iPhone 13 Pro', 'iphone 13pro': 'iPhone 13 Pro', '13 promax': 'iPhone 13 Pro Max',
                 'i13 pm': 'iPhone 13 Pro Max', 'IPHONE 13 MINI': 'iPhone 13 mini', 'xs max': 'iPhone XS Max'}
        for text, expected in cases.items():
            result = resolve_iphone_model(text)
            self.assertEqual(result['model'].name if result['model'] else None, expected, text)
            self.assertFalse(result['ambiguous'], text)

    def test_ambiguous_generation(self):
        result = resolve_iphone_model('Có màn cho iPhone 13 không')
        self.assertTrue(result['ambiguous'])
        self.assertEqual(len(result['candidates']), 4)

    def test_unknown_model(self):
        self.assertIsNone(resolve_iphone_model('iPhone 6')['model'])

    def test_lookup_only_verified_and_active(self):
        model = make_model('iPhone 13 Pro')
        ok = make_product('A', 'IP-BAT-A-001')
        unverified = make_product('B', 'IP-BAT-B-001')
        inactive = make_product('C', 'IP-BAT-C-001', status=Product.Status.DISCONTINUED)
        verify(ok, model)
        verify(unverified, model, 'unverified')
        verify(inactive, model)
        self.assertEqual([c.product for c in compatibility_lookup(model)], [ok])


@override_settings(GEMINI_API_KEY='')
class ChatbotTests(TestCase):
    def setUp(self):
        cache.clear()
        self.model = make_model('iPhone 13 Pro')
        self.product = make_product('Pin iPhone 13 Pro', 'IP-BAT-13PRO-001', cost_price=123456)
        verify(self.product, self.model)

    def test_tools_return_db_data_without_cost_price(self):
        result = tools.check_compatibility('ip 13 pro', 'pin')
        self.assertEqual(result['products'][0]['id'], self.product.pk)
        self.assertNotIn('cost_price', json.dumps(result))
        self.assertNotIn('123456', json.dumps(tools.get_product_detail(product_id=self.product.pk)))

    def test_fallback_without_api_key(self):
        r = self.client.post('/api/chatbot/message/', json.dumps({'message': 'Pin iPhone 13 Pro giá bao nhiêu?'}), **AJAX)
        data = r.json()['data']
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data['mode'], 'basic')
        self.assertEqual(data['products'][0]['id'], self.product.pk)
        types = [a['type'] for a in data['actions']]
        self.assertIn('login', types)  # Guest nhận nút Đăng nhập
        self.assertNotIn('add_to_cart', types)  # ...và không có nút Thêm vào giỏ

    @override_settings(GEMINI_API_KEY='fake-key')
    def test_gemini_error_falls_back(self):
        from chatbot.services import gemini_client

        with mock.patch.object(gemini_client, 'generate_reply', side_effect=gemini_client.GeminiUnavailable('503')):
            r = self.client.post('/api/chatbot/message/', json.dumps({'message': 'Pin iPhone 13 Pro'}), **AJAX)
        self.assertEqual(r.json()['data']['mode'], 'basic')

    def test_rate_limit_429(self):
        setting = ChatbotSetting.get_solo()
        setting.max_messages_per_hour_guest = 2
        setting.save()
        for _ in range(2):
            self.client.post('/api/chatbot/message/', json.dumps({'message': 'xin chào'}), **AJAX)
        r = self.client.post('/api/chatbot/message/', json.dumps({'message': 'xin chào'}), **AJAX)
        self.assertEqual(r.status_code, 429)

    def test_history_only_own_conversation(self):
        other = ChatConversation.objects.create(user=make_customer('khac'), title='bí mật')
        self.client.force_login(make_customer())
        r = self.client.get(f'/api/chatbot/history/?conversation_id={other.pk}')
        self.assertIsNone(r.json()['data']['conversation_id'])

    def test_empty_and_too_long_message(self):
        self.assertEqual(self.client.post('/api/chatbot/message/', json.dumps({'message': ' '}), **AJAX).status_code, 400)
        self.assertEqual(self.client.post('/api/chatbot/message/', json.dumps({'message': 'a' * 1001}), **AJAX).status_code, 400)
