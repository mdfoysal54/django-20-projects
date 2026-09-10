"""LearnHub views.

Access model:
  * catalogue + course pages are public (published courses only);
  * lesson content is gated: enrolled students, the course instructor and
    staff only — anyone else is redirected back to the course page;
  * authoring (create/edit course, add lesson) is instructor-scoped:
    get_object_or_404(Course, …, instructor=request.user).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CourseForm, LessonForm
from .models import Course, Enrollment, Lesson, LessonProgress


def _visible_courses(user):
    """Published courses; logged-in users also see their own drafts."""
    qs = Course.objects.select_related("instructor")
    if user.is_authenticated:
        if user.is_staff:
            return qs
        return qs.filter(Q(status=Course.Status.PUBLISHED) | Q(instructor=user))
    return qs.filter(status=Course.Status.PUBLISHED)


def _enrollment_for(user, course):
    if not user.is_authenticated:
        return None
    return Enrollment.objects.filter(student=user, course=course).first()


def _can_view_lessons(user, course, enrollment) -> bool:
    return bool(
        enrollment
        or (user.is_authenticated and (course.instructor_id == user.id or user.is_staff))
    )


# ------------------------------------------------------------------ catalogue
def index(request):
    featured = _visible_courses(request.user).filter(status=Course.Status.PUBLISHED)[:6]
    level_stats = (
        Course.objects.filter(status=Course.Status.PUBLISHED)
        .values("level").annotate(n=Count("id")).order_by("level")
    )
    context = {
        "featured": featured,
        "level_stats": level_stats,
        "total_courses": Course.objects.filter(status=Course.Status.PUBLISHED).count(),
        "total_lessons": Lesson.objects.filter(course__status=Course.Status.PUBLISHED).count(),
        "total_students": Enrollment.objects.count(),
        "my_enrollments": (
            Enrollment.objects.filter(student=request.user).select_related("course")
            if request.user.is_authenticated else []
        ),
    }
    return render(request, "learn/index.html", context)


def catalog(request):
    courses = _visible_courses(request.user)
    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "")
    if q:
        courses = courses.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(description__icontains=q))
    if level in Course.Level.values:
        courses = courses.filter(level=level)
    courses = courses.annotate(n_lessons=Count("lesson"), n_students=Count("enrollments"))
    return render(request, "learn/catalog.html", {
        "courses": courses, "q": q, "level": level, "levels": Course.Level.choices,
    })


def course_detail(request, slug):
    course = get_object_or_404(_visible_courses(request.user), slug=slug)
    enrollment = _enrollment_for(request.user, course)
    lessons = list(course.lessons)
    completed_ids = set()
    if enrollment:
        completed_ids = set(
            enrollment.progress.filter(completed=True).values_list("lesson_id", flat=True)
        )
    next_lesson = next((l for l in lessons if l.pk not in completed_ids), lessons[0] if lessons else None)
    return render(request, "learn/course_detail.html", {
        "course": course,
        "lessons": lessons,
        "enrollment": enrollment,
        "completed_ids": completed_ids,
        "next_lesson": next_lesson,
        "can_view": _can_view_lessons(request.user, course, enrollment),
    })


# ------------------------------------------------------------------ enrolment
@login_required
@require_POST
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
    if course.instructor_id == request.user.id:
        messages.info(request, "You are the instructor of this course.")
        return redirect(course)
    enrollment, created = Enrollment.objects.get_or_create(student=request.user, course=course)
    if created:
        messages.success(request, f"You're enrolled in “{course.title}”. Happy learning!")
    else:
        messages.info(request, "You are already enrolled in this course.")
    return redirect(course)


@login_required
def my_learning(request):
    enrollments = (
        Enrollment.objects.filter(student=request.user)
        .select_related("course", "course__instructor")
        .prefetch_related("progress")
        .order_by("-enrolled_at")
    )
    return render(request, "learn/my_learning.html", {"enrollments": enrollments})


# ------------------------------------------------------------------ lessons
@login_required
def lesson_detail(request, slug, lesson_pk):
    course = get_object_or_404(_visible_courses(request.user), slug=slug)
    lesson = get_object_or_404(Lesson, pk=lesson_pk, course=course)
    enrollment = _enrollment_for(request.user, course)
    if not _can_view_lessons(request.user, course, enrollment):
        messages.warning(request, "Enrol in this course to unlock its lessons.")
        return redirect(course)

    record = None
    if enrollment:
        record, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    lessons = list(course.lessons)
    idx = next((i for i, l in enumerate(lessons) if l.pk == lesson.pk), 0)
    return render(request, "learn/lesson.html", {
        "course": course,
        "lesson": lesson,
        "record": record,
        "prev": lessons[idx - 1] if idx > 0 else None,
        "next": lessons[idx + 1] if idx + 1 < len(lessons) else None,
        "position": idx + 1,
        "total": len(lessons),
    })


@login_required
@require_POST
def lesson_complete(request, slug, lesson_pk):
    course = get_object_or_404(Course, slug=slug)
    lesson = get_object_or_404(Lesson, pk=lesson_pk, course=course)
    enrollment = _enrollment_for(request.user, course)
    if not enrollment:
        messages.error(request, "Enrol in this course first.")
        return redirect(course)

    record, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    if not record.completed:
        record.completed = True
        record.completed_at = timezone.now()
        record.save(update_fields=["completed", "completed_at"])
        messages.success(request, f"Lesson “{lesson.title}” marked complete — nice work!")
    else:
        messages.info(request, "This lesson was already complete.")

    if enrollment.is_finished:
        messages.success(request, f"🎉 You finished “{course.title}”!")
        return redirect(course)

    lessons = list(course.lessons)
    idx = next((i for i, l in enumerate(lessons) if l.pk == lesson.pk), 0)
    if idx + 1 < len(lessons):
        return redirect("lesson_detail", slug=course.slug, lesson_pk=lessons[idx + 1].pk)
    return redirect(course)


# ------------------------------------------------------------------ authoring
@login_required
def teach(request):
    courses = (
        Course.objects.filter(instructor=request.user)
        .annotate(n_lessons=Count("lesson"), n_students=Count("enrollments"))
        .order_by("-created")
    )
    return render(request, "learn/teach.html", {"courses": courses})


@login_required
def course_create(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.status = Course.Status.DRAFT
            course.save()
            messages.success(request, "Course created as a draft — add your lessons next.")
            return redirect("lesson_create", slug=course.slug)
    else:
        form = CourseForm()
    return render(request, "learn/course_form.html", {"form": form, "mode": "create"})


@login_required
def course_edit(request, slug):
    course = get_object_or_404(Course, slug=slug, instructor=request.user)  # instructor-only
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "publish" and course.lesson_count > 0:
            course.status = Course.Status.PUBLISHED
            course.save(update_fields=["status", "updated"])
            messages.success(request, "Course published! Students can enrol now.")
            return redirect(course)
        if action == "unpublish":
            course.status = Course.Status.DRAFT
            course.save(update_fields=["status", "updated"])
            messages.info(request, "Course moved back to draft.")
            return redirect(course)
        if action == "publish" and course.lesson_count == 0:
            messages.error(request, "Add at least one lesson before publishing.")

        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated.")
            return redirect(course)
    else:
        form = CourseForm(instance=course)
    return render(request, "learn/course_form.html", {"form": form, "course": course, "mode": "edit"})


@login_required
def lesson_create(request, slug):
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    if request.method == "POST":
        form = LessonForm(request.POST, course=course)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, "Lesson added to the curriculum.")
            return redirect("lesson_create", slug=course.slug)
    else:
        next_order = (course.lesson_set.aggregate(m=Max("order"))["m"] or 0) + 1
        form = LessonForm(course=course, initial={"order": next_order, "duration_minutes": 10})
    return render(request, "learn/lesson_form.html", {"form": form, "course": course})


# ------------------------------------------------------------------ account
@login_required
def profile(request):
    enrollments = request.user.enrollments.select_related("course")
    return render(request, "account/profile.html", {
        "enrollments": enrollments,
        "taught_count": request.user.courses_taught.count(),
    })
