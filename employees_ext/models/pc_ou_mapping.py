from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PcOuMapping(models.Model):
    _name = "pc.ou.mapping"
    _description = "Project Code to Operating Unit Mapping"

    project_code = fields.Char(
        string="Project Code",
        required=True
    )
    operating_unit_id = fields.Many2one(
        comodel_name="operating.unit",
        string="Operating Unit",
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='operating_unit_id.company_id', store=True, readonly=True,
    )

    _project_code_unique = models.Constraint(
        'unique(project_code)',
        'A mapping for this Project Code already exists!',
    )
    
    def unlink(self):
        if any(mapping.project_code == 'DEFAULT' for mapping in self):
            raise ValidationError(_('You cannot delete the DEFAULT mapping, you can only edit it!'))
        return super().unlink()
