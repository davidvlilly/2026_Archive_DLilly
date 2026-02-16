"""
Retirement simulation year calculation functions.

Income/Tax Structure (mirrors federal tax form logic):
  total_inc  = ord_inc + pref_inc (AGI equivalent)
  ord_inc    = SS + interest + ira_pull + roth_conv (taxed at bracket rates)
  pref_inc   = qualified dividends + LTCapGn (taxed at 0/15/20% rates)
  
  ord_tax    = tax on ord_inc at bracket rates
  pref_tax   = tax on pref_inc at preferential rates (stacked on ord_inc)
  total_tax  = ord_tax + pref_tax
"""

def get_life_expectancy(age):
    """
    Approximate life expectancy based on IRS Uniform Lifetime Table.
    Returns expected remaining years.
    """
    # Simplified table based on IRS Publication 590-B
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
    """
    RMD distribution period from IRS Uniform Lifetime Table.
    Used to calculate Required Minimum Distribution.
    """
    # IRS Uniform Lifetime Table (updated 2022, SECURE 2.0: RMD starts at 75 for born 1960+)
    table = {
        75: 24.6, 76: 23.7,
        77: 22.9, 78: 22.0, 79: 21.1, 80: 20.2, 81: 19.4,
        82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2,
        87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5,
        92: 10.8, 93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4,
        97: 7.8, 98: 7.3, 99: 6.8, 100: 6.4
    }
    if age < 75:
        return 0  # No RMD required before age 75 (SECURE 2.0, born 1960+)
    elif age > 100:
        return 6.0
    return table.get(age, 6.4)


def calc_federal_tax_single(taxable_income):
    """
    Calculate federal income tax for single filer (2024 brackets).
    """
    brackets = [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (609350, 0.35),
        (float('inf'), 0.37)
    ]
    
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


def get_marginal_rate(taxable_income):
    """
    Get the marginal tax rate for a given taxable income.
    Returns rate rounded to nearest 1% (e.g., 0.10, 0.12, 0.22, etc.)
    """
    brackets = [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (609350, 0.35),
        (float('inf'), 0.37)
    ]
    
    if taxable_income <= 0:
        return 0.10
    
    prev_limit = 0
    for limit, rate in brackets:
        if taxable_income <= limit:
            return round(rate, 2)
        prev_limit = limit
    
    return 0.37


def calc_pref_tax(pref_income, ordinary_taxable_income):
    """
    Calculate preferential income tax (qualified dividends + LTCG).
    Preferential income is stacked on top of ordinary income to determine the rate.
    2024 single filer brackets for preferential income:
      0% up to $47,025
      15% from $47,026 to $518,900
      20% above $518,900
    """
    brackets = [
        (47025, 0.00),
        (518900, 0.15),
        (float('inf'), 0.20)
    ]
    
    # Preferential income stacks on top of ordinary income
    income_before_pref = ordinary_taxable_income
    income_after_pref = ordinary_taxable_income + pref_income
    
    tax = 0
    for limit, rate in brackets:
        if income_before_pref >= limit:
            # Already past this bracket with ordinary income
            continue
        
        # Calculate how much preferential income falls in this bracket
        bracket_start = max(income_before_pref, 0)
        bracket_end = min(income_after_pref, limit)
        
        if bracket_end > bracket_start:
            taxable_in_bracket = bracket_end - bracket_start
            tax += taxable_in_bracket * rate
        
        if income_after_pref <= limit:
            break
        
        income_before_pref = limit
    
    return tax


def calc_ca_tax_single(taxable_income):
    """
    Calculate California income tax for single filer (2024 brackets).
    CA taxes all income at same rates (no preferential rate for dividends/LTCG).
    CA standard deduction for single: $5,540
    """
    brackets = [
        (10412, 0.01),
        (24684, 0.02),
        (38959, 0.04),
        (54081, 0.06),
        (68350, 0.08),
        (349137, 0.093),
        (418961, 0.103),
        (698271, 0.113),
        (float('inf'), 0.123)
    ]
    
    # CA standard deduction for single filer
    ca_std_deduction = 5540
    ca_taxable = max(0, taxable_income - ca_std_deduction)
    
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
    if ca_taxable > 1000000:
        tax += (ca_taxable - 1000000) * 0.01
    
    return tax


