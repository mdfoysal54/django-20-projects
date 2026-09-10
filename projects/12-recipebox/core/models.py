"""RecipeBox models — recipes with scalable ingredients, one-rating-per-user and favourites."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

_NUMBER = re.compile(r"^(\d+(?:\.\d+)?|\d+/\d+)\s+(.*)$")


def format_amount(value: Decimal) -> str:
    """Decimal → tidy string ('100', '1.5', '0.25') with no exponent notation."""
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class Cuisine(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    emoji = models.CharField(max_length=8, default="🍽️")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Cuisines"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Recipe(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes")
    cuisine = models.ForeignKey(Cuisine, on_delete=models.SET_NULL, null=True, blank=True, related_name="recipes")
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    summary = models.CharField(max_length=240, blank=True)
    ingredients = models.TextField(help_text="One ingredient per line, starting with the quantity — e.g. '200 g flour'.")
    steps = models.TextField(help_text="One step per line.")
    prep_minutes = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1)])
    cook_minutes = models.PositiveSmallIntegerField(default=20, validators=[MinValueValidator(0)])
    servings = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    difficulty = models.CharField(max_length=6, choices=Difficulty.choices, default=Difficulty.EASY)
    emoji = models.CharField(max_length=8, default="🍲")
    is_published = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["is_published", "-created"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:60] or "recipe"
            slug, n = base, 1
            while Recipe.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("recipe_detail", kwargs={"slug": self.slug})

    # ---------------------------------------------------------------- derived
    @property
    def total_minutes(self) -> int:
        return self.prep_minutes + self.cook_minutes

    @property
    def average_rating(self):
        return self.ratings.aggregate(avg=models.Avg("stars"))["avg"]

    @property
    def rating_count(self) -> int:
        return self.ratings.count()

    @property
    def favourite_count(self) -> int:
        return self.favourites.count()

    def ingredient_lines(self):
        return [line.strip() for line in self.ingredients.splitlines() if line.strip()]

    def step_lines(self):
        return [line.strip() for line in self.steps.splitlines() if line.strip()]

    def scaled_ingredients(self, servings):
        """Ingredients rescaled from the recipe's own serving count.

        Leading quantities (including fractions like '1/2') are multiplied; any
        line without a leading number is passed through unchanged.
        """
        try:
            servings = int(servings)
        except (TypeError, ValueError):
            servings = self.servings
        servings = max(1, min(servings, 99))
        factor = Decimal(servings) / Decimal(self.servings)
        scaled = []
        for line in self.ingredient_lines():
            match = _NUMBER.match(line)
            if not match:
                scaled.append({"text": line, "amount": None})
                continue
            raw, rest = match.groups()
            try:
                if "/" in raw:
                    numerator, denominator = raw.split("/")
                    value = Decimal(numerator) / Decimal(denominator)
                else:
                    value = Decimal(raw)
            except (InvalidOperation, ZeroDivisionError):
                scaled.append({"text": line, "amount": None})
                continue
            scaled.append({"text": f"{format_amount(value * factor)} {rest}".strip(),
                           "amount": format_amount(value * factor)})
        return scaled

    def scale_factor(self, servings) -> Decimal:
        """Factor to reach `servings`, clamped to a sane 1–99 serving range."""
        try:
            servings = int(servings)
        except (TypeError, ValueError):
            servings = self.servings
        servings = max(1, min(servings, 99))
        return (Decimal(servings) / Decimal(self.servings)).quantize(Decimal("0.01"))

    def can_be_rated_by(self, user) -> bool:
        """You cannot rate your own cooking."""
        if not user.is_authenticated:
            return False
        return user != self.author


class Rating(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_ratings")
    stars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]
        constraints = [
            models.UniqueConstraint(fields=["recipe", "user"], name="one_rating_per_user_per_recipe"),
            models.CheckConstraint(check=models.Q(stars__gte=1) & models.Q(stars__lte=5), name="rating_stars_1_5"),
        ]

    def __str__(self):
        return f"{self.recipe.title}: {self.stars}★ by {self.user.username}"


class Favorite(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="favourites")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_favourites")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["recipe", "user"], name="favourite_unique_per_user")]

    def __str__(self):
        return f"{self.user.username} ♥ {self.recipe.title}"


class Collection(models.Model):
    """A user's named list of recipes (e.g. 'Weeknight dinners')."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collections")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    recipes = models.ManyToManyField(Recipe, blank=True, related_name="collections")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="collection_name_unique_per_owner")]

    def __str__(self):
        return self.name
