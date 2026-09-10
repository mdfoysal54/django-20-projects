"""ShopNest views.

Access rules:
  * catalogue pages are public (published products only);
  * cart & checkout require login — the cart is the user's own (DB-backed,
    never cookie state that can be tampered with);
  * order pages are owner-scoped: get_object_or_404(…, user=request.user).
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AddToCartForm, CartQuantityForm, CheckoutForm
from .models import Cart, CartItem, Category, Order, OutOfStockError, Product

SORT_CHOICES = {
    "newest": "-created",
    "price-asc": "price",
    "price-desc": "-price",
    "name": "name",
}


def _cart_for(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


# ---------------------------------------------------------------- catalogue
def index(request):
    featured = Product.objects.filter(status=Product.Status.PUBLISHED, featured=True)[:8]
    newest = Product.objects.filter(status=Product.Status.PUBLISHED)[:8]
    categories = (
        Category.objects.annotate(
            product_count=Count("products", filter=Q(products__status=Product.Status.PUBLISHED))
        )
        .order_by("name")
    )
    return render(request, "shop/index.html", {"featured": featured, "newest": newest, "categories": categories})


def catalog(request, category_slug=None):
    products = Product.objects.filter(status=Product.Status.PUBLISHED).select_related("category")
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    sort = request.GET.get("sort", "newest")
    if sort in SORT_CHOICES:
        products = products.order_by(SORT_CHOICES[sort])
    categories = Category.objects.all()
    return render(request, "shop/catalog.html", {
        "products": products,
        "category": category,
        "categories": categories,
        "sort": sort,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.Status.PUBLISHED)
    related = (
        Product.objects.filter(category=product.category, status=Product.Status.PUBLISHED)
        .exclude(pk=product.pk)[:4]
    )
    max_qty = product.max_per_order if product.in_stock else 1
    form = AddToCartForm(initial={"quantity": 1})
    form.fields["quantity"].max_value = max(1, max_qty)
    return render(request, "shop/product_detail.html", {
        "product": product,
        "related": related,
        "form": form,
    })


# ---------------------------------------------------------------- cart
@login_required
def cart_detail(request):
    cart = _cart_for(request.user)
    items = cart.items.select_related("product__category").all()
    return render(request, "shop/cart.html", {"cart": cart, "items": items})


@login_required
def cart_add(request, product_id):
    """Add (or merge) a product into the user's cart, clamped to real stock.

    POST adds; a plain GET (e.g. right after the login redirect) bounces the
    visitor back to the product page without side effects.
    """
    product = get_object_or_404(Product, pk=product_id, status=Product.Status.PUBLISHED)
    if request.method != "POST":
        return redirect(product)
    form = AddToCartForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid quantity.")
        return redirect(product)
    quantity = min(form.cleaned_data["quantity"], product.stock, 99)
    if quantity <= 0:
        messages.error(request, f"Sorry — “{product.name}” is out of stock.")
        return redirect(product)

    cart = _cart_for(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    if not created:
        item.quantity = min(item.quantity + quantity, product.stock, 99)
        item.save(update_fields=["quantity"])
    if created:
        messages.success(request, f"“{product.name}” added to your cart.")
    else:
        messages.success(request, f"“{product.name}” quantity updated in your cart.")
    return redirect("cart_detail")


@login_required
@require_POST
def cart_update(request, item_id):
    """Update a line's quantity (0 removes it). Only the owner's lines."""
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    form = CartQuantityForm(request.POST)
    if form.is_valid():
        qty = form.cleaned_data["quantity"]
        if qty <= 0:
            item.delete()
            messages.info(request, "Item removed from your cart.")
        else:
            item.quantity = min(qty, item.product.stock, 99)
            item.save(update_fields=["quantity"])
            messages.success(request, "Cart updated.")
    else:
        messages.error(request, "Invalid quantity.")
    return redirect("cart_detail")


@login_required
@require_POST
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    messages.info(request, "Item removed from your cart.")
    return redirect("cart_detail")


# ---------------------------------------------------------------- checkout
@login_required
def checkout(request):
    cart = _cart_for(request.user)
    if cart.is_empty:
        messages.warning(request, "Your cart is empty — add something first!")
        return redirect("catalog")

    items = cart.items.select_related("product").all()
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = Order.create_from_cart(
                    cart,
                    shipping_address=form.cleaned_data["shipping_address"],
                    city=form.cleaned_data["city"],
                    phone=form.cleaned_data["phone"],
                )
            except OutOfStockError as exc:
                messages.error(request, f"{exc} Please adjust your cart.")
                return redirect("cart_detail")
            messages.success(request, f"Order {order.number} placed — thank you!")
            return redirect("order_detail", pk=order.pk)
    else:
        form = CheckoutForm()
    totals = {"subtotal": cart.total, "shipping": Decimal("0.00"), "grand": cart.total}
    return render(request, "shop/checkout.html", {"cart": cart, "items": items, "form": form, "totals": totals})


# ---------------------------------------------------------------- orders
@login_required
def my_orders(request):
    orders = request.user.orders.prefetch_related("items").all()
    return render(request, "shop/orders.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)  # owner-only: 404 for strangers
    order.items.select_related("product")
    return render(request, "shop/order_detail.html", {"order": order})


# ---------------------------------------------------------------- account
@login_required
def profile(request):
    recent = request.user.orders.all()[:5]
    return render(request, "account/profile.html", {"recent_orders": recent})
