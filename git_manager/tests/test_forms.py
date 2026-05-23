import tempfile
import os
from django.test import TestCase
from git_manager.forms import (
    validate_repo_name,
    validate_git_path,
    validate_remote_name,
    validate_git_url,
    validate_ssh_key_path,
    GitRepoForm,
    GitRemoteForm,
)
from django.core.exceptions import ValidationError


class TestValidators(TestCase):

    def test_validate_repo_name_valid(self):
        self.assertIsNone(validate_repo_name('my-repo'))
        self.assertIsNone(validate_repo_name('repo_123'))

    def test_validate_repo_name_too_short(self):
        with self.assertRaises(ValidationError):
            validate_repo_name('a')

    def test_validate_repo_name_invalid_chars(self):
        with self.assertRaises(ValidationError):
            validate_repo_name('repo@invalid')

    def test_validate_git_path_nonexistent(self):
        with self.assertRaises(ValidationError):
            validate_git_path('/nonexistent/path')

    def test_validate_remote_name_valid(self):
        self.assertIsNone(validate_remote_name('origin'))
        self.assertIsNone(validate_remote_name('backup-repo'))

    def test_validate_remote_name_empty(self):
        with self.assertRaises(ValidationError):
            validate_remote_name('')

    def test_validate_git_url_valid(self):
        self.assertIsNone(validate_git_url('https://github.com/user/repo'))
        self.assertIsNone(validate_git_url('git@github.com:user/repo.git'))
        self.assertIsNone(validate_git_url('ssh://git@github.com/user/repo'))

    def test_validate_git_url_invalid(self):
        with self.assertRaises(ValidationError):
            validate_git_url('not-a-url')

    def test_validate_git_url_empty(self):
        with self.assertRaises(ValidationError):
            validate_git_url('')


class TestGitRepoForm(TestCase):

    def test_valid_form(self):
        temp_dir = tempfile.mkdtemp()
        form = GitRepoForm({
            'name': 'test-repo',
            'path': temp_dir,
            'description': 'Test description'
        })
        self.assertTrue(form.is_valid())

    def test_invalid_name(self):
        temp_dir = tempfile.mkdtemp()
        form = GitRepoForm({
            'name': 'a',
            'path': temp_dir,
            'description': 'Test'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)


class TestGitRemoteForm(TestCase):

    def test_valid_form(self):
        form = GitRemoteForm({
            'name': 'origin',
            'url': 'https://github.com/user/repo.git',
            'branch': 'main',
            'use_force': False,
        })
        self.assertTrue(form.is_valid())

    def test_invalid_remote_name(self):
        form = GitRemoteForm({
            'name': 'invalid@name',
            'url': 'https://github.com/user/repo.git',
            'branch': 'main',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_invalid_url(self):
        form = GitRemoteForm({
            'name': 'origin',
            'url': 'not-a-url',
            'branch': 'main',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('url', form.errors)