# -*- coding: utf-8 -*-
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class CustomerLoyaltyPointsPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        """Add the customer's loyalty points to the portal home values."""
        values = super()._prepare_home_portal_values(counters)

        if "loyalty_points_count" in counters:
            partner = request.env.user.partner_id.commercial_partner_id.sudo()
            values["loyalty_points_count"] = partner.loyalty_points

        return values
