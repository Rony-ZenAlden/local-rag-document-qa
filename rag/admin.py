from django.contrib import admin
from .models import Document, Conversation, Message, UsageLog, ProcessingTask

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['original_name', 'user', 'processed', 'uploaded_at']

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'created_at']

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'success', 'created_at']