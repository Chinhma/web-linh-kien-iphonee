from django import forms
from django.contrib import admin

from core.admin import SingletonAdmin

from .models import ChatbotSetting, ChatConversation, ChatMessage


class ChatbotSettingAdminForm(forms.ModelForm):
    suggested_questions = forms.CharField(
        label='Câu hỏi gợi ý', required=False, widget=forms.Textarea(attrs={'rows': 6, 'cols': 60}),
        help_text='Mỗi dòng một câu hỏi (tối đa 10).')

    class Meta:
        model = ChatbotSetting
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        questions = self.instance.suggested_questions if self.instance.pk else []
        if isinstance(questions, list):
            self.initial['suggested_questions'] = '\n'.join(str(q) for q in questions)

    def clean_suggested_questions(self):
        lines = (self.cleaned_data.get('suggested_questions') or '').splitlines()
        return [q.strip()[:120] for q in lines if q.strip()][:10]


@admin.register(ChatbotSetting)
class ChatbotSettingAdmin(SingletonAdmin):
    form = ChatbotSettingAdminForm


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    can_delete = False
    fields = ['created_at', 'role', 'content', 'intent', 'tool_calls', 'latency_ms', 'is_error']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'user', 'message_count', 'has_error', 'last_message_at']
    list_filter = ['has_error', 'created_at']
    search_fields = ['title', 'user__email', 'messages__content']
    readonly_fields = ['user', 'session_key', 'title', 'message_count', 'has_error', 'created_at', 'last_message_at']
    inlines = [ChatMessageInline]

    def has_add_permission(self, request):
        return False
