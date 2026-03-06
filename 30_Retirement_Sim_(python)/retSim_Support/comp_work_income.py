"""
Work Income component — employment salary before retirement.

Reports ordinary income while age <= end_age. Applies annual COLA.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent


_DEFAULTS = {
    'annual_salary': 0.0,      # $K per year
    'end_age': 53,              # Last year of work
    'cola_rate': 3.0,           # Annual raise %
}


class WorkIncomeDialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Work Income")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        field_defs = [
            ('annual_salary', 'Annual Salary ($K)'),
            ('end_age', 'Last Work Age'),
            ('cola_rate', 'Annual Raise (%)'),
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
            'annual_salary': float(self.fields['annual_salary'].text()),
            'end_age': int(self.fields['end_age'].text()),
            'cola_rate': float(self.fields['cola_rate'].text()),
        }


class WorkIncomeComponent(BaseComponent):
    def __init__(self):
        super().__init__("Work Income", "work_income.csv")
        self.p = _DEFAULTS.copy()
        self._base_salary = 0.0     # $ (converted from $K at sim start)

    def create_input_dialog(self, parent=None):
        return WorkIncomeDialog(self.p, parent)

    def apply_dialog(self, dlg):
        self.p = dlg.get_params()

    def load_params(self, config):
        for k in _DEFAULTS:
            if k in config:
                self.p[k] = config[k]

    def save_params(self):
        return self.p.copy()

    def reset(self):
        self._base_salary = self.p['annual_salary'] * 1000.0

    def calc_for_year(self, ctx):
        if ctx.age <= self.p['end_age'] and self._base_salary > 0:
            cola = self.p['cola_rate'] / 100.0
            years_working = ctx.age - (self.p['end_age'] - 0)  # doesn't matter, use year offset
            # Apply COLA from year 0 of simulation
            income = self._base_salary
            ctx.work_income = income
            # Advance salary for next year (called once per year)
            self._base_salary *= (1 + cola)
        else:
            ctx.work_income = 0.0

        ctx.summary['work_inc'] = ctx.work_income / 1000.0

    def get_csv_header(self):
        return ['year', 'age', 'work_income']

    def get_csv_row(self, ctx):
        return {
            'year': ctx.year,
            'age': ctx.age,
            'work_income': f"{ctx.work_income / 1000.0:.1f}",
        }

    def get_summary_fields(self, ctx):
        return {'work_inc': ctx.work_income / 1000.0}
