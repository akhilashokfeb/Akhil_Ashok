# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LoyaltyPointsTransaction(models.Model):
    _name = "loyalty.points.transaction"
    _description = "Loyalty Points Transaction"
    _order = "transaction_date desc, id desc"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    transaction_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    transaction_type = fields.Selection(
        [
            ("earn", "Earned"),
            ("redeem", "Redeemed"),
            ("reset", "Reset To Draft"),
            ("restore", "Restored"),
            ("refund", "Refunded"),
            ("expire", "Expired"),
        ],
        required=True,
        default="earn",
    )
    points = fields.Integer(required=True)
    remaining_points = fields.Integer(
        help="Unredeemed points remaining on positive earn/restore transactions.",
        index=True,
    )
    expiration_date = fields.Date(
        string="Expiration Date",
        help="Date on which remaining positive points expire.",
        index=True,
    )
    description = fields.Char(string="Description")
    account_move_id = fields.Many2one("account.move", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", ondelete="set null")

    def _get_expiration_date(self, transaction_date):
        return fields.Date.add(
            transaction_date or fields.Date.context_today(self),
            years=1,
        )

    def _get_available_points(self, partner, company=None):
        partner = partner.commercial_partner_id
        company = company or self.env.company
        source_transactions = self.search(
            [
                ("partner_id", "=", partner.id),
                ("company_id", "=", company.id),
                ("transaction_type", "in", ("earn", "restore")),
                ("remaining_points", ">", 0),
            ]
        )
        return sum(source_transactions.mapped("remaining_points"))

    def _consume_points_fifo(
        self,
        partner,
        points,
        company=None,
        strict=True,
        return_details=False,
    ):
        """Consume available loyalty points from oldest positive transactions."""
        partner = partner.commercial_partner_id
        company = company or self.env.company
        points_to_consume = int(points or 0)
        if points_to_consume <= 0:
            return (0, []) if return_details else 0

        source_transactions = self.search(
            [
                ("partner_id", "=", partner.id),
                ("company_id", "=", company.id),
                ("transaction_type", "in", ("earn", "restore")),
                ("remaining_points", ">", 0),
            ],
            order="expiration_date asc, transaction_date asc, id asc",
        )

        available_points = sum(source_transactions.mapped("remaining_points"))
        if available_points < points_to_consume:
            if not strict:
                points_to_consume = available_points
            if not points_to_consume:
                return (0, []) if return_details else 0
        if available_points < points_to_consume:
            raise UserError(
                _(
                    "The customer does not have enough available loyalty points. "
                    "Available: %(available)s, Required: %(required)s",
                    available=available_points,
                    required=points_to_consume,
                )
            )

        remaining = points_to_consume
        consumed_details = []
        for transaction in source_transactions:
            consumed = min(transaction.remaining_points, remaining)
            transaction.remaining_points -= consumed
            consumed_details.append(
                {
                    "points": consumed,
                    "expiration_date": transaction.expiration_date,
                    "company_id": transaction.company_id.id,
                }
            )
            remaining -= consumed
            if not remaining:
                break

        if return_details:
            return points_to_consume, consumed_details
        return points_to_consume

    @api.model
    def _cron_expire_loyalty_points(self):
        """Expire unredeemed loyalty points one year after they were earned."""
        today = fields.Date.context_today(self)
        source_transactions = self.search(
            [
                ("transaction_type", "in", ("earn", "restore")),
                ("remaining_points", ">", 0),
                ("expiration_date", "<=", today),
            ],
            order="partner_id, transaction_date asc, id asc",
        )

        for partner in source_transactions.mapped("partner_id"):
            partner_transactions = source_transactions.filtered(
                lambda transaction: transaction.partner_id == partner
            )
            for company in partner_transactions.mapped("company_id"):
                company_transactions = partner_transactions.filtered(
                    lambda transaction: transaction.company_id == company
                )
                expired_points = sum(company_transactions.mapped("remaining_points"))
                company_transactions.write({"remaining_points": 0})

                if expired_points:
                    self.create(
                        {
                            "partner_id": partner.id,
                            "company_id": company.id,
                            "transaction_date": fields.Date.context_today(self),
                            "transaction_type": "expire",
                            "points": expired_points,
                            "remaining_points": 0,
                            "description": _("Points expired after one year."),
                        }
                    )

    def action_expire_selected_loyalty_points(self):
        """Manual server action to expire only the selected loyalty points."""
        active_ids = self.env.context.get("active_ids")
        selected_transactions = self.browse(active_ids) if active_ids else self
        source_transactions = selected_transactions.filtered(
            lambda transaction: transaction.transaction_type in ("earn", "restore")
            and transaction.remaining_points > 0
        )

        for partner in source_transactions.mapped("partner_id"):
            partner_transactions = source_transactions.filtered(
                lambda transaction: transaction.partner_id == partner
            )
            for company in partner_transactions.mapped("company_id"):
                company_transactions = partner_transactions.filtered(
                    lambda transaction: transaction.company_id == company
                )
                expired_points = sum(company_transactions.mapped("remaining_points"))
                company_transactions.write({"remaining_points": 0})

                if expired_points:
                    self.create(
                        {
                            "partner_id": partner.id,
                            "company_id": company.id,
                            "transaction_date": fields.Date.context_today(self),
                            "transaction_type": "expire",
                            "points": expired_points,
                            "remaining_points": 0,
                            "description": _("Selected points expired manually."),
                        }
                    )
