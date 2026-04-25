import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('remote_access', '0003_remove_request_simplify_session'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('devices', '0003_add_tunnel_port'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceCommand',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('command_key', models.CharField(
                    db_index=True, max_length=64,
                    verbose_name='Ключ команды',
                    help_text='Slug из каталога команд, напр. system_info',
                )),
                ('params', models.JSONField(blank=True, default=dict, verbose_name='Параметры')),
                ('status', models.CharField(
                    choices=[
                        ('pending',   'Ожидает выполнения'),
                        ('running',   'Выполняется'),
                        ('completed', 'Выполнено'),
                        ('failed',    'Ошибка'),
                        ('timeout',   'Таймаут'),
                        ('cancelled', 'Отменено'),
                    ],
                    db_index=True, default='pending', max_length=20, verbose_name='Статус',
                )),
                ('output',        models.TextField(blank=True, verbose_name='Вывод')),
                ('exit_code',     models.IntegerField(blank=True, null=True, verbose_name='Код выхода')),
                ('error_message', models.TextField(blank=True, verbose_name='Сообщение об ошибке')),
                ('created_at',    models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('picked_up_at',  models.DateTimeField(blank=True, null=True, verbose_name='Получено устройством')),
                ('completed_at',  models.DateTimeField(blank=True, null=True, verbose_name='Выполнено')),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commands',
                    to='devices.device',
                    verbose_name='Устройство',
                )),
                ('sent_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_commands',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Кто отправил',
                )),
            ],
            options={
                'verbose_name': 'Команда устройству',
                'verbose_name_plural': 'Команды устройствам',
                'db_table': 'remote_access_device_command',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='devicecommand',
            index=models.Index(fields=['device', 'status'], name='ra_cmd_device_status_idx'),
        ),
        migrations.AddIndex(
            model_name='devicecommand',
            index=models.Index(fields=['device', 'created_at'], name='ra_cmd_device_created_idx'),
        ),
    ]
