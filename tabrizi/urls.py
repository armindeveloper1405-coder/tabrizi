from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from prices import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("ورود/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("خروج/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("خرید/", views.purchase, name="purchase"),
    path("خرید/<int:order_id>/", views.purchase_detail, name="purchase_detail"),
    path(
        "مدیریت/خرید/<int:order_id>/<str:action>/",
        views.review_purchase,
        name="review_purchase",
    ),
    path(
        "مدیریت/خرید/<int:order_id>/رسید/",
        views.receipt_download,
        name="receipt_download",
    ),
]
