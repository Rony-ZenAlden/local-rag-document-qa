from rest_framework import serializers
from .models import Document, Conversation, Message, ProcessingTask

class DocumentSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    class Meta:
        model = Document
        fields = ['id', 'original_name', 'file', 'file_size', 'file_size_mb', 'processed', 'processing_failed', 'uploaded_at']
        read_only_fields = ['file_size', 'processed', 'uploaded_at']
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)
    def validate_file(self, value):
        if not value.name.endswith('.pdf'):
            raise serializers.ValidationError("Only PDF allowed")
        return value

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['role', 'content', 'sources', 'created_at']

class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'created_at', 'messages']

class ProcessingTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingTask
        fields = ['task_id', 'status', 'error_message']