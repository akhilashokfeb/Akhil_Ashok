# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    loyalty_earning_amount = fields.Float(
        string="Amount Required for 1 Point",
        related="company_id.loyalty_earning_amount",
        readonly=False,
    )

    loyalty_redemption_value = fields.Float(
        string="Value of 1 Point",
        related="company_id.loyalty_redemption_value",
        readonly=False,
    )

    @api.constrains("loyalty_earning_amount", "loyalty_redemption_value")
    def _check_loyalty_values(self):
        """Validate that loyalty earning and redemption values are positive."""
        for record in self:
            if record.loyalty_earning_amount <= 0:
                raise ValidationError(
                    _("Amount Required for 1 Point must be greater than zero.")
                )
            if record.loyalty_redemption_value <= 0:
                raise ValidationError(
                    _("Value of 1 Point must be greater than zero.")
                )
