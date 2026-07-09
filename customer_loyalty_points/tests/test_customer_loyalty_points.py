from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestCustomerLoyaltyPoints(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company_2 = cls.company_data_2["company"]
        cls.company.loyalty_earning_amount = 10.0
        cls.company.loyalty_redemption_value = 1.0
        cls.company_2.loyalty_earning_amount = 10.0
        cls.company_2.loyalty_redemption_value = 1.0
        cls.Transaction = cls.env["loyalty.points.transaction"]
        cls.sale_product = cls.env["product.product"].create(
            {
                "name": "Loyalty Test Product",
                "type": "consu",
                "lst_price": 100.0,
                "property_account_income_id": cls.company_data[
                    "default_account_revenue"
                ].id,
                "taxes_id": [Command.clear()],
            }
        )

    def _today(self):
        return fields.Date.context_today(self.Transaction)

    def _next_year(self, date):
        return fields.Date.add(date, years=1)

    def _post_invoice(
        self,
        partner=None,
        amount=100.0,
        invoice_date="2024-01-01",
        company=None,
        currency=None,
    ):
        print("11111111111")
        return self.init_invoice(
            "out_invoice",
            partner=partner or self.partner_a,
            invoice_date=invoice_date,
            amounts=[amount],
            taxes=self.env["account.tax"],
            company=company or self.company,
            currency=currency,
            post=True,
        )

    def _post_refund(
        self,
        partner=None,
        amount=100.0,
        invoice_date="2024-01-02",
        company=None,
    ):
        return self.init_invoice(
            "out_refund",
            partner=partner or self.partner_a,
            invoice_date=invoice_date,
            amounts=[amount],
            taxes=self.env["account.tax"],
            company=company or self.company,
            post=True,
        )

    def _create_sale_order(
        self,
        partner=None,
        amount=100.0,
        company=None,
        pricelist=None,
        date_order=None,
    ):
        company = company or self.company
        values = {
            "partner_id": (partner or self.partner_a).id,
            "company_id": company.id,
            "order_line": [
                Command.create(
                    {
                        "product_id": self.sale_product.id,
                        "product_uom_qty": 1.0,
                        "price_unit": amount,
                        "tax_id": [Command.clear()],
                    }
                )
            ],
        }
        if pricelist:
            values["pricelist_id"] = pricelist.id
        if date_order:
            values["date_order"] = date_order
        return self.env["sale.order"].with_company(company).create(values)

    def _apply_redemption(self, order, points):
        wizard = self.env["loyalty.redeem.wizard"].create(
            {
                "order_id": order.id,
                "points_to_redeem": points,
            }
        )
        wizard.action_apply_redemption()
        return wizard

    def test_invoice_posting_awards_points_to_commercial_partner(self):
        today = self._today()
        child_partner = self.env["res.partner"].create(
            {
                "name": "Child Contact",
                "parent_id": self.partner_a.id,
                "type": "invoice",
            }
        )

        invoice = self._post_invoice(
            partner=child_partner,
            amount=100.0,
            invoice_date=today,
        )

        self.assertEqual(invoice.loyalty_points_awarded, 10)
        self.assertEqual(self.partner_a.loyalty_points, 10)
        self.assertEqual(child_partner.loyalty_points, 10)
        self.assertRecordValues(
            self.Transaction.search([("account_move_id", "=", invoice.id)]),
            [
                {
                    "partner_id": self.partner_a.id,
                    "company_id": self.company.id,
                    "transaction_type": "earn",
                    "points": 10,
                    "remaining_points": 10,
                    "expiration_date": self._next_year(today),
                }
            ],
        )

    def test_refund_posting_recovers_available_points(self):
        self._post_invoice(amount=100.0)

        refund = self._post_refund(amount=50.0)

        self.assertEqual(refund.loyalty_points_recovered, 5)
        self.assertEqual(self.partner_a.loyalty_points, 5)
        self.assertRecordValues(
            self.Transaction.search(
                [
                    ("account_move_id", "=", refund.id),
                    ("transaction_type", "=", "refund"),
                ]
            ),
            [{"points": 5, "remaining_points": 0}],
        )

    def test_refund_posting_does_not_block_when_points_are_already_spent(self):
        self._post_invoice(amount=100.0)
        self.Transaction._consume_points_fifo(
            self.partner_a,
            10,
            company=self.company,
        )

        refund = self._post_refund(amount=100.0)

        self.assertEqual(refund.state, "posted")
        self.assertEqual(refund.loyalty_points_recovered, 0)
        self.assertFalse(
            self.Transaction.search(
                [
                    ("account_move_id", "=", refund.id),
                    ("transaction_type", "=", "refund"),
                ]
            )
        )

    def test_sale_order_redemption_and_cancel_restore_points(self):
        today = self._today()
        self._post_invoice(amount=100.0, invoice_date=today)
        order = self._create_sale_order(amount=100.0)

        self._apply_redemption(order, 4)
        order.action_confirm()

        self.assertTrue(order.loyalty_points_deducted)
        self.assertEqual(self.partner_a.loyalty_points, 6)
        self.assertRecordValues(
            self.Transaction.search(
                [
                    ("sale_order_id", "=", order.id),
                    ("transaction_type", "=", "redeem"),
                ]
            ),
            [
                {
                    "points": 4,
                    "remaining_points": 0,
                    "expiration_date": self._next_year(today),
                }
            ],
        )

        order._action_cancel()

        self.assertFalse(order.loyalty_points_deducted)
        self.assertEqual(order.redeemed_points, 0)
        self.assertEqual(self.partner_a.loyalty_points, 10)
        self.assertRecordValues(
            self.Transaction.search(
                [
                    ("sale_order_id", "=", order.id),
                    ("transaction_type", "=", "restore"),
                ]
            ),
            [
                {
                    "points": 4,
                    "remaining_points": 4,
                    "expiration_date": self._next_year(today),
                }
            ],
        )

    def test_expiry_uses_original_expiration_date_after_restore(self):
        today = self._today()
        self._post_invoice(amount=100.0, invoice_date=today)
        order = self._create_sale_order(amount=100.0)
        self._apply_redemption(order, 4)
        order.action_confirm()
        order._action_cancel()

        restore_transaction = self.Transaction.search(
            [
                ("sale_order_id", "=", order.id),
                ("transaction_type", "=", "restore"),
            ]
        )
        self.assertEqual(
            restore_transaction.expiration_date,
            self._next_year(today),
        )

        self.env.cr.execute(
            "UPDATE loyalty_points_transaction "
            "SET expiration_date = %s "
            "WHERE id = %s",
            [fields.Date.subtract(today, days=1), restore_transaction.id],
        )
        restore_transaction.invalidate_recordset(["expiration_date"])

        self.Transaction._cron_expire_loyalty_points()

        self.assertEqual(restore_transaction.remaining_points, 0)
        self.assertEqual(self.partner_a.loyalty_points, 6)
        self.assertTrue(
            self.Transaction.search(
                [
                    ("partner_id", "=", self.partner_a.id),
                    ("company_id", "=", self.company.id),
                    ("transaction_type", "=", "expire"),
                    ("points", "=", 4),
                ]
            )
        )

    def test_manual_expiry_only_expires_selected_transactions(self):
        invoice_a = self._post_invoice(amount=100.0, invoice_date="2024-01-01")
        invoice_b = self._post_invoice(amount=100.0, invoice_date="2024-01-02")
        source_a = self.Transaction.search(
            [
                ("account_move_id", "=", invoice_a.id),
                ("transaction_type", "=", "earn"),
            ]
        )
        source_b = self.Transaction.search(
            [
                ("account_move_id", "=", invoice_b.id),
                ("transaction_type", "=", "earn"),
            ]
        )

        self.Transaction.with_context(
            active_ids=source_a.ids,
        ).action_expire_selected_loyalty_points()

        self.assertEqual(source_a.remaining_points, 0)
        self.assertEqual(source_b.remaining_points, 10)
        self.assertTrue(
            self.Transaction.search(
                [
                    ("partner_id", "=", self.partner_a.id),
                    ("company_id", "=", self.company.id),
                    ("transaction_type", "=", "expire"),
                    ("points", "=", 10),
                    ("description", "=", "Selected points expired manually."),
                ]
            )
        )

    def test_redeeming_more_than_available_raises(self):
        self._post_invoice(amount=100.0)
        order = self._create_sale_order(amount=100.0)
        order.redeemed_points = 11

        with self.assertRaises(UserError):
            order.action_confirm()

    def test_redemption_cannot_exceed_order_subtotal(self):
        self._post_invoice(amount=100.0)
        order = self._create_sale_order(amount=3.0)
        self._apply_redemption(order, 4)

        with self.assertRaises(UserError):
            order.action_confirm()

    def test_delete_deducted_redemption_line_raises(self):
        self._post_invoice(amount=100.0)
        order = self._create_sale_order(amount=100.0)
        self._apply_redemption(order, 4)
        order.action_confirm()

        with self.assertRaises(UserError):
            order.order_line.filtered("is_loyalty_redemption_line").unlink()

    def test_partner_smart_button_opens_commercial_partner_transactions(self):
        child_partner = self.env["res.partner"].create(
            {
                "name": "Child Contact",
                "parent_id": self.partner_a.id,
                "type": "invoice",
            }
        )

        action = child_partner.action_view_loyalty_transactions()

        self.assertEqual(
            action["domain"],
            [
                ("partner_id", "=", self.partner_a.id),
                ("company_id", "=", self.env.company.id),
            ],
        )
        self.assertEqual(
            action["context"]["default_partner_id"],
            self.partner_a.id,
        )
        self.assertEqual(
            action["context"]["default_company_id"],
            self.env.company.id,
        )

    def test_points_are_isolated_by_company(self):
        self._post_invoice(amount=100.0)
        self._post_invoice(
            amount=200.0,
            company=self.company_2,
        )

        company_1_order = self._create_sale_order(amount=100.0)
        company_2_order = self._create_sale_order(
            amount=100.0,
            company=self.company_2,
        )

        self.assertEqual(company_1_order.points_available, 10)
        self.assertEqual(company_2_order.points_available, 20)

        self.Transaction._consume_points_fifo(
            self.partner_a,
            10,
            company=self.company,
        )

        self.assertEqual(company_1_order.points_available, 0)
        self.assertEqual(company_2_order.points_available, 20)

    def test_company_specific_loyalty_settings_are_used(self):
        self.company.loyalty_earning_amount = 10.0
        self.company_2.loyalty_earning_amount = 20.0

        invoice_company_1 = self._post_invoice(amount=100.0, company=self.company)
        invoice_company_2 = self._post_invoice(amount=100.0, company=self.company_2)

        self.assertEqual(invoice_company_1.loyalty_points_awarded, 10)
        self.assertEqual(invoice_company_2.loyalty_points_awarded, 5)

    def test_multi_currency_invoice_awards_points_in_company_currency(self):
        foreign_currency = self.currency_data["currency"]

        invoice = self._post_invoice(
            amount=100.0,
            invoice_date="2017-01-01",
            currency=foreign_currency,
        )

        self.assertEqual(invoice.amount_total_signed, 50.0)
        self.assertEqual(invoice.loyalty_points_awarded, 5)
        self.assertRecordValues(
            self.Transaction.search([("account_move_id", "=", invoice.id)]),
            [{"points": 5, "remaining_points": 5}],
        )

    def test_multi_currency_redemption_uses_order_currency(self):
        foreign_currency = self.currency_data["currency"]
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Foreign Currency Loyalty Pricelist",
                "currency_id": foreign_currency.id,
                "company_id": self.company.id,
            }
        )
        self._post_invoice(amount=100.0)
        order = self._create_sale_order(
            amount=100.0,
            pricelist=pricelist,
            date_order="2017-01-01",
        )

        wizard = self._apply_redemption(order, 4)

        self.assertEqual(wizard.currency_id, foreign_currency)
        self.assertEqual(wizard.redemption_amount, 8.0)
        redemption_line = order.order_line.filtered("is_loyalty_redemption_line")
        self.assertEqual(redemption_line.price_unit, -8.0)

    def test_loyalty_config_values_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.env["res.config.settings"].create(
                {
                    "company_id": self.company.id,
                    "loyalty_earning_amount": 0.0,
                    "loyalty_redemption_value": 1.0,
                }
            )
