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