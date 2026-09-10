"""BlogPress views — public feed, post pages, authoring and comment moderation."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CommentForm, PostForm
from .models import Category, Comment, Post


def _published():
    return Post.objects.filter(status=Post.Status.PUBLISHED).select_related("author", "category")


def index(request):
    posts = _published()
    return render(request, "blog/index.html", {
        "featured": posts.filter(featured=True)[:3],
        "latest": posts[:9],
        "categories": Category.objects.annotate(n=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))).filter(n__gt=0),
        "total_posts": posts.count(),
        "total_comments": Comment.objects.filter(approved=True).count(),
    })


def post_list(request):
    posts = _published()
    category_slug = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(category=category)
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(body__icontains=q) | Q(excerpt__icontains=q))
    paginator = Paginator(posts, 6)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "blog/post_list.html", {
        "page_obj": page, "category": category, "q": q,
        "categories": Category.objects.all(),
    })


def post_detail(request, slug):
    post = get_object_or_404(_published(), slug=slug)
    post.register_view()
    can_see_pending = request.user.is_authenticated and request.user == post.author
    comments = post.comments.filter(approved=True) if not can_see_pending else post.comments.all()
    created = False
    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Log in to join the discussion.")
            return redirect("login")
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            created = True
            messages.success(request, "Comment submitted — it appears once the author approves it.")
            return redirect(post)
    else:
        form = CommentForm()
    return render(request, "blog/post_detail.html", {
        "post": post, "comments": comments.select_related("author"),
        "form": form, "can_see_pending": can_see_pending, "created": created,
    })


# ------------------------------------------------------------------ authoring
@login_required
def dashboard(request):
    posts = request.user.posts.annotate(
        n_comments=Count("comments", filter=Q(comments__approved=True)),
        n_pending=Count("comments", filter=Q(comments__approved=False)),
    ).order_by("-created")
    return render(request, "blog/dashboard.html", {"posts": posts})


@login_required
def post_create(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.status = Post.Status.DRAFT
            post.save()
            messages.success(request, "Draft saved — publish it from your dashboard when ready.")
            return redirect("dashboard")
    else:
        form = PostForm()
    return render(request, "blog/post_form.html", {"form": form, "mode": "create"})


@login_required
def post_edit(request, slug):
    post = get_object_or_404(Post, slug=slug, author=request.user)   # author-scoped
    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated.")
            return redirect(post)
    else:
        form = PostForm(instance=post)
    return render(request, "blog/post_form.html", {"form": form, "post": post, "mode": "edit"})


@login_required
@require_POST
def post_toggle_publish(request, slug):
    post = get_object_or_404(Post, slug=slug, author=request.user)
    post.status = Post.Status.DRAFT if post.is_published else Post.Status.PUBLISHED
    post.save()
    messages.success(request, f"Post {'unpublished' if not post.is_published else 'published'}.")
    return redirect("dashboard")


@login_required
@require_POST
def post_delete(request, slug):
    post = get_object_or_404(Post, slug=slug, author=request.user)
    title = post.title
    post.delete()
    messages.success(request, f"“{title}” was deleted.")
    return redirect("dashboard")


# ------------------------------------------------------------------ moderation
@login_required
@require_POST
def comment_moderate(request, pk, action):
    comment = get_object_or_404(Comment.objects.select_related("post"), pk=pk, post__author=request.user)
    if action == "approve":
        comment.approved = True
        comment.save(update_fields=["approved"])
        messages.success(request, "Comment approved.")
    elif action == "delete":
        comment.delete()
        messages.success(request, "Comment deleted.")
    return redirect(comment.post)


@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "post_count": request.user.posts.count(),
        "published_count": request.user.posts.filter(status=Post.Status.PUBLISHED).count(),
        "comment_count": request.user.comments.count(),
    })
