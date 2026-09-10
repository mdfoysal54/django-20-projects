"""Seed RecipeBox with cuisines, recipes, ratings, favourites and collections."""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Collection, Cuisine, Favorite, Rating, Recipe

CUISINES = [("Bengali", "🇧🇩"), ("Italian", "🇮🇹"), ("Japanese", "🇯🇵"),
            ("Middle Eastern", "🥙"), ("Breakfast", "🍳")]

RECIPES = [
    ("Nadia", "Bengali", "Kacchi Biryani", "🥘", "easy", 40, 90, 6, True,
     "The Sunday centrepiece: layered rice, slow-cooked mutton and a lot of patience.",
     "1 kg mutton, on the bone\n750 g basmati rice\n2 onions, thinly sliced\n1 tbsp ginger paste\n1 tbsp garlic paste\n4 green chillies\n200 g yoghurt\n100 g ghee\n1 tsp saffron soaked in milk\nSalt to taste",
     "Marinate the mutton in yoghurt and spices overnight.\nPar-boil the rice with whole spices until 70% done.\nFry the onions until deep golden.\nLayer mutton, rice, fried onions and ghee in a heavy pot.\nSeal the lid with dough and cook on low heat for 90 minutes.\nRest for 15 minutes before opening."),
    ("Nadia", "Bengali", "Shorshe Ilish", "🐟", "medium", 20, 25, 4, True,
     "Hilsa in a sharp mustard gravy — the dish that defines a monsoon Sunday.",
     "4 hilsa steaks\n3 tbsp mustard seeds\n4 green chillies\n1/2 tsp turmeric\n4 tbsp mustard oil\nSalt to taste",
     "Grind mustard seeds with two chillies and a splash of water.\nRub the fish with turmeric and salt.\nWarm the mustard oil and lay the fish in gently.\nAdd the mustard paste and remaining chillies.\nSimmer covered for 12 minutes, turning the pan once."),
    ("Rakib", "Italian", "Cacio e Pepe", "🧀", "easy", 5, 12, 2, True,
     "Three ingredients, zero margin for error — the pasta that separates cooks from chefs.",
     "200 g spaghetti\n100 g pecorino romano, finely grated\n2 tsp black pepper, cracked\nSalt for the pasta water",
     "Toast the cracked pepper in a dry pan for 30 seconds.\nBoil the pasta in lightly salted water until al dente.\nReserve a mug of starchy pasta water.\nOff the heat, toss pasta with pecorino and a splash of the water.\nKeep tossing until glossy and creamy — add water, never heat."),
    ("Rakib", "Italian", "Slow Ragù", "🍝", "medium", 25, 180, 6, True,
     "A ragu that rewards patience: three hours, low heat, no shortcuts.",
     "500 g beef mince\n150 g pancetta\n1 onion, finely diced\n2 carrots, finely diced\n2 celery sticks, finely diced\n800 g tinned tomatoes\n250 ml whole milk\n250 ml red wine",
     "Sweat the soffritto in olive oil for 15 minutes.\nBrown the pancetta, then the beef, in batches.\nDeglaze with wine and reduce by half.\nAdd milk and simmer until absorbed.\nAdd tomatoes and simmer uncovered for two hours.\nSeason and rest before serving."),
    ("Ayesha", "Japanese", "Miso Ramen", "🍜", "hard", 30, 60, 4, True,
     "A weeknight ramen built on a fast dashi and a proper miso tare.",
     "4 portions ramen noodles\n3 tbsp white miso\n2 tbsp tahini\n1 litre chicken stock\n20 g dried shiitake\n4 soft-boiled eggs\n2 spring onions, sliced\n200 g pork belly, sliced",
     "Steep the shiitake in hot stock for 20 minutes.\nWhisk miso and tahini into a paste — the tare.\nSear the pork belly until crisp.\nCombine tare with hot stock, taste and adjust.\nCook the noodles, drain, and divide into bowls.\nTop with broth, pork, halved eggs and spring onion."),
    ("Ayesha", "Middle Eastern", "Chicken Shawarma Bowls", "🥙", "easy", 20, 25, 4, True,
     "All the shawarma flavour without the rotating spit — a tray bake plus a garlic sauce.",
     "700 g chicken thighs\n2 tsp cumin\n2 tsp coriander\n1 tsp smoked paprika\n1/2 tsp cinnamon\n4 flatbreads\n200 g yoghurt\n2 cloves garlic, crushed\n1 lemon, juiced",
     "Toss the chicken with spices, oil and half the lemon.\nRoast at 220°C for 22 minutes, then grill for char.\nMix yoghurt with garlic, lemon and salt for the sauce.\nWarm the flatbreads in a dry pan.\nSlice the chicken and pile onto the bread with salad and sauce."),
    ("Marufa", "Breakfast", "Shakshuka", "🍳", "easy", 10, 20, 3, True,
     "Eggs poached in a spiced tomato base — breakfast, brunch or a late dinner.",
     "6 eggs\n800 g tinned tomatoes\n1 onion, sliced\n1 red pepper, sliced\n2 tsp smoked paprika\n1 tsp cumin\n1/2 tsp chilli flakes\n80 g feta, crumbled\nCoriander to finish",
     "Soften the onion and pepper in olive oil for 8 minutes.\nAdd the spices and cook for a minute until fragrant.\nPour in the tomatoes and simmer for 10 minutes.\nMake wells and crack in the eggs.\nCover and cook for 6 minutes until the whites set.\nScatter feta and coriander, and serve with bread."),
    ("Marufa", "Breakfast", "Overnight Oats, Three Ways", "🥣", "easy", 5, 0, 2, True,
     "Five minutes tonight, breakfast solved tomorrow — plus two easy variations.",
     "100 g rolled oats\n250 ml milk\n2 tbsp yoghurt\n1 tbsp chia seeds\n1 banana, sliced\n1 tbsp honey\n20 g almonds, toasted",
     "Mix oats, milk, yoghurt and chia in a jar.\nRefrigerate overnight — at least 6 hours.\nTop with banana, honey and almonds before eating.\nFor a chocolate version add 1 tbsp cocoa.\nFor a berry version add 100 g frozen berries to the jar."),
    ("Marufa", "Bengali", "Chirer Pulao", "🍚", "easy", 15, 15, 4, False,
     "Draft: flattened-rice breakfast pilaf with peanuts and raisins.",
     "200 g flattened rice (chire)\n1 onion, sliced\n50 g peanuts\n30 g raisins\n1/2 tsp turmeric\n2 green chillies\n1 tsp sugar\nSalt to taste",
     "Rinse the chire and drain well.\nFry peanuts and raisins, then set aside.\nSoften the onion with turmeric and chillies.\nFold in the chire and toss for 4 minutes.\nFinish with sugar, salt, peanuts and raisins."),
]

