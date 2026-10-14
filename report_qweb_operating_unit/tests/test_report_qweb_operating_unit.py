from unittest.mock import MagicMock

from odoo.tools import is_html_empty
from odoo.tests import tagged

from odoo.addons.operating_unit.tests.common import OperatingUnitCommon


@tagged("post_install", "-at_install")
class TestReportQwebOperatingUnit(OperatingUnitCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.report_header = "Company report header"
        cls.ou1.report_header = "OU report header"
        cls.mock_user = MagicMock(wraps=cls.env.user)
        cls.mock_user.__contains__ = lambda self, other: True
        cls.mock_user.operating_unit_id = cls.ou1

    def test_rendering(self):
        for layout in ("standard", "striped", "bold", "boxed", "folder", "wave", "bubble"):
            xmlid = f"web.external_layout_{layout}"
            render_context = dict(
                company=self.env.company,
                o=self.env.user,
                is_html_empty=is_html_empty,
            )
            html = (
                self.env["ir.actions.report"]
                ._render_template(
                    xmlid,
                    render_context,
                )
                .decode("utf8")
            )
            self.assertIn(self.env.company.report_header, html)
            html = (
                self.env["ir.actions.report"]
                ._render_template(
                    xmlid,
                    dict(render_context, o=self.mock_user),
                )
                .decode("utf8")
            )
            self.assertIn(self.ou1.report_header, html)

    def test_bubble_ou_header_without_company_header(self):
        self.env.company.report_header = False
        html = self.env["ir.actions.report"]._render_template(
            "web.external_layout_bubble",
            dict(company=self.env.company, o=self.mock_user, is_html_empty=is_html_empty),
        ).decode("utf8")
        self.assertIn(self.ou1.report_header, html)
