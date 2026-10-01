from math import ceil

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models import Q
from django.utils import timezone


class MemberProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
        verbose_name="عضو",
    )
    display_name = models.CharField("نام نمایشی", max_length=120, blank=True)
    balance_grams = models.DecimalField(
        "مانده طلا (گرم)", max_digits=16, decimal_places=3, default=0,
        validators=[MinValueValidator(0)],
    )
    balance_rials = models.DecimalField(
        "مانده حساب (ریال)", max_digits=20, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "پروفایل عضو"
        verbose_name_plural = "پروفایل اعضا"

    def __str__(self):
        return self.display_name or self.user.get_username()


class PriceItem(models.Model):
    name = models.CharField("عنوان نرخ", max_length=100, unique=True)
    unit = models.CharField("واحد", max_length=30, default="ریال")
    sort_order = models.PositiveSmallIntegerField("ترتیب نمایش", default=0)
    is_active = models.BooleanField("نمایش در سایت", default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = "نوع نرخ"
        verbose_name_plural = "انواع نرخ"

    def __str__(self):
        return self.name


class PriceUpdate(models.Model):
    item = models.ForeignKey(
        PriceItem,
        on_delete=models.CASCADE,
        related_name="updates",
        verbose_name="نوع نرخ",
    )
    buy_price = models.DecimalField(
        "قیمت خرید", max_digits=20, decimal_places=0, validators=[MinValueValidator(0)]
    )
    sell_price = models.DecimalField(
        "قیمت فروش", max_digits=20, decimal_places=0, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="price_updates",
        verbose_name="ثبت‌کننده",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "به‌روزرسانی قیمت"
        verbose_name_plural = "به‌روزرسانی قیمت‌ها"

    def __str__(self):
        return f"{self.item} - {self.created_at:%Y-%m-%d %H:%M}"


class PaymentSettings(models.Model):
    bank_name = models.CharField("نام بانک", max_length=80, blank=True)
    card_number = models.CharField("شماره کارت", max_length=19, blank=True)
    card_holder = models.CharField("نام صاحب کارت", max_length=120, blank=True)

    class Meta:
        verbose_name = "اطلاعات کارت بانکی"
        verbose_name_plural = "اطلاعات کارت بانکی"

    def __str__(self):
        return "اطلاعات کارت بانکی"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        AWAITING_ADMIN = "awaiting_admin", "در انتظار تأیید اولیه مدیر"
        PAYMENT_DUE = "payment_due", "در انتظار پرداخت عضو"
        RECEIPT_REVIEW = "receipt_review", "در انتظار بررسی رسید"
        COMPLETED = "completed", "خرید نهایی‌شده"
        REJECTED = "rejected", "ردشده"
        EXPIRED = "expired", "منقضی‌شده"

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name="عضو",
    )
    item = models.ForeignKey(
        PriceItem,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name="نوع نرخ",
    )
    quantity_grams = models.DecimalField(
        "مقدار (گرم)", max_digits=12, decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )
    unit_price = models.DecimalField("قیمت هر گرم (ریال)", max_digits=20, decimal_places=0)
    total_price = models.DecimalField("مبلغ نهایی (ریال)", max_digits=32, decimal_places=3)
    payment_bank_name = models.CharField("بانک مقصد", max_length=80, blank=True)
    payment_card_number = models.CharField("شماره کارت مقصد", max_length=19, blank=True)
    payment_card_holder = models.CharField("صاحب کارت مقصد", max_length=120, blank=True)
    payment_bank_name = models.CharField("بانک مقصد", max_length=80, blank=True)
    payment_card_number = models.CharField("شماره کارت مقصد", max_length=19, blank=True)
    payment_card_holder = models.CharField("صاحب کارت مقصد", max_length=120, blank=True)
    status = models.CharField(
        "وضعیت", max_length=20, choices=Status.choices, default=Status.AWAITING_ADMIN
    )
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    approval_expires_at = models.DateTimeField("مهلت تأیید مدیر")
    receipt_reference = models.CharField("شناسه/شماره پیگیری رسید", max_length=120, blank=True)
    receipt_message = models.TextField("پیام عضو درباره رسید", blank=True)
    receipt_file = models.FileField(
        "تصویر یا فایل رسید", upload_to="purchase_receipts/%Y/%m/", blank=True
    )
    receipt_file = models.FileField(
        "تصویر یا فایل رسید",
        upload_to="purchase_receipts/%Y/%m/",
        blank=True,
    )
    reviewed_at = models.DateTimeField("زمان بررسی نهایی", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_purchase_orders",
        verbose_name="بررسی‌کننده نهایی",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "درخواست خرید"
        verbose_name_plural = "درخواست‌های خرید"
        constraints = [
            models.UniqueConstraint(
                fields=("member",),
                condition=Q(
                    status__in=("awaiting_admin", "payment_due", "receipt_review")
                ),
                name="one_active_purchase_per_member",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("member",),
                condition=Q(
                    status__in=(
                        "awaiting_admin",
                        "payment_due",
                        "receipt_review",
                    )
                ),
                name="one_active_purchase_per_member",
            )
        ]

    def __str__(self):
        return f"خرید {self.item} توسط {self.member}"

    @property
    def approval_seconds_remaining(self):
        return max(0, ceil((self.approval_expires_at - timezone.now()).total_seconds()))
