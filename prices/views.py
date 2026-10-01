from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import ReceiptSubmissionForm
from .models import MemberProfile, PaymentSettings, PriceItem, PriceUpdate, PurchaseOrder


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    latest_updates = PriceUpdate.objects.order_by("-created_at")
    items = (
        PriceItem.objects.filter(is_active=True)
        .prefetch_related(Prefetch("updates", queryset=latest_updates, to_attr="latest_updates"))
    )
    return render(
        request,
        "prices/dashboard.html",
        {
            "profile": profile,
            "price_items": items,
            "latest_update": PriceUpdate.objects.select_related("item").first(),
        },
    )


@login_required
def purchase(request):
    PurchaseOrder.objects.filter(
        member=request.user,
        status=PurchaseOrder.Status.AWAITING_ADMIN,
        approval_expires_at__lte=timezone.now(),
    ).update(status=PurchaseOrder.Status.EXPIRED)
    items = PriceItem.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "updates",
            queryset=PriceUpdate.objects.order_by("-created_at"),
            to_attr="latest_updates",
        )
    )
    priced_items = [item for item in items if item.latest_updates]
    if request.method == "POST":
        if PurchaseOrder.objects.filter(
            member=request.user,
            status__in=(
                PurchaseOrder.Status.AWAITING_ADMIN,
                PurchaseOrder.Status.PAYMENT_DUE,
                PurchaseOrder.Status.RECEIPT_REVIEW,
            ),
        ).exists():
            messages.error(request, "یک درخواست خرید فعال دارید؛ ابتدا همان را پیگیری کنید.")
            return redirect("dashboard")
        try:
            quantity = Decimal(request.POST.get("quantity_grams", ""))
        except (InvalidOperation, TypeError):
            quantity = Decimal("0")
        digits = quantity.as_tuple().digits if quantity.is_finite() else ()
        integer_digits = max(len(digits) + quantity.as_tuple().exponent, 0) if digits else 0
        if (
            not quantity.is_finite()
            or quantity <= 0
            or quantity.as_tuple().exponent < -3
            or integer_digits > 9
        ):
            messages.error(request, "مقدار باید بیشتر از صفر و حداکثر تا سه رقم اعشار باشد.")
            return render(request, "prices/purchase.html", {"price_items": priced_items})
        with transaction.atomic():
            item = (
                PriceItem.objects.select_for_update()
                .filter(pk=request.POST.get("item"), is_active=True)
                .first()
            )
            if item is None:
                messages.error(request, "نوع کالای انتخاب‌شده معتبر نیست.")
                return redirect("purchase")
            update = item.updates.order_by("-created_at").first()
            if update is None:
                messages.error(request, "برای این کالا هنوز قیمت معتبری ثبت نشده است.")
                return redirect("purchase")
            try:
                order = PurchaseOrder.objects.create(
                    member=request.user,
                    item=item,
                    quantity_grams=quantity,
                    unit_price=update.sell_price,
                    total_price=quantity * update.sell_price,
                    approval_expires_at=timezone.now() + timezone.timedelta(seconds=100),
                )
            except IntegrityError:
                messages.error(request, "یک درخواست خرید فعال دارید؛ ابتدا همان را پیگیری کنید.")
                return redirect("dashboard")
        return redirect("purchase_detail", order_id=order.pk)
    return render(request, "prices/purchase.html", {"price_items": priced_items})


