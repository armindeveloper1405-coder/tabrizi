import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=120, verbose_name="نام نمایشی")),
                ("balance_grams", models.DecimalField(decimal_places=3, default=0, max_digits=16, validators=[django.core.validators.MinValueValidator(0)], verbose_name="مانده طلا (گرم)")),
                ("balance_rials", models.DecimalField(decimal_places=0, default=0, max_digits=20, validators=[django.core.validators.MinValueValidator(0)], verbose_name="مانده حساب (ریال)")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="member_profile", to=settings.AUTH_USER_MODEL, verbose_name="عضو")),
            ],
            options={"verbose_name": "پروفایل عضو", "verbose_name_plural": "پروفایل اعضا"},
        ),
        migrations.CreateModel(
            name="PriceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="عنوان نرخ")),
                ("unit", models.CharField(default="ریال", max_length=30, verbose_name="واحد")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="ترتیب نمایش")),
                ("is_active", models.BooleanField(default=True, verbose_name="نمایش در سایت")),
            ],
            options={"verbose_name": "نوع نرخ", "verbose_name_plural": "انواع نرخ", "ordering": ("sort_order", "name")},
        ),
        migrations.CreateModel(
            name="PriceUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("buy_price", models.DecimalField(decimal_places=0, max_digits=20, validators=[django.core.validators.MinValueValidator(0)], verbose_name="قیمت خرید")),
                ("sell_price", models.DecimalField(decimal_places=0, max_digits=20, validators=[django.core.validators.MinValueValidator(0)], verbose_name="قیمت فروش")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="price_updates", to=settings.AUTH_USER_MODEL, verbose_name="ثبت‌کننده")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="updates", to="prices.priceitem", verbose_name="نوع نرخ")),
            ],
            options={"verbose_name": "به‌روزرسانی قیمت", "verbose_name_plural": "به‌روزرسانی قیمت‌ها", "ordering": ("-created_at",)},
        ),
    ]
