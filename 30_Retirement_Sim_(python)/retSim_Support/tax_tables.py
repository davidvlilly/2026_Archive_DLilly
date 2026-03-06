"""
Tax calculation functions and IRS tables.

Pure functions with no side effects — used by comp_tax_liability and account components.
Federal and CA brackets are 2024 base, inflation-adjusted at call time.
Supports MFJ (Married Filing Jointly) and Single filing statuses.
"""


def get_life_expectancy(age):
    """IRS Uniform Lifetime Table — approximate remaining years."""
    table = {
        65: 21.0, 66: 20.2, 67: 19.4, 68: 18.6, 69: 17.8,
        70: 17.0, 71: 16.3, 72: 15.5, 73: 14.8, 74: 14.1,
        75: 13.4, 76: 12.7, 77: 12.1, 78: 11.4, 79: 10.8,
        80: 10.2, 81: 9.7, 82: 9.1, 83: 8.6, 84: 8.1,
        85: 7.6, 86: 7.1, 87: 6.7, 88: 6.3, 89: 5.9,
        90: 5.5, 91: 5.2, 92: 4.9, 93: 4.6, 94: 4.3,
        95: 4.0, 96: 3.7, 97: 3.4, 98: 3.2, 99: 3.0,
        100: 2.8
    }
    if age < 65:
        return 25.0 + (65 - age)
    elif age > 100:
        return 2.0
    return table.get(age, 2.8)


def get_rmd_factor(age):
    """RMD distribution period from IRS Uniform Lifetime Table.
    SECURE 2.0: RMD starts at 75 for those born 1960+.
    """
    table = {
        75: 24.6, 76: 23.7,
        77: 22.9, 78: 22.0, 79: 21.1, 80: 20.2, 81: 19.4,
        82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2,
        87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5,
        92: 10.8, 93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4,
        97: 7.8, 98: 7.3, 99: 6.8, 100: 6.4
    }
    if age < 75:
        return 0
    elif age > 100:
        return 6.0
    return table.get(age, 6.4)


def calc_sepp_72t(ira_balance, age, interest_rate=0.05):
    """72(t) SEPP annual withdrawal using fixed amortization method.
    SEPP = balance * rate / (1 - (1 + rate)^(-life_expectancy))
    """
    life_exp = get_life_expectancy(age)
    if life_exp <= 0 or ira_balance <= 0:
        return 0
    r = interest_rate
    sepp = ira_balance * r / (1 - (1 + r) ** (-life_exp))
    return sepp


# ── Federal income tax brackets (2024 base) ──

_FED_BRACKETS = {
    'MFJ': [
        (23200, 0.10), (94300, 0.12), (201050, 0.22),
        (383900, 0.24), (487450, 0.32), (731200, 0.35),
        (float('inf'), 0.37),
    ],
    'Single': [
        (11600, 0.10), (47150, 0.12), (100525, 0.22),
        (191950, 0.24), (243725, 0.32), (609350, 0.35),
        (float('inf'), 0.37),
    ],
}

_FED_STD_DEDUCTION = {'MFJ': 29200, 'Single': 14600}

# ── Preferential income (LTCG / qualified dividends) brackets (2024 base) ──

_PREF_BRACKETS = {
    'MFJ': [
        (94050, 0.00), (583750, 0.15), (float('inf'), 0.20),
    ],
    'Single': [
        (47025, 0.00), (518900, 0.15), (float('inf'), 0.20),
    ],
}

# ── California brackets (2024 base) ──

_CA_BRACKETS = {
    'MFJ': [
        (20824, 0.01), (49368, 0.02), (77918, 0.04),
        (108162, 0.06), (136700, 0.08), (698274, 0.093),
        (837922, 0.103), (1396542, 0.113), (float('inf'), 0.123),
    ],
    'Single': [
        (10412, 0.01), (24684, 0.02), (38959, 0.04),
        (54081, 0.06), (68350, 0.08), (349137, 0.093),
        (418961, 0.103), (698271, 0.113), (float('inf'), 0.123),
    ],
}

