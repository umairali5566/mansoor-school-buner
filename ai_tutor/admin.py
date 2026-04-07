from django.contrib import admin

from .models import ChatHistory


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "short_question")
    list_filter = ("timestamp",)
    search_fields = ("user__username", "question", "answer")
    readonly_fields = ("user", "question", "answer", "timestamp")

    def has_add_permission(self, request):
        return False

    def short_question(self, obj):
        return obj.question[:60]

