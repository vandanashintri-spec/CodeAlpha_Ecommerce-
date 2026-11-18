from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase

from .management.commands.update_product_prices import (
	EXPECTED_PRODUCT_COUNT,
	PRICE_BY_NAME,
)
from .models import Order, OrderItem, Product


class ProductPriceUpdateCommandTests(TestCase):
	def setUp(self):
		self.products = {
			name: Product.objects.create(
				name=name,
				description=f"Description for {name}",
				price=Decimal("1.23"),
				category="Other",
				image_url=f"https://example.com/{index}.jpg",
				stock=7,
			)
			for index, name in enumerate(PRICE_BY_NAME, start=1)
		}

	def test_command_updates_only_prices_and_is_repeatable(self):
		self.assertEqual(len(PRICE_BY_NAME), EXPECTED_PRODUCT_COUNT)
		self.assertEqual(Product.objects.count(), EXPECTED_PRODUCT_COUNT)
		product_fields_before = list(
			Product.objects.order_by("pk").values(
				"id", "name", "description", "category", "image_url", "stock",
				"created_at",
			)
		)
		user = get_user_model().objects.create_user(
			username="price-command-customer",
			email="price-command@example.com",
			password="test-password",
		)
		order = Order.objects.create(
			user=user,
			full_name="Price Command Customer",
			email="price-command@example.com",
			address="12 Market Street",
			phone="5550100123",
			total=Decimal("3.69"),
		)
		item = OrderItem.objects.create(
			order=order,
			product=self.products["Crossbody Bag"],
			quantity=3,
			price=Decimal("1.23"),
		)
		order_before = Order.objects.values().get(pk=order.pk)
		item_before = OrderItem.objects.values().get(pk=item.pk)

		dry_run_output = StringIO()
		call_command("update_product_prices", "--dry-run", stdout=dry_run_output)
		self.assertIn("no prices changed", dry_run_output.getvalue())
		self.assertEqual(
			set(Product.objects.values_list("price", flat=True)),
			{Decimal("1.23")},
		)

		for _ in range(2):
			output = StringIO()
			call_command("update_product_prices", stdout=output)
			self.assertIn("prices for 50 products", output.getvalue())

		self.assertEqual(Product.objects.count(), EXPECTED_PRODUCT_COUNT)
		self.assertEqual(
			dict(Product.objects.values_list("name", "price")),
			{name: Decimal(price) for name, price in PRICE_BY_NAME.items()},
		)
		self.assertEqual(
			list(
				Product.objects.order_by("pk").values(
					"id", "name", "description", "category", "image_url", "stock",
					"created_at",
				)
			),
			product_fields_before,
		)
		order.refresh_from_db()
		item.refresh_from_db()
		self.assertEqual(Order.objects.values().get(pk=order.pk), order_before)
		self.assertEqual(OrderItem.objects.values().get(pk=item.pk), item_before)

	def test_command_rejects_unexpected_inventory_without_changing_prices(self):
		Product.objects.create(
			name="Unapproved product",
			description="Not in the approved price list.",
			price=Decimal("12.34"),
		)

		with self.assertRaises(CommandError):
			call_command("update_product_prices", stdout=StringIO())

		self.assertEqual(Product.objects.count(), EXPECTED_PRODUCT_COUNT + 1)
		self.assertEqual(
			set(Product.objects.values_list("price", flat=True)),
			{Decimal("1.23"), Decimal("12.34")},
		)


