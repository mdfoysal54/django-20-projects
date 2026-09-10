"""BlogPress models — categories, posts and moderated comments."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def unique_slug(model, value, exclude_pk=None) -> str:
    base = slugify(value)[:60] or "item"
    slug, n = base, 1
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        n += 1
        slug = f"{base}-{n}"
        qs = model.objects.filter(slug=slug)
    return slug


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True, editable=False)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def post_count(self) -> int:
        return self.posts.filter(status=Post.Status.PUBLISHED).count()


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=190, unique=True, blank=True, editable=False)
    excerpt = models.CharField(max_length=240, blank=True, help_text="Optional teaser for cards and feeds")
    body = models.TextField()
    cover_emoji = models.CharField(max_length=8, default="📝")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    featured = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created"]
        indexes = [models.Index(fields=["status", "-published_at"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Post, self.title, self.pk)
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        if self.status == self.Status.DRAFT:
            self.published_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("post_detail", kwargs={"slug": self.slug})

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def reading_minutes(self) -> int:
        words = len(self.body.split())
        return max(1, round(words / 200))

    @property
    def approved_comments(self):
        return self.comments.filter(approved=True)

    @property
    def pending_comments(self) -> int:
        return self.comments.filter(approved=False).count()

    def register_view(self):
        """Atomic counter increment — no read-modify-write race."""
        Post.objects.filter(pk=self.pk).update(views_count=models.F("views_count") + 1)


class Comment(models.Model):
    """Comments are moderated by default: approved=False until the author acts."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField(max_length=2000)
    approved = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self):
        state = "approved" if self.approved else "pending"
        return f"Comment by {self.author.username} ({state})"
