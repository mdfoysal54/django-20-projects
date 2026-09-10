"""RecipeBox — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("recipes/", views.recipe_list, name="recipe_list"),
    path("recipes/<slug:slug>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<slug:slug>/rate/", views.rate, name="rate"),
    path("recipes/<slug:slug>/favourite/", views.toggle_favourite, name="toggle_favourite"),

    # ---- authoring ----------------------------------------------------------
    path("kitchen/", views.my_recipes, name="my_recipes"),
    path("kitchen/new/", views.recipe_create, name="recipe_create"),
    path("kitchen/<slug:slug>/edit/", views.recipe_edit, name="recipe_edit"),
    path("kitchen/<slug:slug>/delete/", views.recipe_delete, name="recipe_delete"),

    # ---- saved --------------------------------------------------------------
    path("favourites/", views.favourites, name="favourites"),
    path("collections/", views.collections, name="collections"),
    path("collections/<int:pk>/toggle/<slug:slug>/", views.collection_toggle, name="collection_toggle"),

    # ---- account ------------------------------------------------------------
    path("profile/", views.profile, name="profile"),

    # ---- accounts (auth) ----------------------------------------------------
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path("accounts/password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html", success_url="done"), name="password_change"),
    path("accounts/password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html"), name="password_change_done"),
]
