from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


PERIODS = [('3', '3 Months'), ('6', '6 Months'), ('9', '9 Months'), ('12', '12 Months')]
SERVICES = [('iqama', 'Iqama'), ('work_permit', 'Work Permit'),
            ('traffic', 'Traffic Violation'), ('other', 'Other Service')]


class ServiceMapping(models.Model):
    _name = 'saddad.service.mapping'
    _description = 'Saddad Service Period Mapping'
    _check_company_auto = True
    _rec_name = 'product_id'
    _order = 'company_id, service_type, period'

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    service_type = fields.Selection(SERVICES, required=True, default='work_permit')
    period = fields.Selection(PERIODS, required=True, default='3')
    product_id = fields.Many2one('product.product', required=True, check_company=True,
                                 domain="[('type', '=', 'service')]")
    currency_id = fields.Many2one(related='company_id.currency_id')
    cost = fields.Monetary(compute='_compute_cost', currency_field='currency_id')
    active = fields.Boolean(default=True)
    default_for_ptr = fields.Boolean(string='Default for PTR', default=False,
        help='Use this active mapping to create the initial PTR service line for this company.')

    _period_unique = models.Constraint('UNIQUE(company_id, service_type, period)',
                                       'A company can have only one mapping per service and period, including archived mappings.')
    _default_unique = models.UniqueIndex('(company_id) WHERE active AND default_for_ptr',
                                         'Only one active default PTR mapping is allowed per company.')

    @api.depends('product_id', 'product_id.standard_price', 'company_id')
    def _compute_cost(self):
        for rec in self:
            rec.cost = rec.product_id.with_company(rec.company_id).standard_price

    @api.constrains('product_id')
    def _check_product(self):
        if any(r.product_id.type != 'service' for r in self):
            raise ValidationError(_('Select a service product.'))


class ApprovalRule(models.Model):
    _name = 'saddad.approval.rule'
    _description = 'Saddad Approval Rule'
    _order = 'company_id, transition'

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one('res.company', index=True,
                                 help='Empty means the default rule for all companies.')
    transition = fields.Selection([('review', 'Review PTR'), ('confirm', 'Confirm PTR'),
                                   ('reset', 'Reset PTR to Draft')], required=True)
    group_id = fields.Many2one('res.groups', required=True, ondelete='restrict')
    notify_email = fields.Boolean(default=True)
    notify_activity = fields.Boolean(default=True)

    _company_transition_unique = models.Constraint('UNIQUE(company_id, transition)',
                                                    'Only one rule per company and transition is allowed.')
    _global_transition_unique = models.UniqueIndex('(transition) WHERE company_id IS NULL')

    @api.model
    def _for_transition(self, company, transition):
        return self.search([('company_id', '=', company.id), ('transition', '=', transition)], limit=1) or self.search([
            ('company_id', '=', False), ('transition', '=', transition)], limit=1)


class ResCompany(models.Model):
    _inherit = 'res.company'

    saddad_ptr_threshold = fields.Integer(string='PTR Expiry Threshold (Days)', default=30)
    saddad_mapping_ids = fields.One2many('saddad.service.mapping', 'company_id')
    saddad_ptr_period = fields.Selection(PERIODS, string='Default PTR Period', compute='_compute_ptr_default')
    saddad_ptr_product_id = fields.Many2one('product.product', string='Default PTR Product', compute='_compute_ptr_default')
    saddad_ptr_automation = fields.Boolean(string='Automatic PTR Creation', default=False,
                                          help='Enable after service products and approval recipients are configured.')

    @api.depends('saddad_mapping_ids.default_for_ptr', 'saddad_mapping_ids.active',
                 'saddad_mapping_ids.product_id', 'saddad_mapping_ids.period')
    def _compute_ptr_default(self):
        for company in self:
            mapping = company.saddad_mapping_ids.filtered(lambda m: m.active and m.default_for_ptr)[:1]
            company.saddad_ptr_period = mapping.period or False
            company.saddad_ptr_product_id = mapping.product_id

    @api.constrains('saddad_ptr_threshold')
    def _check_saddad_settings(self):
        for rec in self:
            if rec.saddad_ptr_threshold < 0:
                raise ValidationError(_('PTR expiry threshold cannot be negative.'))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    saddad_ptr_threshold = fields.Integer(related='company_id.saddad_ptr_threshold', readonly=False)
    saddad_ptr_period = fields.Selection(related='company_id.saddad_ptr_period', readonly=True)
    saddad_ptr_product_id = fields.Many2one(related='company_id.saddad_ptr_product_id', readonly=True)
    saddad_ptr_automation = fields.Boolean(related='company_id.saddad_ptr_automation', readonly=False)


class SaddadSettings(models.TransientModel):
    _name = 'saddad.settings'
    _description = 'Saddad Company Settings'

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    threshold = fields.Integer(string='PTR Expiry Threshold (Days)', required=True, default=lambda s: s.env.company.saddad_ptr_threshold)
    automation = fields.Boolean(string='Automatic PTR Creation', default=lambda s: s.env.company.saddad_ptr_automation)

    @api.onchange('company_id')
    def _onchange_company(self):
        self.threshold = self.company_id.saddad_ptr_threshold
        self.automation = self.company_id.saddad_ptr_automation

    def action_save(self):
        from odoo.exceptions import AccessError
        self.ensure_one()
        if not self.env.user.has_group('Saddad.group_manager') or self.company_id not in self.env.companies:
            raise AccessError(_('Only a Saddad Admin can configure an allowed company.'))
        # Narrow escalation: Saddad Admin is not granted general res.company write access.
        self.company_id.sudo().write({'saddad_ptr_threshold': self.threshold,
                                     'saddad_ptr_automation': self.automation})
        return {'type': 'ir.actions.act_window_close'}