RATERS = [("Nadia", 5, "Made this for eight people. Silence at the table — the good kind."),
          ("Rakib", 5, "The mustard paste tip changed everything."),
          ("Ayesha", 4, "Rich and worth it. I used slightly less ghee."),
          ("Marufa", 3, "Nice but I needed a lot more seasoning."),
          ("customer", 5, "Restaurant quality at home. Cooking this weekly.")]


class Command(BaseCommand):
    help = "Create demo cuisines, recipes, ratings, favourites and collections."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        for name, emoji in CUISINES:
            Cuisine.objects.get_or_create(name=name, defaults={"emoji": emoji})

        for username in ("Nadia", "Rakib", "Ayesha", "Marufa", "customer", "admin"):
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"email": f"{username.lower()}@recipebox.dev"})
            if created:
                user.set_password("DemoPass123!")
            if username == "admin":
                user.is_staff = user.is_superuser = True
            user.save()

        for author_name, cuisine_name, title, emoji, difficulty, prep, cook, servings, published, summary, ingredients, steps in RECIPES:
            author = User.objects.get(username=author_name)
            cuisine = Cuisine.objects.get(name=cuisine_name)
            recipe, created = Recipe.objects.get_or_create(
                title=title,
                defaults={"author": author, "cuisine": cuisine, "emoji": emoji, "difficulty": difficulty,
                          "prep_minutes": prep, "cook_minutes": cook, "servings": servings,
                          "summary": summary, "ingredients": ingredients, "steps": steps,
                          "is_published": published},
            )
            if not created:
                continue
            # A few ratings from people who are not the author.
            for rater_name, stars, review in RATERS:
                rater = User.objects.get(username=rater_name)
                if rater == author:
                    continue
                Rating.objects.get_or_create(recipe=recipe, user=rater,
                                             defaults={"stars": stars, "review": review})

        # Favourites + a collection for the demo customer.
        customer = User.objects.get(username="customer")
        for recipe in Recipe.objects.filter(is_published=True)[:4]:
            Favorite.objects.get_or_create(recipe=recipe, user=customer)

        collection, _ = Collection.objects.get_or_create(
            owner=customer, name="Weeknight dinners",
            defaults={"description": "Under an hour, no fuss."})
        collection.recipes.set(Recipe.objects.filter(is_published=True, prep_minutes__lte=25)[:3])

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Cuisine.objects.count()} cuisines, {Recipe.objects.count()} recipes, "
            f"{Rating.objects.count()} ratings, {Favorite.objects.count()} favourites."
        ))
