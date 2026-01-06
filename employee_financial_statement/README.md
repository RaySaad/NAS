# Employee Financial Statement Module for Odoo 18

## Overview
This module provides a consolidated financial statement report for employees by pulling all journal entry lines where the employee is tagged.

## Features

### Flexible Employee Linking
- **Partner-based**: Links via `partner_id` on journal entry lines (using employee's private address or user's partner)
- **Employee Field**: Links via custom `employee_id` field on journal entry lines
- **Both Methods**: Combines both approaches to capture all related entries

### Output Options
1. **Screen List View**: Interactive view with export capability and optional grouping by account
2. **PDF Report**: Professional report with company branding, logo, and complete formatting
3. **Excel Export**: Full spreadsheet with formatting, headers, and summary totals

### Report Columns
- Date
- JV Reference
- Journal
- Account
- Description
- Debit
- Credit
- Running Balance

### Additional Features
- Date range filtering
- Optional grouping by account
- Running balance calculation
- Summary totals (Total Debit, Total Credit, Net Balance)
- Currency support

## Installation

1. Copy the `employee_financial_statement` folder to your Odoo addons directory
2. Update the app list: Settings → Apps → Update Apps List
3. Search for "Employee Financial Statement" and install

## Dependencies
- `account` (Accounting)
- `hr` (Human Resources)
- `xlsxwriter` (for Excel export - install via pip if not present)

## Usage

### Accessing the Report
Navigate to either:
- **Accounting → Reporting → Employee Statement**
- **HR → Reporting → Employee Financial Statement**

### Generating a Statement
1. Select the employee
2. Choose the linking method based on how your project tags employees:
   - **Partner Based**: If you assign employee's partner to JV lines
   - **Employee Field**: If you use a custom `employee_id` field
   - **Both Methods**: To capture entries from both approaches
3. Set date range (optional)
4. Check "Group by Account" if you want account-wise grouping
5. Click **Generate Statement**

### Exporting
From the results screen:
- **Open Full View**: Opens statement lines in a full list view with native export options
- **Print PDF**: Generates a professional PDF with company branding
- **Export Excel**: Downloads an Excel file with full formatting

## Technical Notes

### Models Created
- `employee.statement.wizard`: Main wizard for generating statements
- `employee.statement.line`: Transient model for storing statement lines

### Model Extended
- `account.move.line`: Adds `employee_id` field for employee-based linking

### Security
- Access granted to Accounting Users and HR Users
- Both groups can generate and view reports

## Customization

### Adding More Columns
Edit `wizard/employee_statement_wizard.py`:
1. Add field to `EmployeeStatementLine` model
2. Update `action_generate_statement()` to populate the field
3. Add field to views in `wizard/employee_statement_wizard_views.xml`
4. Update PDF template in `report/employee_statement_template.xml`
5. Update Excel export in `action_export_excel()` method

### Changing PDF Styling
Edit `report/employee_statement_template.xml` to modify:
- Colors and fonts
- Table layout
- Header/footer content
- Summary box styling

## Support
For issues or feature requests, contact your Odoo administrator or development team.

## License
LGPL-3
