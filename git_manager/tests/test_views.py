import os
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from git_manager.models import SshKey, GitRepo, GitRemote, PushLog


class TestDashboardView(TestCase):
    def setUp(self):
        self.client = Client()
        self.repo = GitRepo.objects.create(name='test-repo', path='/tmp/test-repo')

    @patch('git_manager.views.GitService')
    def test_dashboard_returns_200(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.is_git_repo.return_value = True
        mock_svc.get_current_branch.return_value = 'main'
        mock_svc.get_last_commit.return_value = {
            'full_hash': 'abc123', 'message': 'test'
        }
        mock_svc.get_status.return_value = {'success': True, 'output': ''}
        mock_git.return_value = mock_svc

        response = self.client.get(reverse('git_manager:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/dashboard.html')


class TestReposViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.repo = GitRepo.objects.create(name='test-repo', path='/tmp/test-repo')

    @patch('git_manager.views.GitService')
    def test_repos_view(self, mock_git):
        response = self.client.get(reverse('git_manager:repos'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/repos.html')

    @patch('git_manager.views.GitService')
    def test_repo_detail_200(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.is_git_repo.return_value = True
        mock_svc.get_current_branch.return_value = 'main'
        mock_svc.get_last_commit.return_value = {'full_hash': 'abc', 'message': 'test'}
        mock_svc.get_status.return_value = {'success': True, 'output': ''}
        mock_svc.get_log.return_value = [{'commit': 'abc', 'message': 'test'}]
        mock_git.return_value = mock_svc

        response = self.client.get(reverse('git_manager:repo_detail', args=[self.repo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/repo_detail.html')

    def test_repo_detail_404(self):
        response = self.client.get(reverse('git_manager:repo_detail', args=[999]))
        self.assertEqual(response.status_code, 404)

    @patch('git_manager.views.GitService')
    def test_add_repo_success(self, mock_git):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        mock_svc = MagicMock()
        mock_svc.is_git_repo.return_value = True
        mock_git.return_value = mock_svc

        response = self.client.post(reverse('git_manager:add_repo'), {
            'name': 'new-repo', 'path': temp_dir, 'description': 'test'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(GitRepo.objects.filter(name='new-repo').exists())

    @patch('git_manager.views.GitService')
    def test_add_repo_not_a_git_repo(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.is_git_repo.return_value = False
        mock_git.return_value = mock_svc

        response = self.client.post(reverse('git_manager:add_repo'), {
            'name': 'not-git', 'path': '/tmp/not-git'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GitRepo.objects.filter(name='not-git').exists())

    def test_delete_repo(self):
        response = self.client.post(reverse('git_manager:delete_repo', args=[self.repo.pk]),
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GitRepo.objects.filter(pk=self.repo.pk).exists())


class TestCreateRepoView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('git_manager:create_repo')

    @patch('git_manager.services.init_repo')
    def test_create_repo_success(self, mock_init):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        repo_path = os.path.join(temp_dir, 'new-repo')
        mock_init.return_value = {'success': True, 'path': repo_path}

        response = self.client.post(self.url, {
            'name': 'brand-new', 'path': repo_path, 'description': 'test'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GitRepo.objects.filter(name='brand-new').exists())
        repo = GitRepo.objects.get(name='brand-new')
        self.assertEqual(repo.path, repo_path)
        mock_init.assert_called_once_with(repo_path)

    @patch('git_manager.services.init_repo')
    def test_create_repo_init_failure(self, mock_init):
        mock_init.return_value = {'success': False, 'error': 'Disk full'}

        response = self.client.post(self.url, {
            'name': 'failing', 'path': '/tmp/failing-repo'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GitRepo.objects.filter(name='failing').exists())

    def test_create_repo_invalid_form(self):
        response = self.client.post(self.url, {
            'name': 'a', 'path': '/tmp/some-path'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GitRepo.objects.filter(name='a').exists())

    @patch('git_manager.services.init_repo')
    @patch('git_manager.views.GitRepo.objects.create')
    def test_create_repo_db_error_cleans_up(self, mock_create, mock_init):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        repo_path = os.path.join(temp_dir, 'cleanup-repo')
        mock_init.return_value = {'success': True, 'path': repo_path}
        mock_create.side_effect = Exception('DB error')

        response = self.client.post(self.url, {
            'name': 'cleanup-test', 'path': repo_path
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GitRepo.objects.filter(name='cleanup-test').exists())
        mock_init.assert_called_once_with(repo_path)


class TestRemotesViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.repo = GitRepo.objects.create(name='test-repo', path='/tmp/test-repo')
        self.remote = GitRemote.objects.create(
            repo=self.repo, name='origin', url='https://github.com/user/repo.git'
        )

    @patch('git_manager.views.ssh_service')
    def test_remotes_view(self, mock_ssh):
        mock_ssh.key_exists.return_value = True
        response = self.client.get(reverse('git_manager:remotes'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/remotes.html')

    @patch('git_manager.views.GitService')
    @patch('git_manager.views.ssh_service')
    def test_add_remote_success(self, mock_ssh, mock_git):
        mock_svc = MagicMock()
        mock_svc.add_remote.return_value = {'success': True}
        mock_git.return_value = mock_svc

        response = self.client.post(reverse('git_manager:add_remote'), {
            'repo_id': self.repo.pk, 'name': 'backup',
            'url': 'https://github.com/other/repo.git', 'branch': 'main'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(GitRemote.objects.filter(name='backup').exists())

    @patch('git_manager.views.GitService')
    def test_delete_remote(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.remove_remote.return_value = {'success': True}
        mock_git.return_value = mock_svc

        response = self.client.post(
            reverse('git_manager:delete_remote', args=[self.remote.pk]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GitRemote.objects.filter(pk=self.remote.pk).exists())

    @patch('git_manager.views.ssh_service')
    def test_test_remote(self, mock_ssh):
        mock_ssh.test_connection_for_remote.return_value = {
            'success': True, 'output': 'OK'
        }
        response = self.client.get(
            reverse('git_manager:test_remote', args=[self.remote.pk])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

    @patch('git_manager.views.GitService')
    def test_fetch_remote(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.fetch.return_value = {
            'success': True, 'stdout': 'Fetched', 'stderr': ''
        }
        mock_git.return_value = mock_svc

        response = self.client.get(
            reverse('git_manager:fetch_remote', args=[self.remote.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    @patch('git_manager.views.GitService')
    def test_pull_remote(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.pull.return_value = {
            'success': True, 'stdout': 'Pulled', 'stderr': ''
        }
        mock_git.return_value = mock_svc

        response = self.client.get(
            reverse('git_manager:pull_remote', args=[self.remote.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    @patch('git_manager.views.GitService')
    def test_push_now(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.get_last_commit.return_value = {
            'full_hash': 'abc', 'message': 'test'
        }
        mock_svc.push.return_value = {
            'success': True, 'stdout': 'Pushed', 'stderr': ''
        }
        mock_git.return_value = mock_svc

        response = self.client.post(reverse('git_manager:push_now'), {
            'remote_id': self.remote.pk,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PushLog.objects.filter(remote=self.remote, status='success').exists()
        )


class TestLogsViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.repo = GitRepo.objects.create(name='test-repo', path='/tmp/test-repo')
        self.remote = GitRemote.objects.create(
            repo=self.repo, name='origin', url='https://github.com/user/repo.git'
        )

    def test_logs_view_empty(self):
        response = self.client.get(reverse('git_manager:logs'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/logs.html')

    def test_logs_view_with_data(self):
        PushLog.objects.create(
            repo=self.repo, remote=self.remote, action='push',
            repo_name='test-repo', remote_name='origin', branch='main',
            status='success', triggered_by='manual'
        )
        response = self.client.get(reverse('git_manager:logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test-repo')

    def test_logs_view_filtered(self):
        PushLog.objects.create(
            repo=self.repo, remote=self.remote, action='push',
            repo_name='test-repo', remote_name='origin', branch='main',
            status='success', triggered_by='manual'
        )
        response = self.client.get(reverse('git_manager:logs'), {'status': 'success'})
        self.assertEqual(response.status_code, 200)

    def test_file_logs_view(self):
        response = self.client.get(reverse('git_manager:file_logs'))
        self.assertEqual(response.status_code, 200)


class TestSSHViews(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('git_manager.ssh_views.ssh_service')
    def test_ssh_view(self, mock_ssh):
        mock_ssh.list_all_keys.return_value = []
        response = self.client.get(reverse('git_manager:ssh'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/ssh.html')

    @patch('git_manager.ssh_views.ssh_service')
    def test_ssh_local_view(self, mock_ssh):
        mock_ssh.get_public_key.return_value = 'ssh-ed25519 AAA...'
        mock_ssh.key_exists.return_value = True
        response = self.client.get(reverse('git_manager:ssh_local'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/ssh_local.html')

    @patch('git_manager.ssh_views.ssh_service')
    def test_generate_key(self, mock_ssh):
        mock_ssh.generate_key.return_value = {'success': True}
        mock_ssh.list_all_keys.return_value = []
        response = self.client.post(reverse('git_manager:ssh_generate'), {
            'name': 'mykey', 'comment': 'test'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

    @patch('git_manager.ssh_views.ssh_service')
    def test_upload_key(self, mock_ssh):
        mock_ssh.upload_key.return_value = {'success': True}
        mock_ssh.list_all_keys.return_value = []
        response = self.client.post(reverse('git_manager:ssh_upload'), {
            'name': 'imported', 'private_key': '-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

    @patch('git_manager.ssh_views.ssh_service')
    def test_upload_key_empty(self, mock_ssh):
        response = self.client.post(reverse('git_manager:ssh_upload'), {
            'name': 'empty', 'private_key': ''
        }, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_show_public_key_404(self):
        response = self.client.get(reverse('git_manager:ssh_pubkey', args=['nonexistent']))
        self.assertEqual(response.status_code, 404)

    @patch('git_manager.ssh_views.ssh_service')
    def test_show_public_key(self, mock_ssh):
        SshKey.objects.create(name='mykey', public_key='ssh-ed25519 AAA...')
        response = self.client.get(reverse('git_manager:ssh_pubkey', args=['mykey']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('public_key', response.json())

    @patch('git_manager.ssh_views.ssh_service')
    def test_test_connection(self, mock_ssh):
        mock_ssh.test_connection.return_value = {
            'success': True, 'output': 'OK'
        }
        response = self.client.get(reverse('git_manager:ssh_test'), {
            'host': 'github.com', 'name': 'id_ed25519'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    @patch('git_manager.ssh_views.ssh_service')
    def test_delete_key(self, mock_ssh):
        mock_ssh.delete_key.return_value = {'success': True}
        SshKey.objects.create(name='todelete', key_path='/tmp/key')
        mock_ssh.list_all_keys.return_value = []
        response = self.client.post(
            reverse('git_manager:ssh_delete', args=['todelete']), follow=True
        )
        self.assertEqual(response.status_code, 200)

    @patch('git_manager.ssh_views.ssh_service')
    def test_rename_key(self, mock_ssh):
        mock_ssh.list_all_keys.return_value = []
        mock_ssh.rename_key.return_value = {
            'success': True, 'new_key_path': '/root/.ssh/newkey'
        }
        SshKey.objects.create(name='oldname', key_path='/root/.ssh/oldname')
        response = self.client.post(
            reverse('git_manager:ssh_rename', args=['oldname']),
            {'new_name': 'newname'}, follow=True
        )
        self.assertEqual(response.status_code, 200)

    @patch('git_manager.ssh_views.ssh_service')
    def test_rename_key_empty_new_name(self, mock_ssh):
        response = self.client.post(
            reverse('git_manager:ssh_rename', args=['oldname']),
            {'new_name': ''}, follow=True
        )
        self.assertEqual(response.status_code, 200)


class TestAPIDashboard(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('git_manager.views.GitService')
    def test_api_status(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.get_current_branch.return_value = 'main'
        mock_svc.get_last_commit.return_value = {'full_hash': 'abc', 'message': 'test'}
        mock_git.return_value = mock_svc

        GitRepo.objects.create(name='test', path='/tmp/test', is_active=True)
        response = self.client.get(reverse('git_manager:api_status'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('repos', data)
        self.assertEqual(len(data['repos']), 1)

    def test_api_repos_ids(self):
        GitRepo.objects.create(name='test', path='/tmp/test', is_active=True)
        response = self.client.get(reverse('git_manager:api_repos_ids'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['repos']), 1)
        self.assertEqual(data['repos'][0]['name'], 'test')

    def test_api_repo_ssh_config_404(self):
        response = self.client.get(reverse('git_manager:api_repo_ssh', args=[999]))
        self.assertEqual(response.status_code, 404)

    @patch('git_manager.views.detect_server_ip')
    def test_api_repo_ssh_config(self, mock_ip):
        mock_ip.return_value = '192.168.1.1'
        repo = GitRepo.objects.create(name='test', path='/repos/test', is_active=True)
        response = self.client.get(reverse('git_manager:api_repo_ssh', args=[repo.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['repo'], 'test')


class TestMonitoringViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='test', password='test123')
        self.repo = GitRepo.objects.create(name='test-repo', path='/tmp/test-repo')

    @patch('git_manager.views.GitService')
    def test_check_remotes_requires_login(self, mock_git):
        response = self.client.get(reverse('git_manager:check_remotes'))
        self.assertEqual(response.status_code, 302)

    @patch('git_manager.views.GitService')
    def test_check_remotes_authenticated(self, mock_git):
        self.client.login(username='test', password='test123')
        response = self.client.get(reverse('git_manager:check_remotes'))
        self.assertEqual(response.status_code, 200)

    def test_monitors_requires_login(self):
        response = self.client.get(reverse('git_manager:monitors'))
        self.assertEqual(response.status_code, 302)

    def test_monitors_authenticated(self):
        self.client.login(username='test', password='test123')
        response = self.client.get(reverse('git_manager:monitors'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'git_manager/monitors.html')


class TestRateLimit(TestCase):
    def setUp(self):
        self.client = Client()
        GitRepo.objects.create(name='test', path='/tmp/test', is_active=True)

    @patch('git_manager.views.GitService')
    def test_rate_limit_blocks_excessive_requests(self, mock_git):
        mock_svc = MagicMock()
        mock_svc.get_current_branch.return_value = 'main'
        mock_svc.get_last_commit.return_value = {'full_hash': 'abc', 'message': 'test'}
        mock_git.return_value = mock_svc

        url = reverse('git_manager:api_status')
        for _ in range(30):
            self.client.get(url)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)
