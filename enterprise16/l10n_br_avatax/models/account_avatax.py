# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime, timedelta
from json import dumps
from pprint import pformat

from odoo import models, fields, _, registry, api, SUPERUSER_ID
from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.exceptions import UserError, ValidationError, RedirectWarning
from odoo.tools import float_round, DEFAULT_SERVER_DATETIME_FORMAT, json_float_round

logger = logging.getLogger(__name__)

IAP_SERVICE_NAME = 'l10n_br_avatax_proxy'
DEFAULT_IAP_ENDPOINT = 'https://l10n-br-avatax.api.odoo.com'
DEFAULT_IAP_TEST_ENDPOINT = 'https://l10n-br-avatax.test.odoo.com'
ICP_LOG_NAME = 'l10n_br_avatax.log.end.date'
AVATAX_PRECISION_DIGITS = 2  # defined by API


class L10nBrAccountAvatax(models.AbstractModel):
    _name = 'l10n_br.account.avatax'
    _description = 'Mixin to manage taxes with Avatax Brazil on business documents'

    is_l10n_br_avatax = fields.Boolean(
        compute='_compute_is_l10n_br_avatax',
        help='Technical field that determines if this record will go through Avatax Brazil.'
    )

    @api.depends('country_code', 'fiscal_position_id')
    def _compute_is_l10n_br_avatax(self):
        for record in self:
            record.is_l10n_br_avatax = record.country_code == 'BR' and record.fiscal_position_id.l10n_br_is_avatax

    def _l10n_br_avatax_log(self):
        """Start logging all requests done to Avatax, for 30 minutes."""
        self.env['ir.config_parameter'].set_param(
            ICP_LOG_NAME,
            (fields.Datetime.now() + timedelta(minutes=30)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        )
        return True

    def _l10n_br_get_date_avatax(self):
        """ Returns the transaction date for this record. """
        raise NotImplementedError()

    def _l10n_br_get_avatax_lines(self):
        """ Returns line dicts for this record created with _l10n_br_build_avatax_line(). """
        raise NotImplementedError()

    def _l10n_br_line_model_name(self):
        return self._name + '.line'

    def _l10n_br_avatax_handle_response(self, response, title):
        if response.get('error'):
            logger.warning(pformat(response), stack_info=True)

            inner_errors = []
            for error in response['error'].get('innerError', []):
                # Useful inner errors are line-specific. Ones that aren't are typically not useful for the user.
                if 'lineCode' not in error:
                    continue

                product_name = self.env[self._l10n_br_line_model_name()].browse(error['lineCode']).product_id.display_name

                inner_errors.append(_('What:'))
                inner_errors.append('- %s: %s' % (product_name, error['message']))

                where = error.get('where', {})
                if where:
                    inner_errors.append(_('Where:'))
                for where_key, where_value in sorted(where.items()):
                    if where_key == 'date':
                        continue
                    inner_errors.append('- %s: %s' % (where_key, where_value))

            return '%s\n%s\n%s' % (title, response['error']['message'], '\n'.join(inner_errors))

    def _l10n_br_avatax_validate_lines(self, lines):
        """ Avoids doing requests to Avatax that are guaranteed to fail. """
        errors = []
        for line in lines:
            product = line['tempProduct']
            if not product:
                errors.append(_('- A product is required on each line when using Avatax.'))
            elif product.detailed_type == 'service':
                errors.append(_('- Avatax only supports consumable products. %s is a service product.', product.display_name))
            elif not product.l10n_br_ncm_code_id:
                errors.append(_('- Please configure a Mercosul NCM Code on %s.', product.display_name))
            elif line['lineAmount'] < 0:
                errors.append(_("- Avatax Brazil doesn't support negative lines."))

        if errors:
            raise ValidationError('\n'.join(errors))

    def _l10n_br_build_avatax_line(self, product, total, discount, line_id):
        """ Prepares the line data for the /calculations API call. temp* values are here to help with post-processing
        and will be removed before sending by _remove_temp_values_lines.

        :param product.product product: product on the line
        :param float total: the amount on the line without taxes or discount
        :param float discount: the discount amount on the line
        :param int line_id: the database ID of the line record, this is used to uniquely identify it in Avatax
        :return dict: the basis for the 'lines' value in the /calculations API call
        """
        return {
            'lineCode': line_id,
            'operationType': 'standardSales',
            'useType': product.l10n_br_use_type,
            'otherCostAmount': 0,
            'freightAmount': 0,
            'insuranceAmount': 0,
            'lineTaxedDiscount': discount,
            'lineAmount': total,
            'itemDescriptor': {
                'cest': product.l10n_br_cest_code or '',
                'hsCode': product.l10n_br_ncm_code_id.code,
                'source': product.l10n_br_source_origin or '',
                'productType': product.l10n_br_sped_type or '',
            },
            'tempTransportCostType': product.l10n_br_transport_cost_type,
            'tempProduct': product,
        }

    def _l10n_br_distribute_transport_cost_over_lines(self, lines, transport_cost_type):
        """ Avatax requires transport costs to be specified per line. This distributes transport costs (indicated by
        their product's l10n_br_transport_cost_type) over the lines in proportion to their subtotals. """
        type_to_api_field = {
            'freight': 'freightAmount',
            'insurance': 'insuranceAmount',
            'other': 'otherCostAmount',
        }
        api_field = type_to_api_field[transport_cost_type]

        transport_lines = [line for line in lines if line['tempTransportCostType'] == transport_cost_type]
        regular_lines = [line for line in lines if not line['tempTransportCostType']]
        total = sum(line['lineAmount'] for line in regular_lines)

        if not regular_lines:
            raise UserError(_('Avatax requires at least one non-transport line.'))

        for transport_line in transport_lines:
            transport_net = transport_line['lineAmount'] - transport_line['lineTaxedDiscount']
            remaining = transport_net
            for line in regular_lines[:-1]:
                current_cost = float_round(
                    transport_net * (line['lineAmount'] / total),
                    precision_digits=AVATAX_PRECISION_DIGITS
                )
                remaining -= current_cost
                line[api_field] += current_cost

            # put remainder on last line to avoid rounding issues
            regular_lines[-1][api_field] += remaining

        return [line for line in lines if line['tempTransportCostType'] != transport_cost_type]

    def _l10n_br_remove_temp_values_lines(self, lines):
        for line in lines:
            del line['tempTransportCostType']
            del line['tempProduct']

    def _l10n_br_repr_amounts(self, lines):
        """ Ensures all amount fields have the right amount of decimals before sending it to the API. """
        for line in lines:
            for amount_field in ('lineAmount', 'freightAmount', 'insuranceAmount', 'otherCostAmount'):
                line[amount_field] = json_float_round(line[amount_field], AVATAX_PRECISION_DIGITS)

    def _l10n_br_call_avatax_taxes(self):
        """Query Avatax with all the transactions linked to `self`.

        :return (dict<Model, dict>): a mapping between document records and the response from Avatax
        """
        if not self:
            return {}

        company_sudo = self.company_id.sudo()
        api_id, api_key = company_sudo.l10n_br_avatax_api_identifier, company_sudo.l10n_br_avatax_api_key
        if not api_id or not api_key:
            raise RedirectWarning(
                _('Please create an Avatax account'),
                self.env.ref('base_setup.action_general_configuration').id,
                _('Go to the configuration panel'),
            )

        transactions = {record: record._l10n_br_get_calculate_payload() for record in self}
        return {
            record: record._l10n_br_iap_calculate_tax(transaction)
            for record, transaction in transactions.items()
        }

    def _l10n_br_get_calculate_payload(self):
        """ Returns the full payload containing one record to be used in a /transactions API call. """
        self.ensure_one()
        transaction_date = self._l10n_br_get_date_avatax()
        partner = self.partner_id
        company = self.company_id.partner_id

        lines = self._l10n_br_distribute_transport_cost_over_lines(self._l10n_br_get_avatax_lines(), 'freight')
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'insurance')
        lines = self._l10n_br_distribute_transport_cost_over_lines(lines, 'other')

        self._l10n_br_avatax_validate_lines(lines)
        self._l10n_br_remove_temp_values_lines(lines)
        self._l10n_br_repr_amounts(lines)

        if partner.country_code not in ('BR', False):
            customer_type = 'foreign'
        elif partner.is_company:
            customer_type = 'business'
        else:
            customer_type = 'individual'

        simplifiedTaxesSettings = {}
        if company.l10n_br_tax_regime == 'simplified':
            simplifiedTaxesSettings = {'pCredSN': self.company_id.l10n_br_icms_rate}

        return {
            'header': {
                'transactionDate': (transaction_date or fields.Date.today()).isoformat(),
                'amountCalcType': 'gross',
                'documentCode': '%s_%s' % (self._name, self.id),
                'messageType': 'goods',
                'companyLocation': '',
                'locations': {
                    'entity': {  # the customer
                        'type': customer_type,
                        'activitySector': {
                            'code': partner.l10n_br_activity_sector,
                        },
                        'taxesSettings': {
                            'icmsTaxPayer': partner.l10n_br_taxpayer == "icms",
                        },
                        'taxRegime': partner.l10n_br_tax_regime,
                        'address': {
                            'zipcode': partner.zip,
                        },
                        'federalTaxId': partner.vat if partner.vat else partner.l10n_br_cpf_code,
                        'suframa': partner.l10n_br_isuf_code or '',
                    },
                    'establishment': {  # the seller
                        'type': 'business',
                        'activitySector': {
                            'code': company.l10n_br_activity_sector,
                        },
                        'taxesSettings': {
                            'icmsTaxPayer': company.l10n_br_taxpayer == "icms",
                            **simplifiedTaxesSettings,
                        },
                        'taxRegime': company.l10n_br_tax_regime,
                        'address': {
                            'zipcode': company.zip,
                        },
                        'federalTaxId': company.vat if company.vat else company.l10n_br_cpf_code,
                        'suframa': company.l10n_br_isuf_code or '',
                    },
                },
            },
            'lines': lines,
        }

    def _l10n_br_map_avatax(self):
        """ Link Avatax response to Odoo's models.

        :return (tuple(detail, summary)):
            detail (dict<Model, Model<account.tax>>): mapping between the document lines and its
                related taxes.
            summary (dict<Model, dict<Model<account.tax>, float>>): mapping between each tax and
                the total computed amount, for each document.
        """
        self.ensure_one()

        if self.currency_id.name != 'BRL':
            raise UserError(_('%s has to use Brazilian Real to calculate taxes with Avatax.', self.display_name))

        def find_or_create_tax(doc, tax_name, price_include):
            def repartition_line(repartition_type):
                return (0, 0, {
                    'repartition_type': repartition_type,
                    'company_id': doc.company_id.id,
                })

            key = (tax_name, price_include, doc.company_id)
            if key not in tax_cache:
                tax_cache[key] = self.env['account.tax'].with_context(active_test=False).search([
                    ('l10n_br_avatax_code', '=', tax_name),
                    ('price_include', '=', price_include),
                    ('company_id', '=', doc.company_id.id)
                ])

                # all these taxes are archived by default, unarchive when used
                tax_cache[key].active = True

                if not tax_cache[key]:  # fall back on creating a bare-bones tax
                    tax_cache[key] = self.env['account.tax'].sudo().with_company(doc.company_id).create({
                        'name': tax_name,
                        'l10n_br_avatax_code': tax_name,
                        'amount': 1,  # leaving it at the default 0 causes accounting to ignore these
                        'amount_type': 'percent',
                        'price_include': price_include,
                        'tax_scope': 'consu',  # l10n_br_avatax only supports goods
                        'refund_repartition_line_ids': [
                            repartition_line('base'),
                            repartition_line('tax'),
                        ],
                        'invoice_repartition_line_ids': [
                            repartition_line('base'),
                            repartition_line('tax'),
                        ],
                    })

            return tax_cache[key]
        tax_cache = {}

        query_results = self._l10n_br_call_avatax_taxes()
        details, summary = {}, {}
        errors = []
        for document, query_result in query_results.items():
            error = self._l10n_br_avatax_handle_response(query_result, _(
                'Odoo could not fetch the taxes related to %(document)s.',
                document=document.display_name,
            ))
            if error:
                errors.append(error)
        if errors:
            raise UserError('\n\n'.join(errors))

        for document, query_result in query_results.items():
            subtracted_tax_types = set()
            tax_type_to_price_include = {}
            for line_result in query_result['lines']:
                record_id = line_result['lineCode']
                record = self.env[self._l10n_br_line_model_name()].browse(int(record_id))
                details[record] = {}
                details[record]['total'] = line_result['lineNetFigure']
                details[record]['tax_amount'] = 0
                details[record]['tax_ids'] = self.env['account.tax']
                for detail in line_result['taxDetails']:
                    if detail['taxImpact']['impactOnNetAmount'] != 'Informative':
                        tax_amount = detail['tax']
                        if detail['taxImpact']['impactOnNetAmount'] == 'Subtracted':
                            tax_amount = -tax_amount
                            subtracted_tax_types.add(detail['taxType'])

                        price_include = detail['taxImpact']['impactOnNetAmount'] == 'Included'

                        # In the unlikely event there is an included and excluded tax with the same tax type we take
                        # whichever comes first. The tax computation will still be correct and the taxByType summary
                        # later will group them together.
                        tax_type_to_price_include.setdefault(detail['taxType'], price_include)
                        tax = find_or_create_tax(document, detail['taxType'], price_include)

                        details[record]['tax_amount'] += tax_amount
                        details[record]['tax_ids'] += tax

            summary[document] = {}
            for tax_type, type_details in query_result['summary']['taxByType'].items():
                tax = find_or_create_tax(document, tax_type, tax_type_to_price_include.get(tax_type, False))

                amount = type_details['tax']
                if tax_type in subtracted_tax_types:
                    amount = -amount

                summary[document][tax] = amount

        details = {record: taxes for record, taxes in details.items() if taxes['tax_ids']}

        return details, summary

    def _l10n_br_log(self, message):
        """ Log when the ICP's value is in the future. """
        log_end_date = self.env['ir.config_parameter'].sudo().get_param(
            ICP_LOG_NAME, ''
        )
        try:
            log_end_date = datetime.strptime(log_end_date, DEFAULT_SERVER_DATETIME_FORMAT)
            need_log = fields.Datetime.now() < log_end_date
        except ValueError:
            need_log = False
        if need_log:
            # This creates a new cursor to make sure the log is committed even when an
            # exception is thrown later in this request.
            self.env.flush_all()
            dbname = self._cr.dbname
            with registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['ir.logging'].create({
                    'name': 'Avatax Brazil',
                    'type': 'server',
                    'level': 'INFO',
                    'dbname': dbname,
                    'message': message,
                    'func': '',
                    'path': '',
                    'line': '',
                })

    # IAP related methods
    def _l10n_br_iap_request(self, route, json=None, company=None):
        company = company or self.company_id
        avatax_api_id, avatax_api_key = company.sudo().l10n_br_avatax_api_identifier, company.sudo().l10n_br_avatax_api_key

        default_endpoint = DEFAULT_IAP_ENDPOINT if company.l10n_br_avalara_environment == 'production' else DEFAULT_IAP_TEST_ENDPOINT
        iap_endpoint = self.env['ir.config_parameter'].sudo().get_param('l10n_br_avatax_iap.endpoint', default_endpoint)
        environment = company.l10n_br_avalara_environment
        url = f'{iap_endpoint}/api/l10n_br_avatax/1/{route}'

        params = {
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            'account_token': self.env['iap.account'].get(IAP_SERVICE_NAME).account_token,
            'avatax': {
                'is_production': environment and environment == 'production',
                'json': json or {},
            }
        }

        if avatax_api_id:
            params['api_id'] = avatax_api_id
            params['api_secret'] = avatax_api_key

        start = str(datetime.utcnow())
        response = iap_jsonrpc(url, params=params, timeout=60)  # longer timeout because create_account can take some time
        end = str(datetime.utcnow())

        # Avatax support requested that requests and responses be provided in JSON, so they can easily load them in their
        # internal tools for troubleshooting.
        self._l10n_br_log(
            f"start={start}\n"
            f"end={end}\n"
            f"args={pformat(url)}\n"
            f"request={dumps(json, indent=2)}\n"
            f"response={dumps(response, indent=2)}"
        )

        return response

    def _l10n_br_iap_ping(self, company):
        # This takes company because this function is called directly from res.config.settings instead of a sale.order or account.move
        return self._l10n_br_iap_request('ping', company=company)

    def _l10n_br_iap_create_account(self, account_data, company):
        # This takes company because this function is called directly from res.config.settings instead of a sale.order or account.move
        return self._l10n_br_iap_request('create_account', account_data, company=company)

    def _l10n_br_iap_calculate_tax(self, transaction):
        return self._l10n_br_iap_request('calculate_tax', transaction)
