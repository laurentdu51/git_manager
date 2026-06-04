import os
import tempfile
import shutil
from django.test import TestCase
from git_manager.services import GitService


class TestGitService(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
        os.system('git init -q')
        os.system('git config user.email "test@test.com"')
        os.system('git config user.name "Test"')
        with open('test.txt', 'w') as f:
            f.write('test content')
        os.system('git add .')
        os.system('git commit -q -m "Initial commit"')

    def tearDown(self):
        os.chdir('/')
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_git_repo(self):
        svc = GitService(self.temp_dir)
        self.assertTrue(svc.is_git_repo())

    def test_is_not_git_repo(self):
        temp_dir = tempfile.mkdtemp()
        svc = GitService(temp_dir)
        self.assertFalse(svc.is_git_repo())
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_current_branch(self):
        svc = GitService(self.temp_dir)
        branch = svc.get_current_branch()
        self.assertEqual(branch, 'master')

    def test_get_last_commit(self):
        svc = GitService(self.temp_dir)
        commit = svc.get_last_commit()
        self.assertIn('full_hash', commit)
        self.assertIn('message', commit)
        self.assertEqual(commit['message'], 'Initial commit')

    def test_get_status(self):
        svc = GitService(self.temp_dir)
        status = svc.get_status()
        self.assertIn('success', status)

    def test_add_remote(self):
        svc = GitService(self.temp_dir)
        result = svc.add_remote('origin', 'https://github.com/test/test.git')
        self.assertTrue(result['success'])

    def test_get_remotes(self):
        svc = GitService(self.temp_dir)
        svc.add_remote('origin', 'https://github.com/test/test.git')
        remotes = svc.get_remotes()
        self.assertTrue(len(remotes) > 0)

    def test_remove_remote(self):
        svc = GitService(self.temp_dir)
        svc.add_remote('test', 'https://github.com/test/test.git')
        result = svc.remove_remote('test')
        self.assertTrue(result['success'])

    def test_get_log(self):
        svc = GitService(self.temp_dir)
        logs = svc.get_log(5)
        self.assertIsInstance(logs, list)

    def test_push_requires_remote_and_branch(self):
        svc = GitService(self.temp_dir)
        result = svc.push('', '')
        self.assertFalse(result['success'])
        self.assertIn('required', result['stderr'])

    def test_get_ahead_behind_requires_params(self):
        svc = GitService(self.temp_dir)
        result = svc.get_ahead_behind('', '')
        self.assertFalse(result['success'])
        self.assertIn('required', result['stderr'])

    def test_get_ahead_behind_missing_remote_branch(self):
        svc = GitService(self.temp_dir)
        result = svc.get_ahead_behind('origin', 'main')
        self.assertFalse(result['success'])

    def test_invalid_repo_path_raises_error(self):
        with self.assertRaises(ValueError):
            GitService('')
        with self.assertRaises(ValueError):
            GitService(None)

    def test_nonexistent_path_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            GitService('/nonexistent/path')


class TestInitRepo(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.temp_dir, 'new-repo')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_repo_creates_directory(self):
        from git_manager.services import init_repo
        result = init_repo(self.repo_path)
        self.assertTrue(result['success'])
        self.assertTrue(os.path.isdir(self.repo_path))
        self.assertTrue(os.path.isdir(os.path.join(self.repo_path, '.git')))

    def test_init_repo_is_valid_git_repo(self):
        from git_manager.services import init_repo
        result = init_repo(self.repo_path)
        self.assertTrue(result['success'])
        svc = GitService(self.repo_path)
        self.assertTrue(svc.is_git_repo())

    def test_init_repo_has_initial_commit(self):
        from git_manager.services import init_repo
        init_repo(self.repo_path)
        svc = GitService(self.repo_path)
        commit = svc.get_last_commit()
        self.assertEqual(commit['message'], 'Initial commit')

    def test_init_repo_default_branch(self):
        from git_manager.services import init_repo
        init_repo(self.repo_path, default_branch='main')
        svc = GitService(self.repo_path)
        self.assertEqual(svc.get_current_branch(), 'main')

    def test_init_repo_deny_current_branch(self):
        from git_manager.services import init_repo
        init_repo(self.repo_path)
        svc = GitService(self.repo_path)
        result = svc._run(['git', 'config', 'receive.denyCurrentBranch'])
        self.assertTrue(result['success'])
        self.assertEqual(result['stdout'], 'updateInstead')

    def test_init_repo_custom_branch(self):
        from git_manager.services import init_repo
        result = init_repo(self.repo_path, default_branch='develop')
        self.assertTrue(result['success'])
        svc = GitService(self.repo_path)
        self.assertEqual(svc.get_current_branch(), 'develop')

    def test_init_repo_on_existing_non_git_directory(self):
        from git_manager.services import init_repo
        existing = os.path.join(self.temp_dir, 'existing-dir')
        os.makedirs(existing)
        result = init_repo(existing)
        self.assertTrue(result['success'])
        svc = GitService(existing)
        self.assertTrue(svc.is_git_repo())


class TestCloneRepo(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_path = os.path.join(self.temp_dir, 'source')
        self.target_path = os.path.join(self.temp_dir, 'clone')
        os.makedirs(self.source_path)
        os.chdir(self.source_path)
        os.system('git init -q')
        os.system('git config user.email "test@test.com"')
        os.system('git config user.name "Test"')
        with open('file.txt', 'w') as f:
            f.write('hello')
        os.system('git add .')
        os.system('git commit -q -m "Initial"')

    def tearDown(self):
        os.chdir('/')
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clone_local_repo(self):
        from git_manager.services import clone_repo
        result = clone_repo(self.source_path, self.target_path)
        self.assertTrue(result['success'])
        self.assertTrue(os.path.isdir(self.target_path))
        self.assertTrue(os.path.isdir(os.path.join(self.target_path, '.git')))
        svc = GitService(self.target_path)
        self.assertTrue(svc.is_git_repo())
        self.assertTrue(os.path.isfile(os.path.join(self.target_path, 'file.txt')))

    def test_clone_sets_receive_deny_current_branch(self):
        from git_manager.services import clone_repo
        clone_repo(self.source_path, self.target_path)
        svc = GitService(self.target_path)
        result = svc._run(['git', 'config', 'receive.denyCurrentBranch'])
        self.assertEqual(result['stdout'], 'updateInstead')

    def test_clone_sets_pull_rebase(self):
        from git_manager.services import clone_repo
        clone_repo(self.source_path, self.target_path)
        svc = GitService(self.target_path)
        result = svc._run(['git', 'config', 'pull.rebase'])
        self.assertEqual(result['stdout'], 'false')

    def test_clone_sets_git_identity(self):
        from git_manager.services import clone_repo
        clone_repo(self.source_path, self.target_path)
        svc = GitService(self.target_path)
        email = svc._run(['git', 'config', 'user.email'])['stdout']
        name = svc._run(['git', 'config', 'user.name'])['stdout']
        self.assertEqual(email, 'deploy@local.test')
        self.assertEqual(name, 'Git Manager')

    def test_clone_remote_name_custom(self):
        from git_manager.services import clone_repo
        result = clone_repo(self.source_path, self.target_path, remote_name='upstream')
        self.assertTrue(result['success'])
        svc = GitService(self.target_path)
        remotes = svc.get_remotes()
        self.assertEqual(remotes[0]['name'], 'upstream')

    def test_clone_invalid_url(self):
        from git_manager.services import clone_repo
        result = clone_repo('https://invalid.url/repo.git',
                            os.path.join(self.temp_dir, 'fail'))
        self.assertFalse(result['success'])
        self.assertIn('error', result)

