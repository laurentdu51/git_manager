from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from . import ssh_views

app_name = 'git_manager'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # Dépôts
    path('repos/', views.repos_view, name='repos'),
    path('repos/add/', views.add_repo, name='add_repo'),
    path('repos/create/', views.create_repo, name='create_repo'),
    path('repos/<int:pk>/', views.repo_detail, name='repo_detail'),
    path('repos/<int:pk>/delete/', views.delete_repo, name='delete_repo'),
    
    # Remotes
    path('remotes/', views.remotes_view, name='remotes'),
    path('remotes/add/', views.add_remote, name='add_remote'),
    path('remotes/<int:pk>/edit/', views.edit_remote, name='edit_remote'),
    path('remotes/<int:pk>/delete/', views.delete_remote, name='delete_remote'),
    path('remotes/<int:pk>/test/', views.test_remote, name='test_remote'),
    path('remotes/<int:pk>/fetch/', views.fetch_remote, name='fetch_remote'),
    path('remotes/<int:pk>/pull/', views.pull_remote, name='pull_remote'),
    path('remotes/push/', views.push_now, name='push_now'),
    
    # Surveillance
    path('monitors/', views.monitors_view, name='monitors'),
    path('api/check-remotes/', views.check_remotes_view, name='check_remotes'),
    
    # SSH multi-clés
    path('ssh/', ssh_views.ssh_view, name='ssh'),
    path('ssh/generate/', ssh_views.generate_key, name='ssh_generate'),
    path('ssh/upload/', ssh_views.upload_key, name='ssh_upload'),
    path('ssh/<str:name>/delete/', ssh_views.delete_key, name='ssh_delete'),
    path('ssh/<str:name>/pubkey/', ssh_views.show_public_key, name='ssh_pubkey'),
    path('ssh/rename/<str:name>/', ssh_views.rename_key, name='ssh_rename'),
    path('ssh/test/', ssh_views.test_connection, name='ssh_test'),
    
    # SSH local
    path('ssh/local/', views.ssh_local_view, name='ssh_local'),
    
    # Healthcheck
    path('api/health/', views.api_health, name='api_health'),

    # API
    path('api/status/', views.api_status, name='api_status'),
    path('api/repos/ids/', views.api_repos_ids, name='api_repos_ids'),
    path('api/repos/<int:pk>/ssh/', views.api_repo_ssh_config, name='api_repo_ssh'),
    
    # Logs
    path('logs/', views.logs_view, name='logs'),
    path('logs/file/', views.file_logs_view, name='file_logs'),
    path('logs/file/raw/', views.file_logs_raw, name='file_logs_raw'),
]

# Ajout des URLs pour les migrations
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)