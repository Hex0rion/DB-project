import os
import re
from datetime import datetime, date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.db import connection
from django.http import HttpResponseForbidden, HttpResponseNotFound, Http404
from django.shortcuts import render, redirect, get_object_or_404

from core.models import User, Project, DevFile, Task
from .forms import DevFileForm

# === Аутентификация и авторизация ===
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


# === Управление пользователями ===
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

# === Домашняя страница ===
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

# === Проекты ===
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

def project_detail_view(request, project_id):
    user_role = request.COOKIES.get('user_role')
    user_id = request.COOKIES.get('user_id')

    with connection.cursor() as cursor:
        # Получение данных проекта
        cursor.execute("""
            SELECT id, name, start_date, end_date, status
            FROM projects
            WHERE id = %s
        """, [project_id])
        row = cursor.fetchone()
        if row is None:
            return HttpResponseNotFound("Проект не найден")

        project = {
            'id': row[0],
            'name': row[1],
            'start_date': row[2],
            'end_date': row[3],
            'status': row[4],
        }

        # Проверка прав: admin или manager проекта
        user_is_manager = False
        if user_role == 'admin':
            user_is_manager = True
        elif user_role == 'manager':
            cursor.execute("""
                SELECT u.id, u.full_name, u.role
                FROM users u
                WHERE u.role IN ('admin', 'manager', 'dev', 'tester')
                AND NOT EXISTS (
                    SELECT 1 FROM assignments a
                    WHERE a.project_id = %s AND a.user_id = u.id
                )
            """, [project_id])
            user_is_manager = cursor.fetchone()[0] > 0

        # Обработка POST-запроса: назначение/удаление
        if request.method == 'POST' and user_is_manager:
            remove_user_id = request.POST.get('remove_user_id')
            if remove_user_id:
                cursor.execute("""
                    DELETE FROM assignments
                    WHERE project_id = %s AND user_id = %s
                """, [project_id, remove_user_id])
                return redirect(f"/projects/{project_id}/")

            target_user_id = request.POST.get('user_id')
            assign_role = request.POST.get('assign_role')
            if target_user_id and assign_role:
                cursor.execute("""
                    SELECT COUNT(*) FROM assignments
                    WHERE project_id = %s AND user_id = %s
                """, [project_id, target_user_id])
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO assignments (project_id, user_id, role, assigned_date)
                        VALUES (%s, %s, %s, NOW())
                    """, [project_id, target_user_id, assign_role])
                return redirect(f"/projects/{project_id}/")

        # Получение последних версий файлов
        cursor.execute("""
            SELECT f1.file_name, f1.file_path, f1.uploaded_at, u.full_name
            FROM dev_files f1
            JOIN (
                SELECT file_name, MAX(uploaded_at) AS last_upload
                FROM dev_files
                WHERE project_id = %s
                GROUP BY file_name
            ) f2 ON f1.file_name = f2.file_name AND f1.uploaded_at = f2.last_upload
            JOIN users u ON f1.author_id = u.id
            WHERE f1.project_id = %s
            ORDER BY f1.uploaded_at DESC
        """, [project_id, project_id])
        files = [
            {'file_name': r[0], 'file_path': r[1], 'uploaded_at': r[2], 'full_name': r[3]}
            for r in cursor.fetchall()
        ]

        # Получение тестов
        cursor.execute("""
            SELECT id, test_type, description, status, tested_at
            FROM tests
            WHERE project_id = %s
            ORDER BY tested_at DESC
        """, [project_id])
        tests = cursor.fetchall()

        # Получение назначенных пользователей
        cursor.execute("""
            SELECT u.id, u.full_name, a.role
            FROM assignments a
            JOIN users u ON u.id = a.user_id
            WHERE a.project_id = %s
        """, [project_id])
        assigned_raw = cursor.fetchall()

        responsible_by_role = {
            'manager': [],
            'dev': [],
            'tester': [],
        }

        for user_id, full_name, role in assigned_raw:
            if role in responsible_by_role:
                responsible_by_role[role].append({
                    'id': user_id,
                    'full_name': full_name,
                    'role': role,
                    'role_display': role_display(role),
                })

        # Укомплектованность по ролям
        staff_fulfilled = {
            'manager': len(responsible_by_role['manager']) > 0,
            'dev': len(responsible_by_role['dev']) > 0,
            'tester': len(responsible_by_role['tester']) > 0,
        }

        # Доступные пользователи
        cursor.execute("""
            SELECT u.id, u.full_name, u.role, u.login
            FROM users u
            WHERE u.role IN ('manager', 'dev', 'tester', 'admin')
            AND NOT EXISTS (
                SELECT 1 FROM assignments a
                WHERE a.project_id = %s AND a.user_id = u.id
            )
        """, [project_id])

        available_users = [
            {
                'id': r[0],
                'full_name': r[1],
                'role': r[2],
                'login': r[3],
                'role_display': role_display(r[2])
            }
            for r in cursor.fetchall()
        ]

    assigned_counts = {
        'manager': len(responsible_by_role['manager']),
        'dev': len(responsible_by_role['dev']),
        'tester': len(responsible_by_role['tester']),
    }

    return render(request, 'core/project_detail.html', {
        'project': project,
        'files': files,
        'tests': tests,
        'assignments': [
            {
                'id': r[0],
                'full_name': r[1],
                'role': r[2],
                'role_display': role_display(r[2])
            }
            for r in assigned_raw
        ],
        'staff_fulfilled': staff_fulfilled,
        'assigned_counts': assigned_counts, 
        'available_users': available_users,
        'role': user_role,
        'user_is_manager': user_is_manager,
        'roles': ['manager', 'dev', 'tester'],
    })

# === Назначения ===
def assign_user(request, project_id):
    user_id = request.POST.get("user_id")
    role = request.POST.get("assign_role")
    if user_id and role:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO assignments (project_id, user_id, role)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE role = VALUES(role)
            """, [project_id, user_id, role])
    return redirect(f"/projects/{project_id}/")

