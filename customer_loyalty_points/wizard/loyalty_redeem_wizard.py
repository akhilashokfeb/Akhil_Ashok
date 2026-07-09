# -*- coding: utf-8 -*-
from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError


class LoyaltyRedeemWizard(models.TransientModel):
    _name = "loyalty.redeem.wizard"
    _description = "Loyalty Redeem Wizard"

    order_id = fields.Many2one(
        "sale.order",
        required=True,
        readonly=True,
    )
    points_available = fields.Integer(
        string="Available Points",
        readonly=True,
        related="order_id.points_available",
    )
    points_to_redeem = fields.Integer(
        string="Points to Redeem",
        required=True,
    )
    redemption_amount = fields.Monetary(
        string="Redemption Amount",
        compute="_compute_loyalty_redemption_amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id",
        readonly=True,
    )

    @api.onchange("points_to_redeem")
    def _onchange_points_to_redeem(self):
        """Prevent redeeming more loyalty points than are available."""
        if (
            not self.points_to_redeem
            or self.points_to_redeem <= self.points_available
        ):
            return

        available_points = self.points_available
        redeem_points = self.points_to_redeem
        return {
            "warning": {
                "title": _("Invalid Loyalty Redemption"),
                "message": _(
                    "The number of points to redeem (%(redeem)s) cannot exceed "
                    "the customer's available loyalty points (%(available)s).",
                    redeem=redeem_points,
                    available=available_points,
                ),
            }
        }

    @api.depends("points_to_redeem")
    def _compute_loyalty_redemption_amount(self):
        """Compute redemption amount in the sale order currency."""
        for rec in self:
            if rec.points_to_redeem <= 0:
                rec.redemption_amount = 0.0
                continue

            company = rec.order_id.company_id or self.env.company
            company_currency = company.currency_id
            order_currency = rec.order_id.currency_id
            redemption_value = company.loyalty_redemption_value or 0.50
            amount_company_currency = rec.points_to_redeem * redemption_value
            rec.redemption_amount = company_currency._convert(
                amount_company_currency,
                order_currency,
                company,
                rec.order_id.date_order,
            )

    def action_apply_redemption(self):
        """Apply loyalty redemption as a negative sale order line."""
        self.ensure_one()
        order = self.order_id
        if self.points_to_redeem <= 0:
            raise UserError(
                _("Please enter a valid number of loyalty points to redeem.")
            )

        if self.points_to_redeem > self.points_available:
            raise UserError(
                _("You cannot redeem more points than the customer has.")
            )

        product = self.env.ref(
            "customer_loyalty_points.product_template_loyalty_redemption"
        ).product_variant_id

        amount = self.redemption_amount
        self.order_id.redeemed_points = self.points_to_redeem

        redemption_lines = order.order_line.filtered(
            lambda line: line.is_loyalty_redemption_line
            or line.product_id == product
        )

        values = {
            "name": _("Loyalty Points Redemption (%s points)") % self.points_to_redeem,
            "product_id": product.id,
            "product_uom_qty": 1.0,
            "price_unit": -amount,
            "tax_id": [Command.clear()],
            "is_loyalty_redemption_line": True,
        }

        if redemption_lines:
            redemption_lines[0].write(values)
            (redemption_lines - redemption_lines[0]).unlink()
        else:
            order.write({"order_line": [Command.create(values)]})

        return {"type": "ir.actions.act_window_close"}
