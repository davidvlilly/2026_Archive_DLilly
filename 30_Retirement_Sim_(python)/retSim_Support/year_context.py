"""
YearContext — shared mutable state passed to every component during a single year's calculation.

The simulation engine creates a fresh YearContext for each year, populates the input fields,
then passes it to each component's calc_for_year(). Components read what they need and
write their results back into the context.
"""


class YearContext:
    def __init__(self, year, age, inflation_factor, target_draw,
                 stock_ror, fixed_ror, stock_pct, filing_status='MFJ'):
        # ── Inputs (set by engine) ──
        self.year = year
        self.age = age
        self.inflation_factor = inflation_factor
        self.target_draw = target_draw          # Desired spending ($), already COLA-adjusted
        self.stock_ror = stock_ror              # e.g. 0.07
        self.fixed_ror = fixed_ror              # e.g. 0.04
        self.stock_pct = stock_pct              # e.g. 0.70
        self.fixed_pct = 1.0 - stock_pct
        self.filing_status = filing_status      # 'MFJ' or 'Single'

        # ── Accumulated by income components (Phase 1) ──
        self.work_income = 0.0
        self.pension_income = 0.0
        self.ss_income = 0.0
        self.rental_income = 0.0

        # ── Property costs (Phase 1) ──
        self.property_debt_service = 0.0
        self.property_net_cost = 0.0            # debt_service - rental_income

        # ── Standard account income (Phase 2) ──
        self.interest_income = 0.0              # Fixed portion interest → ordinary
        self.div_income = 0.0                   # Stock portion dividends → preferential
        self.lt_cap_gain = 0.0                  # LTCG from std withdrawals → preferential

        # ── Account activity (Phase 2) ──
        self.ira_pull = 0.0
        self.roth_conv = 0.0
        self.roth_pull = 0.0
        self.rmd = 0.0
        self.life_exp = 0.0
        self.sepp_active = False

        # ── Aggregates (computed by engine between phases) ──
        self.ord_income = 0.0
        self.pref_income = 0.0
        self.total_income = 0.0

        # ── Tax results (Phase 3) ──
        self.ord_tax = 0.0
        self.pref_tax = 0.0
        self.ca_tax = 0.0
        self.total_tax = 0.0
        self.tax_rate = 0.0                     # Effective rate
        self.marg_rate = 0.0                    # Marginal rate

        # ── End-of-year account balances (set by account components) ──
        self.ira_end = 0.0
        self.std_end = 0.0
        self.roth_end = 0.0
        self.total_sav = 0.0
        self.amount_avail = 0.0                 # After-tax liquidation value

        # ── Gains/expenses tracking ──
        self.total_gains = 0.0
        self.total_expenses = 0.0
        self.net_gain_loss = 0.0

        # ── Per-component summary for main_summary.csv ──
        self.summary = {}

    def compute_aggregates(self):
        """Compute aggregate income totals from component contributions."""
        self.ord_income = (self.ss_income + self.pension_income +
                           self.work_income + self.interest_income +
                           self.ira_pull + self.roth_conv)
        self.pref_income = self.div_income + self.lt_cap_gain
        self.total_income = self.ord_income + self.pref_income

    def compute_totals(self):
        """Compute final totals after all components have run."""
        self.total_sav = self.ira_end + self.std_end + self.roth_end
        self.total_expenses = self.target_draw + self.total_tax
        self.net_gain_loss = self.total_gains - self.total_expenses
        if self.total_income > 0:
            self.tax_rate = self.total_tax / self.total_income
        else:
            self.tax_rate = 0.0
