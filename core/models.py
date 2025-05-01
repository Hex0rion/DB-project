from django.db import models

class User(models.Model):
    id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    login = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20)  # enum хранится как строка

    class Meta:
        db_table = 'users'
        managed = False

class Project(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    status = models.CharField(max_length=20)

    class Meta:
        db_table = 'projects'
        managed = False


class Task(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'tasks'
        managed = False

class Assignment(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(Task, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'assignments'
        managed = False

class DevFile(models.Model):
    id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING)
    filename = models.CharField(max_length=255)
    path = models.CharField(max_length=255)

    class Meta:
        db_table = 'dev_files'
        managed = False

class TestResult(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(Task, on_delete=models.DO_NOTHING)
    result = models.TextField()
    created_at = models.DateTimeField()

class Meta:
    db_table = 'users'
    managed = False
    app_label = 'core'

class TestTemplate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'test_templates'

    def __str__(self):
        return self.name

class TestResult(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    tester = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[('passed', 'Пройден'), ('failed', 'Провален')])
    tested_at = models.DateTimeField(auto_now_add=True)
    template = models.ForeignKey('TestTemplate', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'test_results'

class FileVersion(models.Model):
    file = models.ForeignKey('DevFile', on_delete=models.CASCADE, db_column='file_id')
    version_number = models.IntegerField()
    commit_message = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now_add=True)
    content_path = models.TextField()
    author = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, db_column='author_id')

    class Meta:
        db_table = 'file_versions'