class StorefrontTests(TestCase):
	def setUp(self):
		self.product = Product.objects.create(
			name="Travel mug",
			description="A durable mug for a long journey.",
			price="18.50",
			category="Electronics",
			stock=5,
		)

	def test_home_search_and_category_filter(self):
		response = self.client.get("/", {"q": "long journey", "category": "Electronics"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.product.name)
		self.assertEqual(list(response.context["products"]), [self.product])

	def test_shoes_search_returns_all_footwear_products(self):
		footwear = [
			Product.objects.create(
				name=name,
				description=description,
				price=Decimal("20.00"),
				category="Fashion",
				stock=4,
			)
			for name, description in [
				("Punjabi Jutti Flats", "Embroidered traditional flats."),
				("Womens Ballet Flats", "Woven ballet flats."),
				("Mens Brown Leather Loafers", "Leather loafers."),
				("Womens Block Heel Sandals", "Sandals with block heels."),
				("Running Sneakers", "Cushioned footwear for running."),
			]
		]

		response = self.client.get("/", {"q": "shoes"})

		self.assertEqual(response.status_code, 200)
		self.assertSetEqual(
			{product.pk for product in response.context["products"]},
			{product.pk for product in footwear},
		)

	def test_cart_can_be_updated_and_removed(self):
		self.client.post(f"/cart/add/{self.product.pk}/", {"quantity": 2})
		self.client.post(f"/cart/update/{self.product.pk}/", {"quantity": 3})

		response = self.client.get("/cart/")
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "value=\"3\"")

		self.client.post(f"/cart/remove/{self.product.pk}/")
		self.assertContains(self.client.get("/cart/"), "Your cart is empty")

	def test_checkout_creates_order_and_decrements_stock(self):
		user = get_user_model().objects.create_user(
			username="shopper",
			email="shopper@example.com",
			password="Safe-test-password-2026",
		)
		self.client.force_login(user)
		self.client.post(f"/cart/add/{self.product.pk}/", {"quantity": 2})

		response = self.client.post("/checkout/", {
			"full_name": "Test Shopper",
			"email": "shopper@example.com",
			"phone": "5550100123",
			"address": "12 Market Street",
		})

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "shop/order_success.html")
		order = Order.objects.get(user=user)
		self.assertEqual(order.total, Decimal("37.00"))
		self.assertEqual(order.payment_method, "COD")
		self.assertEqual(order.payment_status, "Pending")
		self.assertEqual(OrderItem.objects.get(order=order).quantity, 2)
		self.product.refresh_from_db()
		self.assertEqual(self.product.stock, 3)
		self.assertEqual(self.client.session.get("cart"), {})
		self.assertEqual(len(mail.outbox), 1)

	def test_checkout_rejects_invalid_phone_and_address(self):
		user = get_user_model().objects.create_user(
			username="shopper",
			email="shopper@example.com",
			password="test-password",
		)
		self.client.force_login(user)
		self.client.post(f"/cart/add/{self.product.pk}/", {"quantity": 2})
		valid_data = {
			"full_name": "Test Shopper",
			"email": "shopper@example.com",
			"phone": "5550100123",
			"address": "12 Market Street",
		}

		for phone in ("123456789", "12345678901", "12345abcde", "12345-7890", ""):
			with self.subTest(phone=phone):
				response = self.client.post(
					"/checkout/",
					{**valid_data, "phone": phone},
				)
				self.assertEqual(response.status_code, 200)
				self.assertContains(response, 'pattern="[0-9]{10}"')
				self.assertContains(response, 'maxlength="10"')
				self.assertContains(response, 'minlength="8"')
				self.assertContains(
					response,
					"Phone number must contain exactly 10 digits.",
				)
				self.assertFalse(Order.objects.exists())

		for address in (
			"",
			"      ",
			"123456789",
			"!@#$%^&*()",
			"!!! 12345",
			"123 Main",
		):
			with self.subTest(address=address):
				response = self.client.post(
					"/checkout/",
					{**valid_data, "address": address},
				)
				self.assertEqual(response.status_code, 200)
				self.assertContains(
					response,
					"Enter a valid delivery address with at least five letters",
				)
				self.assertFalse(Order.objects.exists())

		self.product.refresh_from_db()
		self.assertEqual(self.product.stock, 5)

	def test_signup_and_logout(self):
		response = self.client.post("/signup/", {
			"username": "new-shopper",
			"email": "new@example.com",
			"password1": "Safe-test-password-2026",
			"password2": "Safe-test-password-2026",
		})

		self.assertRedirects(response, "/")
		self.assertTrue(self.client.session.get("_auth_user_id"))

		response = self.client.post("/logout/")
		self.assertRedirects(response, "/")
		self.assertNotIn("_auth_user_id", self.client.session)

	def test_admin_can_access_product_management(self):
		customer = get_user_model().objects.create_user(
			username="customer",
			email="customer@example.com",
			password="Safe-test-password-2026",
		)
		order = Order.objects.create(
			user=customer,
			full_name="Test Customer",
			email="customer@example.com",
			address="12 Market Street",
			phone="5550100123",
			total=Decimal("18.50"),
		)
		OrderItem.objects.create(
			order=order,
			product=self.product,
			quantity=1,
			price=Decimal("18.50"),
		)
		admin = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="Safe-test-password-2026",
		)
		self.client.force_login(admin)

		product_response = self.client.get("/admin/shop/product/")
		order_response = self.client.get("/admin/shop/order/")

		self.assertEqual(product_response.status_code, 200)
		self.assertContains(product_response, self.product.name)
		self.assertEqual(order_response.status_code, 200)
		self.assertContains(order_response, "Test Customer")
