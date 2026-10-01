from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import MemberProfile, PriceItem, PriceUpdate


class MemberDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="member", password="Strong-test-password-123"
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('dashboard')}"
        )

    def test_member_can_see_latest_prices_and_own_balance(self):
        profile = self.user.member_profile
        profile.balance_grams = "2.500"
        profile.balance_rials = "1250000"
        profile.save()
        item = PriceItem.objects.get(name="نقدی ۴۸")
        PriceUpdate.objects.create(
            item=item, buy_price=71000000, sell_price=73000000, created_by=self.user
        )
        self.client.login(username="member", password="Strong-test-password-123")

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نقدی ۴۸")
        self.assertContains(response, 'class="price-buy"')
        self.assertContains(response, 'class="price-sell"')
        self.assertContains(response, "static/css/site.css")
        self.assertContains(response, "2.500")
        self.assertEqual(
            response.context["price_items"][1].latest_updates[0].buy_price,
            Decimal("71000000"),
        )

    def test_user_creation_creates_member_profile(self):
        self.assertTrue(MemberProfile.objects.filter(user=self.user).exists())

    def test_logout_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)
