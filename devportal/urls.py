from django.contrib import admin
from django.urls import path
from core.views import login_view, logout_view
from core.views import register_view
from core.views import home_view
from core.views import users_view, create_user_view
from core.views import edit_user_view, delete_user_view
from core.views import approve_user_view
from core.views import reject_user_view
from django.shortcuts import redirect
from core.views import (
    project_list_view,
    project_create_view,
    project_edit_view,
    project_delete_view,
    project_detail_view,
)
from core.views import assignment_list_view, file_list_view, testresult_list_view
from core.views import file_upload_view
from core.views import file_versions_view
from core.views import (
    project_detail_view,
    project_upload_file_view,
    project_add_test_view,
    project_assign_user_view,
)
from core.views import project_sync_files_view 

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
    path('projects/', project_list_view, name='project_list'),
    path('assignments/', assignment_list_view, name='assignment_list'),
    path('files/', file_list_view, name='file_list'),
    path('tests/', testresult_list_view, name='testresult_list'),
    path('files/upload/', file_upload_view, name='file_upload'),
    path('files/versions/<int:file_id>/', file_versions_view, name='file_versions'),
    path('projects/<int:project_id>/', project_detail_view, name='project_detail'),
    path('projects/<int:project_id>/upload/', project_upload_file_view, name='project_upload_file'),
    path('projects/<int:project_id>/add_test/', project_add_test_view, name='project_add_test'),
    path('projects/<int:project_id>/assign_user/', project_assign_user_view, name='project_assign_user'),
    path("projects/<int:project_id>/upload/", project_upload_file_view, name="project_upload"),
    path('projects/<int:project_id>/sync_files/', project_sync_files_view, name='project_sync_files'),

]