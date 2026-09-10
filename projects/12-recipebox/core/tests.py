"""RecipeBox domain tests — scaling maths, one rating per user, favourites, privacy."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Collection, Cuisine, Favorite, Rating, Recipe, format_amount


def make_recipe(author, title="Chicken Biryani", servings=4, published=True, **kw):
    return Recipe.objects.create(
        author=author, title=title, servings=servings, is_published=published,
        ingredients=kw.pop("ingredients", "200 g basmati rice\n1/2 tsp turmeric\n2 onions, sliced\nSalt to taste"),
        steps=kw.pop("steps", "Soak the rice.\nFry the onions.\nLayer and steam for 20 minutes."),
        **kw,
    )


class ScalingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("cook", password="Str0ng!Passw0rd")
        self.recipe = make_recipe(self.author, servings=4)

    def test_halving_the_recipe_halves_quantities(self):
        scaled = self.recipe.scaled_ingredients(2)
        self.assertEqual(scaled[0]["text"], "100 g basmati rice")
        self.assertEqual(scaled[2]["text"], "1 onions, sliced")

    def test_doubling_the_recipe_doubles_quantities(self):
        scaled = self.recipe.scaled_ingredients(8)
        self.assertEqual(scaled[0]["text"], "400 g basmati rice")

    def test_fractional_amounts_scale(self):
        scaled = self.recipe.scaled_ingredients(8)          # ×2 of 1/2 tsp
        self.assertEqual(scaled[1]["text"], "1 tsp turmeric")
        scaled = self.recipe.scaled_ingredients(2)          # ×0.5 → 0.25
        self.assertEqual(scaled[1]["text"], "0.25 tsp turmeric")

    def test_lines_without_quantities_pass_through(self):
        scaled = self.recipe.scaled_ingredients(2)
        self.assertEqual(scaled[3]["text"], "Salt to taste")
        self.assertIsNone(scaled[3]["amount"])

    def test_scale_factor_and_amount_formatting(self):
        self.assertEqual(self.recipe.scale_factor(6), Decimal("1.50"))
        self.assertEqual(format_amount(Decimal("1.500")), "1.5")
        self.assertEqual(format_amount(Decimal("100.00")), "100")
        self.assertEqual(format_amount(Decimal("0.2500")), "0.25")

    def test_absurd_serving_counts_are_clamped(self):
        self.assertEqual(len(self.recipe.scaled_ingredients(0)), len(self.recipe.ingredient_lines()))
        self.assertLessEqual(int(self.recipe.scale_factor(10000)), 99)
        self.assertEqual(self.recipe.scale_factor("nonsense"), Decimal("1.00"))


class RatingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("cook", password="Str0ng!Passw0rd")
        self.taster = User.objects.create_user("taster", password="Str0ng!Passw0rd")
        self.other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        self.recipe = make_recipe(self.author)

    def test_rating_recorded_and_average_computed(self):
        self.client.force_login(self.taster)
        self.client.post(self.recipe.get_absolute_url() and reverse("rate", kwargs={"slug": self.recipe.slug}),
                         {"stars": 5, "review": "Perfect."})
        self.assertEqual(self.recipe.ratings.count(), 1)
        self.assertEqual(self.recipe.average_rating, 5)

    def test_second_rating_updates_rather_than_duplicates(self):
        Rating.objects.create(recipe=self.recipe, user=self.taster, stars=3)
        self.client.force_login(self.taster)
        self.client.post(reverse("rate", kwargs={"slug": self.recipe.slug}), {"stars": 4, "review": "Better second time."})
        self.assertEqual(self.recipe.ratings.count(), 1)
        self.assertEqual(self.recipe.ratings.first().stars, 4)

    def test_database_refuses_a_duplicate_rating(self):
        Rating.objects.create(recipe=self.recipe, user=self.taster, stars=4)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rating.objects.create(recipe=self.recipe, user=self.taster, stars=5)

    def test_author_cannot_rate_their_own_recipe(self):
        self.assertFalse(self.recipe.can_be_rated_by(self.author))
        self.client.force_login(self.author)
        response = self.client.post(reverse("rate", kwargs={"slug": self.recipe.slug}), {"stars": 5}, follow=True)
        self.assertContains(response, "cannot rate your own recipe")
        self.assertFalse(self.recipe.ratings.exists())

    def test_stars_out_of_range_are_rejected_by_the_db(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rating.objects.create(recipe=self.recipe, user=self.taster, stars=9)

    def test_anonymous_rating_is_refused(self):
        response = self.client.post(reverse("rate", kwargs={"slug": self.recipe.slug}), {"stars": 5})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.recipe.ratings.exists())


class FavouriteTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("cook", password="Str0ng!Passw0rd")
        self.fan = User.objects.create_user("fan", password="Str0ng!Passw0rd")
        self.recipe = make_recipe(self.author)

    def test_toggle_adds_then_removes(self):
        self.client.force_login(self.fan)
        url = reverse("toggle_favourite", kwargs={"slug": self.recipe.slug})
        self.client.post(url)
        self.assertTrue(Favorite.objects.filter(recipe=self.recipe, user=self.fan).exists())
        self.client.post(url)
        self.assertFalse(Favorite.objects.filter(recipe=self.recipe, user=self.fan).exists())

    def test_cannot_favourite_twice_in_the_database(self):
        Favorite.objects.create(recipe=self.recipe, user=self.fan)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Favorite.objects.create(recipe=self.recipe, user=self.fan)

    def test_favourites_page_lists_only_yours(self):
        other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        Favorite.objects.create(recipe=self.recipe, user=other)
        self.client.force_login(self.fan)
        response = self.client.get(reverse("favourites"))
        self.assertNotContains(response, self.recipe.title)


class PrivacyAndOwnershipTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("cook", password="Str0ng!Passw0rd")
        self.stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.draft = make_recipe(self.author, title="Secret Sauce", published=False)
        self.published = make_recipe(self.author, title="Public Curry")

    def test_draft_is_404_for_strangers_and_public_for_the_author(self):
        response = self.client.get(self.draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 200)

    def test_drafts_are_absent_from_public_lists(self):
        response = self.client.get(reverse("recipe_list"))
        self.assertContains(response, "Public Curry")
        self.assertNotContains(response, "Secret Sauce")

    def test_only_the_author_can_edit_or_delete(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(reverse("recipe_edit", kwargs={"slug": self.published.slug})).status_code, 404)
        self.assertEqual(self.client.post(reverse("recipe_delete", kwargs={"slug": self.published.slug})).status_code, 404)
        self.assertTrue(Recipe.objects.filter(pk=self.published.pk).exists())

    def test_author_can_delete_own_recipe(self):
        self.client.force_login(self.author)
        self.client.post(reverse("recipe_delete", kwargs={"slug": self.published.slug}))
        self.assertFalse(Recipe.objects.filter(pk=self.published.pk).exists())

    def test_collection_is_owner_scoped(self):
        collection = Collection.objects.create(owner=self.author, name="Weeknights")
        self.client.force_login(self.stranger)
        response = self.client.post(reverse("collection_toggle",
                                            kwargs={"pk": collection.pk, "slug": self.published.slug}))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(collection.recipes.exists())

    def test_collection_unique_name_per_owner(self):
        Collection.objects.create(owner=self.author, name="Weeknights")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Collection.objects.create(owner=self.author, name="Weeknights")


class ListingAndFilterTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("cook", password="Str0ng!Passw0rd")
        self.cuisine = Cuisine.objects.create(name="Bengali", emoji="🇧🇩")
        make_recipe(self.author, title="Slow Biryani", cuisine=self.cuisine, prep_minutes=30, cook_minutes=90)
        make_recipe(self.author, title="Quick Omelette", prep_minutes=3, cook_minutes=5, difficulty="easy")

    def test_filters_by_cuisine(self):
        response = self.client.get(reverse("recipe_list"), {"cuisine": self.cuisine.slug})
        self.assertContains(response, "Slow Biryani")
        self.assertNotContains(response, "Quick Omelette")

    def test_filters_by_total_time(self):
        response = self.client.get(reverse("recipe_list"), {"max_time": "10"})
        self.assertContains(response, "Quick Omelette")
        self.assertNotContains(response, "Slow Biryani")

    def test_search_matches_ingredients(self):
        response = self.client.get(reverse("recipe_list"), {"q": "turmeric"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Slow Biryani")

    def test_sort_by_rating_puts_best_first(self):
        best = Recipe.objects.get(title="Quick Omelette")
        Rating.objects.create(recipe=best, user=self.author, stars=5)
        response = self.client.get(reverse("recipe_list"), {"sort": "rating"})
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.content.decode().find("Quick Omelette"),
                        response.content.decode().find("Slow Biryani"))


class SeederTests(TestCase):
    def test_seed_demo_populates_recipe_box(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Recipe.objects.count(), 8)
        self.assertGreaterEqual(Cuisine.objects.count(), 4)
        self.assertTrue(Rating.objects.exists())
        self.assertTrue(Favorite.objects.exists())
        self.assertTrue(Collection.objects.exists())
        self.assertTrue(Recipe.objects.filter(is_published=False).exists())   # a draft to demo
