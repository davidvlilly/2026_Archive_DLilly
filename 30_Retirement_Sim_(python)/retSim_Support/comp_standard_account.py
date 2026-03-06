"""
Standard (Taxable) Brokerage Account component.

This is the central cash-flow hub: income from all sources flows in,
spending and taxes flow out. Tracks cost basis for LTCG calculation.

Stock portion: capital appreciation + 1.5% qualified dividend yield.
Fixed portion: full interest rate as ordinary income.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent

_DEFAULTS = {
    'initial_balance': 300.0,   # $K
    'initial_pretax': 0.0,      # $K unrealized gains in stock portion
}

DIV_YIELD = 0.015               # 1.5% qualified dividend yield on stock portion


class StandardAccountDialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Standard Account")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        field_defs = [
            ('initial_balance', 'Initial Balance ($K)'),
            ('initial_pretax', 'Unrealized Gains ($K)'),
        ]
        for i, (key, label) in enumerate(field_defs):
            grid.addWidget(QLabel(label), i, 0)
            edit = QLineEdit(str(params.get(key, '')))
            edit.setFixedWidth(100)
            grid.addWidget(edit, i, 1)
            self.fields[key] = edit

        layout.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_params(self):
        return {
            'initial_balance': float(self.fields['initial_balance'].text()),
            'initial_pretax': float(self.fields['initial_pretax'].text()),
        }


class StandardAccountComponent(BaseComponent):
    def __init__(self):
        super().__init__("Standard Acct", "standard_account.csv")
        self.p = _DEFAULTS.copy()

        # Internal state
        self._balance = 0.0
        self._stock_cost_basis = 0.0
        self._std_growth = 0.0
        self._interest_inc = 0.0
        self._div_inc = 0.0
        self._lt_cap_gain = 0.0
        self._std_withdrawal = 0.0

    def create_input_dialog(self, parent=None):
        return StandardAccountDialog(self.p, parent)

    def apply_dialog(self, dlg):
        self.p = dlg.get_params()

    def load_params(self, config):
        for k in _DEFAULTS:
            if k in config:
                self.p[k] = config[k]

    def save_params(self):
        return self.p.copy()

    def reset(self):
        K = 1000.0
        self._balance = self.p['initial_balance'] * K
        pretax = self.p['initial_pretax'] * K
        # Cost basis = stock_value - unrealized gains
        # stock_value computed at first calc from balance * stock_pct
        self._initial_pretax = pretax

    def init_basis(self, stock_pct):
        """Called by engine after reset to set initial cost basis."""
        stock_value = self._balance * stock_pct
        self._stock_cost_basis = stock_value - self._initial_pretax

    def calc_for_year(self, ctx):
        """Phase 2: Compute income from standard account.
        Does NOT finalize ending balance — that happens in finalize().
        """
        beg = self._balance
        stock_pct = ctx.stock_pct
        fixed_pct = ctx.fixed_pct

        stock_value = beg * stock_pct
        fixed_value = beg * fixed_pct

        # Income streams
        self._div_inc = stock_value * DIV_YIELD
        self._interest_inc = fixed_value * ctx.fixed_ror

        # Capital appreciation (stock price gain, excludes dividends)
        self._std_growth = stock_value * (ctx.stock_ror - DIV_YIELD)

        # Taxable gain percentage for LTCG on withdrawals
        if stock_value > 0:
            taxable_gain = stock_value - self._stock_cost_basis
            self._stock_taxable_pct = max(0, min(1.0, taxable_gain / stock_value))
        else:
            self._stock_taxable_pct = 0.0

        # Report to context
        ctx.interest_income = self._interest_inc
        ctx.div_income = self._div_inc

        # Store beginning balance for CSV
        self._beg_balance = beg

    def compute_withdrawal_and_ltcg(self, ctx):
        """Called by engine during iterative convergence.
        Estimates std withdrawal and resulting LTCG given current tax estimate.
        """
        # What's needed from standard account after all other income
        withdrawal = (ctx.target_draw + ctx.total_tax + ctx.property_net_cost
                      - ctx.ss_income - ctx.pension_income - ctx.work_income
                      - ctx.ira_pull - self._div_inc - self._interest_inc)
        if withdrawal < 0:
            withdrawal = 0
        self._std_withdrawal = withdrawal

        # LTCG from stock portion of withdrawal
        stock_portion = withdrawal * ctx.stock_pct
        ctx.lt_cap_gain = stock_portion * self._stock_taxable_pct

    def finalize(self, ctx):
        """Phase 5: Apply all cash flows to compute ending balance."""
        K = 1000.0
        beg = self._balance

        # Cash inflows: all income + account pulls
        inflows = (ctx.ss_income + ctx.pension_income + ctx.work_income +
                   ctx.ira_pull + self._div_inc + self._interest_inc)

        # Cash outflows: draw + tax + property costs
        outflows = ctx.target_draw + ctx.total_tax + ctx.property_net_cost

        # Ending balance: beginning + growth + inflows - outflows
        # May be negative — engine will cover shortfall from IRA/Roth
        end = beg + self._std_growth + inflows - outflows

        # Update cost basis (proportional reduction on withdrawal)
        stock_value_beg = beg * ctx.stock_pct
        if stock_value_beg > 0:
            stock_portion_withdrawn = self._std_withdrawal * ctx.stock_pct
            basis_withdrawn = stock_portion_withdrawn * (self._stock_cost_basis / stock_value_beg)
            self._stock_cost_basis -= basis_withdrawn
            if self._stock_cost_basis < 0:
                self._stock_cost_basis = 0

        self._balance = end
        ctx.std_end = end

        # Track gains
        ctx.total_gains += self._std_growth + self._div_inc + self._interest_inc

        ctx.summary['std_end'] = end / K

    def get_balance(self):
        return self._balance

    def set_balance(self, val):
        self._balance = val

    def get_csv_header(self):
        return ['year', 'age', 'std_beg', 'growth', 'interest_inc',
                'div_inc', 'ltcg', 'std_end']

    def get_csv_row(self, ctx):
        K = 1000.0
        return {
            'year': ctx.year,
            'age': ctx.age,
            'std_beg': f"{self._beg_balance / K:.1f}",
            'growth': f"{self._std_growth / K:.1f}",
            'interest_inc': f"{self._interest_inc / K:.1f}",
            'div_inc': f"{self._div_inc / K:.1f}",
            'ltcg': f"{ctx.lt_cap_gain / K:.1f}",
            'std_end': f"{self._balance / K:.1f}",
        }

    def get_summary_fields(self, ctx):
        K = 1000.0
        return {'std_end': self._balance / K}