def remove_user(request, project_id):
    user_id = request.POST.get("remove_user_id")
    if user_id:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM assignments WHERE project_id = %s AND user_id = %s",
                [project_id, user_id]
            )
    return redirect(f"/projects/{project_id}/")

def assignment_list_view(request):
    user_role = request.COOKIES.get('user_role')
    user_id = request.COOKIES.get('user_id')

    selected_project_id = request.GET.get('project_id')
    selected_project = None
    assigned = []
    available = []

    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        remove_user_id = request.POST.get('remove_user_id')
        if remove_user_id:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM assignments
                    WHERE project_id = %s AND user_id = %s
                """, [project_id, remove_user_id])
            return redirect(f"/assignments/?project_id={project_id}")
        target_user_id = request.POST.get('user_id')
        assign_role = request.POST.get('assign_role')

        if user_role in ['admin', 'manager'] and project_id and target_user_id and assign_role:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM assignments
                    WHERE project_id = %s AND user_id = %s
                """, [project_id, target_user_id])
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("""
                        INSERT INTO assignments (project_id, user_id, role, assigned_date)
                        VALUES (%s, %s, %s, NOW())
                    """, [project_id, target_user_id, assign_role])

            return redirect(f'/assignments/?project_id={project_id}')

    with connection.cursor() as cursor:
        # все проекты
        cursor.execute("SELECT id, name, start_date, end_date FROM projects")
        project_rows = cursor.fetchall()

        projects = []
        for row in project_rows:
            pid = row[0]
            cursor.execute("""
                SELECT COUNT(*) FROM assignments WHERE project_id = %s AND role = 'dev'
            """, [pid])
            dev_count = cursor.fetchone()[0]
            cursor.execute("""
                SELECT COUNT(*) FROM assignments WHERE project_id = %s AND role = 'tester'
            """, [pid])
            tester_count = cursor.fetchone()[0]
            cursor.execute("""
                SELECT COUNT(*) FROM assignments WHERE project_id = %s AND role = 'manager'
            """, [pid])
            manager_count = cursor.fetchone()[0]

            projects.append({
                'id': pid,
                'name': row[1],
                'start_date': row[2],
                'end_date': row[3],
                'roles_count': {
                    'dev': dev_count,
                    'tester': tester_count,
                    'manager': manager_count,
                },
                'staff_fulfilled': {
                    'dev': dev_count > 0,
                    'tester': tester_count > 0,
                    'manager': manager_count > 0,
                }
            })

        # Если выбран проект
        if selected_project_id:
            cursor.execute("SELECT id, name FROM projects WHERE id = %s", [selected_project_id])
            row = cursor.fetchone()
            if row:
                selected_project = {
                    'id': row[0],
                    'name': row[1],
                }

                # Назначенные пользователи
                cursor.execute("""
                    SELECT u.id, u.full_name, a.role
                    FROM assignments a
                    JOIN users u ON u.id = a.user_id
                    WHERE a.project_id = %s
                """, [selected_project_id])
                assigned = [
                    {
                        'id': row[0],
                        'full_name': row[1],
                        'role': row[2],
                        'role_display': role_display(row[2])
                    }
                    for row in cursor.fetchall()
                ]

                # Свободные пользователи
                cursor.execute("""
                    SELECT u.id, u.full_name, u.login, u.role
                    FROM users u
                    WHERE u.role IN ('admin', 'manager', 'tester', 'dev')
                    AND NOT EXISTS (
                        SELECT 1 FROM assignments a
                        WHERE a.project_id = %s AND a.user_id = u.id
                    )
                """, [selected_project_id])
                available = [
                    {
                        'id': row[0],
                        'full_name': row[1],
                        'login': row[2], 
                        'role': row[3],
                        'role_display': role_display(row[3])
                    }
                    for row in cursor.fetchall()
                ]

    return render(request, 'core/assignments.html', {
        'projects': projects,
        'selected_project': selected_project,
        'assigned': assigned,
        'available': available
    })

