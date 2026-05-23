from django.db import models


class SshKey(models.Model):
    name = models.CharField(max_length=100, unique=True)
    key_path = models.CharField(max_length=500, default='/root/.ssh/id_ed25519')
    public_key = models.TextField(blank=True)
    fingerprint = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Clé SSH"
        verbose_name_plural = "Clés SSH"


class GitRepo(models.Model):
    name = models.CharField(max_length=100, unique=True)
    path = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.path})"

    class Meta:
        verbose_name = "Dépôt Git"
        verbose_name_plural = "Dépôts Git"


class GitRemote(models.Model):
    repo = models.ForeignKey(GitRepo, on_delete=models.CASCADE, related_name='remotes')
    name = models.CharField(max_length=100)
    url = models.CharField(max_length=500)
    branch = models.CharField(max_length=100, default='main')
    ssh_key = models.ForeignKey(SshKey, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    use_force = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.repo.name} → {self.name}"

    class Meta:
        unique_together = ('repo', 'name')
        verbose_name = "Remote Git"
        verbose_name_plural = "Remotes Git"


class PushLog(models.Model):
    ACTION_CHOICES = [
        ('push', 'Push'),
        ('pull', 'Pull'),
        ('fetch', 'Fetch'),
        ('test', 'Test'),
        ('check', 'Vérification'),
    ]
    STATUS_CHOICES = [
        ('success', 'Succès'),
        ('error', 'Erreur'),
        ('pending', 'En cours'),
    ]
    TRIGGERED_BY_CHOICES = [
        ('manual', 'Manuel'),
        ('scheduler', 'Planifié'),
        ('webhook', 'Webhook'),
        ('api', 'API'),
    ]
    repo = models.ForeignKey(GitRepo, on_delete=models.SET_NULL, null=True, blank=True)
    remote = models.ForeignKey(GitRemote, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='push')
    repo_name = models.CharField(max_length=100, blank=True)
    remote_name = models.CharField(max_length=100)
    branch = models.CharField(max_length=100)
    commit_hash = models.CharField(max_length=40, blank=True)
    commit_message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    output = models.TextField(blank=True)
    error_output = models.TextField(blank=True)
    triggered_by = models.CharField(max_length=20, choices=TRIGGERED_BY_CHOICES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.status}] {self.action} {self.repo_name}/{self.remote_name}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Log d'action"
        verbose_name_plural = "Logs d'actions"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['triggered_by']),
        ]


class RemoteMonitor(models.Model):
    """Stocke le dernier état connu de chaque remote."""
    STATUS_CHOICES = [
        ('ok', 'OK'),
        ('error', 'Erreur'),
        ('ahead', 'En avance'),
        ('behind', 'En retard'),
        ('diverged', 'Divergé'),
        ('unknown', 'Inconnu'),
    ]

    remote = models.OneToOneField(GitRemote, on_delete=models.CASCADE, related_name='monitor')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    ssh_reachable = models.BooleanField(null=True, blank=True)
    commits_ahead = models.IntegerField(default=0)
    commits_behind = models.IntegerField(default=0)
    last_check = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    check_duration_ms = models.IntegerField(default=0)

    def __str__(self):
        return f"Monitor {self.remote} → {self.status}"

    class Meta:
        verbose_name = "Surveillance remote"
        verbose_name_plural = "Surveillance remotes"
