from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('git_manager', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RemoteMonitor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('ok', 'OK'), ('error', 'Erreur'), ('ahead', 'En avance'), ('behind', 'En retard'), ('diverged', 'Divergé'), ('unknown', 'Inconnu')], default='unknown', max_length=20)),
                ('ssh_reachable', models.BooleanField(blank=True, null=True)),
                ('commits_ahead', models.IntegerField(default=0)),
                ('commits_behind', models.IntegerField(default=0)),
                ('last_check', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('check_duration_ms', models.IntegerField(default=0)),
                ('remote', models.OneToOneField(on_delete=models.CASCADE, related_name='monitor', to='git_manager.gitremote')),
            ],
            options={
                'verbose_name': 'Surveillance remote',
                'verbose_name_plural': 'Surveillance remotes',
            },
        ),
        migrations.AlterField(
            model_name='pushlog',
            name='triggered_by',
            field=models.CharField(choices=[('manual', 'Manuel'), ('scheduler', 'Planifié'), ('webhook', 'Webhook'), ('api', 'API')], default='manual', max_length=20),
        ),
        migrations.AddIndex(
            model_name='pushlog',
            index=models.Index(fields=['-created_at'], name='git_manager_created_ idx'),
        ),
        migrations.AddIndex(
            model_name='pushlog',
            index=models.Index(fields=['status'], name='git_manager_status_idx'),
        ),
        migrations.AddIndex(
            model_name='pushlog',
            index=models.Index(fields=['triggered_by'], name='git_manager_trigger_idx'),
        ),
    ]