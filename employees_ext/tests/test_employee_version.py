from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmployeeVersionCompatibility(TransactionCase):
    def test_iqama_marital_and_custom_code(self):
        employee = self.env['hr.employee'].create({
            'name': 'NAS HR Version Regression',
            'employee_code': 'NAS-HR-VERSION-REGRESSION',
            'identification_id': 'NAS-IQAMA-1',
            'marital': 'other',
            'gender': 'female',
            'employee_type': '3',
        })
        for name in ('identification_id', 'marital'):
            field = employee._fields[name]
            self.assertFalse(field.store)
            self.assertEqual(tuple(field.related), ('version_id', name))
        version = employee.version_id
        self.assertEqual(version.identification_id, 'NAS-IQAMA-1')
        self.assertEqual(version.marital, 'other')
        self.assertEqual(version.sex, 'female')
        employee.write({'identification_id': 'NAS-IQAMA-2', 'marital': 'married'})
        self.assertEqual(version.identification_id, 'NAS-IQAMA-2')
        self.assertEqual(version.marital, 'married')
        self.assertEqual(employee.employee_code, 'NAS-HR-VERSION-REGRESSION')
        self.assertEqual(employee.employee_type, '3')
        data = employee.read(['identification_id', 'marital', 'employee_code'])[0]
        self.assertEqual(data['identification_id'], 'NAS-IQAMA-2')
