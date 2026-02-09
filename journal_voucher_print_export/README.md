# Journal Voucher Print & Excel Export

Complete solution for journal entry printing and exporting with professional PDF and Excel output.

**Author:** Fakhraddin A. Sa'ad

## Features

### PDF Printing
- **Professional Design**: Beautiful voucher layout with company branding
- **Color-Coded Status**: Visual indicators for draft/posted/cancelled entries
- **Detailed Information**: Header details, line items, totals, and signatures
- **Balance Validation**: Shows balance status with checkmark or warning
- **Responsive Layout**: Clean, professional appearance suitable for printing
- **Works for All Sizes**: Handles both small and large entries

### Excel Export
- **Memory Efficient**: Handles 5000+ line entries without issues
- **Professional Formatting**: Company branding, colors, borders, frozen headers
- **Chunk Processing**: Processes large datasets in 500-line batches
- **Balance Validation**: Ensures entries are balanced before export
- **Draft Support**: Can export draft entries if balanced
- **Visual Warnings**: Red highlighting for non-posted entries
- **Odoo 18 Compatible**: Full support for analytic distribution
- **Safe Filename Handling**: Works with draft entries (no name yet)

### Smart Detection
- **Auto-Choose Format**: PDF for entries <1000 lines, Excel for larger
- **User-Friendly**: One-click solution for optimal output format
- **Performance Optimized**: Prevents PDF memory issues on large entries

## Installation

1. Install `xlsxwriter` Python library:
   ```bash
   pip3 install xlsxwriter --break-system-packages
   ```

2. Copy this module to your Odoo addons directory

3. Update Apps List in Odoo

4. Install "Journal Voucher Print & Excel Export" module

## Usage

### Three Print/Export Options:

#### Option 1: Print Voucher (PDF)
1. Open any journal entry (draft or posted)
2. Click **"Print Voucher"** button
3. Beautiful PDF downloads immediately
4. For large entries (>1000 lines), shows suggestion to use Excel

#### Option 2: Export to Excel
1. Open any journal entry (draft or posted)
2. Click **"Export to Excel"** button
3. System validates balance
4. Excel file downloads if validation passes
5. Perfect for entries with 1000+ lines
6. Draft entries export as "Journal_Voucher_Draft_[ID].xlsx"

#### Option 3: Smart Print (Recommended)
1. Open any journal entry
2. Click **"Smart Print"** button
3. System automatically chooses:
   - PDF for entries with ≤1000 lines
   - Excel for entries with >1000 lines
4. Best of both worlds!

## Balance Validation

Both PDF and Excel require balanced entries:

- **Tolerance**: 0.01 for rounding differences
- **Error Message**: Shows exact debit, credit, and difference
- **Helpful Tip**: Suggests posting draft entries to auto-balance

## Changelog

### Version 18.0.1.0.1
- **Fixed**: Draft entry filename error in Excel export
- **Improved**: Filename handling for entries without numbers
- Draft entries now export with format: `Journal_Voucher_Draft_{ID}.xlsx`

### Version 18.0.1.0.0
- Initial unified release
- Merged PDF printing and Excel export modules
- Added smart print auto-detection
- Balance validation for both formats
- Draft entry support
- Professional QWeb PDF template
- Memory-efficient Excel export
- Odoo 18 analytic distribution support

## Technical Details

- **PDF**: QWeb-based template with responsive design
- **Excel**: xlsxwriter with chunk processing
- **Chunk Size**: 500 lines per batch
- **Max Recommended**: Tested up to 10,000 lines
- **Excel File Size**: ~1-2 MB for 5000 lines
- **Processing Time**: ~5-10 seconds for 5000 lines
- **Odoo Version**: 18.0+
- **Balance Tolerance**: 0.01

## Support

For issues or feature requests, contact: Fakhraddin A. Sa'ad

## License

LGPL-3
