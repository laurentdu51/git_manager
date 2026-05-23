from django.contrib import admin

from .models import SshKey, GitRepo, GitRemote, PushLog, RemoteMonitor


@admin.register(SshKey)
class SshKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'fingerprint', 'created_at')
    search_fields = ('name', 'fingerprint')
    readonly_fields = ('public_key', 'fingerprint', 'created_at')


@admin.register(GitRepo)
class GitRepoAdmin(admin.ModelAdmin):
    list_display = ('name', 'path', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'path', 'description')


class GitRemoteInline(admin.TabularInline):
    model = GitRemote
    extra = 0
    fields = ('name', 'url', 'branch', 'ssh_key', 'is_active')
    autocomplete_fields = ('ssh_key',)


@admin.register(GitRemote)
class GitRemoteAdmin(admin.ModelAdmin):
    list_display = ('name', 'repo', 'url', 'branch', 'is_active')
    list_filter = ('is_active', 'repo')
    search_fields = ('name', 'url')
    autocomplete_fields = ('repo', 'ssh_key')


@admin.register(PushLog)
class PushLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'repo_name', 'remote_name', 'status', 'branch')
    list_filter = ('action', 'status', 'triggered_by')
    search_fields = ('repo_name', 'remote_name', 'commit_message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(RemoteMonitor)
class RemoteMonitorAdmin(admin.ModelAdmin):
    list_display = ('remote', 'status', 'commits_ahead', 'commits_behind', 'last_check')
    list_filter = ('status',)
    autocomplete_fields = ('remote',)
