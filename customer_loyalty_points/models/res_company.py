# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    loyalty_earning_amount = fields.Float(
        string="Amount Required for 1 Point",
        default=10.0,
    )
    loyalty_redemption_value = fields.Float(
        string="Value of 1 Point",
        default=0.50,
    )
