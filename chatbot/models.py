from django.conf import settings
from django.db import models

from core.models import SingletonModel

DEFAULT_SUGGESTIONS = [
    'Tôi cần thay pin iPhone 11',
    'Màn hình nào tương thích với iPhone 13 Pro?',
    'Tìm giúp tôi chân sạc iPhone 12',
    'Pin iPhone 14 có những loại nào?',
    'Sản phẩm nào đang được giảm giá?',
    'Tôi muốn kiểm tra linh kiện còn hàng không',
]


def default_suggestions():
    return list(DEFAULT_SUGGESTIONS)


class ChatConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='chat_conversations')
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    title = models.CharField('Tiêu đề', max_length=60, blank=True)
    message_count = models.PositiveIntegerField('Số tin nhắn', default=0)
    has_error = models.BooleanField('Có lỗi', default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Hội thoại'
        verbose_name_plural = 'Hội thoại chatbot'
        ordering = ['-last_message_at', '-created_at']

    def __str__(self):
        return self.title or f'Hội thoại #{self.pk}'


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'Khách'
        ASSISTANT = 'assistant', 'iParts AI Assistant'

    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    products = models.JSONField('ID sản phẩm gợi ý', default=list, blank=True)
    intent = models.CharField('Ý định', max_length=50, blank=True, db_index=True)
    tool_calls = models.JSONField('Công cụ đã gọi', default=list, blank=True)
    meta = models.JSONField('Dữ liệu phụ (model/danh mục được hỏi, chế độ)', default=dict, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    is_error = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Tin nhắn'
        verbose_name_plural = 'Tin nhắn chatbot'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.get_role_display()}: {self.content[:50]}'


class ChatbotSetting(SingletonModel):
    cache_key = 'iparts:chatbot_setting'

    is_enabled = models.BooleanField('Bật chatbot', default=True)
    greeting_message = models.TextField(
        'Lời chào',
        default='Xin chào! Mình là iParts AI Assistant. Mình có thể giúp bạn tìm linh kiện, tư vấn sản phẩm '
                'và kiểm tra linh kiện tương thích với dòng iPhone của bạn.',
    )
    suggested_questions = models.JSONField('Câu hỏi gợi ý', default=default_suggestions, blank=True)
    extra_store_info = models.TextField('Thông tin cửa hàng bổ sung cho AI', blank=True)
    max_messages_per_hour_guest = models.PositiveIntegerField('Giới hạn/giờ (khách vãng lai)', default=20)
    max_messages_per_hour_customer = models.PositiveIntegerField('Giới hạn/giờ (khách hàng)', default=60)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cấu hình chatbot'
        verbose_name_plural = 'Cấu hình chatbot'

    def __str__(self):
        return 'Cấu hình iParts AI Assistant'
