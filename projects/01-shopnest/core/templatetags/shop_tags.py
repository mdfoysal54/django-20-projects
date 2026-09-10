"""ShopNest template tags — navigation categories + cart badge."""
from django import template
from django.db.models import Count, Q

from ..models import Cart, Category, Product

register = template.Library()


@register.inclusion_tag("partials/category_nav.html")
def category_nav():
    categories = Category.objects.annotate(
        published_count=Count("products", filter=Q(products__status=Product.Status.PUBLISHED))
    ).filter(published_count__gt=0)
    return {"categories": categories}


@register.simple_tag
def cart_count(user):
    """Number of units in the current user's cart (0 for anonymous users)."""
    if not user.is_authenticated:
        return 0
    cart = Cart.objects.filter(user=user).first()
    return cart.item_count if cart else 0
