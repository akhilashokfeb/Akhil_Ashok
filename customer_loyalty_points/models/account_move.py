# -*- coding: utf-8 -*-
from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    loyalty_points_awarded = fields.Integer(
        string="Loyalty Points Awarded",
        help="Number of loyalty points awarded when this customer invoice was posted.",
        default=0,
    )
    loyalty_points_recovered = fields.Integer(
        string="Loyalty Points Recovered",
        copy=False,
        readonly=True,
        default=0,
        help="Number of loyalty points recovered when this credit note is posted.",
    )

    def _get_loyalty_earning_amount(self):
        """Return the configured amount required to earn one loyalty point."""
        self.ensure_one()
        earning_amount = self.company_id.loyalty_earning_amount
        return earning_amount if earning_amount > 0 else 10.0

    def _post(self, soft=True):
        """ Extends the standard posting process to record loyalty point
    transactions for customer invoices and credit notes.
    """
        moves = super()._post(soft)
        transaction = self.env["loyalty.points.transaction"]

        for move in moves.filtered(
            lambda m: m.move_type in ("out_invoice", "out_refund")
        ):
            partner = move.partner_id.commercial_partner_id
            earning_amount = move._get_loyalty_earning_amount()
            points = int(abs(move.amount_total_signed) // earning_amount)

            if not points and move.move_type == "out_refund":
                continue

            if move.move_type == "out_invoice":
                points_to_award = points - move.loyalty_points_awarded
                if points_to_award > 0:
                    move.loyalty_points_awarded = points

                    transaction.create(
                        {
                            "partner_id": partner.id,
                            "company_id": move.company_id.id,
                            "transaction_date": move.invoice_date,
                            "transaction_type": "earn",
                            "points": points_to_award,
                            "remaining_points": points_to_award,
                            "expiration_date": transaction._get_expiration_date(
                                move.invoice_date
                            ),
                            "account_move_id": move.id,
                            "description": _("Points earned from invoice %s") % (
                                move.name or move.ref or move.id
                            ),
                        }
                    )
                elif move.loyalty_points_awarded != points:
                    move.loyalty_points_awarded = points

            elif move.move_type == "out_refund":
                if not move.loyalty_points_recovered:
                    recovered_points, consumed_details = transaction._consume_points_fifo(
                        partner,
                        points,
                        company=move.company_id,
                        strict=False,
                        return_details=True,
                    )
                    if not recovered_points:
                        continue

                    move.loyalty_points_recovered = recovered_points

                    for consumed_detail in consumed_details:
                        transaction.create(
                            {
                                "partner_id": partner.id,
                                "company_id": move.company_id.id,
                                "transaction_date": move.invoice_date,
                                "transaction_type": "refund",
                                "points": consumed_detail["points"],
                                "remaining_points": 0,
                                "expiration_date": consumed_detail["expiration_date"],
                                "account_move_id": move.id,
                                "description": _(
                                    "Points deducted from credit note %s"
                                ) % (
                                    move.name or move.ref or move.id
                                ),
                            }
                        )

        return moves

    def button_draft(self):
        """Reverse loyalty point effects when invoices are reset to draft."""
        moves_to_recover = self.filtered(
            lambda m: (
                m.state == "posted"
                and m.move_type in ("out_invoice", "out_refund")
            )
        )

        transaction = self.env["loyalty.points.transaction"]
        res = super().button_draft()

        for move in moves_to_recover.filtered(
            lambda m: m.move_type == "out_invoice" and m.loyalty_points_awarded
        ):
            partner = move.partner_id.commercial_partner_id
            points_awarded = move.loyalty_points_awarded

            recovered_points, consumed_details = transaction._consume_points_fifo(
                partner,
                points_awarded,
                company=move.company_id,
                strict=False,
                return_details=True,
            )
            move.loyalty_points_awarded = points_awarded - recovered_points

            if not recovered_points:
                continue

            for consumed_detail in consumed_details:
                transaction.create(
                    {
                        "partner_id": partner.id,
                        "company_id": move.company_id.id,
                        "transaction_date": fields.Date.context_today(move),
                        "transaction_type": "reset",
                        "points": consumed_detail["points"],
                        "remaining_points": 0,
                        "expiration_date": consumed_detail["expiration_date"],
                        "account_move_id": move.id,
                        "description": _(
                            "Points reversed because invoice %s was reset to draft"
                        ) % (
                            move.name or move.ref or move.id
                        ),
                    }
                )

        for move in moves_to_recover.filtered(
            lambda m: m.move_type == "out_refund" and m.loyalty_points_recovered
        ):
            partner = move.partner_id.commercial_partner_id
            refund_transactions = transaction.search(
                [
                    ("account_move_id", "=", move.id),
                    ("company_id", "=", move.company_id.id),
                    ("transaction_type", "=", "refund"),
                ]
            )

            move.loyalty_points_recovered = 0

            for refund_transaction in refund_transactions:
                transaction.create(
                    {
                        "partner_id": partner.id,
                        "company_id": move.company_id.id,
                        "transaction_date": fields.Date.context_today(move),
                        "transaction_type": "restore",
                        "points": refund_transaction.points,
                        "remaining_points": refund_transaction.points,
                        "expiration_date": refund_transaction.expiration_date,
                        "account_move_id": move.id,
                        "description": _(
                            "Points restored because credit note %s was reset to draft"
                        ) % (
                            move.name or move.ref or move.id
                        ),
                    }
                )

        return res
