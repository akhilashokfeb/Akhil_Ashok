# -*- coding: utf-8 -*-
{
    "name": "Customer Loyalty Points",
    "version": "17.0.1.0.0",
    "category": "Sales",
    "summary": (
        "Earn loyalty points from posted invoices and redeem them on sales "
        "orders."
    ),
    "depends": [
        "base",
        "account",
        "portal",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/loyalty_points_security.xml",
        "data/loyalty_product_data.xml",
        "data/loyalty_points_cron.xml",
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
        "views/res_config_settings_views.xml",
        "views/loyalty_points_transaction_views.xml",
        "views/portal_templates.xml",
        "wizard/loyalty_redeem_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "customer_loyalty_points/static/src/scss/loyalty.scss",
        ],
        "web.assets_frontend": [
            "customer_loyalty_points/static/src/js/portal.js",
        ],
    },
    "installable": True,
    "application": False,
}
