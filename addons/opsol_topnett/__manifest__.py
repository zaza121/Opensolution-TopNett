# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo customisations for TopNett',
    'author': 'Opensolution',
    'category': 'Human Resources',
    'version': '1.0.0',
    'description': """""",
    'summary': '',
    'sequence': 11,
    'website': 'https://www.opensolution.mc',
    'depends': ['hr', 'hr_payroll'],
    'license': 'LGPL-3',
    'data': [
        # data
        'data/input_data.xml',
        # security
        'security/ir.model.access.csv',
        # views
        # 'views/menus.xml',
        # 'views/crm_lead_views.xml',
        # 'views/sale_order_views.xml',
        'views/hr_employee_views.xml',
        'views/imp_salaire_line_views.xml',
        # 'views/res_partner_bank_views.xml',
        # 'views/account_move_views.xml',
        # 'views/mail_templates_email_layouts.xml',
        # 'views/account_invoice_send_views.xml',
        # 'views/templates.xml',
        # wizards
        # reports
        # 'reports/situation_invoice_report.xml',
        # 'reports/account_move_report.xml',
        # 'reports/sale_order_report.xml',
    ],
    'images': ['static/description/banner.png'],
    'assets': {
        # 'web.report_assets_common': ['opsol_sammy/static/src/scss/_fonts.scss'],
        # 'web.assets_backend': ['opsol_sammy/static/src/scss/_fonts.scss'],
    },
}
