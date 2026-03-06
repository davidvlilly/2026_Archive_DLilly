"""
Tax Liability component.

Computes federal + state (CA) taxes on aggregated income from all components.
Must run after all income/account components have reported their contributions.
Uses tax_tables.py for the actual bracket calculations.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QComboBox, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent
from retSim_Support.tax_tables import (calc_federal_tax, calc_pref_tax,
                                        calc_ca_tax, get_marginal_rate,
                                        get_federal_std_deduction)


_DEFAULTS = {
    'filing_status': 'MFJ',
    'state': 'CA',
}


class TaxDialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tax Settings")
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Filing Status"), 0, 0)
        self.filing_combo = QComboBox()
        self.filing_combo.addItems(['MFJ', 'Single'])
        idx = 0 if params.get('filing_status', 'MFJ') == 'MFJ' else 1
        self.filing_combo.setCurrentIndex(idx)
        grid.addWidget(self.filing_combo, 0, 1)

        grid.addWidget(QLabel("State"), 1, 0)
        self.state_combo = QComboBox()
        self.state_combo.addItems(['CA', 'None'])
        idx = 0 if params.get('state', 'CA') == 'CA' else 1
        self.state_combo.setCurrentIndex(idx)
        grid.addWidget(self.state_combo, 1, 1)

        layout.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_params(self):
        return {
            'filing_status': self.filing_combo.currentText(),
            'state': self.state_combo.currentText(),
        }


class TaxLiabilityComponent(BaseComponent):
    def __init__(self):
        super().__init__("Tax Settings", "tax_liability.csv")
        self.p = _DEFAULTS.copy()

    def create_input_dialog(self, parent=None):
        return TaxDialog(self.p, parent)

    def apply_dialog(self, dlg):
        self.p = dlg.get_params()

    def load_params(self, config):
        for k in _DEFAULTS:
            if k in config:
                self.p[k] = config[k]

    def save_params(self):
        return self.p.copy()

    def reset(self):
        pass

    def calc_for_year(self, ctx):
        """Phase 3: Compute taxes on aggregated income.
        Expects ctx.ord_income and ctx.pref_income to be set.
        """
        inf = ctx.inflation_factor
        fs = self.p['filing_status']

        # Federal standard deduction (inflation-adjusted)
        std_deduction = get_federal_std_deduction(fs) * inf

        # Ordinary taxable income
        ord_taxable = max(0, ctx.ord_income - std_deduction)

        # Federal ordinary tax
        ctx.ord_tax = calc_federal_tax(ord_taxable, inf, fs)

        # Federal preferential tax (stacked on ordinary)
        ctx.pref_tax = calc_pref_tax(ctx.pref_income, ord_taxable, inf, fs)

        # State tax
        if self.p['state'] == 'CA':
            ctx.ca_tax = calc_ca_tax(ctx.ord_income + ctx.pref_income, inf, fs)
        else:
            ctx.ca_tax = 0.0

        ctx.total_tax = ctx.ord_tax + ctx.pref_tax + ctx.ca_tax

        # Marginal rate
        ctx.marg_rate = get_marginal_rate(ord_taxable, inf, fs)

    def calc_liquidation_tax(self, ctx, ira_balance, std_taxable_gain):
        """Compute tax on full liquidation (for amount_avail calculation)."""
        inf = ctx.inflation_factor
        fs = self.p['filing_status']
        std_deduction = get_federal_std_deduction(fs) * inf

        liq_ord_taxable = max(0, ira_balance - std_deduction)
        liq_ord_tax = calc_federal_tax(liq_ord_taxable, inf, fs)
        liq_pref_tax = calc_pref_tax(std_taxable_gain, liq_ord_taxable, inf, fs)
        liq_ca_tax = 0.0
        if self.p['state'] == 'CA':
            liq_ca_tax = calc_ca_tax(ira_balance + std_taxable_gain, inf, fs)

        return liq_ord_tax + liq_pref_tax + liq_ca_tax

    def get_csv_header(self):
        return ['year', 'age', 'ord_inc', 'pref_inc', 'ord_tax', 'pref_tax',
                'ca_tax', 'total_tax', 'eff_rate', 'marg_rate']

    def get_csv_row(self, ctx):
        K = 1000.0
        return {
            'year': ctx.year,
            'age': ctx.age,
            'ord_inc': f"{ctx.ord_income / K:.1f}",
            'pref_inc': f"{ctx.pref_income / K:.1f}",
            'ord_tax': f"{ctx.ord_tax / K:.1f}",
            'pref_tax': f"{ctx.pref_tax / K:.1f}",
            'ca_tax': f"{ctx.ca_tax / K:.1f}",
            'total_tax': f"{ctx.total_tax / K:.1f}",
            'eff_rate': f"{ctx.tax_rate:.0%}",
            'marg_rate': f"{ctx.marg_rate:.0%}",
        }

    def get_summary_fields(self, ctx):
        K = 1000.0
        return {
            'total_tax': ctx.total_tax / K,
            'tax_rate': ctx.tax_rate,
            'marg_rate': ctx.marg_rate,
        }
