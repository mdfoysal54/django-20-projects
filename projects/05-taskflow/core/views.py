"""TaskFlow views — everything membership-scoped through core.access."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import get_project_for, projects_for, require_project_role
from .forms import CommentForm, MemberAddForm, ProjectForm, TaskForm
from .models import Activity, Comment, Membership, Project, Task


def _dashboard_context(user):
    projects = projects_for(user).annotate(
        n_tasks=Count("tasks", distinct=True),
        n_done=Count("tasks", filter=Q(tasks__status=Task.Status.DONE), distinct=True),
    )
    today = timezone.localdate()
    my_tasks = (
        Task.objects.filter(assignee=user)
        .exclude(status=Task.Status.DONE)
        .select_related("project")
        .order_by("due_date", "-priority")[:8]
    )
    overdue = Task.objects.filter(
        assignee=user, due_date__lt=today, project__in=projects_for(user),
    ).exclude(status=Task.Status.DONE).count()
    return {"projects": projects, "my_tasks": my_tasks, "overdue_count": overdue, "today": today}


# ------------------------------------------------------------------ dashboard
@login_required
def index(request):
    return render(request, "tasks/index.html", _dashboard_context(request.user))


# ------------------------------------------------------------------ projects
@login_required
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            Activity.log(project, request.user, f"created the project “{project.name}”")
            messages.success(request, f"Project “{project.name}” created.")
            return redirect(project)
    else:
        form = ProjectForm()
    return render(request, "tasks/project_form.html", {"form": form, "mode": "create"})


@login_required
@require_project_role("viewer")
def project_detail(request, slug, project):
    tasks = project.tasks.select_related("assignee")
    columns = []
    for status_value in Task.BOARD_COLUMNS:
        columns.append({
            "value": status_value,
            "label": Task.Status(status_value).label,
            "tasks": [t for t in tasks if t.status == status_value],
        })
    unassigned = tasks.filter(assignee__isnull=True).exclude(status=Task.Status.DONE).count()
    return render(request, "tasks/project_detail.html", {
        "project": project,
        "columns": columns,
        "members": project.memberships.select_related("user"),
        "activities": project.activities.select_related("user")[:12],
        "unassigned_count": unassigned,
        "my_role": project.role_of(request.user),
    })


@login_required
@require_project_role("admin")
def project_edit(request, slug, project):
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated.")
            return redirect(project)
    else:
        form = ProjectForm(instance=project)
    return render(request, "tasks/project_form.html", {"form": form, "project": project, "mode": "edit"})


@login_required
@require_project_role("owner")
@require_POST
def project_archive(request, slug, project):
    project.archived = not project.archived
    project.save(update_fields=["archived", "updated"])
    Activity.log(project, request.user, f"{'archived' if project.archived else 'unarchived'} the project")
    messages.success(request, f"Project {'archived' if project.archived else 'restored'}.")
    return redirect(project)


# ------------------------------------------------------------------ members
@login_required
@require_project_role("admin")
def member_list(request, slug, project):
    form = MemberAddForm(project=project)
    if request.method == "POST":
        form = MemberAddForm(request.POST, project=project)
        if form.is_valid():
            Membership.objects.create(project=project, user=form.user, role=form.cleaned_data["role"])
            Activity.log(project, request.user, f"added {form.user.username} as {form.cleaned_data['role']}")
            messages.success(request, f"{form.user.username} joined the project.")
            return redirect("member_list", slug=project.slug)
    return render(request, "tasks/member_list.html", {
        "project": project,
        "form": form,
        "members": project.memberships.select_related("user"),
    })


@login_required
@require_project_role("admin")
@require_POST
def member_remove(request, slug, project, user_id):
    membership = get_object_or_404(Membership, project=project, user_id=user_id)
    username = membership.user.username
    membership.delete()
    Activity.log(project, request.user, f"removed {username} from the project")
    messages.success(request, f"{username} was removed.")
    return redirect("member_list", slug=project.slug)


# ------------------------------------------------------------------ tasks
@login_required
@require_project_role("member")
def task_create(request, slug, project):
    if request.method == "POST":
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.created_by = request.user
            task.position = (project.tasks.aggregate(m=Max("position"))["m"] or 0) + 1
            task.save()
            Activity.log(project, request.user, f"created task “{task.title}”", task=task)
            messages.success(request, "Task created.")
            return redirect(project)
    else:
        form = TaskForm(project=project)
    return render(request, "tasks/task_form.html", {"form": form, "project": project, "mode": "create"})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("project", "assignee"), pk=pk)
    project = get_project_for(request.user, task.project.slug)   # membership gate
    comment_form = CommentForm()
    if request.method == "POST" and project.can_edit(request.user):
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            Activity.log(project, request.user, f"commented on “{task.title}”", task=task)
            messages.success(request, "Comment added.")
            return redirect(task)
    elif request.method == "POST":
        messages.error(request, "Viewers cannot comment on this project.")
    return render(request, "tasks/task_detail.html", {
        "task": task,
        "project": project,
        "comments": task.comments.select_related("author"),
        "comment_form": comment_form,
        "can_edit": project.can_edit(request.user),
        "my_role": project.role_of(request.user),
    })


@login_required
@require_project_role("member")
def task_edit(request, slug, project, pk):
    task = get_object_or_404(Task, pk=pk, project=project)
    if request.method == "POST":
        form = TaskForm(request.POST, project=project, instance=task)
        if form.is_valid():
            form.save()
            Activity.log(project, request.user, f"updated task “{task.title}”", task=task)
            messages.success(request, "Task updated.")
            return redirect(task)
    else:
        form = TaskForm(project=project, instance=task)
    return render(request, "tasks/task_form.html", {"form": form, "project": project, "task": task, "mode": "edit"})


@login_required
@require_project_role("member")
@require_POST
def task_move(request, slug, project, pk):
    """Move a task to another board column (or relative position)."""
    task = get_object_or_404(Task, pk=pk, project=project)
    new_status = request.POST.get("status", "")
    if new_status not in Task.Status.values:
        messages.error(request, "Unknown column.")
        return redirect(project)
    if task.status != new_status:
        task.set_status(new_status, by_user=request.user)
    direction = request.POST.get("direction")
    if direction in ("up", "down"):
        siblings = list(project.tasks.filter(status=task.status).order_by("position", "pk")
                        .values_list("pk", flat=True))
        if task.pk in siblings:
            index = siblings.index(task.pk)
            swap_with = index - 1 if direction == "up" else index + 1
            if 0 <= swap_with < len(siblings):
                other = Task.objects.get(pk=siblings[swap_with])
                task.position, other.position = other.position, task.position
                Task.objects.bulk_update([task, other], ["position"])
    return redirect(project)


@login_required
@require_project_role("admin")
@require_POST
def task_delete(request, slug, project, pk):
    task = get_object_or_404(Task, pk=pk, project=project)
    title = task.title
    task.delete()
    Activity.log(project, request.user, f"deleted task “{title}”")
    messages.success(request, f"Task “{title}” deleted.")
    return redirect(project)


# ------------------------------------------------------------------ my work
@login_required
def my_tasks(request):
    tasks = (
        Task.objects.filter(assignee=request.user, project__in=projects_for(request.user))
        .select_related("project")
        .order_by("status", "due_date")
    )
    return render(request, "tasks/my_tasks.html", {"tasks": tasks})


@login_required
def activity_feed(request):
    activities = (
        Activity.objects.filter(project__in=projects_for(request.user))
        .select_related("user", "project", "task")[:50]
    )
    return render(request, "tasks/activity.html", {"activities": activities})


# ------------------------------------------------------------------ account
@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "owned": request.user.owned_projects.count(),
        "memberships": request.user.memberships.count(),
        "assigned": request.user.assigned_tasks.exclude(status=Task.Status.DONE).count(),
    })

