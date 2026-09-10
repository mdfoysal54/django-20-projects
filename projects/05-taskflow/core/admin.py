"""TaskFlow — Django admin registrations."""
from django.contrib import admin

from .models import Activity, Comment, Membership, Project, Task


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ["user", "role"]


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ["title", "status", "priority", "assignee", "due_date"]
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "task_count", "done_count", "member_count", "archived", "updated"]
    list_filter = ["archived", "created"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline, TaskInline]
    actions = ["archive", "restore"]

    @admin.display(description="Tasks")
    def task_count(self, obj):
        return obj.task_count

    @admin.display(description="Done")
    def done_count(self, obj):
        return obj.done_count

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.member_count

    @admin.action(description="Archive selected projects")
    def archive(self, request, queryset):
        queryset.update(archived=True)

    @admin.action(description="Restore selected projects")
    def restore(self, request, queryset):
        queryset.update(archived=False)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "status", "priority", "assignee", "due_date", "updated"]
    list_filter = ["status", "priority", "project"]
    search_fields = ["title", "description"]
    list_editable = ["status", "priority", "assignee"]
    date_hierarchy = "created"
    readonly_fields = ["completed_at", "created", "updated"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "project", "role", "joined"]
    list_filter = ["role", "project"]
    search_fields = ["user__username", "project__name"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["task", "author", "created", "short_body"]
    search_fields = ["body", "author__username", "task__title"]

    @admin.display(description="Comment")
    def short_body(self, obj):
        return obj.body[:80]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["created", "user", "project", "verb"]
    list_filter = ["project"]
    search_fields = ["verb", "user__username"]
    date_hierarchy = "created"
