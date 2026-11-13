
from decimal import Decimal
from .models import Product


class Cart:

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.get("cart", {})

    def add(self, product, quantity=1):
        product_id = str(product.id)
        current_quantity = int(self.cart.get(product_id, 0))

        self.cart[product_id] = min(
            current_quantity + quantity,
            product.stock
        )
        self.save()

    def update(self, product, quantity):
        if quantity <= 0:
            self.remove(product)
        else:
            self.cart[str(product.id)] = min(
                quantity, product.stock
            )
            self.save()

    def remove(self, product):
        self.cart.pop(str(product.id), None)
        self.save()

    def save(self):
        self.session["cart"] = self.cart
        self.session.modified = True

    def clear(self):
        self.session["cart"] = {}
        self.cart = {}
        self.save()

    def __iter__(self):
        products = Product.objects.filter(
            id__in=self.cart.keys()
        )

        for product in products:
            quantity = int(self.cart[str(product.id)])

            yield {
                "product": product,
                "quantity": quantity,
                "subtotal": product.price * quantity
            }

    def __len__(self):
        return sum(int(q) for q in self.cart.values())

    @property
    def total(self):
        return sum(
            (item["subtotal"] for item in self),
            Decimal("0.00")
        )
