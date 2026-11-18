from collections import Counter
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Product


PRICE_BY_NAME = {
    "wireless headphone": "4999.00",
    "Bluetooth Speaker": "1999.00",
    "Canvas Tote Bag": "799.00",
    "Modern Desk Lamp": "1499.00",
    "Creative Writing Journal": "399.00",
    "Floral Midi Dress": "2499.00",
    "Linen Shirt Dress": "2999.00",
    "Classic Black Wrap Dress": "3299.00",
    "Everyday Cotton T-Shirt": "599.00",
    "Denim Jacket": "2999.00",
    "Running Sneakers": "3999.00",
    "Crossbody Bag": "1499.00",
    "Wireless Earbuds": "2499.00",
    "Smart Watch": "5999.00",
    "Portable Power Bank": "1299.00",
    "Ceramic Plant Pot": "599.00",
    "Cotton Throw Blanket": "1999.00",
    "Everyday Cookbook": "699.00",
    "Sketchbook Set": "499.00",
    "Insulated Water Bottle": "799.00",
    "Festive Silk Saree": "5999.00",
    "Embroidered Anarkali Suit": "4499.00",
    "Cotton Kurta Set": "2499.00",
    "Mens Kurta Pajama": "2499.00",
    "Nehru Jacket": "3499.00",
    "Mens Festive Sherwani": "9999.00",
    "5G Smartphone 128GB": "24999.00",
    "14-inch Laptop": "59999.00",
    "10-inch Tablet": "17999.00",
    "Bluetooth Keyboard": "1499.00",
    "Wireless Mouse": "799.00",
    "USB-C Multiport Hub": "1499.00",
    "Padded Laptop Sleeve": "1199.00",
    "Protective Phone Case": "499.00",
    "Punjabi Jutti Flats": "1499.00",
    "Red Embroidered Juttis": "1699.00",
    "Womens Ballet Flats": "1299.00",
    "Mens Brown Leather Loafers": "3499.00",
    "Womens Block Heel Sandals": "2499.00",
    "Embroidered Lehenga Set": "7999.00",
    "Traditional Dupatta": "999.00",
    "Mens Kurta with Patterned Vest": "3499.00",
    "Over-Ear Headphones": "3499.00",
    "USB-C Cable Set": "499.00",
    "5G Smartphone 256GB": "29999.00",
    "14-inch Laptop 16GB": "74999.00",
    "10-inch Tablet 128GB": "19999.00",
    "Mechanical Keyboard": "2499.00",
    "Stainless Steel Cookware Set": "3999.00",
    "Insulated Bento Lunch Box": "899.00",
}
EXPECTED_PRODUCT_COUNT = 50


class Command(BaseCommand):
    help = "Update the prices of ByteCart's existing products to the approved INR prices."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the product list without changing prices.",
        )

    def handle(self, *args, **options):
        if len(PRICE_BY_NAME) != EXPECTED_PRODUCT_COUNT:
            raise CommandError(
                f"Expected {EXPECTED_PRODUCT_COUNT} configured prices, "
                f"found {len(PRICE_BY_NAME)}."
            )

        with transaction.atomic():
            products = list(Product.objects.select_for_update().order_by("pk"))
            names = [product.name for product in products]
            duplicates = sorted(
                name for name, count in Counter(names).items() if count > 1
            )
            actual_names = set(names)
            expected_names = set(PRICE_BY_NAME)
            missing = sorted(expected_names - actual_names)
            unexpected = sorted(actual_names - expected_names)
            problems = []

            if len(products) != EXPECTED_PRODUCT_COUNT:
                problems.append(
                    f"expected {EXPECTED_PRODUCT_COUNT} products, found {len(products)}"
                )
            if duplicates:
                problems.append(f"duplicate product names: {', '.join(duplicates)}")
            if missing:
                problems.append(f"missing products: {', '.join(missing)}")
            if unexpected:
                problems.append(f"unexpected products: {', '.join(unexpected)}")
            if problems:
                raise CommandError(
                    "Product inventory validation failed: " + "; ".join(problems)
                )

            if options["dry_run"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Dry run: validated {EXPECTED_PRODUCT_COUNT} products; no prices changed."
                    )
                )
                return

            for product in products:
                product.price = Decimal(PRICE_BY_NAME[product.name])

            updated_count = Product.objects.bulk_update(products, ["price"])
            if updated_count != EXPECTED_PRODUCT_COUNT:
                raise CommandError(
                    f"Expected to update {EXPECTED_PRODUCT_COUNT} products, "
                    f"but updated {updated_count}."
                )

            verified_prices = dict(
                Product.objects.filter(pk__in=[product.pk for product in products])
                .values_list("name", "price")
            )
            if len(verified_prices) != EXPECTED_PRODUCT_COUNT or any(
                verified_prices.get(name) != Decimal(price)
                for name, price in PRICE_BY_NAME.items()
            ):
                raise CommandError("Price verification failed; the transaction was rolled back.")

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated and verified prices for {updated_count} products."
            )
        )
