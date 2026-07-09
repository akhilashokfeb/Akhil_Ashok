# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    points_available = fields.Integer(
        string="Available Points",
        compute="_compute_points_available",
    )

    redeemed_points = fields.Integer(
        string="Redeemed Points",
        readonly=True,
        copy=False,
    )

    loyalty_points_deducted = fields.Boolean(
        string="Loyalty Points Deducted",
        default=False,
        copy=False,
        readonly=True,
    )

    @api.depends(
        "partner_id",
        "partner_id.loyalty_points",
        "company_id",
    )
    def _compute_points_available(self):
        """Compute loyalty points available for the selected customer."""
        transaction_model = self.env["loyalty.points.transaction"]
        for order in self:
            partner = order.partner_id.commercial_partner_id
            order.points_available = (
                transaction_model._get_available_points(partner, order.company_id)
                if partner and order.company_id
                else 0
            )

    def action_redeem_now(self):
        """Open the loyalty redemption wizard."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Redeem Loyalty Points"),
            "res_model": "loyalty.redeem.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_points_available": self.points_available,
            },
        }

    @api.onchange("partner_id")
    def _onchange_partner_id_clear_loyalty_redemption(self):
        """Reset loyalty redemption when the customer is changed."""
        for order in self:
            if order.redeemed_points:
                order.redeemed_points = 0
                order.order_line = order.order_line.filtered(
                    lambda line: not line.is_loyalty_redemption_line
                )

    def action_confirm(self):
        """Validate and apply loyalty redemption during order confirmation."""
        for sale_order in self:
            if sale_order.redeemed_points > sale_order.points_available:
                raise UserError(
                    _(
                        "The redeemed loyalty points (%(redeemed)s) cannot exceed "
                        "the customer's available loyalty points (%(available)s).",
                        redeemed=sale_order.redeemed_points,
                        available=sale_order.points_available,
                    )
                )
            redemption_total = abs(
                sum(
                    sale_order.order_line.filtered(
                        lambda line: line.is_loyalty_redemption_line
                    ).mapped("price_total")
                )
            )
            other_subtotal = sum(
                sale_order.order_line.filtered(
                    lambda line: (
                        not line.is_loyalty_redemption_line
                        and not line.display_type
                    )
                ).mapped("price_total")
            )
            if redemption_total > other_subtotal:
                raise UserError(
                    _(
                        "The loyalty redemption amount cannot be greater than "
                        "the order subtotal."
                    )
                )
        res = super().action_confirm()
        transaction_model = self.env["loyalty.points.transaction"]
        for sale_order in self:
            if (
                sale_order.redeemed_points
                and not sale_order.loyalty_points_deducted
            ):
                partner = sale_order.partner_id.commercial_partner_id
                (
                    consumed_points,
                    consumed_details,
                ) = transaction_model._consume_points_fifo(
                    partner,
                    sale_order.redeemed_points,
                    company=sale_order.company_id,
                    return_details=True,
                )
                if not consumed_points:
                    continue
                sale_order.loyalty_points_deducted = True
                for consumed_detail in consumed_details:
                    transaction_model.create(
                        {
                            "partner_id": partner.id,
                            "company_id": sale_order.company_id.id,
                            "transaction_date": fields.Date.context_today(sale_order),
                            "transaction_type": "redeem",
                            "points": consumed_detail["points"],
                            "remaining_points": 0,
                            "expiration_date": consumed_detail["expiration_date"],
                            "sale_order_id": sale_order.id,
                            "description": _("Points redeemed on sale order %s") % (
                                sale_order.name or sale_order.id
                            ),
                        }
                    )
        return res

    def _action_cancel(self):
        """Restore redeemed loyalty points on cancellation."""
        orders_with_redemption = self.filtered(lambda order: order.redeemed_points)
        res = super()._action_cancel()
        transaction_model = self.env["loyalty.points.transaction"]
        for order in orders_with_redemption:
            if order.loyalty_points_deducted:
                order.loyalty_points_deducted = False
                redemption_transactions = transaction_model.search(
                    [
                        ("sale_order_id", "=", order.id),
                        ("company_id", "=", order.company_id.id),
                        ("transaction_type", "=", "redeem"),
                    ]
                )
                for redemption_transaction in redemption_transactions:
                    transaction_model.create(
                        {
                            "partner_id": order.partner_id.commercial_partner_id.id,
                            "company_id": order.company_id.id,
                            "transaction_date": fields.Date.context_today(order),
                            "transaction_type": "restore",
                            "points": redemption_transaction.points,
                            "remaining_points": redemption_transaction.points,
                            "expiration_date": redemption_transaction.expiration_date,
                            "sale_order_id": order.id,
                            "description": _(
                                "Points restored because sale order %s was cancelled"
                            ) % (
                                order.name or order.id
                            ),
                        }
                    )
            order.redeemed_points = 0
            order.order_line.filtered("is_loyalty_redemption_line").unlink()
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_loyalty_redemption_line = fields.Boolean(
        string="Loyalty Redemption Line",
        copy=False,
        default=False,
        readonly=True,
    )

    def unlink(self):
        """Prevent deleting redemption lines after loyalty points are deducted.

        Allows draft redemption lines to be removed and resets the redeemed
        points on affected orders when no redemption line remains.
        """
        loyalty_lines = self.filtered("is_loyalty_redemption_line")
        deducted_orders = loyalty_lines.mapped("order_id").filtered(
            lambda order: order.loyalty_points_deducted
        )

        if deducted_orders:
            raise UserError(
                _(
                    "You cannot delete a loyalty redemption line after points "
                    "were deducted."
                )
            )

        affected_orders = loyalty_lines.mapped("order_id")
        res = super().unlink()

        for order in affected_orders:
            if not order.order_line.filtered("is_loyalty_redemption_line"):
                order.redeemed_points = 0

        return res
