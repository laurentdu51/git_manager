from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='SshKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('key_path', models.CharField(default='/root/.ssh/id_ed25519', max_length=500)),
                ('public_key', models.TextField(blank=True)),
                ('fingerprint', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Clé SSH', 'verbose_name_plural': 'Clés SSH'},
        ),
        migrations.CreateModel(
            name='GitRepo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('path', models.CharField(max_length=500)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Dépôt Git', 'verbose_name_plural': 'Dépôts Git'},
        ),
        migrations.CreateModel(
            name='GitRemote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('url', models.CharField(max_length=500)),
                ('branch', models.CharField(default='main', max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('use_force', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('repo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='remotes', to='git_manager.gitrepo')),
                ('ssh_key', models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='git_manager.sshkey')),
            ],
            options={
                'verbose_name': 'Remote Git',
                'verbose_name_plural': 'Remotes Git',
                'unique_together': {('repo', 'name')},
            },
        ),
        migrations.CreateModel(
            name='PushLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('repo_name', models.CharField(blank=True, max_length=100)),
                ('remote_name', models.CharField(max_length=100)),
                ('branch', models.CharField(max_length=100)),
                ('commit_hash', models.CharField(blank=True, max_length=40)),
                ('commit_message', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('success', 'Succès'), ('error', 'Erreur'), ('pending', 'En cours')],
                    default='pending', max_length=10)),
                ('output', models.TextField(blank=True)),
                ('error_output', models.TextField(blank=True)),
                ('triggered_by', models.CharField(default='manual', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('repo', models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='git_manager.gitrepo')),
                ('remote', models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='git_manager.gitremote')),
            ],
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Log de push',
                'verbose_name_plural': 'Logs de push',
            },
        ),
    ]
