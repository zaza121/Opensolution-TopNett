# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Faccturation immobilier',
    'author': 'Opensolution',
    'category': 'Accounting',
    'version': '1.0.0',
    'description': """""",
    'summary': '',
    'sequence': 11,
    'website': 'https://www.opensolution.mc',
    'depends': ['account', 'sale_management'],
    'license': 'LGPL-3',
    'data': [
        # reports
        "reports/situation_invoice_report.xml",
        # data
        'data/sequence.xml',
        'data/mail_template_data.xml',
        'data/rounding_data.xml',
        'data/product_data.xml',
        # 'data/recurring_cron.xml',
        # security
        'security/ir.model.access.csv',
        # views
        'views/menus.xml',
        'views/invoice_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/situation_views.xml',
        'views/res_config_settings_views.xml',
        # 'views/recurring_payment_view.xml'
        # wizards
        "wizards/update_situation_wiz_views.xml",
    ],
    'assets': {
        'web.report_assets_common': ['immo_bill/static/css/style.scss'],
    },
    'images': ['static/description/banner.png'],
}
