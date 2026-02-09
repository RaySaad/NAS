# Journal Voucher Excel Export

Export large journal entries to professionally formatted Excel files.

## Features

- **Smart Print Detection**: Automatically uses PDF for small entries (<1000 lines) and Excel for large entries
- **Professional Formatting**: Company branding, colors, borders, and frozen headers
- **Memory Efficient**: Handles 5000+ line entries without memory issues using chunk processing
- **Balance Validation**: Automatic balance check with visual indicators
- **Easy Navigation**: Frozen headers for easy scrolling through thousands of lines

## Installation

1. Install `xlsxwriter` Python library:
   ```bash
   pip install xlsxwriter
   ```

2. Copy this module to your Odoo addons directory

3. Update Apps List in Odoo

4. Install "Journal Voucher Excel Export" module

## Usage

### Option 1: Smart Print (Recommended)
1. Open any posted journal entry
2. Click **"Print Voucher"** button
3. System automatically chooses PDF or Excel based on entry size

### Option 2: Force Excel Export
1. Open any posted journal entry
2. Click **"Export to Excel"** button
3. Excel file downloads immediately

## Excel Output Includes

- Company name and branding
- Journal entry details (number, date, journal, reference)
- Complete line items with:
  - Account code and name
  - Partner
  - Employee
  - Label/description
  - Debit and Credit amounts
  - Analytic account
- Automatic totals with formulas
- Balance validation
- Professional color scheme

## Technical Details

- **Chunk Size**: 500 lines per batch for memory efficiency
- **Max Recommended**: Tested up to 10,000 lines
- **File Size**: ~1-2 MB for 5000 lines
- **Processing Time**: ~5-10 seconds for 5000 lines

## Support

For issues or feature requests, contact your system administrator.

## License

LGPL-3

## Author

Your Company