# === Файлы ===
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

def delete_file_view(request, file_id):
    user_id = request.COOKIES.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("SELECT project_id, file_name, file_path FROM dev_files WHERE id = %s", [file_id])
        row = cursor.fetchone()

        if not row:
            return HttpResponseNotFound("Файл не найден.")

        project_id, file_name, file_path = row

        # фиксируем коммит об удалении
        cursor.execute("""
            INSERT INTO commits (project_id, author_id, committed_at, commit_message,
                                 file_name, action, old_path, new_path, diff)
            VALUES (%s, %s, NOW(), %s, %s, 'deleted', %s, '', NULL)
        """, [project_id, user_id, f"Удаление файла {file_name}", file_name, file_path])

        # удаляем текущую версию из dev_files
        cursor.execute("DELETE FROM dev_files WHERE id = %s", [file_id])

    messages.success(request, f"Файл «{file_name}» удалён.")
    return redirect('/files/')

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

# === Работа с файлами через коммиты ===
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

            cursor.execute("""
                INSERT INTO dev_files (project_id, author_id, file_name, file_path, uploaded_at)
                VALUES (%s, %s, %s, %s, %s)
            """, [project_id, user_id, file_name, new_path_rel, committed_at])

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

    query += " ORDER BY c.committed_at"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        raw_commits = cursor.fetchall()

    commits = []
    file_state = {}

    for row in raw_commits:
        file_name = row[3]
        new_path = row[5]

        if file_name not in file_state:
            status = 'создан'
        elif file_state[file_name] == 'удалён':
            status = 'создан'
        else:
            status = 'обновлён'

        if not new_path:
            status = 'удалён'
            file_state[file_name] = 'удалён'
        else:
            file_state[file_name] = 'существует'

        commits.append({
            'id': row[0],
            'committed_at': row[1],
            'message': row[2],
            'file_name': file_name,
            'file_path': new_path,
            'author': row[6],
            'status': status,
        })

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

# === Тесты ===
def testresult_list_view(request):
    user_role = request.COOKIES.get('user_role')
    if not user_role:
        return redirect('/login/')

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, task_id, status FROM test_results")
        rows = cursor.fetchall()

    test_results = [{'id': row[0], 'task_id': row[1], 'result': row[2]} for row in rows]

    return render(request, 'core/tests.html', {'test_results': test_results})

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

# === Утилиты ===
def dictfetchall(cursor):
    "Преобразует результат cursor.fetchall() в список словарей"
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def role_display(role):
    return {
        'admin': 'Администратор',
        'manager': 'Менеджер',
        'dev': 'Разработчик',
        'tester': 'Тестировщик',
    }.get(role, role)
