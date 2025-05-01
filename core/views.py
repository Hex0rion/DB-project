from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from core.models import User
from django.contrib.auth.decorators import login_required
from core.models import Project
from django.contrib.auth.hashers import check_password
from django.db import connection
import re
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden, Http404
from core.models import Project
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.contrib.messages import get_messages
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages

def login_view(request):
    if request.method == 'POST':
        login_input = request.POST.get('username')
        password = request.POST.get('password')

        try:
            user = User.objects.get(login=login_input)

            if check_password(password, user.password):
                if user.role == 'pending':
                    messages.error(request, 'Ваша учетная запись ожидает подтверждения администратора.')
                    return redirect('/login/')

                response = redirect('/')
                response.set_cookie('user_id', user.id)
                response.set_cookie('user_role', user.role)
                response.set_cookie('user_name', user.full_name)
                return response
            else:
                messages.error(request, 'Неверный логин или пароль.')
        except User.DoesNotExist:
            messages.error(request, 'Пользователь не найден.')

    return render(request, 'core/login.html', {'show_login_messages': True})




def logout_view(request):
    response = redirect('/login/')
    response.delete_cookie('user_id')
    response.delete_cookie('user_role')
    response.delete_cookie('username')
    return response

def approve_user_view(request, user_id):
    if request.COOKIES.get('user_role') != 'admin':
        return HttpResponseForbidden("Доступ запрещен")

    with connection.cursor() as cursor:
        cursor.execute("SELECT role, desired_role, login FROM users WHERE id = %s", [user_id])
        result = cursor.fetchone()

        if not result:
            return HttpResponseNotFound("Пользователь не найден")

        role, desired_role, login = result

        if role == 'pending' and desired_role:
            cursor.execute("""
                UPDATE users
                SET role = %s,
                    desired_role = NULL
                WHERE id = %s
            """, [desired_role, user_id])

            messages.success(request, f"Роль пользователя {login} подтверждена.")

    return redirect('/users/')


