from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0003_add_tunnel_port'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='vnc_tunnel_port',
            field=models.IntegerField(
                blank=True,
                null=True,
                unique=True,
                help_text='Порт обратного VNC-туннеля (21001-21020). Назначается автоматически.',
            ),
        ),
    ]
