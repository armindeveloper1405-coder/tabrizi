from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PaymentSettings, PriceItem, PriceUpdate, PurchaseOrder


class PurchaseWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.member = user_model.objects.create_user(
            username="purchase-member", password="Strong-test-password-198!"
        )
        self.admin = user_model.objects.create_superuser(
            username="purchase-admin",
            email="admin@example.test",
            password="Strong-admin-password-198!",
        )
        self.item = PriceItem.objects.create(name="طلای آزمایشی")
        PriceUpdate.objects.create(
            item=self.item,
            buy_price=71000000,
            sell_price=73000000,
            created_by=self.admin,
        )
        self.payment = PaymentSettings.objects.create(
            bank_name="بانک آزمایشی",
            card_number="1234567812345678",
            card_holder="صاحب کارت",
        )

    def create_order(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("purchase"),
            {"item": self.item.pk, "quantity_grams": "1.250"},
        )
        self.assertEqual(response.status_code, 302)
        return PurchaseOrder.objects.get(member=self.member)

    def test_purchase_uses_sell_price_and_approval_snapshots_card(self):
        order = self.create_order()
        self.assertEqual(order.unit_price, Decimal("73000000"))
        self.assertEqual(order.total_price, Decimal("91250000.000"))
        self.assertAlmostEqual(
            (order.approval_expires_at - timezone.now()).total_seconds(),
            100,
            delta=2,
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("review_purchase", args=(order.pk, "approve"))
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PAYMENT_DUE)
        self.assertEqual(order.payment_card_number, self.payment.card_number)

    def test_expired_request_is_not_approved_and_member_can_start_again(self):
        order = self.create_order()
        order.approval_expires_at = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=("approval_expires_at",))

        self.client.force_login(self.admin)
        self.client.post(reverse("review_purchase", args=(order.pk, "approve")))
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.EXPIRED)

        self.client.force_login(self.member)
        response = self.client.post(
            reverse("purchase"),
            {"item": self.item.pk, "quantity_grams": "0.500"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PurchaseOrder.objects.filter(member=self.member).count(), 2)

    def test_member_is_returned_to_purchase_page_after_approval_deadline(self):
        order = self.create_order()
        order.approval_expires_at = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=("approval_expires_at",))

        self.client.force_login(self.member)
        response = self.client.get(reverse("purchase_detail", args=(order.pk,)))

        self.assertRedirects(response, reverse("purchase"))
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.EXPIRED)

    def test_new_request_expires_old_request_after_deadline(self):
        expired_order = self.create_order()
        expired_order.approval_expires_at = timezone.now() - timedelta(seconds=1)
        expired_order.save(update_fields=("approval_expires_at",))

        response = self.client.post(
            reverse("purchase"),
            {"item": self.item.pk, "quantity_grams": "0.500"},
        )

        self.assertEqual(response.status_code, 302)
        expired_order.refresh_from_db()
        self.assertEqual(expired_order.status, PurchaseOrder.Status.EXPIRED)
        self.assertEqual(
            PurchaseOrder.objects.filter(member=self.member)
            .exclude(status=PurchaseOrder.Status.EXPIRED)
            .count(),
            1,
        )

    def test_member_cannot_view_another_members_order(self):
        order = self.create_order()
        another_member = get_user_model().objects.create_user(
            username="another-member", password="Strong-test-password-198!"
        )
        self.client.force_login(another_member)

        response = self.client.get(reverse("purchase_detail", args=(order.pk,)))

        self.assertEqual(response.status_code, 404)

    def test_receipt_requires_file_and_admin_finishes_purchase(self):
        order = self.create_order()
        self.client.force_login(self.admin)
        self.client.post(reverse("review_purchase", args=(order.pk, "approve")))
        self.client.force_login(self.member)

        missing_file_response = self.client.post(
            reverse("purchase_detail", args=(order.pk,)),
            {
                "receipt_reference": "TRACK-123",
                "receipt_message": "پرداخت انجام شد",
            },
        )
        self.assertEqual(missing_file_response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PAYMENT_DUE)

        receipt = SimpleUploadedFile(
            "receipt.pdf", b"%PDF-1.7\nreceipt", content_type="application/pdf"
        )
        response = self.client.post(
            reverse("purchase_detail", args=(order.pk,)),
            {
                "receipt_reference": "TRACK-123",
                "receipt_message": "پرداخت انجام شد",
                "receipt_file": receipt,
            },
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.RECEIPT_REVIEW)

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("review_purchase", args=(order.pk, "complete"))
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.COMPLETED)

    def test_receipt_rejects_mismatched_file_content(self):
        from .forms import ReceiptSubmissionForm

        form = ReceiptSubmissionForm(
            data={
                "receipt_reference": "TRACK-123",
                "receipt_message": "پرداخت انجام شد",
            },
            files={
                "receipt_file": SimpleUploadedFile(
                    "receipt.pdf", b"not a pdf", content_type="application/pdf"
                )
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("receipt_file", form.errors)