_CA_STD_DEDUCTION = {'MFJ': 11080, 'Single': 5540}


def get_federal_std_deduction(filing_status='MFJ'):
    """Federal standard deduction (2024 base, before inflation adjustment)."""
    return _FED_STD_DEDUCTION.get(filing_status, _FED_STD_DEDUCTION['MFJ'])


# Backward compat — MFJ default
FEDERAL_STD_DEDUCTION_BASE = 29200


def calc_federal_tax(taxable_income, inflation_factor=1.0, filing_status='MFJ'):
    """Federal income tax (2024 brackets, inflation-adjusted)."""
    brackets = [(limit * inflation_factor, rate)
                for limit, rate in _FED_BRACKETS.get(filing_status, _FED_BRACKETS['MFJ'])]
    tax = 0
    prev_limit = 0
    remaining = taxable_income
    for limit, rate in brackets:
        bracket_income = min(remaining, limit - prev_limit)
        if bracket_income <= 0:
            break
        tax += bracket_income * rate
        remaining -= bracket_income
        prev_limit = limit
    return tax


# Keep old name as alias
def calc_federal_tax_joint(taxable_income, inflation_factor=1.0):
    return calc_federal_tax(taxable_income, inflation_factor, 'MFJ')


def get_marginal_rate(taxable_income, inflation_factor=1.0, filing_status='MFJ'):
    """Marginal federal tax rate."""
    brackets = [(limit * inflation_factor, rate)
                for limit, rate in _FED_BRACKETS.get(filing_status, _FED_BRACKETS['MFJ'])]
    if taxable_income <= 0:
        return 0.10
    for limit, rate in brackets:
        if taxable_income <= limit:
            return round(rate, 2)
    return 0.37


def calc_pref_tax(pref_income, ordinary_taxable_income, inflation_factor=1.0, filing_status='MFJ'):
    """Preferential income tax (qualified dividends + LTCG).
    Stacked on top of ordinary income to determine rate bracket.
    """
    brackets = [(limit * inflation_factor, rate)
                for limit, rate in _PREF_BRACKETS.get(filing_status, _PREF_BRACKETS['MFJ'])]
    income_before_pref = ordinary_taxable_income
    income_after_pref = ordinary_taxable_income + pref_income
    tax = 0
    for limit, rate in brackets:
        if income_before_pref >= limit:
            continue
        bracket_start = max(income_before_pref, 0)
        bracket_end = min(income_after_pref, limit)
        if bracket_end > bracket_start:
            taxable_in_bracket = bracket_end - bracket_start
            tax += taxable_in_bracket * rate
        if income_after_pref <= limit:
            break
        income_before_pref = limit
    return tax


def calc_ca_tax(taxable_income, inflation_factor=1.0, filing_status='MFJ'):
    """California income tax (2024 brackets, inflation-adjusted).
    CA taxes all income at same rates (no preferential rate).
    """
    brackets = [(limit * inflation_factor, rate)
                for limit, rate in _CA_BRACKETS.get(filing_status, _CA_BRACKETS['MFJ'])]
    ca_std_ded = _CA_STD_DEDUCTION.get(filing_status, _CA_STD_DEDUCTION['MFJ']) * inflation_factor
    ca_taxable = max(0, taxable_income - ca_std_ded)

    tax = 0
    prev_limit = 0
    remaining = ca_taxable
    for limit, rate in brackets:
        bracket_income = min(remaining, limit - prev_limit)
        if bracket_income <= 0:
            break
        tax += bracket_income * rate
        remaining -= bracket_income
        prev_limit = limit

    # Mental Health Services Tax: additional 1% on income over $1M
    mhst_threshold = 1000000 * inflation_factor
    if ca_taxable > mhst_threshold:
        tax += (ca_taxable - mhst_threshold) * 0.01
    return tax


# Keep old name as alias
def calc_ca_tax_joint(taxable_income, inflation_factor=1.0):
    return calc_ca_tax(taxable_income, inflation_factor, 'MFJ')
