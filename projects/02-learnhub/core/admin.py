"""LearnHub — Django admin registrations."""
from django.contrib import admin, messages

from .models import Course, Enrollment, Lesson, LessonProgress


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ["order", "title", "duration_minutes", "resource_url", "content"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "instructor", "level", "price", "status", "lesson_count", "student_count", "created"]
    list_filter = ["status", "level", "created"]
    search_fields = ["title", "summary", "description", "instructor__username"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [LessonInline]
    list_per_page = 25
    actions = ["publish", "unpublish", "archive"]

    @admin.display(description="Lessons")
    def lesson_count(self, obj):
        return obj.lesson_count

    @admin.display(description="Students")
    def student_count(self, obj):
        return obj.student_count

    @admin.action(description="Publish selected courses")
    def publish(self, request, queryset):
        n = queryset.update(status=Course.Status.PUBLISHED)
        messages.success(request, f"{n} course(s) published.")

    @admin.action(description="Move selected courses to draft")
    def unpublish(self, request, queryset):
        n = queryset.update(status=Course.Status.DRAFT)
        messages.success(request, f"{n} course(s) moved to draft.")

    @admin.action(description="Archive selected courses")
    def archive(self, request, queryset):
        n = queryset.update(status=Course.Status.ARCHIVED)
        messages.success(request, f"{n} course(s) archived.")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["course", "order", "title", "duration_minutes"]
    list_filter = ["course"]
    search_fields = ["title", "content"]
    ordering = ["course", "order"]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "course", "enrolled_at", "completed_lessons", "progress_percent"]
    list_filter = ["course", "enrolled_at"]
    search_fields = ["student__username", "course__title"]
    readonly_fields = ["enrolled_at"]

    @admin.display(description="Done")
    def completed_lessons(self, obj):
        return obj.completed_lessons

    @admin.display(description="Progress")
    def progress_percent(self, obj):
        return f"{obj.progress_percent}%"


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "lesson", "completed", "completed_at"]
    list_filter = ["completed"]
    search_fields = ["enrollment__student__username", "lesson__title"]
