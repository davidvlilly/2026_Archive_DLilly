"""
Social Security component.

Reports SS benefit starting at claim_age, with COLA adjustments.
Benefit is reduced for early claiming (before age 69 baseline).
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent


# Age-based adjustment factors.
# ss_base is the benefit at age 69.  For claim ages not listed, factor = 1.00
# (i.e., for ages 62-65 and 70+, ss_base is used directly).
_SS_AGE_FACTORS = {
    66: 0.76,
    67: 0.84,
    68: 0.92,
    69: 1.00,
}

_DEFAULTS = {
    'ss_base': 80.0,            # $K at age 69 (base before adjustment)
    'claim_age': 62,
    'cola_rate': 2.5,           # %
}


class SocialSecurityDialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Social Security")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        field_defs = [
            ('ss_base', 'SS Benefit @69 ($K)'),
            ('claim_age', 'Claim Age'),
            ('cola_rate', 'COLA Rate (%)'),
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
            'ss_base': float(self.fields['ss_base'].text()),
            'claim_age': int(self.fields['claim_age'].text()),
            'cola_rate': float(self.fields['cola_rate'].text()),
        }


class SocialSecurityComponent(BaseComponent):
    def __init__(self):
        super().__init__("Social Security", "social_security.csv")
        self.p = _DEFAULTS.copy()
        self._base_benefit = 0.0    # $ (adjusted for claim age)
        self._cumulative = 0.0
        self._started = False

    def create_input_dialog(self, parent=None):
        return SocialSecurityDialog(self.p, parent)

    def apply_dialog(self, dlg):
        self.p = dlg.get_params()

    def load_params(self, config):
        for k in _DEFAULTS:
            if k in config:
                self.p[k] = config[k]

    def save_params(self):
        return self.p.copy()

    def reset(self):
        self._cumulative = 0.0
        self._started = False
        # Apply age-based reduction factor
        claim_age = self.p['claim_age']
        factor = _SS_AGE_FACTORS.get(claim_age, 1.00)
        self._base_benefit = self.p['ss_base'] * 1000.0 * factor

    def calc_for_year(self, ctx):
        if ctx.age >= self.p['claim_age'] and self._base_benefit > 0:
            cola = self.p['cola_rate'] / 100.0
            years_receiving = ctx.age - self.p['claim_age']
            annual = self._base_benefit * ((1 + cola) ** years_receiving)
            ctx.ss_income = annual
            self._cumulative += annual
            self._started = True
        else:
            ctx.ss_income = 0.0

        ctx.summary['ss_inc'] = ctx.ss_income / 1000.0

    def get_csv_header(self):
        return ['year', 'age', 'ss_income', 'cumulative']

    def get_csv_row(self, ctx):
        return {
            'year': ctx.year,
            'age': ctx.age,
            'ss_income': f"{ctx.ss_income / 1000.0:.1f}",
            'cumulative': f"{self._cumulative / 1000.0:.1f}",
        }

    def get_summary_fields(self, ctx):
        return {'ss_inc': ctx.ss_income / 1000.0}
