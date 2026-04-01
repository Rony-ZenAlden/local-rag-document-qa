# rag/views.py
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
from .models import Document, Conversation, Message, UsageLog, ProcessingTask
from .tasks import process_document_task
from .services.rag_engine import RAGEngine, list_all_indexes
import time
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Serializers
# =============================================================================

class DocumentSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = ['id', 'original_name', 'file', 'file_size', 'file_size_mb', 
                  'processed', 'processing_failed', 'error_message', 'uploaded_at']
        read_only_fields = ['file_size', 'processed', 'processing_failed', 
                           'error_message', 'uploaded_at']
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)
    
    def validate_file(self, value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are allowed")
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB"
            )
        return value


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'sources', 'created_at', 'tokens_used']
        read_only_fields = ['created_at', 'tokens_used']


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages', 'message_count']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()


class ProcessingTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingTask
        fields = ['task_id', 'status', 'progress', 'created_at', 
                  'completed_at', 'error_message']


class UsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageLog
        fields = ['id', 'action', 'tokens_input', 'tokens_output', 
                  'latency_ms', 'success', 'error_message', 'created_at']


class AskRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=2000, required=True)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_query(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Query must be at least 3 characters")
        dangerous_patterns = ['ignore previous', 'system prompt', 'developer mode', 
                             'bypass', 'jailbreak']
        for pattern in dangerous_patterns:
            if pattern in value.lower():
                raise serializers.ValidationError("Invalid query detected")
        return value


# =============================================================================
# Throttle Classes
# =============================================================================

class UploadRateThrottle(UserRateThrottle):
    rate = f'{getattr(settings, "MAX_FILES_PER_USER", 5)}/hour'

class AskRateThrottle(UserRateThrottle):
    rate = '60/hour'


# =============================================================================
# Helper: Get Anonymous ID
# =============================================================================

def get_anonymous_id(request):
    """Get consistent ID for anonymous users."""
    if hasattr(request, 'session') and request.session.session_key:
        return f"session_{request.session.session_key}"
    ip = request.META.get('REMOTE_ADDR', 'unknown').replace('.', '_')
    return f"session_{ip}"


# =============================================================================
# Document Upload Views
# =============================================================================

# In rag/views.py, replace the upload_document function with this:

# In rag/views.py, replace ONLY the upload_document function with this:

@api_view(['POST'])
@throttle_classes([UploadRateThrottle])
def upload_document(request):
    """Upload a PDF document for RAG processing (no auth)."""
    try:
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj = request.FILES['file']
        
        if not file_obj.name.lower().endswith('.pdf'):
            return Response({'error': 'Only PDF files are allowed'}, status=status.HTTP_400_BAD_REQUEST)
        
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_obj.size > max_size:
            return Response(
                {'error': f'File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save document (user is nullable)
        doc = Document.objects.create(
            original_name=file_obj.name,
            file=file_obj,
            file_size=file_obj.size
        )
        
        # Get anonymous ID
        anon_id = get_anonymous_id(request)  # Returns "session_XXX" or "public"
        logger.info(f"Upload from anonymous ID: {anon_id}")
        
        # ✅ Queue async processing with CORRECT parameters
        # Extract clean session_id (without 'session_' prefix) for RAGEngine
        session_id = None
        if anon_id and anon_id.startswith("session_"):
            session_id = anon_id.replace("session_", "")
            logger.info(f"Using session_id for vector index: {session_id}")
        
        task = process_document_task.delay(
            doc.id, 
            user_id=None,  # ✅ No authenticated user
            session_id=None  # ✅ Clean string for vector index isolation
        )
        
        # Create processing task record (user is nullable)
        ProcessingTask.objects.create(
            document=doc,
            task_id=task.id,
            status='pending',
            user_id=None  # ✅ No authenticated user
        )
        
        logger.info(f"Document uploaded: {doc.id}, {file_obj.name}, task: {task.id}")
        
        return Response({
            'message': 'Document uploaded successfully',
            'document_id': doc.id,
            'task_id': task.id,
            'status': 'processing'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return Response({'error': f'Upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_task_status(request, task_id):
    """Get status of document processing task."""
    try:
        task = ProcessingTask.objects.get(task_id=task_id)
        serializer = ProcessingTaskSerializer(task)
        return Response(serializer.data)
    except ProcessingTask.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def list_documents(request):
    """List all documents (public mode)."""
    try:
        docs = Document.objects.all().order_by('-uploaded_at')
        serializer = DocumentSerializer(docs, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': f'Failed to list documents: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def delete_document(request, document_id):
    """Delete a document and its vector index."""
    try:
        doc = Document.objects.get(id=document_id)
        anon_id = get_anonymous_id(request)
        engine = RAGEngine(session_id=anon_id.replace("session_", "") if anon_id.startswith("session_") else None)
        engine.delete_index()
        doc.delete()
        return Response({'message': 'Document deleted successfully'})
    except Document.DoesNotExist:
        return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Delete failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Q&A Views
# =============================================================================

@api_view(['POST'])
@throttle_classes([AskRateThrottle])
def ask_question(request):
    """Ask a question to the RAG system (no auth)."""
    try:
        serializer = AskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        conversation_id = serializer.validated_data.get('conversation_id')
        
        anon_id = get_anonymous_id(request)
        engine = RAGEngine(public=True)  # ✅ All users share same index
        start_time = time.time()
        result = engine.ask(query)
        latency = int((time.time() - start_time) * 1000)
        
        if not result['success']:
            UsageLog.objects.create(
                action='ask_question',
                success=False,
                error_message=result['answer'],
                latency_ms=latency
            )
            return Response({'error': result['answer']}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create conversation (user is nullable)
        if conversation_id:
            conversation = Conversation.objects.filter(id=conversation_id).first()
        if not conversation:
            conversation = Conversation.objects.create(title=query[:50] + '...' if len(query) > 50 else query)
        
        Message.objects.create(conversation=conversation, role='user', content=query)
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=result['answer'],
            sources=result['sources'],
            tokens_used=len(result['answer']) // 4
        )
        conversation.save()
        
        UsageLog.objects.create(
            action='ask_question',
            tokens_input=len(query) // 4,
            tokens_output=len(result['answer']) // 4,
            latency_ms=latency,
            success=True
        )
        
        return Response({
            'answer': result['answer'],
            'sources': result['sources'],
            'conversation_id': conversation.id,
            'latency_ms': latency
        })
        
    except Exception as e:
        return Response({'error': f'Question failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Conversation Views
# =============================================================================

@api_view(['GET'])
def list_conversations(request):
    """List all conversations."""
    try:
        convs = Conversation.objects.all().order_by('-updated_at')
        serializer = ConversationSerializer(convs, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': f'Failed to list conversations: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_conversation(request, conversation_id):
    """Get a specific conversation with messages."""
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)
    except Conversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Failed to get conversation: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def delete_conversation(request, conversation_id):
    """Delete a conversation."""
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        conversation.delete()
        return Response({'message': 'Conversation deleted'})
    except Conversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Delete failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Stats & Health Views
# =============================================================================

@api_view(['GET'])
def get_usage_stats(request):
    """Get usage statistics (global stats in public mode)."""
    try:
        from django.db.models import Sum
        stats = {
            'total_documents': Document.objects.count(),
            'total_conversations': Conversation.objects.count(),
            'total_questions': UsageLog.objects.filter(action='ask_question').count(),
            'total_tokens': UsageLog.objects.aggregate(
                total_input=Sum('tokens_input'),
                total_output=Sum('tokens_output')
            ),
            'recent_logs': UsageLogSerializer(
                UsageLog.objects.all().order_by('-created_at')[:10],
                many=True
            ).data,
            'vector_indexes': list_all_indexes()
        }
        return Response(stats)
    except Exception as e:
        return Response({'error': f'Failed to get stats: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    """Health check endpoint."""
    try:
        from django.db import connection
        connection.ensure_connection()
        db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'database': db_status,
        'version': '1.0.0'
    })