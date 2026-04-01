# rag/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Health Check
    path('health/', views.health_check, name='health_check'),
    
    # Documents
    path('documents/upload/', views.upload_document, name='upload_document'),
    path('documents/', views.list_documents, name='list_documents'),
    path('documents/<int:document_id>/', views.delete_document, name='delete_document'),
    
    # Tasks
    path('tasks/<str:task_id>/', views.get_task_status, name='get_task_status'),
    
    # Q&A
    path('ask/', views.ask_question, name='ask_question'),
    
    # Conversations
    path('conversations/', views.list_conversations, name='list_conversations'),
    path('conversations/<int:conversation_id>/', views.get_conversation, name='get_conversation'),
    path('conversations/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    
    # Usage & Stats
    path('usage/', views.get_usage_stats, name='usage_stats'),
]