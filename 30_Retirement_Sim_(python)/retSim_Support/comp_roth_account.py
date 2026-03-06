"""
Roth IRA Account component.

Handles Roth conversions from IRA (threshold-based), growth, and
last-resort withdrawals when other accounts are depleted.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent

_DEFAULTS = {
    'initial_balance': 35.0,    # $K
    'conv_threshold': 0.0,      # $K — convert IRA→Roth up to this ord_inc level
}


class RothDialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Roth Account")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        field_defs = [
            ('initial_balance', 'Initial Balance ($K)'),
            ('conv_threshold', 'Conv Threshold ($K)'),
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
            'conv_threshold': float(self.fields['conv_threshold'].text()),
        }


class RothAccountComponent(BaseComponent):
    def __init__(self):
        super().__init__("Roth", "roth_account.csv")
        self.p = _DEFAULTS.copy()

        # Internal state
        self._balance = 0.0
        self._beg_balance = 0.0
        self._growth = 0.0

    def create_input_dialog(self, parent=None):
        return RothDialog(self.p, parent)

    def apply_dialog(self, dlg):
        self.p = dlg.get_params()

    def load_params(self, config):
        for k in _DEFAULTS:
            if k in config:
                self.p[k] = config[k]

    def save_params(self):
        return self.p.copy()

    def reset(self):
        self._balance = self.p['initial_balance'] * 1000.0

    def calc_for_year(self, ctx, ira_component):
        """Phase 2: Determine Roth conversion and pulls.

        Roth conversions happen if:
          - Age < 75 (before RMDs dominate)
          - conv_threshold > 0
          - Current ordinary income < threshold
        Conversion amount is limited by available IRA balance after ira_pull.
        """
        self._beg_balance = self._balance
        K = 1000.0
        threshold = self.p['conv_threshold'] * K

        # Roth conversion
        roth_conv = 0.0
        if ctx.age < 75 and threshold > 0:
            base_ord = (ctx.ss_income + ctx.pension_income + ctx.work_income +
                        ctx.interest_income + ctx.ira_pull)
            if base_ord < threshold:
                roth_conv = threshold - base_ord

            # Cap at available IRA (after ira_pull)
            available = ira_component.get_balance() - ctx.ira_pull
            if roth_conv > available:
                roth_conv = max(0, available)

        ctx.roth_conv = roth_conv
        ctx.roth_pull = 0.0     # Set later if needed for shortfall

    def apply_growth_and_conversions(self, ctx):
        """Phase 5: Apply growth and add conversions."""
        blended_ror = ctx.stock_pct * ctx.stock_ror + ctx.fixed_pct * ctx.fixed_ror
        self._growth = self._balance * blended_ror
        self._balance = self._balance + self._growth + ctx.roth_conv - ctx.roth_pull

        if self._balance < 0:
            self._balance = 0

        ctx.roth_end = self._balance
        ctx.total_gains += self._growth
        ctx.summary['roth_end'] = self._balance / 1000.0

    def cover_shortfall(self, shortfall):
        """Pull from Roth to cover remaining shortfall (last resort).
        Returns amount actually pulled.
        """
        pull = min(shortfall, self._balance)
        self._balance -= pull
        return pull

    def get_balance(self):
        return self._balance

    def get_csv_header(self):
        return ['year', 'age', 'roth_beg', 'growth', 'conversion_in',
                'pull', 'roth_end']

    def get_csv_row(self, ctx):
        K = 1000.0
        return {
            'year': ctx.year,
            'age': ctx.age,
            'roth_beg': f"{self._beg_balance / K:.1f}",
            'growth': f"{self._growth / K:.1f}",
            'conversion_in': f"{ctx.roth_conv / K:.1f}",
            'pull': f"{ctx.roth_pull / K:.1f}",
            'roth_end': f"{self._balance / K:.1f}",
        }

    def get_summary_fields(self, ctx):
        return {'roth_end': self._balance / 1000.0}
