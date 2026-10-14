"""Check contact layout with Odoo's real inheritance engine, without a DB."""
import argparse
import copy
from pathlib import Path
import sys

from lxml import etree

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--odoo-root', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.odoo_root))

from odoo.tools.template_inheritance import apply_inheritance_specs
from odoo.addons.base.models import ir_ui_view  # Registers hasclass XPath.

root = Path(__file__).resolve().parents[1]
base = etree.parse(str(args.odoo_root / 'odoo/addons/base/views/res_partner_views.xml'))
source = base.xpath("//record[@id='view_partner_form']/field[@name='arch']/form")[0]
custom = etree.parse(str(root / 'contacts_ext/views/contact_views.xml'))
specs = copy.deepcopy(custom.xpath("//record[@id='view_partner_form_custom_fields']/field[@name='arch']")[0])
specs.tag = 'data'
class InheritanceValidator:
    name = 'contact layout regression'
    xml_id = 'contacts_ext.view_partner_form_custom_fields'

    def _raise_view_error(self, message, node):
        raise ValueError(message)

# Applying inheritance alone does not execute the registry's selector rules.
# Run the same validation that rejected translated @title selectors on upgrade.
validator = InheritanceValidator()
ir_ui_view.IrUiView._valid_inheritance(validator, specs)
invalid = etree.fromstring(b'<data><xpath expr="//i[@title=\'Phone\']" position="replace"/></data>')
try:
    ir_ui_view.IrUiView._valid_inheritance(validator, invalid)
except ValueError as error:
    assert "'title'" in str(error)
else:
    raise AssertionError('Translated selector validation must reject @title')
view = apply_inheritance_specs(copy.deepcopy(source), specs)
left, right = view.xpath('./sheet/group/group')
for name in ('vat', 'customer_code', 'identification_number', 'country_code', 'job_title', 'working_place', 'gender'):
    assert left.xpath(f"./field[@name='{name}']"), f'{name} must remain in left column'
for name in ('function', 'phone', 'mobile', 'email', 'website', 'category_id', 'second_mobile'):
    assert len(right.xpath(f"./field[@name='{name}']")) == 1, f'{name} must appear once in right column'
assert len(view.xpath('./sheet/notebook/page[@name="subscription"]')) == 1
assert len(view.xpath('./sheet//field[@name="second_mobile"]')) == 1
assert not view.xpath('./sheet/div[hasclass("mb8")]//field[@name="phone" or @name="email"]')
print('PASS: contact columns, phone/mobile/email, single Mobile 2 and Subscription tab')

# Check the employee layout against native 19.0 markup too. Broad anchors to
# work_phone/department_id used to inject custom fields into header h5s/tabs.
employee_base = etree.parse(str(args.odoo_root / 'addons/hr/views/hr_employee_views.xml'))
source = employee_base.xpath("//record[@id='view_employee_form']/field[@name='arch']/form")[0]
employee_custom = etree.parse(str(root / 'employees_ext/views/employee_views.xml'))
specs = copy.deepcopy(employee_custom.xpath("//record[@id='view_employee_ext_form_own']/field[@name='arch']")[0])
specs.tag = 'data'
ir_ui_view.IrUiView._valid_inheritance(validator, specs)
employee_view = apply_inheritance_specs(copy.deepcopy(source), specs)
header_title = employee_view.xpath('./sheet//h2[@name="nas_employee_header_job_title"]/field[@name="job_title"]')
assert len(header_title) == 1, 'The existing Job Title must be visible below the employee name'
avatar = employee_view.xpath('./sheet/div/div[hasclass("o_employee_avatar")]')[0]
assert avatar.getparent()[-1] is avatar, 'Avatar must be the right-most header element'
assert avatar.xpath('./field[@name="image_1920"]'), 'Native avatar upload must remain'
assert employee_view.xpath('./sheet//div[hasclass("o_presence_status_pill_wrapper")]'), 'Native presence/chat controls must remain'
details = employee_view.xpath('./sheet/group[@name="nas_employee_details"]')[0]
left, right = details.xpath('./group')
for name in ('work_email', 'work_phone', 'employee_code', 'employee_section', 'customer_account',
             'project_code', 'job_number', 'mobile_phone', 'category_ids'):
    assert len(left.xpath(f"./field[@name='{name}']")) == 1, f'{name} must be labeled in left employee column'
