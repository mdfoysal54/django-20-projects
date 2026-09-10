"""RecipeBox views — browse, cook, rate, favourite."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CollectionForm, RatingForm, RecipeForm
from .models import Collection, Cuisine, Favorite, Rating, Recipe

SORTS = {
    "newest": ("-created", "Newest first"),
    "rating": ("-avg_rating", "Best rated"),
    "fast": ("total_time", "Quickest"),
    "popular": ("-fav_count", "Most cooked"),
}


def _public_recipes():
    return (Recipe.objects.filter(is_published=True)
            .select_related("author", "cuisine")
            .annotate(avg_rating=Avg("ratings__stars"), n_ratings=Count("ratings", distinct=True),
                      n_favs=Count("favourites", distinct=True)))


def index(request):
    recipes = _public_recipes()
    return render(request, "recipes/index.html", {
        "featured": recipes.filter(avg_rating__gte=4)[:3] or recipes[:3],
        "latest": recipes.order_by("-created")[:6],
        "cuisines": Cuisine.objects.annotate(n=Count("recipes", filter=Q(recipes__is_published=True))),
        "total_recipes": recipes.count(),
        "total_ratings": Rating.objects.count(),
    })


def recipe_list(request):
    recipes = _public_recipes()
    cuisine_slug = request.GET.get("cuisine", "")
    difficulty = request.GET.get("difficulty", "")
    max_time = request.GET.get("max_time", "")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest")

    if cuisine_slug:
        recipes = recipes.filter(cuisine__slug=cuisine_slug)
    if difficulty in dict(Recipe.Difficulty.choices):
        recipes = recipes.filter(difficulty=difficulty)
    if max_time.isdigit():
        recipes = recipes.filter(prep_minutes__lte=int(max_time), cook_minutes__lte=int(max_time))
    if q:
        recipes = recipes.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(ingredients__icontains=q))

    if sort == "rating":
        recipes = recipes.order_by("-avg_rating", "-n_ratings")
    elif sort == "fast":
        recipes = recipes.order_by("prep_minutes", "cook_minutes")
    elif sort == "popular":
        recipes = recipes.order_by("-n_favs")
    else:
        recipes = recipes.order_by("-created")

    paginator = Paginator(recipes, 9)
    return render(request, "recipes/recipe_list.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q, "sort": sort,
        "cuisine_slug": cuisine_slug, "difficulty": difficulty, "max_time": max_time,
        "cuisines": Cuisine.objects.all(), "difficulties": Recipe.Difficulty.choices,
        "sorts": [(key, meta[1]) for key, meta in SORTS.items()],
    })


def recipe_detail(request, slug):
    recipe = get_object_or_404(Recipe.objects.select_related("author", "cuisine")
                               .annotate(avg_rating=Avg("ratings__stars")), slug=slug)
    if not recipe.is_published and request.user != recipe.author and not request.user.is_staff:
        raise Http404("No recipe found.")            # drafts stay private

    requested_servings = request.GET.get("servings")
    try:
        servings = int(requested_servings) if requested_servings else recipe.servings
    except ValueError:
        servings = recipe.servings
    servings = max(1, min(servings, 99))

    my_rating = None
    is_favourite = False
    if request.user.is_authenticated:
        my_rating = recipe.ratings.filter(user=request.user).first()
        is_favourite = recipe.favourites.filter(user=request.user).exists()

    return render(request, "recipes/recipe_detail.html", {
        "recipe": recipe,
        "ingredients": recipe.scaled_ingredients(servings),
        "servings": servings,
        "scale_factor": recipe.scale_factor(servings),
        "can_rate": recipe.can_be_rated_by(request.user),
        "my_rating": my_rating,
        "rating_form": RatingForm(instance=my_rating),
        "is_favourite": is_favourite,
        "ratings": recipe.ratings.select_related("user").order_by("-updated")[:10],
        "is_author": request.user.is_authenticated and request.user == recipe.author,
    })


@login_required
@require_POST
def rate(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    if not recipe.can_be_rated_by(request.user):
        messages.error(request, "You cannot rate your own recipe.")
        return redirect(recipe)
    form = RatingForm(request.POST)
    if form.is_valid():
        rating, created = Rating.objects.update_or_create(
            recipe=recipe, user=request.user,
            defaults={"stars": form.cleaned_data["stars"], "review": form.cleaned_data["review"]},
        )
        messages.success(request, f"{'Thanks for rating' if created else 'Rating updated'} — {rating.stars}★.")
    else:
        messages.error(request, "Pick a star rating between 1 and 5.")
    return redirect(recipe)


@login_required
@require_POST
def toggle_favourite(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    favourite = Favorite.objects.filter(recipe=recipe, user=request.user).first()
    if favourite:
        favourite.delete()
        messages.success(request, "Removed from your favourites.")
    else:
        Favorite.objects.create(recipe=recipe, user=request.user)
        messages.success(request, "Saved to your favourites.")
    return redirect(recipe)


# ------------------------------------------------------------------ authoring
@login_required
def recipe_create(request):
    if request.method == "POST":
        form = RecipeForm(request.POST)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.author = request.user
            recipe.save()
            messages.success(request, "Recipe saved.")
            return redirect(recipe)
        messages.error(request, "Please fix the highlighted fields.")
    else:
        form = RecipeForm()
    return render(request, "recipes/recipe_form.html", {"form": form, "mode": "create"})


@login_required
def recipe_edit(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, author=request.user)
    if request.method == "POST":
        form = RecipeForm(request.POST, instance=recipe)
        if form.is_valid():
            form.save()
            messages.success(request, "Recipe updated.")
            return redirect(recipe)
    else:
        form = RecipeForm(instance=recipe)
    return render(request, "recipes/recipe_form.html", {"form": form, "recipe": recipe, "mode": "edit"})


@login_required
@require_POST
def recipe_delete(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, author=request.user)
    title = recipe.title
    recipe.delete()
    messages.success(request, f"“{title}” deleted.")
    return redirect("my_recipes")


@login_required
def my_recipes(request):
    recipes = (Recipe.objects.filter(author=request.user)
               .annotate(avg_rating=Avg("ratings__stars"), n_ratings=Count("ratings", distinct=True),
                         n_favs=Count("favourites", distinct=True)))
    return render(request, "recipes/my_recipes.html", {"recipes": recipes})


@login_required
def favourites(request):
    saved = (Favorite.objects.filter(user=request.user)
             .select_related("recipe", "recipe__author")
             .annotate(avg=Avg("recipe__ratings__stars")))
    return render(request, "recipes/favourites.html", {"favourites": saved})


# ---------------------------------------------------------------- collections
@login_required
def collections(request):
    form = CollectionForm()
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.owner = request.user
            if Collection.objects.filter(owner=request.user, name=collection.name).exists():
                messages.error(request, "You already have a collection with that name.")
            else:
                collection.save()
                messages.success(request, "Collection created.")
                return redirect("collections")
    items = request.user.collections.annotate(n=Count("recipes"))
    return render(request, "recipes/collections.html", {"form": form, "collections": items})


@login_required
@require_POST
def collection_toggle(request, pk, slug):
    collection = get_object_or_404(Collection, pk=pk, owner=request.user)
    recipe = get_object_or_404(Recipe, slug=slug)
    if collection.recipes.filter(pk=recipe.pk).exists():
        collection.recipes.remove(recipe)
        messages.success(request, f"Removed {recipe.title} from {collection.name}.")
    else:
        collection.recipes.add(recipe)
        messages.success(request, f"Added {recipe.title} to {collection.name}.")
    return redirect(recipe)


@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "recipe_count": request.user.recipes.count(),
        "published_count": request.user.recipes.filter(is_published=True).count(),
        "rating_count": request.user.recipe_ratings.count(),
        "favourite_count": request.user.recipe_favourites.count(),
        "collections": request.user.collections.annotate(n=Count("recipes")),
    })
