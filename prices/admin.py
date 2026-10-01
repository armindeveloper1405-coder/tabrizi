from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import MemberProfile, PaymentSettings, PriceItem, PriceUpdate, PurchaseOrder


class MemberProfileInline(admin.StackedInline):
    model = MemberProfile
    can_delete = False
    extra = 0


User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class MemberAdmin(UserAdmin):
    inlines = (*UserAdmin.inlines, MemberProfileInline)


@admin.register(PriceItem)
class PriceItemAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)


@admin.register(PriceUpdate)
class PriceUpdateAdmin(admin.ModelAdmin):
    list_display = ("item", "buy_price", "sell_price", "created_at", "created_by")
    list_filter = ("item", "created_at")
    search_fields = ("item__name", "created_by__username")
    readonly_fields = ("created_at", "created_by")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    fields = ("bank_name", "card_number", "card_holder")

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "member", "item", "quantity_grams", "total_price",
        "status", "created_at", "approval_expires_at", "workflow_link",
    )
    list_filter = ("status", "item", "created_at")
    search_fields = ("member__username", "member__first_name", "receipt_reference")
    readonly_fields = (
        "member", "item", "quantity_grams", "unit_price", "total_price",
        "created_at", "approval_expires_at", "receipt_reference",
        "receipt_message", "receipt_file_link", "payment_bank_name",
        "payment_card_number", "payment_card_holder", "reviewed_at", "reviewed_by",
    )
    actions = ("approve_orders", "complete_orders", "reject_orders")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields

    @admin.display(description="پیگیری / بررسی")
    def workflow_link(self, obj):
        return format_html(
            '<a href="{}">باز کردن گردش خرید</a>',
            reverse("purchase_detail", args=(obj.pk,)),
        )

    @admin.display(description="رسید")
    def receipt_file_link(self, obj):
        if not obj.receipt_file:
            return "رسیدی ثبت نشده"
        return format_html(
            '<a href="{}">دریافت امن فایل رسید</a>',
            reverse("receipt_download", args=(obj.pk,)),
        )

    @admin.action(description="تأیید اولیه درخواست‌های انتخاب‌شده")
    def approve_orders(self, request, queryset):
        approved = expired = 0
        with transaction.atomic():
            for order in queryset.select_for_update().filter(
                status=PurchaseOrder.Status.AWAITING_ADMIN
            ):
                if order.approval_expires_at <= timezone.now():
                    order.status = PurchaseOrder.Status.EXPIRED
                    expired += 1
                else:
                    payment_settings = PaymentSettings.objects.first()
                    if not payment_settings or not payment_settings.card_number:
                        self.message_user(
                            request,
                            "پیش از تأیید، اطلاعات کارت بانکی را در پنل ثبت کنید.",
                            level="error",
                        )
                        continue
                    order.status = PurchaseOrder.Status.PAYMENT_DUE
                    order.payment_bank_name = payment_settings.bank_name
                    order.payment_card_number = payment_settings.card_number
                    order.payment_card_holder = payment_settings.card_holder
                    approved += 1
                order.save(
                    update_fields=(
                        "status",
                        "payment_bank_name",
                        "payment_card_number",
                        "payment_card_holder",
                    )
                )
        self.message_user(request, f"{approved} درخواست تأیید و {expired} درخواست منقضی شد.")

    @admin.action(description="نهایی‌کردن خریدهای دارای رسید")
    def complete_orders(self, request, queryset):
        count = 0
        with transaction.atomic():
            for order in queryset.select_for_update().filter(
                status=PurchaseOrder.Status.RECEIPT_REVIEW
            ):
                order.status = PurchaseOrder.Status.COMPLETED
                order.reviewed_at = timezone.now()
                order.reviewed_by = request.user
                order.save(update_fields=("status", "reviewed_at", "reviewed_by"))
                count += 1
        self.message_user(request, f"{count} خرید نهایی شد.")

    @admin.action(description="رد درخواست‌های انتخاب‌شده")
    def reject_orders(self, request, queryset):
        count = 0
        with transaction.atomic():
            for order in queryset.select_for_update().filter(
                status__in=(
                    PurchaseOrder.Status.AWAITING_ADMIN,
                    PurchaseOrder.Status.PAYMENT_DUE,
                    PurchaseOrder.Status.RECEIPT_REVIEW,
                )
            ):
                order.status = PurchaseOrder.Status.REJECTED
                order.reviewed_at = timezone.now()
                order.reviewed_by = request.user
                order.save(update_fields=("status", "reviewed_at", "reviewed_by"))
                count += 1
        self.message_user(request, f"{count} درخواست رد شد.")
