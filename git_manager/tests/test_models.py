from django.test import TestCase
from git_manager.models import SshKey, GitRepo, GitRemote, PushLog, RemoteMonitor


class TestSshKeyModel(TestCase):
    def test_create_ssh_key(self):
        key = SshKey.objects.create(
            name='mykey', key_path='/root/.ssh/id_ed25519',
            public_key='ssh-ed25519 AAA...', fingerprint='SHA256:abc'
        )
        self.assertEqual(str(key), 'mykey')

    def test_verbose_name(self):
        self.assertEqual(SshKey._meta.verbose_name, 'Clé SSH')
        self.assertEqual(SshKey._meta.verbose_name_plural, 'Clés SSH')


class TestGitRepoModel(TestCase):
    def test_create_repo(self):
        repo = GitRepo.objects.create(name='test', path='/tmp/repo')
        self.assertEqual(str(repo), 'test (/tmp/repo)')
        self.assertTrue(repo.is_active)

    def test_verbose_name(self):
        self.assertEqual(GitRepo._meta.verbose_name, 'Dépôt Git')


class TestGitRemoteModel(TestCase):
    def setUp(self):
        self.repo = GitRepo.objects.create(name='test', path='/tmp/repo')

    def test_create_remote(self):
        remote = GitRemote.objects.create(
            repo=self.repo, name='origin', url='https://github.com/user/repo.git'
        )
        self.assertEqual(str(remote), 'test → origin')
        self.assertEqual(remote.branch, 'main')

    def test_unique_together(self):
        GitRemote.objects.create(repo=self.repo, name='origin', url='https://github.com/user/repo.git')
        with self.assertRaises(Exception):
            GitRemote.objects.create(repo=self.repo, name='origin', url='https://github.com/other/repo.git')


class TestPushLogModel(TestCase):
    def setUp(self):
        self.repo = GitRepo.objects.create(name='test', path='/tmp/repo')
        self.remote = GitRemote.objects.create(repo=self.repo, name='origin', url='https://github.com/user/repo.git')

    def test_create_push_log(self):
        log = PushLog.objects.create(
            repo=self.repo, remote=self.remote, action='push',
            repo_name='test', remote_name='origin', branch='main',
            status='success', triggered_by='manual'
        )
        self.assertIn('success', str(log))
        self.assertIn('push', str(log))

    def test_default_ordering(self):
        PushLog.objects.create(
            repo=self.repo, remote=self.remote, action='push',
            repo_name='test', remote_name='origin', branch='main',
            status='success', triggered_by='manual'
        )
        log = PushLog.objects.first()
        self.assertIsNotNone(log)


class TestRemoteMonitorModel(TestCase):
    def setUp(self):
        self.repo = GitRepo.objects.create(name='test', path='/tmp/repo')
        self.remote = GitRemote.objects.create(repo=self.repo, name='origin', url='https://github.com/user/repo.git')

    def test_create_monitor(self):
        monitor = RemoteMonitor.objects.create(remote=self.remote, status='ok')
        self.assertEqual(str(monitor), f'Monitor {self.remote} → ok')

    def test_one_to_one_relation(self):
        monitor = RemoteMonitor.objects.create(remote=self.remote, status='ok')
        self.assertEqual(monitor.remote, self.remote)
        self.assertEqual(self.remote.monitor, monitor)
