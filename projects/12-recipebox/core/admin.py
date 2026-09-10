"""RecipeBox — Django admin registrations."""
from django.contrib import admin, messages

from .models import Collection, Cuisine, Favorite, Rating, Recipe


@admin.register(Cuisine)
class CuisineAdmin(admin.ModelAdmin):
    list_display = ["emoji", "name", "slug", "recipe_count"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Recipes")
    def recipe_count(self, obj):
        return obj.recipes.filter(is_published=True).count()


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 0
    readonly_fields = ["user", "created", "updated"]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["emoji", "title", "author", "cuisine", "difficulty", "total_time",
                    "servings", "is_published", "avg_stars"]
    list_filter = ["is_published", "difficulty", "cuisine", "author"]
    search_fields = ["title", "summary", "ingredients", "steps"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [RatingInline]
    actions = ["publish", "unpublish"]

    @admin.display(description="Time")
    def total_time(self, obj):
        return f"{obj.total_minutes} min"

    @admin.display(description="Avg ★")
    def avg_stars(self, obj):
        avg = obj.average_rating
        return f"{avg:.1f}" if avg else "—"

    @admin.action(description="Publish selected recipes")
    def publish(self, request, queryset):
        n = queryset.update(is_published=True)
        messages.success(request, f"{n} recipe(s) published.")

    @admin.action(description="Unpublish selected recipes")
    def unpublish(self, request, queryset):
        n = queryset.update(is_published=False)
        messages.success(request, f"{n} recipe(s) hidden.")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["recipe", "user", "stars", "review", "updated"]
    list_filter = ["stars", "updated"]
    search_fields = ["recipe__title", "user__username", "review"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["recipe", "user", "created"]
    search_fields = ["recipe__title", "user__username"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "recipe_count", "created"]
    search_fields = ["name", "owner__username"]
    filter_horizontal = ["recipes"]

    @admin.display(description="Recipes")
    def recipe_count(self, obj):
        return obj.recipes.count()
