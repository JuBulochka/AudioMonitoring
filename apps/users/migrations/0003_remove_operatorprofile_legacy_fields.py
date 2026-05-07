from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove legacy OperatorProfile fields that were dropped from the model
    but never removed from the DB: preferred_timezone, items_per_page.
    Their NOT NULL constraint caused IntegrityError when creating new profiles.
    """

    dependencies = [
        ('users', '0002_user_employee_number_is_frozen_assigned_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='operatorprofile',
            name='preferred_timezone',
        ),
        migrations.RemoveField(
            model_name='operatorprofile',
            name='items_per_page',
        ),
    ]
