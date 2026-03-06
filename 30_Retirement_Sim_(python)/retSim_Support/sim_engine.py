"""
Simulation Engine — year-by-year loop and calcOneYear orchestration.

Owns the multi-phase calculation flow:
  Phase 1: Income sources report in
  Phase 2: Account components (std → IRA → Roth)
  Phase 3: Tax computed on full income picture
  Phase 4: Iterative convergence (tax ↔ withdrawal)
  Phase 5: Finalize balances, write CSVs
"""

import csv
import os
from retSim_Support.year_context import YearContext
from retSim_Support.comp_work_income import WorkIncomeComponent
from retSim_Support.comp_pension import PensionComponent
from retSim_Support.comp_social_security import SocialSecurityComponent
from retSim_Support.comp_property import PropertyComponent
from retSim_Support.comp_standard_account import StandardAccountComponent
from retSim_Support.comp_ira_account import IRAAccountComponent
from retSim_Support.comp_roth_account import RothAccountComponent
from retSim_Support.comp_tax_liability import TaxLiabilityComponent
from retSim_Support.tax_tables import get_federal_std_deduction


def _get_component(components, cls):
    """Find the first component of given class."""
    for c in components:
        if isinstance(c, cls):
            return c
    return None


def _get_components(components, cls):
    """Find all components of given class."""
    return [c for c in components if isinstance(c, cls)]