def register_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        login_input = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        desired_role = request.POST.get("desired_role", "guest") or "guest"
        role = desired_role if desired_role == 'guest' else 'pending'

        # Для возврата значений в шаблон при ошибке
        context = {
            'full_name': full_name,
            'username': login_input,
            'email': email,
            'desired_role': desired_role,
        }

        # Проверки
        if not all([full_name, login_input, email, password, password2, desired_role]):
            messages.error(request, 'Все поля обязательны!')
            return render(request, 'core/register.html', context)

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            messages.error(request, 'Некорректный email.')
            return render(request, 'core/register.html', context)

        if password != password2:
            messages.error(request, 'Пароли не совпадают!')
            return render(request, 'core/register.html', context)

        if desired_role not in ['admin', 'manager', 'dev', 'tester', 'guest']:
            messages.error(request, 'Некорректная желаемая роль.')
            return render(request, 'core/register.html', context)

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users WHERE login = %s", [login_input])
            if cursor.fetchone()[0] > 0:
                messages.error(request, 'Такой логин уже существует!')
                return render(request, 'core/register.html', context)

            cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s", [email])
            if cursor.fetchone()[0] > 0:
                messages.error(request, 'Этот email уже используется!')
                return render(request, 'core/register.html', context)

            hashed_password = make_password(password)
            cursor.execute("""
                INSERT INTO users (full_name, login, email, password, role, desired_role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [full_name, login_input, email, hashed_password, role, desired_role])

        messages.success(request, 'Успешная регистрация. Теперь войдите.')
        return redirect('/login/')

    return render(request, 'core/register.html')


def reject_user_view(request, user_id):
    if request.COOKIES.get('user_role') != 'admin':
        return HttpResponseForbidden("Доступ запрещен")

    with connection.cursor() as cursor:
        cursor.execute("SELECT role, desired_role, login FROM users WHERE id = %s", [user_id])
        result = cursor.fetchone()

        if not result:
            return HttpResponseNotFound("Пользователь не найден")

        role, desired_role, login = result

        if role == 'pending' and desired_role:
            cursor.execute("""
                UPDATE users
                SET desired_role = NULL
                WHERE id = %s
            """, [user_id])

            messages.info(request, f"Заявка на роль у пользователя {login} отклонена.")

    return redirect('/users/')



def home_view(request):
    user_id = request.COOKIES.get('user_id')
    role = request.COOKIES.get('user_role')
    username = request.COOKIES.get('user_name')

    if not user_id:
        return redirect('/login/')

    projects = Project.objects.all().only('id', 'name')

    return render(request, 'core/home.html', {
        'username': username,
        'role': role,
        'projects': projects,
    })

def users_view(request):
    if request.COOKIES.get('user_role') != 'admin':
        return HttpResponseForbidden("Доступ запрещен")

    search = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    query = "SELECT id, full_name, login, role, desired_role FROM users WHERE 1=1"
    params = []

    if search:
        query += " AND login LIKE %s"
        params.append(f"%{search}%")
    if role_filter:
        query += " AND role = %s"
        params.append(role_filter)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    users = [
        {
            'id': row[0],
            'full_name': row[1],
            'login': row[2],
            'role': row[3],
            'desired_role': row[4],
        }
        for row in rows
    ]

    return render(request, 'core/users.html', {
        'users': users,
        'search': search,
        'role_filter': role_filter,
    })




def create_user_view(request):
    if request.COOKIES.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        login = request.POST.get('login')
        password = request.POST.get('password')
        role = request.POST.get('role')

        # Если роль — гость, то желаемую роль указывать не нужно
        desired_role = None if role == 'guest' else role
        email = ''  # если не используется — можно оставить пустым

        if not (full_name and login and password and role):
            messages.error(request, 'Все поля обязательны.')
            return render(request, 'core/create_user.html')

        if User.objects.filter(login=login).exists():
            messages.error(request, 'Такой логин уже существует.')
            return render(request, 'core/create_user.html')

        hashed_password = make_password(password)

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (full_name, login, email, password, role, desired_role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [full_name, login, email, hashed_password, role, desired_role])

        messages.success(request, 'Пользователь успешно создан.')
        return redirect('/users/')

    return render(request, 'core/create_user.html')



def edit_user_view(request, id):
    if request.COOKIES.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')

    try:
        user = User.objects.get(id=id)
    except User.DoesNotExist:
        messages.error(request, 'Пользователь не найден.')
        return redirect('/users/')

    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE users SET role = %s WHERE id = %s", [new_role, id])
            messages.success(request, 'Роль обновлена.')
            return redirect('/users/')

    return render(request, 'core/edit_user.html', {'user': user})


def delete_user_view(request, id):
    if request.COOKIES.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", [id])
    messages.success(request, 'Пользователь удалён.')
    return redirect('/users/')

from datetime import datetime


from datetime import datetime

from datetime import datetime, date
from django.shortcuts import render, redirect
from django.db import connection

from datetime import datetime, date

def project_list_view(request):
    user_role = request.COOKIES.get('user_role')
    if not user_role:
        return redirect('/login/')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, start_date, end_date, status FROM projects")
        rows = cursor.fetchall()

    now = date.today()
    projects = []

    for row in rows:
        id, name, start_date, end_date, status = row

        # Преобразуем datetime → date, если необходимо
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()

        status_class = ""

        if start_date and end_date and start_date < end_date and status != 'завершён':
            total_duration = (end_date - start_date).days
            time_left = (end_date - now).days
            passed_percent = 1 - time_left / total_duration if total_duration > 0 else 1

            if time_left < 0:
                status_class = "status-overdue"
            elif passed_percent >= 0.9:
                status_class = "status-10"
            elif passed_percent >= 0.7:
                status_class = "status-30"
            elif passed_percent >= 0.5:
                status_class = "status-50"
            else:
                status_class = "status-healthy"

        projects.append({
            'id': id,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'status': status,
            'status_class': status_class,
        })

    return render(request, 'core/projects.html', {
        'projects': projects,
        'role': user_role,
    })


from datetime import datetime

def project_create_view(request):
    user_role = request.COOKIES.get('user_role')
    if user_role not in ['admin', 'manager']:
        return HttpResponseForbidden("Доступ запрещён")

    VALID_STATUSES = ['в работе', 'на паузе', 'завершён', 'отменён', 'планируется']

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        status = request.POST.get('status', '').strip()

        if not name or not status:
            messages.error(request, "Название и статус обязательны.")
            return render(request, 'core/project_create.html', {
                'statuses': VALID_STATUSES,
                'input': request.POST,
            })

        if status not in VALID_STATUSES:
            messages.error(request, "Недопустимый статус проекта.")
            return render(request, 'core/project_create.html', {
                'statuses': VALID_STATUSES,
                'input': request.POST,
            })

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
        except ValueError:
            messages.error(request, "Некорректный формат даты. Используйте YYYY-MM-DD.")
            return render(request, 'core/project_create.html', {
                'statuses': VALID_STATUSES,
                'input': request.POST,
            })

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM projects WHERE name = %s", [name])
            if cursor.fetchone()[0] > 0:
                messages.error(request, "Проект с таким названием уже существует.")
                return render(request, 'core/project_create.html', {
                    'statuses': VALID_STATUSES,
                    'input': request.POST,
                })

            cursor.execute("""
                INSERT INTO projects (name, start_date, end_date, status)
                VALUES (%s, %s, %s, %s)
            """, [name, start_date or None, end_date or None, status])

        messages.success(request, "Проект успешно создан.")
        return redirect('/projects/')

    return render(request, 'core/project_create.html', {
        'statuses': VALID_STATUSES
    })




from django.http import HttpResponseNotFound

def project_edit_view(request, project_id):
    user_role = request.COOKIES.get('user_role')
    if user_role not in ['admin', 'manager']:
        return HttpResponseForbidden("Доступ запрещён")

    VALID_STATUSES = ['в работе', 'на паузе', 'завершён', 'отменён', 'планируется']

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name, start_date, end_date, status FROM projects WHERE id = %s", [project_id])
        row = cursor.fetchone()

    if not row:
        return HttpResponseNotFound("Проект не найден")

    project = {
        'id': row[0],
        'name': row[1],
        'start_date': row[2],
        'end_date': row[3],
        'status': row[4],
    }

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        status = request.POST.get('status', '').strip()

        if not name or not status:
            messages.error(request, "Название и статус обязательны.")
            return render(request, 'core/project_edit.html', {
                'project': project,
                'statuses': VALID_STATUSES,
                'input': request.POST,
            })

        if status not in VALID_STATUSES:
            messages.error(request, "Недопустимый статус проекта.")
            return render(request, 'core/project_edit.html', {
                'project': project,
                'statuses': VALID_STATUSES,
                'input': request.POST,
            })

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
        except ValueError:
            messages.error(request, "Некорректный формат даты. Используйте YYYY-MM-DD.")
            return render(request, 'core/project_edit.html', {
                'project': project,
                'statuses': VALID_STATUSES,
                'input': request.POST,
            })

        # Проверка уникальности названия
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM projects WHERE name = %s AND id != %s", [name, project_id])
            if cursor.fetchone()[0] > 0:
                messages.error(request, "Проект с таким названием уже существует.")
                return render(request, 'core/project_edit.html', {
                    'project': project,
                    'statuses': VALID_STATUSES,
                    'input': request.POST,
                })

        # Обновление проекта
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE projects
                SET name = %s, start_date = %s, end_date = %s, status = %s
                WHERE id = %s
            """, [name, start_date or None, end_date or None, status, project_id])

        messages.success(request, "Проект обновлён.")
        return redirect('/projects/')

    # GET-запрос
    return render(request, 'core/project_edit.html', {
        'project': project,
        'statuses': VALID_STATUSES,
        'input': project,
    })


