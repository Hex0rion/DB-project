from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from core.views import (
    login_view, logout_view, register_view, home_view,
    users_view, create_user_view, edit_user_view, delete_user_view,
    approve_user_view, reject_user_view,
    project_list_view, project_create_view, project_edit_view, project_delete_view,
    project_detail_view, project_upload_file_view, project_add_test_view,
    project_assign_user_view, project_sync_files_view,
    assignment_list_view, file_list_view, testresult_list_view,
    file_upload_view, file_versions_view,
    upload_file
)
from django.conf import settings
from django.conf.urls.static import static
from core.views import project_commit_upload_view
from core.views import commit_detail_view
from core.views import project_commits_view  
from core.views import delete_file_view
from core import views
from core.views import assignment_list_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('', home_view, name='home'),
    path('users/', users_view, name='users'),
    path('users/create/', lambda request: redirect('/register/')),
    path('users/edit/<int:id>/', edit_user_view, name='edit_user'),
    path('users/delete/<int:id>/', delete_user_view, name='delete_user'),
    path('users/approve/<int:user_id>/', approve_user_view, name='approve_user'),
    path('users/reject/<int:user_id>/', reject_user_view, name='reject_user'),
    path('projects/', project_list_view, name='project_list'),
    path('projects/create/', project_create_view, name='project_create'),
    path('projects/<int:project_id>/', project_detail_view, name='project_detail'),
    path('projects/edit/<int:project_id>/', project_edit_view, name='project_edit'),
    path('projects/delete/<int:project_id>/', project_delete_view, name='project_delete'),
    path('assignments/', assignment_list_view, name='assignment_list'),
    path('files/', file_list_view, name='file_list'),
    path('tests/', testresult_list_view, name='testresult_list'),
    path('files/upload/', file_upload_view, name='file_upload'),
    path('files/versions/<int:file_id>/', file_versions_view, name='file_versions'),
    path('projects/<int:project_id>/upload/', project_upload_file_view, name='project_upload_file'),
    path('projects/<int:project_id>/add_test/', project_add_test_view, name='project_add_test'),
    path('projects/<int:project_id>/assign_user/', project_assign_user_view, name='project_assign_user'),
    path("projects/<int:project_id>/sync_files/", project_sync_files_view, name='project_sync_files'),
    path('upload/<int:task_id>/', upload_file, name='upload_file'),
    path('commits/<int:commit_id>/', commit_detail_view, name='commit_detail'),
    path('projects/<int:project_id>/commits/', project_commits_view, name='project_commits'),
    path('files/delete/<int:file_id>/', delete_file_view, name='delete_file'),
    path('assignments/', views.assignment_list_view, name='assignment_list_view'),
    path('projects/<int:project_id>/commit_upload/', project_commit_upload_view, name='project_commit_upload'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