def run_simulation(sim_config, results_dir='results'):
    """Run the full simulation and write CSV output files.

    Returns list of per-year result dicts (for plotting).
    """
    os.makedirs(results_dir, exist_ok=True)

    components = sim_config.components
    K = 1000.0

    # Categorize components
    work = _get_component(components, WorkIncomeComponent)
    pension = _get_component(components, PensionComponent)
    ss = _get_component(components, SocialSecurityComponent)
    properties = _get_components(components, PropertyComponent)
    std_acct = _get_component(components, StandardAccountComponent)
    ira_acct = _get_component(components, IRAAccountComponent)
    roth_acct = _get_component(components, RothAccountComponent)
    tax = _get_component(components, TaxLiabilityComponent)

    # Reset all components
    for c in components:
        c.reset()

    # Initialize account-specific setup
    start_age = sim_config.age_at(sim_config.year_start)
    if std_acct:
        std_acct.init_basis(sim_config.stock_pct)
    if ira_acct:
        sepp_rate = pension.p.get('sepp_rate', 0) / 100.0 if pension else 0
        ira_acct.init_sepp(start_age, sepp_rate)
    for prop in properties:
        prop.init_amortization(sim_config.year_start)

    # Prepare CSV writers
    csv_files = {}
    csv_writers = {}
    for c in components:
        filepath = os.path.join(results_dir, c.csv_filename)
        f = open(filepath, 'w', newline='')
        writer = csv.DictWriter(f, fieldnames=c.get_csv_header())
        writer.writeheader()
        csv_files[c.name] = f
        csv_writers[c.name] = writer

    # Main summary CSV
    summary_columns = ['year', 'age', 'draw']
    if work:
        summary_columns.append('work_inc')
    if pension:
        summary_columns.append('pension')
    if ss:
        summary_columns.append('ss_inc')
    for prop in properties:
        summary_columns.append(prop.csv_filename.replace('.csv', '_eq'))
    summary_columns.extend([
        'ira_pull', 'roth_conv', 'roth_pull',
        'ord_inc', 'pref_inc', 'total_tax', 'tax_rate', 'marg_rate',
        'std_end', 'ira_end', 'roth_end', 'total_sav', 'amount_avail',
        'total_gains', 'total_expenses', 'net_gain_loss',
    ])
    summary_path = os.path.join(results_dir, 'main_summary.csv')
    summary_file = open(summary_path, 'w', newline='')
    summary_writer = csv.DictWriter(summary_file, fieldnames=summary_columns)
    summary_writer.writeheader()

    # Year-by-year simulation
    results = []
    inflation_rate = sim_config.inflation
    base_year = 2024  # Tax bracket base year
    filing_status = tax.p.get('filing_status', 'MFJ') if tax else 'MFJ'

    # Identify home property for equity loan tracking
    home_prop = None
    for p in properties:
        if 'home' in p.csv_filename.lower():
            home_prop = p
            break

    # Last-resort funding: sell inv property or take home equity loan
    inv_sold = False
    inv_sold_year = None
    HM_LOAN_AMOUNT = 2000 * K       # $2M home equity loan
    HM_LOAN_RATE = 0.03
    HM_LOAN_TERM = 10
    HM_LOAN_PAYMENT = HM_LOAN_AMOUNT * HM_LOAN_RATE / (1 - (1 + HM_LOAN_RATE) ** (-HM_LOAN_TERM))
    hm_loan_years = []

    for year in range(sim_config.year_start, sim_config.year_stop + 1):
        age = sim_config.age_at(year)
        years_from_start = year - sim_config.year_start
        inflation_factor = (1 + inflation_rate) ** (year - base_year)
        target_draw = sim_config.draw_start * K * ((1 + sim_config.draw_cola) ** years_from_start)

        ctx = YearContext(
            year=year,
            age=age,
            inflation_factor=inflation_factor,
            target_draw=target_draw,
            stock_ror=sim_config.stock_ror,
            fixed_ror=sim_config.fixed_ror,
            stock_pct=sim_config.stock_pct,
            filing_status=filing_status,
        )

        # ── Last-resort funding when all accounts depleted ──
        all_depleted = True
        if ira_acct and ira_acct.get_balance() > 0:
            all_depleted = False
        if std_acct and std_acct.get_balance() > 0:
            all_depleted = False
        if roth_acct and roth_acct.get_balance() > 0:
            all_depleted = False

        if all_depleted:
            funded = False
            # Try selling investment property first
            if not inv_sold:
                inv_prop = None
                for p in properties:
                    if 'inv' in p.csv_filename.lower():
                        inv_prop = p
                        break
                if inv_prop and inv_prop.get_equity() > 0:
                    eq = inv_prop.get_equity()
                    sale_tax = inv_prop.get_tax_liability()
                    net_proceeds = max(0, eq - sale_tax)
                    if std_acct:
                        std_acct.set_balance(net_proceeds)
                    inv_prop.mark_sold()
                    inv_sold = True
                    inv_sold_year = year
                    funded = True

            # Take $2M home equity loan
            if not funded and std_acct:
                std_acct.set_balance(HM_LOAN_AMOUNT)
                if home_prop:
                    home_prop.take_equity_loan(HM_LOAN_AMOUNT)
                hm_loan_years.append(year)

        # Add home loan debt service to draw for active loans
        hm_loan_debt = 0
        for loan_yr in hm_loan_years:
            if (year - loan_yr) < HM_LOAN_TERM:
                hm_loan_debt += HM_LOAN_PAYMENT
        ctx.target_draw = target_draw + hm_loan_debt

        # ── Phase 1: Income sources ──
        if work:
            work.calc_for_year(ctx)
        if pension:
            pension.calc_for_year(ctx)
        if ss:
            ss.calc_for_year(ctx)
        for prop in properties:
            prop.calc_for_year(ctx)

        # ── Phase 2: Standard account income (interest, dividends) ──
        if std_acct:
            std_acct.calc_for_year(ctx)

        # ── Phase 2b: IRA withdrawal determination ──
        # Pass std account balance and growth so IRA can estimate shortfall
        if ira_acct:
            std_bal = std_acct.get_balance() if std_acct else 0
            std_grw = std_acct._std_growth if std_acct else 0
            ira_acct.calc_for_year(ctx, std_bal, std_grw)

        # ── Phase 2c: Roth conversion ──
        if roth_acct and ira_acct:
            roth_acct.calc_for_year(ctx, ira_acct)

        # ── Phase 3-4: Iterative tax/withdrawal convergence ──
        for _iteration in range(5):
            # Compute income aggregates
            ctx.compute_aggregates()

            # Tax calculation
            if tax:
                tax.calc_for_year(ctx)

            # Compute std withdrawal and LTCG given current tax
            if std_acct:
                std_acct.compute_withdrawal_and_ltcg(ctx)

            # Recompute pref_income with updated LTCG
            ctx.pref_income = ctx.div_income + ctx.lt_cap_gain
            ctx.total_income = ctx.ord_income + ctx.pref_income

            # Recompute tax with updated pref_income
            prev_tax = ctx.total_tax
            if tax:
                tax.calc_for_year(ctx)

            if abs(ctx.total_tax - prev_tax) < 1.0:
                break

        # ── Phase 5: Finalize account balances ──
        if std_acct:
            std_acct.finalize(ctx)

        if ira_acct:
            ira_acct.apply_growth_and_withdrawals(ctx)

        if roth_acct:
            roth_acct.apply_growth_and_conversions(ctx)

        # ── Shortfall coverage: IRA → Roth ──
        if std_acct and ctx.std_end < 0:
            shortfall = -ctx.std_end
            if ira_acct:
                pulled = ira_acct.cover_shortfall(shortfall)
                ctx.ira_pull += pulled
                ctx.ira_end = ira_acct.get_balance()
                std_acct.set_balance(std_acct.get_balance() + pulled)
                ctx.std_end = std_acct.get_balance()
                shortfall -= pulled

            if shortfall > 0 and roth_acct:
                pulled = roth_acct.cover_shortfall(shortfall)
                ctx.roth_pull = pulled
                ctx.roth_end = roth_acct.get_balance()
                std_acct.set_balance(std_acct.get_balance() + pulled)
                ctx.std_end = std_acct.get_balance()

        # Ensure non-negative; track unfunded shortfall
        had_unfunded = False
        unfunded_amount = 0
        if std_acct and ctx.std_end < 0:
            had_unfunded = True
            unfunded_amount = -ctx.std_end
            std_acct.set_balance(0)
            ctx.std_end = 0

        # ── HEL amortization (only if payment was actually funded) ──
        if home_prop and hm_loan_debt > 0:
            if not had_unfunded:
                home_prop.apply_hel_payment(hm_loan_debt, HM_LOAN_RATE)
                home_prop.recalc_equity()
            else:
                home_prop._hel_debt_service = hm_loan_debt

        # Charge unfunded shortfall as debt against home
        if had_unfunded and unfunded_amount > 0 and home_prop:
            home_prop.take_equity_loan(unfunded_amount)
            home_prop.recalc_equity()

        # Update home equity summary after all adjustments
        if home_prop and (hm_loan_debt > 0 or had_unfunded):
            summary_key = home_prop.csv_filename.replace('.csv', '_eq')
            ctx.summary[summary_key] = home_prop.get_equity() / K

        # ── Compute totals ──
        ctx.compute_totals()

        # Amount available (after-tax liquidation value)
        if tax and ira_acct and std_acct:
            std_stock_value = ctx.std_end * ctx.stock_pct
            std_taxable_gain = max(0, std_stock_value - std_acct._stock_cost_basis)
            liq_tax = tax.calc_liquidation_tax(ctx, ctx.ira_end, std_taxable_gain)
            ctx.amount_avail = ctx.total_sav - liq_tax
        else:
            ctx.amount_avail = ctx.total_sav

        # ── Write CSV rows ──
        for c in components:
            csv_writers[c.name].writerow(c.get_csv_row(ctx))

        # ── Write summary row ──
        # Report base draw (living expenses), not adjusted draw
        base_draw = sim_config.draw_start * K * ((1 + sim_config.draw_cola) ** years_from_start)
        row = {
            'year': year,
            'age': age,
            'draw': f"{base_draw / K:.0f}",
        }
        if work:
            row['work_inc'] = f"{ctx.work_income / K:.0f}"
        if pension:
            row['pension'] = f"{ctx.pension_income / K:.0f}"
        if ss:
            row['ss_inc'] = f"{ctx.ss_income / K:.0f}"
        for prop in properties:
            key = prop.csv_filename.replace('.csv', '_eq')
            row[key] = f"{prop.get_equity() / K:.0f}"

        row.update({
            'ira_pull': f"{ctx.ira_pull / K:.0f}",
            'roth_conv': f"{ctx.roth_conv / K:.0f}",
            'roth_pull': f"{ctx.roth_pull / K:.0f}",
            'ord_inc': f"{ctx.ord_income / K:.0f}",
            'pref_inc': f"{ctx.pref_income / K:.0f}",
            'total_tax': f"{ctx.total_tax / K:.0f}",
            'tax_rate': f"{ctx.tax_rate:.0%}",
            'marg_rate': f"{ctx.marg_rate:.0%}",
            'std_end': f"{ctx.std_end / K:.0f}",
            'ira_end': f"{ctx.ira_end / K:.0f}",
            'roth_end': f"{ctx.roth_end / K:.0f}",
            'total_sav': f"{ctx.total_sav / K:.0f}",
            'amount_avail': f"{ctx.amount_avail / K:.0f}",
            'total_gains': f"{ctx.total_gains / K:.0f}",
            'total_expenses': f"{ctx.total_expenses / K:.0f}",
            'net_gain_loss': f"{ctx.net_gain_loss / K:.0f}",
        })
        summary_writer.writerow(row)

        # Store for plotting (values in $K)
        results.append({
            'year': year,
            'age': age,
            'draw': base_draw / K,
            'work_income': ctx.work_income / K,
            'pension_income': ctx.pension_income / K,
            'ss_income': ctx.ss_income / K,
            'ira_pull': ctx.ira_pull / K,
            'roth_conv': ctx.roth_conv / K,
            'roth_pull': ctx.roth_pull / K,
            'ord_inc': ctx.ord_income / K,
            'pref_inc': ctx.pref_income / K,
            'total_inc': ctx.total_income / K,
            'ord_tax': ctx.ord_tax / K,
            'pref_tax': ctx.pref_tax / K,
            'ca_tax': ctx.ca_tax / K,
            'total_tax': ctx.total_tax / K,
            'tax_rate': ctx.tax_rate,
            'marg_rate': ctx.marg_rate,
            'std_end': ctx.std_end / K,
            'ira_end': ctx.ira_end / K,
            'roth_end': ctx.roth_end / K,
            'total_sav': ctx.total_sav / K,
            'amount_avail': ctx.amount_avail / K,
            'total_gains': ctx.total_gains / K,
            'total_expenses': ctx.total_expenses / K,
            'net_gain_loss': ctx.net_gain_loss / K,
            # Property gain: appreciation + rental income
            'prop_gain': (sum(p.get_appreciation() for p in properties)
                          + ctx.rental_income) / K,
            # Property equity for plots
            **{prop.csv_filename.replace('.csv', '_eq'): prop.get_equity() / K
               for prop in properties},
            **{prop.csv_filename.replace('.csv', '_debt'): prop.get_debt_service() / K
               for prop in properties},
            # Property tax liability (for after-tax NW)
            **{prop.csv_filename.replace('.csv', '_tax'): (prop.get_tax_liability() / K
               if prop.get_equity() > 0 else 0)
               for prop in properties},
            # Last-resort events
            'inv_sold': (inv_sold_year == year),
            'hm_loan': (year in hm_loan_years),
            'hm_loan_debt': hm_loan_debt / K,
        })

    # Close all CSV files
    for f in csv_files.values():
        f.close()
    summary_file.close()

    print(f"Simulation complete: {len(results)} years written to {results_dir}/")
    return results
