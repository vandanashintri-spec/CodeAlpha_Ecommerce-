
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path(
        "product/<int:pk>/",
        views.product_detail,
        name="product_detail"
    ),

    path("cart/", views.cart_detail, name="cart_detail"),

    path(
        "cart/add/<int:pk>/",
        views.cart_add,
        name="cart_add"
    ),

    path(
        "cart/update/<int:pk>/",
        views.cart_update,
        name="cart_update"
    ),

    path(
        "cart/remove/<int:pk>/",
        views.cart_remove,
        name="cart_remove"
    ),

    path("signup/", views.signup, name="signup"),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login"
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout"
    ),

    path("checkout/", views.checkout, name="checkout"),
]