def project_delete_view(request, project_id):
    user_role = request.COOKIES.get('user_role')
    if user_role not in ['admin', 'manager']:
        return HttpResponseForbidden("Доступ запрещён")

    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM projects WHERE id = %s", [project_id])
        if not cursor.fetchone():
            return HttpResponseNotFound("Проект не найден")

        cursor.execute("DELETE FROM projects WHERE id = %s", [project_id])

    messages.success(request, "Проект удалён.")
    return redirect('/projects/')

from django.shortcuts import render, redirect
from django.db import connection

def project_detail_view(request, project_id):
    with connection.cursor() as cursor:
        # Получаем проект
        cursor.execute("""
            SELECT id, name, start_date, end_date, status
            FROM projects
            WHERE id = %s
        """, [project_id])
        row = cursor.fetchone()
        if not row:
            return redirect('/projects/')

        project = {
            'id': row[0],
            'name': row[1],
            'start_date': row[2],
            'end_date': row[3],
            'status': row[4],
        }

        # ✅ Получаем файлы проекта + авторов
        cursor.execute("""
            SELECT f.id, f.file_name, f.file_path, f.uploaded_at, u.full_name
            FROM dev_files f
            LEFT JOIN users u ON f.author_id = u.id
            WHERE f.project_id = %s
            ORDER BY f.uploaded_at DESC
        """, [project_id])
        files = [
            {
                'id': row[0],
                'file_name': row[1],
                'file_path': row[2],
                'uploaded_at': row[3],
                'full_name': row[4],
            }
            for row in cursor.fetchall()
        ]

        # ✅ Получаем тесты проекта
        cursor.execute("""
            SELECT id, test_type, description, status, tested_at
            FROM tests
            WHERE project_id = %s
            ORDER BY tested_at DESC
        """, [project_id])
        tests = cursor.fetchall()

        # ✅ Получаем ответственных
        cursor.execute("""
            SELECT u.id, u.full_name
            FROM users u
            JOIN assignments a ON a.user_id = u.id
            WHERE a.project_id = %s
        """, [project_id])
        responsible = cursor.fetchall()

    return render(request, 'core/project_detail.html', {
        'project': project,
        'files': files,
        'tests': tests,
        'responsible': responsible,
        'role': request.COOKIES.get('user_role'),
    })


