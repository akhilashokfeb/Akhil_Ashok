# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    loyalty_transaction_ids = fields.One2many(
        "loyalty.points.transaction",
        "partner_id",
        string="Loyalty Transactions",
        readonly=True,
    )

    loyalty_points = fields.Integer(
        string="Loyalty Points",
        compute="_compute_loyalty_points",
        readonly=True,
        help=(
            "Displays the customer's available loyalty points from transaction "
            "balances."
        ),
    )

    commercial_loyalty_points = fields.Integer(
        string="Loyalty Points",
        compute="_compute_commercial_loyalty_points",
    )

    @api.depends(
        "commercial_partner_id",
        "commercial_partner_id.loyalty_transaction_ids.remaining_points",
    )
    def _compute_loyalty_points(self):
        """Compute the available loyalty points for each partner."""
        commercial_partner_ids = self.mapped("commercial_partner_id").ids
        transaction_data = []
        if commercial_partner_ids:
            transaction_data = self.env["loyalty.points.transaction"].read_group(
                [
                    ("partner_id", "in", commercial_partner_ids),
                    ("company_id", "=", self.env.company.id),
                    ("remaining_points", ">", 0),
                ],
                ["remaining_points:sum"],
                ["partner_id"],
            )
        points_by_partner = {
            data["partner_id"][0]: data["remaining_points"]
            for data in transaction_data
        }
        for partner in self:
            commercial_partner = partner.commercial_partner_id
            partner.loyalty_points = points_by_partner.get(
                commercial_partner.id,
                0,
            )

    @api.depends("commercial_partner_id.loyalty_points")
    def _compute_commercial_loyalty_points(self):
        """Compute the commercial partner's available loyalty points."""
        for partner in self:
            partner.commercial_loyalty_points = (
                partner.commercial_partner_id.loyalty_points
                if partner.commercial_partner_id
                else 0
            )

    def action_view_loyalty_transactions(self):
        """Open the loyalty transactions for the commercial partner."""
        self.ensure_one()
        commercial_partner = self.commercial_partner_id
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "customer_loyalty_points.action_loyalty_points_transactions"
        )
        action["domain"] = [
            ("partner_id", "=", commercial_partner.id),
            ("company_id", "=", self.env.company.id),
        ]
        action["context"] = {
            "default_partner_id": commercial_partner.id,
            "default_company_id": self.env.company.id,
            "search_default_partner_id": commercial_partner.id,
        }
        return action