for name in ('department_id', 'border_number', 'operating_unit_id', 'country_code', 'company_country_code',
             'arrival_date', 'employee_type', 'profession_id', 'identification_id', 'project_joining_date',
             'job_title', 'crm_id', 'user_name', 'job_id', 'parent_id', 'coach_id'):
    assert len(right.xpath(f"./field[@name='{name}']")) == 1, f'{name} must be in right employee column'
assert not employee_view.xpath('./sheet//h5/field[@name="work_phone" or @name="employee_code"]')
assert not employee_view.xpath('./sheet//h5/i[hasclass("fa-phone") or hasclass("fa-envelope") or hasclass("fa-mobile") or hasclass("fa-tags")]')
assert details.getparent().index(details) < details.getparent().index(employee_view.xpath('./sheet/notebook')[0])
assert employee_view.xpath('./sheet/notebook/page[@name="work_information"]//div[@id="o_employee_org_chart"]')
assert len(employee_view.xpath('./sheet//field[@name="employee_code"]')) == 1
pages = employee_view.xpath('./sheet/notebook/page')
assert [p.get('name') for p in pages[:3]] == ['resume', 'work_information', 'personal_information']
assert pages[1].get('string') == 'Work Information'
assert pages[2].get('string') == 'Private Information'
assert len(employee_view.xpath('./sheet/notebook/page[@name="hr_settings"]//group[@name="user"]/field[@name="employee_type"]')) == 1
assert not employee_view.xpath('./sheet/notebook/page[@name="payroll_information"]//field[@name="employee_type"]')
assert employee_view.xpath('./sheet/notebook/page[@name="hr_settings"]//group[@name="managers"]')
assert employee_view.xpath('./sheet/notebook/page[@name="payroll_information"]//field[@name="contract_type_id"]')
assert employee_view.xpath('./sheet/notebook/page[@name="payroll_information"]//field[@name="resource_calendar_id"]')
assert employee_view.xpath('./sheet/notebook/page[@name="personal_information"]//field[@name="bank_account_ids"]')
assert len(employee_view.xpath('./sheet/notebook/page[@name="personal_information"]//field[@name="identification_id"]')) == 1
assert len(employee_view.xpath('./sheet/notebook/page[@name="personal_information"]//field[@name="study_school"]')) == 1
assert len(employee_view.xpath('./sheet/notebook/page[@name="personal_information"]//field[@name="private_car_plate"]')) == 1
print('PASS: labeled employee details above tabs, original custom fields and native org-chart anchor')
print('PASS: existing Job Title below name and native upload photo on the right')
print('PASS: familiar tab navigation, sector in Settings, native contract/approver/bank controls retained')

# Enterprise Payroll applies before this custom view (priority 10 versus 16).
# Check that its native fields and contract widgets survive the layout change.
payroll_path = args.odoo_root / 'enterprise/hr_payroll/views/hr_employee_views.xml'
if payroll_path.is_file():
    native = copy.deepcopy(employee_base.xpath("//record[@id='view_employee_form']/field[@name='arch']/form")[0])
    payroll_specs = copy.deepcopy(etree.parse(str(payroll_path)).xpath(
        "//record[@id='payroll_hr_employee_view_form']/field[@name='arch']"
    )[0])
    payroll_specs.tag = 'data'
    ir_ui_view.IrUiView._valid_inheritance(validator, payroll_specs)
    native = apply_inheritance_specs(native, payroll_specs)
    custom_specs = copy.deepcopy(employee_custom.xpath(
        "//record[@id='view_employee_ext_form_own']/field[@name='arch']"
    )[0])
    custom_specs.tag = 'data'
    combined = apply_inheritance_specs(native, custom_specs)
    personal = combined.xpath('./sheet/notebook/page[@name="personal_information"]')[0]
    for name in ('legal_name', 'lang', 'disabled', 'is_non_resident', 'study_school', 'private_car_plate'):
        assert personal.xpath(f".//field[@name='{name}']"), f'Payroll/private field {name} must survive'
    payroll = combined.xpath('./sheet/notebook/page[@name="payroll_information"]')[0]
    for name in ('wage', 'wage_type', 'schedule_pay', 'registration_number', 'structure_type_id', 'resource_calendar_id'):
        assert payroll.xpath(f".//field[@name='{name}']"), f'Native payroll control {name} must survive'
    print('PASS: Enterprise Payroll inheritance, personal/payroll fields and contract controls retained')
