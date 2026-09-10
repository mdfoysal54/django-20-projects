"""QuizMaster — Django admin registrations."""
from django.contrib import admin, messages

from .models import Answer, Attempt, Category, Option, Question, Quiz


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["emoji", "name", "slug", "quiz_count"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Quizzes")
    def quiz_count(self, obj):
        return obj.quizzes.count()


class OptionInline(admin.TabularInline):
    model = Option
    extra = 2
    fields = ["order", "text", "is_correct"]


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ["order", "kind", "text", "points", "active"]
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["emoji", "title", "author", "category", "visibility", "question_count",
                    "total_points", "pass_mark", "attempt_count"]
    list_filter = ["visibility", "category", "author", "one_attempt_only"]
    search_fields = ["title", "description", "author__username"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [QuestionInline]
    actions = ["publish", "unpublish"]

    @admin.display(description="Questions")
    def question_count(self, obj):
        return obj.question_count

    @admin.display(description="Attempts")
    def attempt_count(self, obj):
        return obj.attempts.count()

    @admin.action(description="Publish selected quizzes")
    def publish(self, request, queryset):
        n = queryset.update(visibility=Quiz.Visibility.PUBLIC)
        messages.success(request, f"{n} quiz(zes) published.")

    @admin.action(description="Return selected quizzes to draft")
    def unpublish(self, request, queryset):
        n = queryset.update(visibility=Quiz.Visibility.DRAFT)
        messages.success(request, f"{n} quiz(zes) moved to draft.")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["quiz", "order", "kind", "short_text", "points", "active", "correct_count"]
    list_filter = ["kind", "active", "quiz"]
    search_fields = ["text", "quiz__title"]
    inlines = [OptionInline]

    @admin.display(description="Question")
    def short_text(self, obj):
        return obj.text[:60]

    @admin.display(description="Correct")
    def correct_count(self, obj):
        return obj.correct_options().count()


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    can_delete = False
    readonly_fields = ["question", "text_answer", "points_awarded", "is_correct", "graded_at"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "quiz", "score", "max_score", "percent_display", "passed",
                    "started_at", "submitted_at"]
    list_filter = ["quiz", "submitted_at"]
    search_fields = ["user__username", "quiz__title"]
    date_hierarchy = "started_at"
    readonly_fields = ["started_at", "submitted_at", "score", "max_score"]
    inlines = [AnswerInline]
    actions = ["regrade"]

    @admin.display(description="Score %")
    def percent_display(self, obj):
        return f"{obj.percent}%"

    @admin.display(boolean=True, description="Passed?")
    def passed(self, obj):
        return obj.passed

    @admin.action(description="Re-grade selected attempts")
    def regrade(self, request, queryset):
        n = 0
        for attempt in queryset.filter(submitted_at__isnull=False):
            for answer in attempt.answers.all():
                answer.grade()
            attempt.score = sum(a.points_awarded for a in attempt.answers.all())
            attempt.save(update_fields=["score"])
            n += 1
        messages.success(request, f"{n} attempt(s) re-graded from the stored answers.")


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ["question", "order", "text", "is_correct"]
    list_filter = ["is_correct"]
    search_fields = ["text", "question__text"]