def assignment_list_view(request):
    user_role = request.COOKIES.get('user_role')
    if not user_role:
        return redirect('/login/')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, task_id, user_id FROM assignments")
        rows = cursor.fetchall()

    assignments = [{'id': row[0], 'task_id': row[1], 'user_id': row[2]} for row in rows]

    return render(request, 'core/assignments.html', {'assignments': assignments})

def file_list_view(request):
    project_id = request.GET.get('project_id')
    author_id = request.GET.get('author_id')

    query = "SELECT id, project_id, author_id, file_name, file_path, uploaded_at FROM dev_files WHERE 1=1"
    params = []

    if project_id:
        query += " AND project_id = %s"
        params.append(project_id)
    if author_id:
        query += " AND author_id = %s"
        params.append(author_id)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    files = [
        {
            'id': row[0],
            'project_id': row[1],
            'author_id': row[2],
            'file_name': row[3],
            'file_path': row[4],
            'uploaded_at': row[5],
        }
        for row in rows
    ]

    return render(request, 'core/files.html', {'files': files})

def testresult_list_view(request):
    user_role = request.COOKIES.get('user_role')
    if not user_role:
        return redirect('/login/')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, task_id, status FROM test_results")
        rows = cursor.fetchall()

    test_results = [{'id': row[0], 'task_id': row[1], 'result': row[2]} for row in rows]

    return render(request, 'core/tests.html', {'test_results': test_results})

def file_upload_view(request):
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        author_id = request.COOKIES.get('user_id')
        file_name = request.POST.get('file_name')
        file_path = request.POST.get('file_path')  # Или реальный путь после загрузки

        if not (task_id and file_name and file_path):
            messages.error(request, "Все поля обязательны.")
            return render(request, 'core/file_upload.html')

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO dev_files (task_id, author_id, file_name, file_path, uploaded_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, [task_id, author_id, file_name, file_path])

        messages.success(request, "Файл успешно добавлен!")
        return redirect('/files/')

    return render(request, 'core/file_upload.html')

