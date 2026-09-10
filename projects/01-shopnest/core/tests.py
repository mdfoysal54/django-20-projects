"""ShopNest domain tests: catalogue, cart, checkout, orders, ownership."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Cart, CartItem, Category, Order, Product


def make_product(name="Test Widget", price="19.99", stock=5, status=Product.Status.PUBLISHED, **kw):
    category, _ = Category.objects.get_or_create(name="Test Category")
    return Product.objects.create(
        name=name, category=category, price=Decimal(price), stock=stock, status=status, **kw
    )


class CatalogueTests(TestCase):
    def test_home_lists_only_published_products(self):
        published = make_product("Visible Product")
        draft = make_product("Hidden Draft", status=Product.Status.DRAFT)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, published.name)
        self.assertNotContains(response, draft.name)

    def test_catalog_by_category_and_sort(self):
        make_product("Alpha", price="5.00", stock=1)
        make_product("Beta", price="50.00", stock=1)
        cat = Category.objects.get()
        response = self.client.get(reverse("catalog_category", kwargs={"category_slug": cat.slug}))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("catalog"), {"sort": "price-asc"})
        body = response.content.decode()
        self.assertLess(body.index("Alpha"), body.index("Beta"))

    def test_unknown_category_is_404(self):
        self.assertEqual(self.client.get("/shop/category/nope/").status_code, 404)

    def test_draft_product_page_is_404(self):
        draft = make_product("Drafty", status=Product.Status.DRAFT)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)

    def test_product_detail_shows_stock_state(self):
        in_stock = make_product("In Stock Item", stock=3)
        out = make_product("Sold Out", stock=0)
        self.assertContains(self.client.get(in_stock.get_absolute_url()), "In stock")
        self.assertContains(self.client.get(out.get_absolute_url()), "Out of stock")


class CartFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("shopper", password="Str0ng!Passw0rd")
        self.product = make_product("Nice Thing", price="10.00", stock=5)
        self.client.force_login(self.user)

    def add(self, quantity=1):
        return self.client.post(reverse("cart_add", kwargs={"product_id": self.product.pk}), {"quantity": quantity})

    def test_anonymous_add_redirects_to_login(self):
        self.client.logout()
        response = self.add()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_add_then_merge_duplicates(self):
        self.add(2)
        self.add(1)
        cart = Cart.objects.get(user=self.user)
        item = cart.items.get(product=self.product)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(cart.total, Decimal("30.00"))

    def test_add_clamped_to_stock(self):
        self.add(50)          # 50 wanted, 5 in stock
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.get(product=self.product).quantity, 5)

    def test_absurd_quantity_is_rejected(self):
        response = self.add(999)   # above the form ceiling of 99
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

    def test_update_quantity_and_remove(self):
        self.add(2)
        item = CartItem.objects.get(cart__user=self.user)
        self.client.post(reverse("cart_update", kwargs={"item_id": item.pk}), {"quantity": 4})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)
        response = self.client.post(reverse("cart_remove", kwargs={"item_id": item.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_cannot_touch_another_users_cart_line(self):
        other = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        other_cart = Cart.objects.create(user=other)
        foreign_item = CartItem.objects.create(cart=other_cart, product=self.product, quantity=1)
        response = self.client.post(
            reverse("cart_update", kwargs={"item_id": foreign_item.pk}), {"quantity": 2}
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse("cart_remove", kwargs={"item_id": foreign_item.pk}))
        self.assertEqual(response.status_code, 404)


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer", password="Str0ng!Passw0rd")
        self.client.force_login(self.user)
        self.product = make_product("Orderable Item", price="25.00", stock=4)

    def checkout_post(self):
        return self.client.post(reverse("checkout"), {
            "shipping_address": "House 1, Road 1",
            "city": "Dhaka",
            "phone": "+8801711111111",
        })

    def test_full_order_flow(self):
        self.client.post(reverse("cart_add", kwargs={"product_id": self.product.pk}), {"quantity": 3})
        response = self.checkout_post()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertIn(f"/orders/{order.pk}/", response.url)

        self.assertEqual(order.total_amount, Decimal("75.00"))
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.product_name, self.product.name)   # snapshot
        self.assertEqual(item.unit_price, Decimal("25.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)                   # stock decremented
        self.assertFalse(Cart.objects.get(user=self.user).items.exists())

    def test_checkout_never_oversells(self):
        self.client.post(reverse("cart_add", kwargs={"product_id": self.product.pk}), {"quantity": 3})
        # Stock drops below the promised quantity after it was added to cart.
        Product.objects.filter(pk=self.product.pk).update(stock=1)
        response = self.checkout_post()
        self.assertEqual(response.status_code, 302)               # bounced back to cart
        self.assertIn("/cart/", response.url)
        self.assertEqual(Order.objects.count(), 0)                # nothing created
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)                   # never went negative

    def test_checkout_requires_shipping_fields(self):
        self.client.post(reverse("cart_add", kwargs={"product_id": self.product.pk}), {"quantity": 1})
        response = self.client.post(reverse("checkout"), {"city": "", "shipping_address": "", "phone": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_checkout_redirects_to_catalog(self):
        response = self.client.get(reverse("checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/shop/", response.url)

    def test_order_ownership_enforced(self):
        self.client.post(reverse("cart_add", kwargs={"product_id": self.product.pk}), {"quantity": 1})
        order = Order.create_from_cart(Cart.objects.get(user=self.user), city="Dhaka")
        stranger = User.objects.create_user("thief", password="Str0ng!Passw0rd")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("order_detail", kwargs={"pk": order.pk})).status_code, 404)
        self.assertEqual(self.client.get(reverse("my_orders")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("my_orders")), order.number)

    def test_invalid_phone_rejected(self):
        self.client.post(reverse("cart_add", kwargs={"product_id": self.product.pk}), {"quantity": 1})
        response = self.client.post(reverse("checkout"), {
            "shipping_address": "X", "city": "Dhaka", "phone": "abc"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "phone")


class SeederTests(TestCase):
    def test_seed_demo_populates_store(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Product.objects.count(), 10)
        self.assertGreaterEqual(Category.objects.count(), 5)
        self.assertTrue(User.objects.filter(username="admin").exists())
        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertTrue(Order.objects.exists())
        # Everything seeded is sellable.
        self.assertFalse(Product.objects.exclude(status=Product.Status.PUBLISHED).exists())
