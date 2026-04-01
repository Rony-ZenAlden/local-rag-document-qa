# rag/tasks.py - COMPLETE FIXED VERSION
from celery import shared_task
from django.core.files.storage import default_storage
from .models import Document, ProcessingTask, UsageLog
from .services.rag_engine import RAGEngine
import time
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_document_task(self, document_id, user_id=None, session_id=None):
    """
    Async task to process uploaded PDF and create vector index.
    
    Args:
        document_id: ID of the Document to process (integer)
        user_id: Optional Django User ID for database association (integer or None)
        session_id: Optional session identifier for vector index isolation (string, without 'session_' prefix)
    """
    try:
        # Get document
        doc = Document.objects.get(id=document_id)
        
        # ✅ Convert user_id to integer or None for database
        db_user_id = user_id if isinstance(user_id, int) else None
        
        # ✅ Use get_or_create to avoid UNIQUE constraint errors
        task_obj, created = ProcessingTask.objects.get_or_create(
            task_id=self.request.id,
            defaults={
                'document': doc,
                'status': 'processing',
                'user_id': db_user_id,
                'progress': 0
            }
        )
        
        # If task wasn't newly created, update its status
        if not created:
            task_obj.status = 'processing'
            task_obj.progress = 0
            task_obj.error_message = None
            task_obj.save()
        
        # Get file path
        file_path = default_storage.path(doc.file.name)
        logger.info(f"Processing document {document_id}: {file_path}")
        
        # ✅ Initialize RAG engine with session_id for vector index (not user_id)
        if session_id:
            engine = RAGEngine(session_id=session_id)
        elif db_user_id:
            engine = RAGEngine(user_id=db_user_id)
        else:
            engine = RAGEngine(public=True)  # ✅ Default to public
        
        # Process PDF
        start_time = time.time()
        success, message = engine.process_pdf(file_path)
        latency = int((time.time() - start_time) * 1000)
        
        if success:
            # Update document status
            doc.processed = True
            doc.save()
            
            # Update task status
            task_obj.status = 'completed'
            task_obj.completed_at = timezone.now()
            task_obj.progress = 100
            task_obj.save()
            
            # Log success
            UsageLog.objects.create(
                user_id=db_user_id,
                action='document_upload',
                tokens_input=doc.file_size // 100,
                latency_ms=latency,
                success=True
            )
            
            logger.info(f"Document {document_id} processed successfully for {session_id or db_user_id or 'public'}")
            return {'status': 'completed', 'document_id': document_id}
            
        else:
            # Update document status
            doc.processing_failed = True
            doc.error_message = message
            doc.save()
            
            # Update task status
            task_obj.status = 'failed'
            task_obj.error_message = message
            task_obj.save()
            
            # Log failure
            UsageLog.objects.create(
                user_id=db_user_id,
                action='document_upload',
                error_message=message,
                latency_ms=latency,
                success=False
            )
            
            logger.error(f"Document {document_id} processing failed: {message}")
            return {'status': 'failed', 'error': message}
            
    except Document.DoesNotExist:
        error_msg = f"Document {document_id} not found"
        logger.error(error_msg)
        ProcessingTask.objects.filter(task_id=self.request.id).update(
            status='failed',
            error_message=error_msg
        )
        return {'status': 'failed', 'error': error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        ProcessingTask.objects.filter(task_id=self.request.id).update(
            status='failed',
            error_message=error_msg
        )
        return {'status': 'failed', 'error': error_msg}