def calculate_year(params, prev_ira_end, prev_std_end, prev_roth_end, prev_std_cost_basis=None):
    """
    Calculate one year of retirement simulation.
    
    params: dict with year, age, draw, ira_beg, std_beg, SS_inc, 
            stock_ROR, fixed_ROR, stock_pct, fixed_pct, roth_conv_threshold
    prev_ira_end: IRA balance at end of previous year (or initial for year 1)
    prev_std_end: Standard balance at end of previous year (or initial for year 1)
    prev_roth_end: Roth balance at end of previous year (or initial for year 1)
    prev_std_cost_basis: Cost basis of std account stock portion (defaults to full value if None)
    
    Returns: dict with all calculated values for the year
    """
    year = params['year']
    age = params['age']
    draw = params['draw']
    SS_inc = params['SS_inc']
    stock_ROR = params['stock_ROR'] / 100.0
    fixed_ROR = params['fixed_ROR'] / 100.0
    stock_pct = params['stock_pct'] / 100.0
    fixed_pct = params['fixed_pct'] / 100.0
    roth_conv_threshold = params.get('roth_conv_threshold', 0)
    
    # Beginning balances for this year
    ira_beg = prev_ira_end
    std_beg = prev_std_end
    roth_beg = prev_roth_end
    
    # Stock basis - if None, assume all basis (no gains yet)
    stock_value_beg = std_beg * stock_pct
    if prev_std_cost_basis is None:
        std_stock_basis_beg = stock_value_beg
    else:
        std_stock_basis_beg = prev_std_cost_basis
    
    # Life expectancy
    life_exp = get_life_expectancy(age)
    
    # RMD calculation
    rmd_factor = get_rmd_factor(age)
    if rmd_factor > 0 and ira_beg > 0:
        RMD = ira_beg / rmd_factor
    else:
        RMD = 0
    
    # Income from standard account
    # Stock portion: 1.5% dividend yield (treated as qualified/preferential)
    #   Dividends are paid out as cash income, NOT included in stock price growth.
    #   Stock price growth (stock_ROR) is capital appreciation only (excludes dividend).
    # Fixed portion: full interest rate (treated as ordinary income)
    stock_value = std_beg * stock_pct
    fixed_value = std_beg * fixed_pct
    div_income = stock_value * 0.015  # Qualified dividends -> preferential
    interest_income = fixed_value * fixed_ROR  # Interest -> ordinary
    
    # Calculate stock gain in std account (capital appreciation only, excludes dividends)
    std_stock_gain = stock_value * (stock_ROR - 0.015)
    
    # Calculate std account growth: price appreciation only
    # Dividends and interest are separate cash income streams added to std_end individually
    # This ensures std total return = stock_ROR * stock_pct + fixed_ROR * fixed_pct
    #   (same as IRA/Roth blended_ror)
    std_growth = stock_value * (stock_ROR - 0.015)
    
    # Blended return rate for IRA and Roth (where dividends ARE reinvested internally)
    blended_ror = stock_pct * stock_ROR + fixed_pct * fixed_ROR
    
    # Withdrawal sequencing strategy (after age 75):
    # 1. Use std account first (if available)
    # 2. Then IRA, but cap ord_inc at 180K
    # 3. Then Roth for remainder
    
    # Start with RMD as the minimum IRA pull (forced withdrawal)
    ira_pull = RMD
    
    # Base ordinary income from non-discretionary sources
    base_ord_inc_fixed = SS_inc + interest_income + RMD
    
    # Estimate total tax with just base income (fed + CA + estimated pref)
    standard_deduction = 14600
    est_taxable = max(0, base_ord_inc_fixed - standard_deduction)
    est_fed_tax = calc_federal_tax_single(est_taxable)
    est_pref_tax = calc_pref_tax(div_income, est_taxable)  # at least dividends are known
    est_ca_tax = calc_ca_tax_single(base_ord_inc_fixed + div_income)
    est_total_tax = est_fed_tax + est_pref_tax + est_ca_tax
    
    # Calculate how much we need to cover (draw + estimated tax)
    amount_needed = draw + est_total_tax
    
    # What's available from std account (income coming in: SS + RMD, plus growth)
    std_available_for_draw = std_beg + std_growth + SS_inc + RMD - est_total_tax
    
    # Shortfall after using std account
    shortfall_after_std = amount_needed - std_available_for_draw
    if shortfall_after_std < 0:
        shortfall_after_std = 0
    
    # If there's a shortfall, determine how much more to pull from IRA
    # But cap ord_inc at 180K (so additional IRA pull is limited)
    ord_inc_cap = 180000
    max_additional_ira_for_cap = ord_inc_cap - base_ord_inc_fixed
    if max_additional_ira_for_cap < 0:
        max_additional_ira_for_cap = 0
    
    # Additional IRA pull is the lesser of: shortfall, available IRA, or amount to reach cap
    additional_ira_pull = min(shortfall_after_std, ira_beg - RMD, max_additional_ira_for_cap)
    if additional_ira_pull < 0:
        additional_ira_pull = 0
    
    ira_pull = RMD + additional_ira_pull
    
    # Cap ira_pull at available IRA balance
    if ira_pull > ira_beg:
        ira_pull = ira_beg
    
    # Calculate base ordinary income (before roth conversion)
    # Ordinary income: SS + interest + ira_pull (excludes dividends which are preferential)
    base_ord_inc = SS_inc + interest_income + ira_pull
    
    # Determine roth conversion amount based on threshold (only before RMDs start at 75)
    roth_conv = 0
    if age < 75 and roth_conv_threshold > 0 and base_ord_inc < roth_conv_threshold:
        # Convert enough to bring ord_inc up to threshold
        roth_conv = roth_conv_threshold - base_ord_inc
    
    # Cap roth_conv at available IRA balance (after ira_pull)
    available_for_conv = ira_beg - ira_pull
    if roth_conv > available_for_conv:
        roth_conv = max(0, available_for_conv)
    
    # Ordinary income (includes roth conversion)
    ord_inc = base_ord_inc + roth_conv
    
    # Calculate ordinary taxable income
    standard_deduction = 14600
    ord_taxable = max(0, ord_inc - standard_deduction)
    
    # Calculate ordinary federal tax
    ord_tax = calc_federal_tax_single(ord_taxable)
    
    # --- Iterative solve for std_withdrawal / pref_tax / ca_tax / total_tax ---
    # std_withdrawal depends on total_tax, but total_tax depends on LTCG from std_withdrawal.
    # Iterate to converge (typically 2-3 passes).
    
    # Calculate taxable percentage of stock portion based on basis
    if stock_value_beg > 0:
        std_taxable_gain = stock_value_beg - std_stock_basis_beg
        std_stock_taxable_pct = std_taxable_gain / stock_value_beg
        std_stock_taxable_pct = max(0, min(1.0, std_stock_taxable_pct))
    else:
        std_taxable_gain = 0
        std_stock_taxable_pct = 0
    
    # Start with estimate using only ord_tax
    total_tax_est = ord_tax
    for _iteration in range(5):
        # Estimate std withdrawal given current total_tax estimate
        std_withdrawal = draw + total_tax_est - SS_inc - ira_pull - div_income - interest_income
        if std_withdrawal < 0:
            std_withdrawal = 0
        
        # LTCG from stock portion of withdrawal
        stock_portion_withdrawal = std_withdrawal * stock_pct
        LTCapGn = stock_portion_withdrawal * std_stock_taxable_pct
        
        # Preferential income: qualified dividends + LTCG
        pref_inc = div_income + LTCapGn
        
        # Federal preferential tax (stacked on top of ordinary taxable income)
        pref_tax = calc_pref_tax(pref_inc, ord_taxable)
        
        # CA taxes all income at same graduated rates
        ca_tax = calc_ca_tax_single(ord_inc + pref_inc)
        
        # Total tax
        total_tax_new = ord_tax + pref_tax + ca_tax
        
        # Check convergence (within $1)
        if abs(total_tax_new - total_tax_est) < 1.0:
            total_tax_est = total_tax_new
            break
        total_tax_est = total_tax_new
    
    total_tax = total_tax_est
    total_inc = ord_inc + pref_inc
    
    # IRA end of year: apply growth then subtract pull and roth conversion
    # IRA/Roth use blended_ror which includes dividends reinvested internally
    ira_growth = ira_beg * blended_ror
    ira_end = ira_beg + ira_growth - ira_pull - roth_conv
    if ira_end < 0:
        ira_end = 0
    
    # Roth end of year: beginning + growth + conversion
    roth_growth = roth_beg * blended_ror
    roth_end = roth_beg + roth_growth + roth_conv
    
    # Standard account end of year
    # std_growth is capital appreciation only (stock price gains + fixed interest)
    # Cash inflows: SS_inc, ira_pull, div_income, interest_income
    # Cash outflows: total_tax, draw
    std_end = std_beg + std_growth + SS_inc + ira_pull + div_income + interest_income - total_tax - draw
    
    # If std_end is negative, we need to pull from Roth
    roth_pull = 0
    if std_end < 0:
        # Need to pull from Roth to cover shortfall
        shortfall = -std_end
        roth_pull = min(shortfall, roth_end)
        roth_end = roth_end - roth_pull
        std_end = std_end + roth_pull
    
    # Ensure std_end is never negative (if Roth couldn't cover it all)
    if std_end < 0:
        std_end = 0
    
    # Update stock basis for end of year
    # Basis reduces proportionally when we withdraw
    if stock_value_beg > 0:
        basis_portion_withdrawn = stock_portion_withdrawal * (std_stock_basis_beg / stock_value_beg)
    else:
        basis_portion_withdrawn = 0
    
    std_stock_basis_end = std_stock_basis_beg - basis_portion_withdrawn
    if std_stock_basis_end < 0:
        std_stock_basis_end = 0
    
    # Calculate end of year stock value and taxable gain
    stock_value_end = std_end * stock_pct
    std_taxable_gain_end = stock_value_end - std_stock_basis_end
    if std_taxable_gain_end < 0:
        std_taxable_gain_end = 0
    
    # Total savings
    total_sav = ira_end + std_end + roth_end
    
    # Effective tax rate (total tax / total income)
    if total_inc > 0:
        tax_rate = total_tax / total_inc
    else:
        tax_rate = 0
    
    # Marginal tax rate (rounded to 1%)
    marg_rate = get_marginal_rate(ord_taxable)
    
    # Track gains and expenses
    total_gains = ira_growth + std_growth + roth_growth + div_income + interest_income
    total_expenses = draw + total_tax
    net_gain_loss = total_gains - total_expenses
    
    # Calculate amount_avail: after-tax value if everything liquidated
    # IRA: fully taxable as ordinary income
    # Std: only taxable gains on stock portion (preferential)
    # Roth: tax-free
    
    # Taxable if liquidated: IRA + std stock gains
    liquidation_ord_inc = ira_end
    liquidation_pref = std_taxable_gain_end
    
    # Calculate tax on full liquidation (federal + CA)
    liquidation_taxable = max(0, liquidation_ord_inc - 14600)  # standard deduction
    liquidation_ord_tax = calc_federal_tax_single(liquidation_taxable)
    liquidation_pref_tax = calc_pref_tax(liquidation_pref, liquidation_taxable)
    liquidation_ca_tax = calc_ca_tax_single(liquidation_ord_inc + liquidation_pref)
    liquidation_total_tax = liquidation_ord_tax + liquidation_pref_tax + liquidation_ca_tax
    
    amount_avail = total_sav - liquidation_total_tax
    
    return {
        'year': year,
        'age': age,
        'draw': draw,
        'ira_beg': ira_beg,
        'std_beg': std_beg,
        'roth_beg': roth_beg,
        'SS_inc': SS_inc,
        'life_exp': life_exp,
        'RMD': RMD,
        'ira_pull': ira_pull,
        'roth_conv': roth_conv,
        'roth_pull': roth_pull,
        'total_inc': total_inc,
        'ord_inc': ord_inc,
        'pref_inc': pref_inc,
        'ord_tax': ord_tax,
        'pref_tax': pref_tax,
        'ca_tax': ca_tax,
        'total_tax': total_tax,
        'ira_end': ira_end,
        'std_end': std_end,
        'roth_end': roth_end,
        'total_sav': total_sav,
        'amount_avail': amount_avail,
        'std_stock_gain': std_stock_gain,
        'std_stock_basis': std_stock_basis_end,
        'std_taxable_gain': std_taxable_gain_end,
        'LTCapGn': LTCapGn,
        'total_gains': total_gains,
        'total_expenses': total_expenses,
        'net_gain_loss': net_gain_loss,
        'marg_rate': marg_rate,
        'tax_rate': tax_rate
    }
