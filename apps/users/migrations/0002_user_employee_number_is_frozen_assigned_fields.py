from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        # Add employee_number to User (nullable first for existing rows)
        migrations.AddField(
            model_name='user',
            name='employee_number',
            field=models.CharField(
                blank=True, max_length=20, unique=True, null=True,
                verbose_name='Табельный номер',
            ),
        ),
        # Add is_frozen to User
        migrations.AddField(
            model_name='user',
            name='is_frozen',
            field=models.BooleanField(
                default=False,
                verbose_name='Аккаунт заморожен',
                help_text='Замороженный оператор не может войти в систему.',
            ),
        ),
        # Remove old assigned_regions M2M (replaced by assigned_fields)
        migrations.RemoveField(
            model_name='operatorprofile',
            name='assigned_regions',
        ),
        # Add assigned_fields M2M to OperatorProfile
        migrations.AddField(
            model_name='operatorprofile',
            name='assigned_fields',
            field=models.ManyToManyField(
                blank=True,
                related_name='assigned_operators',
                to='devices.field',
                verbose_name='Назначенные месторождения',
            ),
        ),
        # Make email non-required at DB level (allow blank)
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(
                blank=True, default='', max_length=254,
                verbose_name='email address',
            ),
        ),
        # Remove supervisor/engineer/readonly role choices — now only admin/operator
        # (data migration not needed; no existing rows with removed roles in fresh DB)
    ]