@login_required
def purchase_detail(request, order_id):
    orders = PurchaseOrder.objects.select_related("item", "member")
    can_review = request.user.is_staff and request.user.has_perm("prices.change_purchaseorder")
    if can_review:
        order = get_object_or_404(orders, pk=order_id)
    else:
        order = get_object_or_404(orders, pk=order_id, member=request.user)
    if (
        order.status == PurchaseOrder.Status.AWAITING_ADMIN
        and order.approval_expires_at <= timezone.now()
    ):
        order.status = PurchaseOrder.Status.EXPIRED
        order.save(update_fields=("status",))
        if order.member_id == request.user.pk:
            messages.info(request, "مهلت تأیید تمام شد؛ می‌توانید درخواست تازه‌ای ثبت کنید.")
            return redirect("purchase")

    form = ReceiptSubmissionForm()
    if request.method == "POST":
        if order.member_id != request.user.pk or order.status != PurchaseOrder.Status.PAYMENT_DUE:
            return HttpResponseForbidden("این درخواست در حال حاضر قابل ثبت رسید نیست.")
        form = ReceiptSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                locked_order = PurchaseOrder.objects.select_for_update().get(
                    pk=order.pk, member=request.user
                )
                if locked_order.status != PurchaseOrder.Status.PAYMENT_DUE:
                    return HttpResponseForbidden("وضعیت این درخواست تغییر کرده است.")
                locked_order.receipt_reference = form.cleaned_data["receipt_reference"]
                locked_order.receipt_message = form.cleaned_data["receipt_message"]
                locked_order.receipt_file = form.cleaned_data["receipt_file"]
                locked_order.status = PurchaseOrder.Status.RECEIPT_REVIEW
                locked_order.save(
                    update_fields=(
                        "receipt_reference",
                        "receipt_message",
                        "receipt_file",
                        "status",
                    )
                )
            messages.success(request, "رسید برای بررسی مدیر ارسال شد.")
            return redirect("purchase_detail", order_id=order.pk)

    return render(
        request,
        "prices/purchase_detail.html",
        {
            "order": order,
            "form": form,
            "can_review": can_review,
            "remaining_seconds": order.approval_seconds_remaining,
        },
    )


@staff_member_required
def review_purchase(request, order_id, action):
    if request.method != "POST":
        return HttpResponseForbidden("درخواست نامعتبر است.")
    if not request.user.has_perm("prices.change_purchaseorder"):
        return HttpResponseForbidden("اجازه انجام این عملیات را ندارید.")
    with transaction.atomic():
        order = get_object_or_404(PurchaseOrder.objects.select_for_update(), pk=order_id)
        if action == "approve" and order.status == PurchaseOrder.Status.AWAITING_ADMIN:
            if order.approval_expires_at <= timezone.now():
                order.status = PurchaseOrder.Status.EXPIRED
                order.save(update_fields=("status",))
                messages.error(request, "مهلت تأیید این درخواست تمام شده است.")
            else:
                payment_settings = PaymentSettings.objects.first()
                if not payment_settings or not payment_settings.card_number:
                    messages.error(
                        request,
                        "پیش از تأیید درخواست، اطلاعات کارت بانکی را در پنل ثبت کنید.",
                    )
                    return redirect("purchase_detail", order_id=order.pk)
                order.status = PurchaseOrder.Status.PAYMENT_DUE
                order.payment_bank_name = payment_settings.bank_name
                order.payment_card_number = payment_settings.card_number
                order.payment_card_holder = payment_settings.card_holder
                order.save(
                    update_fields=(
                        "status",
                        "payment_bank_name",
                        "payment_card_number",
                        "payment_card_holder",
                    )
                )
                messages.success(request, "درخواست تأیید شد؛ عضو می‌تواند پرداخت کند.")
        elif action == "complete" and order.status == PurchaseOrder.Status.RECEIPT_REVIEW:
            order.status = PurchaseOrder.Status.COMPLETED
            order.reviewed_at = timezone.now()
            order.reviewed_by = request.user
            order.save(update_fields=("status", "reviewed_at", "reviewed_by"))
            messages.success(request, "خرید نهایی شد.")
        elif action == "reject" and order.status in (
            PurchaseOrder.Status.AWAITING_ADMIN,
            PurchaseOrder.Status.PAYMENT_DUE,
            PurchaseOrder.Status.RECEIPT_REVIEW,
        ):
            order.status = PurchaseOrder.Status.REJECTED
            order.reviewed_at = timezone.now()
            order.reviewed_by = request.user
            order.save(update_fields=("status", "reviewed_at", "reviewed_by"))
            messages.success(request, "درخواست رد شد.")
        else:
            messages.error(request, "این درخواست قبلاً بررسی شده یا وضعیت آن تغییر کرده است.")
    return redirect("purchase_detail", order_id=order.pk)


@staff_member_required
@require_GET
def receipt_download(request, order_id):
    if not request.user.has_perm("prices.view_purchaseorder"):
        return HttpResponseForbidden("اجازه مشاهده رسید را ندارید.")
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if not order.receipt_file:
        return HttpResponseForbidden("برای این درخواست فایلی ثبت نشده است.")
    response = FileResponse(
        order.receipt_file.open("rb"),
        as_attachment=True,
        filename=f"purchase-receipt-{order.pk}",
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
