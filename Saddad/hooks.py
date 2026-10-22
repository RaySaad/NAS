def pre_init_hook(env):
    """Reject a renamed addon before loading case-sensitive external IDs."""
    if __package__.rsplit('.', 1)[-1] != 'Saddad':
        from odoo.exceptions import UserError
        raise UserError(
            "The addon directory must be named 'Saddad' (capital S), not 'saddad'. "
            "Stop Odoo, rename the folder via an intermediate name on Windows, "
            "restart Odoo, update the Apps list, and install the module with "
            "technical name 'Saddad'. Do not retry the lowercase app entry."
        )


def post_init_hook(env):
    """Initialize eight renewal mappings for the installing main company only."""
    import json
    from odoo.tools import file_open
    with file_open('Saddad/data/product_catalog.json', 'r') as source:
        catalog = json.load(source)
    company = env.ref('base.main_company')
    for row in catalog:
        env.ref(row['xmlid']).with_company(company).standard_price = row['cost']
    seed_mappings(env)


def seed_mappings(env):
    company = env.ref('base.main_company')
    mappings = env['saddad.service.mapping'].with_company(company)
    for service, start in [('iqama', 15), ('work_permit', 26)]:
        for offset, period in enumerate(['3', '6', '9', '12']):
            if mappings.with_context(active_test=False).search_count([
                    ('company_id', '=', company.id), ('service_type', '=', service), ('period', '=', period)]):
                continue
            mappings.create({'company_id': company.id, 'service_type': service, 'period': period,
                'product_id': env.ref(f'Saddad.product_muqeem_{start+offset:03d}').id,
                'default_for_ptr': service == 'work_permit' and period == '3' and not mappings.search_count([
                    ('company_id', '=', company.id), ('default_for_ptr', '=', True)])})
