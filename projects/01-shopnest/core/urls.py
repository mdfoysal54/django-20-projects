"""ShopNest — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    # ---- storefront ------------------------------------------------------
    path("", views.index, name="home"),
    path("shop/", views.catalog, name="catalog"),
    path("shop/category/<slug:category_slug>/", views.catalog, name="catalog_category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),

    # ---- cart ------------------------------------------------------------
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/item/<int:item_id>/update/", views.cart_update, name="cart_update"),
    path("cart/item/<int:item_id>/remove/", views.cart_remove, name="cart_remove"),

    # ---- checkout & orders ----------------------------------------------
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.my_orders, name="my_orders"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),

    # ---- account ----------------------------------------------------------
    path("profile/", views.profile, name="profile"),

    # ---- accounts (auth) --------------------------------------------------
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="done",
        ),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
