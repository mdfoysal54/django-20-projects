"""BlogPress — Django admin registrations."""
from django.contrib import admin, messages

from .models import Category, Comment, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "post_count"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Published posts")
    def post_count(self, obj):
        return obj.post_count


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["cover_emoji", "title", "author", "category", "status", "featured", "views_count", "published_at"]
    list_filter = ["status", "featured", "category", "author"]
    search_fields = ["title", "body", "excerpt"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created"
    list_editable = ["featured"]
    actions = ["publish", "unpublish"]

    @admin.action(description="Publish selected posts")
    def publish(self, request, queryset):
        n = queryset.update(status=Post.Status.PUBLISHED)
        messages.success(request, f"{n} post(s) published.")

    @admin.action(description="Unpublish selected posts")
    def unpublish(self, request, queryset):
        n = queryset.update(status=Post.Status.DRAFT)
        messages.success(request, f"{n} post(s) moved to draft.")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["post", "author", "approved", "created", "short_body"]
    list_filter = ["approved", "created"]
    search_fields = ["body", "author__username", "post__title"]
    actions = ["approve", "reject"]

    @admin.display(description="Comment")
    def short_body(self, obj):
        return obj.body[:60]

    @admin.action(description="Approve selected comments")
    def approve(self, request, queryset):
        n = queryset.update(approved=True)
        messages.success(request, f"{n} comment(s) approved.")

    @admin.action(description="Unapprove selected comments")
    def reject(self, request, queryset):
        n = queryset.update(approved=False)
        messages.success(request, f"{n} comment(s) hidden.")