def file_versions_view(request, file_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT fv.id, fv.version_number, fv.commit_message, fv.updated_at, u.full_name
            FROM file_versions fv
            LEFT JOIN users u ON fv.author_id = u.id
            WHERE fv.file_id = %s
            ORDER BY fv.version_number DESC
        """, [file_id])
        versions = dictfetchall(cursor)
    return render(request, 'core/file_versions.html', {'versions': versions, 'file_id': file_id})

def dictfetchall(cursor):
    "Преобразует результат cursor.fetchall() в список словарей"
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

from django.shortcuts import redirect
from django.contrib import messages
from django.db import connection
import os
from django.conf import settings

import os
from django.conf import settings
from django.shortcuts import redirect
from django.db import connection

# Обновим функцию для загрузки файла с автоматическим указанием project_id
from datetime import datetime

from django.shortcuts import redirect
from django.contrib import messages
from django.db import connection

import os
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.db import connection
from datetime import datetime

def project_upload_file_view(request, project_id):
    if request.method == "POST":
        file = request.FILES.get("file")
        file_name = request.POST.get("file_name") or file.name
        user_id = request.COOKIES.get("user_id")

        # Путь на диске: media/uploads/project_<id>/
        relative_path = f"uploads/project_{project_id}/{file_name}"
        full_dir = os.path.join(settings.MEDIA_ROOT, f"uploads/project_{project_id}")
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        os.makedirs(full_dir, exist_ok=True)

        with open(full_path, 'wb') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO dev_files (project_id, author_id, file_name, file_path, uploaded_at)
                VALUES (%s, %s, %s, %s, %s)
            """, [project_id, user_id, file_name, relative_path, datetime.now()])

        messages.success(request, f"Файл «{file_name}» загружен.")
    return redirect(f"/projects/{project_id}/")


from datetime import datetime
from django.shortcuts import redirect
from django.contrib import messages
from django.db import connection

def project_add_test_view(request, project_id):
    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', '').strip()
        test_type = request.POST.get('test_type', '').strip()
        tester_id = request.COOKIES.get('user_id')

        if not description or not status or not test_type:
            messages.error(request, "Все поля обязательны для заполнения.")
            return redirect(f'/projects/{project_id}/')

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tests (project_id, test_type, description, status, tester_id)
                VALUES (%s, %s, %s, %s, %s)
            """, [project_id, test_type, description, status, tester_id])

        messages.success(request, "Тест успешно добавлен.")
    return redirect(f'/projects/{project_id}/')

def project_assign_user_view(request, project_id):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if not user_id:
            messages.error(request, "Пользователь не выбран.")
            return redirect(f'/projects/{project_id}/')

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO assignments (project_id, user_id)
                VALUES (%s, %s)
            """, [project_id, user_id])

        messages.success(request, "Пользователь назначен.")
    return redirect(f'/projects/{project_id}/')

import os
from django.shortcuts import redirect
from django.contrib import messages
from django.db import connection

