"""Parse reviewed Qiwa invoice layouts without treating PDF status as a payment action."""
import re
import unicodedata
from datetime import datetime

DATE = r'\d{2}/\d{2}/\d{4}'
MONEY = r'\d{1,3}(?:,\d{3})*\.\d{2}'


def _date(value):
    try:
        return datetime.strptime(value, '%d/%m/%Y').date()
    except ValueError:
        return False


def _compact(value):
    return re.sub(r'\s+', '', value).casefold()


def parse_qiwa_text(text):
    text = unicodedata.normalize('NFKC', text).replace('\x00', '')
    text = text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    # Browser timestamps may be glued to a reference, amount, or four-digit-year date.
    # Require the full timestamp plus the Qiwa page title: never trim arbitrary digits.
    text = re.sub(r'\d{1,2}/\d{1,2}/\d{2},\s*\d{1,2}:\d{2}\s*[AP]M[^\n]*(?:قوى|Qiwa)[^\n]*', '\n', text, flags=re.I)
    text = re.sub(r'^\s*https://working-permits\.qiwa\.sa[^\n]*', '', text, flags=re.M)
    result = {'text': text, 'employees': [], 'reference': False, 'invoice_number': False,
              'issue_date': False, 'due_date': False, 'period': False,
              'payment_status': 'unknown', 'payment_date': False, 'export_date': False,
              'document_total': False}
    identities = list(dict.fromkeys(re.findall(r'(?<!\d)[12]\d{9}(?!\d)', text)))
    for identity in identities:
        # The same table can extract in visual or PDF drawing order.
        patterns = [
            re.escape(identity) + rf'[^\d]{{0,60}}(3|6|9|12)\s*({DATE})\s*({MONEY})(?!\d)',
            re.escape(identity) + rf'\s*({MONEY})\s*({DATE})\s*(3|6|9|12)(?!\d)',
        ]
        candidates = set()
        for index, pattern in enumerate(patterns):
            for a, b, c in re.findall(pattern, text):
                period, validity, amount = (a, b, c) if index == 0 else (c, b, a)
                date = _date(validity)
                if date:
                    candidates.add((period, date, float(amount.replace(',', ''))))
        value = {'identity': identity}
        if len(candidates) == 1:
            period, validity, amount = candidates.pop()
            value.update(period=period, permit_valid_until=validity, amount=amount)
        result['employees'].append(value)

    invoices = list(re.finditer(r'(?<!\d)\d{19}(?!\d)', text))
    references = list(re.finditer(r'(?<!\d)\d{15}(?!\d)', text))
    pairs = {(i.group(), r.group()) for i in invoices for r in references if i.group().startswith(r.group())}
    if len({i.group() for i in invoices}) == 1:
        result['invoice_number'] = invoices[0].group()
        # Issue date belongs to the invoice header, never to the export footer.
        following = text[invoices[0].end():invoices[0].end()+100]
        following = re.split(r'(?<!\d)[12]\d{9}(?!\d)', following, maxsplit=1)[0]
        dates = re.findall(DATE, following)
        if len(dates) == 1:
            result['issue_date'] = _date(dates[0])
    if len(pairs) == 1:
        invoice, reference = pairs.pop()
        result['invoice_number'], result['reference'] = invoice, reference
        ref_matches = [r for r in references if r.group() == reference]
        # Read status only in the payment summary, not from unrelated instructions.
        start = ref_matches[-1].start()
        summary = text[max(0, start-250):start]
        compact = _compact(summary)
        if re.search(r'\bunpaid\b|pending\s+payment', summary, re.I) or 'بانتظار' in compact or ('حاله' in compact and 'ارط' in compact):
            result['payment_status'] = 'unpaid'
        elif re.search(r'\bpaid\b', summary, re.I) or any(token in compact for token in ('مدفوع', 'مدوع', 'وعمد')):
            result['payment_status'] = 'paid'
        # Damaged font encoding in the supplied layouts preserves these export-label
        # fragments. Keep export dates separate even when they differ from issue dates.
        tail = text[ref_matches[-1].end():]
        transaction_dates = []
        export_dates = []
        for line in tail.splitlines():
            found = [_date(d) for d in re.findall(DATE, line)]
            found = [d for d in found if d]
            label = _compact(line)
            if any(token in label for token in ('تاريخالتصدير', 'رصدال', 'exportdate')):
                export_dates.extend(found)
            else:
                transaction_dates.extend(found)
        if len(set(export_dates)) == 1:
            result['export_date'] = export_dates[0]
        if len(set(transaction_dates)) == 1:
            if result['payment_status'] == 'paid':
                result['payment_date'] = transaction_dates[0]
            elif result['payment_status'] == 'unpaid':
                result['due_date'] = transaction_dates[0]
        # Accept a total only from an explicitly labelled total line.
        totals = []
        for line in text[:start].splitlines():
            if re.search(r'total', line, re.I) or any(token in _compact(line) for token in ('إجمالي', 'اجمالي', 'مالی')):
                amounts = re.findall(MONEY, line)
                if len(amounts) == 1:
                    totals.append(float(amounts[0].replace(',', '')))
        if len(set(totals)) == 1:
            result['document_total'] = totals[0]
    periods = {row.get('period') for row in result['employees']}
    if len(periods) == 1 and None not in periods:
        result['period'] = periods.pop()
    return result
