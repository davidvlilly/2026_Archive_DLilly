"""
Traditional IRA Account component.

Handles RMD (age 75+, SECURE 2.0), 72(t) SEPP (age < 59.5),
and additional withdrawals to cover spending shortfalls.
Growth uses blended return rate (stock + fixed).
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent
from retSim_Support.tax_tables import get_rmd_factor, get_life_expectancy, calc_sepp_72t

# Cap on ordinary income from IRA pulls (to manage tax bracket)
ORD_INC_CAP = 180000

_DEFAULTS = {
    'initial_balance': 2090.0,  # $K
}


class IRADialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IRA Account")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        field_defs = [
            ('initial_balance', 'Initial Balance ($K)'),
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
        }


class IRAAccountComponent(BaseComponent):
    def __init__(self):
        super().__init__("IRA", "ira_account.csv")
        self.p = _DEFAULTS.copy()

        # Internal state
        self._balance = 0.0
        self._sepp_amount = 0.0     # Fixed SEPP annual withdrawal
        self._beg_balance = 0.0
        self._growth = 0.0

    def create_input_dialog(self, parent=None):
        return IRADialog(self.p, parent)

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

    def init_sepp(self, age, sepp_rate):
        """Called by engine after reset to compute SEPP amount.
        sepp_rate: decimal (e.g. 0.05 for 5%)
        """
        if sepp_rate > 0:
            self._sepp_amount = calc_sepp_72t(self._balance, age, sepp_rate)
        else:
            self._sepp_amount = 0

    def calc_for_year(self, ctx, std_balance=0, std_growth=0):
        """Phase 2: Determine IRA withdrawal amount.

        Mirrors reference logic:
          1. RMD is the minimum pull
          2. Estimate tax with base income
          3. See if std account can cover draw + tax
          4. If not, pull additional from IRA (capped at ord_inc cap)
        """
        from retSim_Support.tax_tables import (calc_federal_tax, calc_pref_tax,
                                                calc_ca_tax, get_federal_std_deduction)

        self._beg_balance = self._balance

        # Life expectancy and RMD
        ctx.life_exp = get_life_expectancy(ctx.age)
        rmd_factor = get_rmd_factor(ctx.age)
        if rmd_factor > 0 and self._balance > 0:
            ctx.rmd = self._balance / rmd_factor
        else:
            ctx.rmd = 0

        # 72(t) SEPP: fixed withdrawal if age < 59.5
        use_sepp = (ctx.age < 59.5 and self._sepp_amount > 0)
        ctx.sepp_active = use_sepp

        if use_sepp:
            ctx.ira_pull = min(self._sepp_amount, self._balance)
        else:
            # Start with RMD as minimum
            ira_pull = ctx.rmd

            # Base ordinary income from fixed sources + RMD
            base_ord_inc = (ctx.ss_income + ctx.pension_income +
                            ctx.work_income + ctx.interest_income + ctx.rmd)

            # Estimate tax with just base income
            inf = ctx.inflation_factor
            fs = ctx.filing_status
            std_deduction = get_federal_std_deduction(fs) * inf
            est_taxable = max(0, base_ord_inc - std_deduction)
            est_fed_tax = calc_federal_tax(est_taxable, inf, fs)
            est_pref_tax = calc_pref_tax(ctx.div_income, est_taxable, inf, fs)
            est_ca_tax = calc_ca_tax(base_ord_inc + ctx.div_income, inf, fs)
            est_total_tax = est_fed_tax + est_pref_tax + est_ca_tax

            # How much std account can provide
            std_available = (std_balance + std_growth +
                             ctx.ss_income + ctx.pension_income + ctx.work_income +
                             ctx.rmd + ctx.div_income + ctx.interest_income -
                             est_total_tax)

            # How much is needed total
            amount_needed = ctx.target_draw + est_total_tax + ctx.property_net_cost

            # Shortfall after std account
            shortfall_after_std = amount_needed - std_available
            if shortfall_after_std < 0:
                shortfall_after_std = 0

            # Cap additional IRA pull to keep ord_inc under cap
            max_additional = max(0, ORD_INC_CAP - base_ord_inc)
            additional = min(shortfall_after_std,
                             self._balance - ctx.rmd,
                             max_additional)
            if additional < 0:
                additional = 0

            ira_pull = ctx.rmd + additional

            # Cap at available balance
            if ira_pull > self._balance:
                ira_pull = self._balance

            ctx.ira_pull = ira_pull

    def apply_growth_and_withdrawals(self, ctx):
        """Phase 5: Apply growth and subtract pulls + Roth conversions."""
        blended_ror = ctx.stock_pct * ctx.stock_ror + ctx.fixed_pct * ctx.fixed_ror
        self._growth = self._balance * blended_ror
        self._balance = self._balance + self._growth - ctx.ira_pull - ctx.roth_conv

        if self._balance < 0:
            self._balance = 0

        ctx.ira_end = self._balance
        ctx.total_gains += self._growth
        ctx.summary['ira_end'] = self._balance / 1000.0

    def cover_shortfall(self, shortfall):
        """Pull additional from IRA to cover standard account shortfall.
        Returns amount actually pulled.
        """
        pull = min(shortfall, self._balance)
        self._balance -= pull
        return pull

    def get_balance(self):
        return self._balance

    def get_csv_header(self):
        return ['year', 'age', 'ira_beg', 'growth', 'rmd',
                'ira_pull', 'roth_conv', 'ira_end']

    def get_csv_row(self, ctx):
        K = 1000.0
        return {
            'year': ctx.year,
            'age': ctx.age,
            'ira_beg': f"{self._beg_balance / K:.1f}",
            'growth': f"{self._growth / K:.1f}",
            'rmd': f"{ctx.rmd / K:.1f}",
            'ira_pull': f"{ctx.ira_pull / K:.1f}",
            'roth_conv': f"{ctx.roth_conv / K:.1f}",
            'ira_end': f"{self._balance / K:.1f}",
        }

    def get_summary_fields(self, ctx):
        return {'ira_end': self._balance / 1000.0}
