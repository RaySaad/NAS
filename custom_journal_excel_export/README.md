# Journal Voucher Excel Export

Export large journal entries to professionally formatted Excel files.

**Author:** Fakhraddin A. Sa'ad

## Features

- **Smart Print Detection**: Automatically uses PDF for small entries (<1000 lines) and Excel for large entries
- **Professional Formatting**: Company branding, colors, borders, and frozen headers
- **Memory Efficient**: Handles 5000+ line entries without memory issues using chunk processing
- **Balance Validation**: Automatic balance check with visual indicators
- **Easy Navigation**: Frozen headers for easy scrolling through thousands of lines
- **Odoo 18 Compatible**: Full support for new analytic distribution field structure

## Installation

1. Install `xlsxwriter` Python library:
   ```bash
   pip3 install xlsxwriter --break-system-packages
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
  - Debit and Credit amounts (in SR)
  - Analytic account(s)
- Automatic totals with formulas
- Balance validation (Debit - Credit = 0.00)
- Professional color scheme

## Technical Details

- **Chunk Size**: 500 lines per batch for memory efficiency
- **Max Recommended**: Tested up to 10,000 lines
- **File Size**: ~1-2 MB for 5000 lines
- **Processing Time**: ~5-10 seconds for 5000 lines
- **Odoo Version**: 18.0+

## Changelog

### Version 18.0.1.0.1
- Fixed Odoo 18 compatibility issue with analytic_distribution field
- Updated to handle multiple analytic accounts per line
- Improved error handling for analytic processing
- Updated author information

### Version 18.0.1.0.0
- Initial release
- Smart print detection
- Professional Excel formatting
- Chunk processing for large datasets

## Support

For issues or feature requests, contact: Fakhraddin A. Sa'ad

## License

LGPL-3
