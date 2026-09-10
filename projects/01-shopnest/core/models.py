"""ShopNest data models — catalogue, carts, orders, order lines.

Domain rules enforced here (and re-checked at the view/service layer):
  * an order line is a *snapshot* of product name + price, so history stays
    accurate even if the product later changes or is deleted;
  * stock is decremented only inside the order creation transaction, and
    never below zero (checked with row locks at checkout);
  * prices are Decimal everywhere — floats are banned for money.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.urls import reverse
from django.utils.text import slugify


class OutOfStockError(Exception):
    """Raised at checkout when an item cannot be fulfilled."""

    def __init__(self, product_name: str):
        self.product_name = product_name
        super().__init__(f"Not enough stock left for: {product_name}")


def unique_slug(model: type[models.Model], value: str, exclude_pk=None) -> str:
    """Return a URL-safe slug guaranteed unique across `model`."""
    base = slugify(value)[:50] or "item"
    slug, n = base, 1
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        n += 1
        slug = f"{base}-{n}"
        qs = model.objects.filter(slug=slug)
    return slug


# ------------------------------------------------------------------ catalogue
class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True, editable=False)
    icon = models.CharField(max_length=8, default="🛍️", help_text="Emoji shown on cards")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.icon} {self.name}"


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=190, unique=True, blank=True, editable=False)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    stock = models.PositiveIntegerField(default=0, help_text="Units available to sell")
    image = models.ImageField(upload_to="products/", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    featured = models.BooleanField(default=False, help_text="Show in the storefront hero")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Product, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"slug": self.slug})

    @property
    def published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def in_stock(self) -> bool:
        return self.published and self.stock > 0

    @property
    def max_per_order(self) -> int:
        return min(self.stock, 99)


# ------------------------------------------------------------------ shopping cart
class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user.username}"

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items.all())

    @property
    def total(self) -> Decimal:
        return sum((i.subtotal for i in self.items.all()), Decimal("0.00"))

    @property
    def is_empty(self) -> bool:
        return not self.items.exists()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    added = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "product")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self) -> Decimal:
        return self.product.price * self.quantity


# ------------------------------------------------------------------ orders
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    BADGE = {
        Status.PENDING: "badge-warn",
        Status.PAID: "badge-info",
        Status.SHIPPED: "badge-brand",
        Status.DELIVERED: "badge-ok",
        Status.CANCELLED: "badge-bad",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Shipping details (snapshot at purchase time).
    shipping_address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # Financial snapshot — immutable once the order is placed.
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Order {self.number} · {self.user.username}"

    @property
    def number(self) -> str:
        return f"SN-{self.pk:06d}"

    @property
    def status_badge(self) -> str:
        return self.BADGE.get(self.status, "badge-info")

    def get_absolute_url(self):
        return reverse("order_detail", kwargs={"pk": self.pk})

    @classmethod
    @transaction.atomic
    def create_from_cart(cls, cart: Cart, *, shipping_address="", city="", phone="") -> "Order":
        """Snapshot the cart into an Order, decrement stock, empty the cart.

        Stock lines are locked with select_for_update so two checkouts can
        never oversell the same product.
        """
        items = list(cart.items.select_related("product").all())
        if not items:
            raise ValueError("Cannot place an order from an empty cart.")

        products = list(
            Product.objects.select_for_update().filter(pk__in=[i.product_id for i in items])
        )
        stock_by_id = {p.pk: p for p in products}
        for item in items:
            product = stock_by_id[item.product_id]
            if product.stock < item.quantity:
                raise OutOfStockError(product.name)

        order = cls.objects.create(
            user=cart.user,
            shipping_address=shipping_address,
            city=city,
            phone=phone,
            total_amount=sum(
                (stock_by_id[i.product_id].price * i.quantity for i in items),
                Decimal("0.00"),
            ),
        )
        for item in items:
            product = stock_by_id[item.product_id]
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=item.quantity,
            )
        for item in items:
            Product.objects.filter(pk=item.product_id).update(stock=F("stock") - item.quantity)
        cart.items.all().delete()
        return order


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="order_items")
    product_name = models.CharField(max_length=160)          # snapshot
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity
