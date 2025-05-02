from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from core.permissions import session_role_required

from core.views import (
    login_view, logout_view, register_view, home_view,
    users_view, create_user_view, edit_user_view, delete_user_view,
    approve_user_view, reject_user_view,
    project_list_view, project_create_view, project_edit_view, project_delete_view,
    project_detail_view, project_upload_file_view, project_add_test_view,
    project_sync_files_view, project_commit_upload_view,
    project_commits_view, commit_detail_view, delete_file_view,
    assignment_list_view, file_list_view, testresult_list_view,
    file_upload_view, file_versions_view, upload_file,
    assign_user, remove_user, project_tests_send_files_view,
    project_tests_mark_status_view
)

from functools import wraps
from django.shortcuts import redirect, render

from core.permissions import session_role_required

urlpatterns = [
    # Аутентификация
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),

    # Главная — доступна всем
    path('', home_view, name='home'),

    # Пользователи — только admin
    path('users/', session_role_required('admin')(users_view), name='users'),
    path('users/create/', lambda request: redirect('/register/')),
    path('users/edit/<int:id>/', session_role_required('admin')(edit_user_view), name='edit_user'),
    path('users/delete/<int:id>/', session_role_required('admin')(delete_user_view), name='delete_user'),
    path('users/approve/<int:user_id>/', session_role_required('admin')(approve_user_view), name='approve_user'),
    path('users/reject/<int:user_id>/', session_role_required('admin')(reject_user_view), name='reject_user'),

    # Проекты — dev, tester, manager, admin
    path('projects/', session_role_required('dev', 'tester', 'manager', 'admin')(project_list_view), name='project_list'),
    path('projects/create/', session_role_required('manager', 'admin')(project_create_view), name='project_create'),
    path('projects/<int:project_id>/', session_role_required('dev', 'tester', 'manager', 'admin')(project_detail_view), name='project_detail'),
    path('projects/edit/<int:project_id>/', session_role_required('manager', 'admin')(project_edit_view), name='project_edit'),
    path('projects/delete/<int:project_id>/', session_role_required('manager', 'admin')(project_delete_view), name='project_delete'),
    path('projects/<int:project_id>/upload/', session_role_required('dev', 'manager', 'admin')(project_upload_file_view), name='project_upload_file'),
    path('projects/<int:project_id>/add_test/', session_role_required('manager', 'tester', 'admin')(project_add_test_view), name='project_add_test'),
    path('projects/<int:project_id>/sync_files/', session_role_required('dev', 'manager', 'admin')(project_sync_files_view), name='project_sync_files'),
    path('projects/<int:project_id>/commit_upload/', session_role_required('dev', 'manager', 'admin')(project_commit_upload_view), name='project_commit_upload'),
    path('projects/<int:project_id>/assign_user/', session_role_required('manager', 'admin')(assign_user), name='assign_user'),
    path('projects/<int:project_id>/remove_user/', session_role_required('manager', 'admin')(remove_user), name='remove_user'),
    path('projects/<int:project_id>/commits/', session_role_required('dev', 'manager', 'admin')(project_commits_view), name='project_commits'),

    # Назначения — только manager и admin
    path('assignments/', session_role_required('manager', 'admin')(assignment_list_view), name='assignment_list'),

    # Файлы — manager, admin
    path('files/', session_role_required('manager', 'admin')(file_list_view), name='file_list'),
    path('files/upload/', session_role_required('manager', 'admin')(file_upload_view), name='file_upload'),
    path('files/delete/<int:file_id>/', session_role_required('manager', 'admin')(delete_file_view), name='delete_file'),
    path('files/versions/<int:file_id>/', session_role_required('manager', 'admin')(file_versions_view), name='file_versions'),

    # Коммиты — dev, manager, admin
    path('commits/<int:commit_id>/', session_role_required('dev', 'manager', 'admin')(commit_detail_view), name='commit_detail'),

    # Вспомогательные — dev, manager, admin
    path('upload/<int:task_id>/', session_role_required('dev', 'manager', 'admin')(upload_file), name='upload_file'),

    # Тесты — tester, manager, admin
    path('tests/', session_role_required('tester', 'manager', 'admin')(testresult_list_view), name='testresult_list'),
    path('projects/<int:project_id>/tests/add/', session_role_required('manager', 'tester', 'admin')(project_add_test_view), name='project_tests_add'),
    path('projects/<int:project_id>/tests/<int:test_id>/mark_status/<str:status>/', session_role_required('tester', 'manager', 'admin')(project_tests_mark_status_view), name='project_tests_mark_status'),
    path('projects/<int:project_id>/tests/<int:test_id>/send_files/', session_role_required('dev', 'manager', 'admin')(project_tests_send_files_view), name='project_tests_send_files'),
]

# Статика
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