def project_sync_files_view(request, project_id):
    uploads_dir = os.path.join("C:/Users/BMSTU/Documents/uploads", f"project_{project_id}")
    os.makedirs(uploads_dir, exist_ok=True)
    author_id = request.COOKIES.get("user_id")

    added_count = 0
    for file_name in os.listdir(uploads_dir):
        file_path = os.path.join(uploads_dir, file_name)

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM dev_files WHERE file_name = %s AND project_id = %s", [file_name, project_id])
            if cursor.fetchone():
                continue  # файл уже добавлен

            try:
                cursor.execute("""
                    INSERT INTO dev_files (project_id, author_id, file_name, file_path, uploaded_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, [project_id, author_id, file_name, file_path])
                added_count += 1
            except Exception as e:
                print("Ошибка при вставке файла:", e)
                messages.error(request, f"Ошибка при добавлении: {file_name}")

    if added_count > 0:
        messages.success(request, f"Синхронизировано файлов: {added_count}")
    else:
        messages.info(request, "Новых файлов не найдено.")

    return redirect(f"/projects/{project_id}/")

from django.shortcuts import render, redirect, get_object_or_404
from .models import DevFile, Task
from .forms import DevFileForm

def upload_file(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        form = DevFileForm(request.POST, request.FILES)
        if form.is_valid():
            dev_file = form.save(commit=False)
            dev_file.task = task
            dev_file.filename = form.cleaned_data['file'].name
            dev_file.save()
            return redirect('project_detail', project_id=task.project.id)
    else:
        form = DevFileForm()
    return render(request, 'upload_file.html', {'form': form, 'task': task})

import os
from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect

def project_commit_upload_view(request, project_id):
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        file_name = request.POST.get("file_name") or uploaded_file.name
        commit_message = request.POST.get("commit_message") or f"Обновление файла {file_name}"
        user_id = request.COOKIES.get("user_id")

        # Время коммита
        committed_at = datetime.now()

        # Создание уникальной папки под коммит
        with connection.cursor() as cursor:
            # вставка коммита (временно, с пустыми путями)
            cursor.execute("""
                INSERT INTO commits (
                    project_id, author_id, committed_at, commit_message,
                    file_name, action, old_path, new_path, diff
                ) VALUES (%s, %s, %s, %s, %s, %s, NULL, '', NULL)
            """, [project_id, user_id, committed_at, commit_message, file_name, 'added'])

            commit_id = cursor.lastrowid

        # Путь к файлу
        commit_dir = os.path.join(settings.MEDIA_ROOT, f'uploads/project_{project_id}/commit_{commit_id}')
        os.makedirs(commit_dir, exist_ok=True)

        new_path_rel = f'uploads/project_{project_id}/commit_{commit_id}/{uploaded_file.name}'
        new_path_abs = os.path.join(settings.MEDIA_ROOT, new_path_rel)

        with open(new_path_abs, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # Обновляем путь к файлу в коммите
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE commits SET new_path = %s WHERE id = %s
            """, [new_path_rel, commit_id])

        messages.success(request, f"Файл «{file_name}» загружен в коммит #{commit_id}")
    return redirect(f'/projects/{project_id}/')

def project_commits_view(request, project_id):
    file_filter = request.GET.get('file')

    query = """
        SELECT c.id, c.committed_at, c.commit_message,
               c.file_name, c.action, c.new_path,
               u.full_name
        FROM commits c
        JOIN users u ON c.author_id = u.id
        WHERE c.project_id = %s
    """
    params = [project_id]

    if file_filter:
        query += " AND c.file_name = %s"
        params.append(file_filter)

    query += " ORDER BY c.committed_at DESC"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        commits = [
            {
                'id': row[0],
                'committed_at': row[1],
                'message': row[2],
                'file_name': row[3],
                'action': row[4],
                'file_path': row[5],
                'author': row[6],
            }
            for row in cursor.fetchall()
        ]

    return render(request, 'core/project_commits.html', {
        'commits': commits,
        'project_id': project_id,
        'filtered_file': file_filter
    })

def commit_detail_view(request, commit_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.id, c.project_id, c.file_name, c.action,
                   c.commit_message, c.committed_at, c.diff,
                   c.new_path, c.old_path,
                   u.full_name
            FROM commits c
            JOIN users u ON c.author_id = u.id
            WHERE c.id = %s
        """, [commit_id])

        row = cursor.fetchone()
        if not row:
            return redirect('/')

        commit = {
            'id': row[0],
            'project_id': row[1],
            'file_name': row[2],
            'action': row[3],
            'message': row[4],
            'date': row[5],
            'diff': row[6],
            'new_path': row[7],
            'old_path': row[8],
            'author': row[9],
        }

    return render(request, 'core/commit_detail.html', {
        'commit': commit
    })
