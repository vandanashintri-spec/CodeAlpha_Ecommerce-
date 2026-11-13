
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import CheckoutForm, SignUpForm
from .models import Order, OrderItem, Product

FOOTWEAR_SEARCH_TERMS = (
    "shoe", "sneaker", "boot", "loafer", "flat", "jutti",
    "sandal", "footwear", "heel", "pump", "slipper",
)
logger = logging.getLogger(__name__)


def home(request):
    products = Product.objects.all()

    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")

    if query:
        search_filter = Q(name__icontains=query) | Q(description__icontains=query)
        if query.casefold() in {"shoe", "shoes", "footwear"}:
            for term in FOOTWEAR_SEARCH_TERMS:
                search_filter |= Q(name__icontains=term) | Q(description__icontains=term)
        products = products.filter(search_filter)

    if category:
        products = products.filter(category=category)

    categories = Product.CATEGORY_CHOICES

    return render(request, "shop/home.html", {
        "products": products,
        "categories": categories,
        "query": query,
        "selected_category": category,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)

    return render(
        request,
        "shop/product_detail.html",
        {"product": product}
    )


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)

    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        quantity = 1

    if product.stock < 1:
        messages.error(request, "Product is out of stock.")
    else:
        Cart(request).add(product, quantity)
        messages.success(
            request,
            f"{product.name} added to your cart."
        )

    return redirect(request.POST.get("next") or "cart_detail")


def cart_detail(request):
    return render(
        request,
        "shop/cart.html",
        {"cart": Cart(request)}
    )


@require_POST
def cart_update(request, pk):
    product = get_object_or_404(Product, pk=pk)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    Cart(request).update(product, quantity)

    return redirect("cart_detail")


@require_POST
def cart_remove(request, pk):
    product = get_object_or_404(Product, pk=pk)

    Cart(request).remove(product)

    return redirect("cart_detail")


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = SignUpForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)

        messages.success(
            request,
            "Account created successfully!"
        )

        return redirect("home")

    return render(
        request,
        "registration/signup.html",
        {"form": form}
    )


@login_required
def checkout(request):
    cart = Cart(request)

    if len(cart) == 0:
        messages.info(request, "Your cart is empty.")
        return redirect("home")

    initial = {
        "full_name": request.user.get_full_name()
        or request.user.username,
        "email": request.user.email,
    }

    form = CheckoutForm(
        request.POST or None,
        initial=initial
    )

    if request.method == "POST" and form.is_valid():

        with transaction.atomic():

            items = list(cart)
            locked_products = {}

            for item in items:
                product = Product.objects.select_for_update().get(
                    pk=item["product"].pk
                )

                if product.stock < item["quantity"]:
                    messages.error(
                        request,
                        f"Not enough stock for {product.name}."
                    )
                    return redirect("cart_detail")
                locked_products[product.pk] = product

            total = sum(
                (
                    locked_products[item["product"].pk].price * item["quantity"]
                    for item in items
                ),
                Decimal("0.00"),
            )

            order = Order.objects.create(
                user=request.user,
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                phone=form.cleaned_data["phone"],
                address=form.cleaned_data["address"],
                total=total,
                payment_method="COD",
            )

            for item in items:
                product = locked_products[item["product"].pk]

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item["quantity"],
                    price=product.price,
                )

                product.stock -= item["quantity"]
                product.save(update_fields=["stock"])

        cart.clear()
        try:
            send_mail(
                subject=f"ByteCart order #{order.pk} received",
                message=(
                    f"Thank you for your order, {order.full_name}.\n"
                    f"Order number: {order.pk}\n"
                    f"Total: ${order.total}\n"
                    "Payment method: Cash on delivery."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.email],
            )
        except Exception:
            logger.exception("Could not send confirmation for order %s", order.pk)

        return render(
            request,
            "shop/order_success.html",
            {"order": order}
        )

    return render(
        request,
        "shop/checkout.html",
        {"form": form, "cart": cart}
    )
