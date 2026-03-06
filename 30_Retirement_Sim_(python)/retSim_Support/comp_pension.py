"""
Pension component — supports Simple mode (direct entry) and Formula mode (CalPERS).

Simple mode: user enters annual benefit, start age, COLA.
Formula mode: user selects plan type, enters salary/service details; benefit is computed.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QComboBox, QDialogButtonBox,
                              QGroupBox, QRadioButton, QHBoxLayout)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent


# CalPERS 2% at 55 benefit factor table: age -> (exact, +1/4, +1/2, +3/4) as percentages
_CALPERS_2_AT_55 = {
    50: (1.100, 1.146, 1.190, 1.236),
    51: (1.280, 1.326, 1.370, 1.416),
    52: (1.460, 1.506, 1.550, 1.596),
    53: (1.640, 1.686, 1.730, 1.776),
    54: (1.820, 1.866, 1.910, 1.956),
    55: (2.000, 2.016, 2.032, 2.048),
    56: (2.064, 2.080, 2.096, 2.110),
    57: (2.126, 2.142, 2.158, 2.172),
    58: (2.188, 2.204, 2.220, 2.236),
    59: (2.250, 2.268, 2.282, 2.298),
    60: (2.314, 2.330, 2.346, 2.360),
    61: (2.376, 2.392, 2.406, 2.422),
    62: (2.438, 2.454, 2.470, 2.486),
    63: (2.500, 2.500, 2.500, 2.500),
}

# CalPERS 2% at 60 benefit factor table
_CALPERS_2_AT_60 = {
    50: (1.092, 1.114, 1.136, 1.158),
    51: (1.180, 1.202, 1.224, 1.246),
    52: (1.268, 1.290, 1.312, 1.334),
    53: (1.356, 1.378, 1.400, 1.422),
    54: (1.444, 1.466, 1.488, 1.510),
    55: (1.532, 1.554, 1.576, 1.598),
    56: (1.620, 1.642, 1.664, 1.686),
    57: (1.708, 1.730, 1.752, 1.774),
    58: (1.796, 1.818, 1.840, 1.862),
    59: (1.884, 1.906, 1.928, 1.950),
    60: (2.000, 2.016, 2.032, 2.048),
    61: (2.064, 2.080, 2.096, 2.110),
    62: (2.126, 2.142, 2.158, 2.172),
    63: (2.188, 2.188, 2.188, 2.188),
}

# CalPERS 2% at 62 benefit factor table
_CALPERS_2_AT_62 = {
    52: (1.000, 1.020, 1.040, 1.060),
    53: (1.080, 1.100, 1.120, 1.140),
    54: (1.160, 1.180, 1.200, 1.220),
    55: (1.240, 1.260, 1.280, 1.300),
    56: (1.320, 1.340, 1.360, 1.380),
    57: (1.400, 1.420, 1.440, 1.460),
    58: (1.480, 1.500, 1.520, 1.540),
    59: (1.560, 1.580, 1.600, 1.620),
    60: (1.640, 1.660, 1.680, 1.700),
    61: (1.720, 1.740, 1.760, 1.780),
    62: (2.000, 2.025, 2.050, 2.075),
    63: (2.100, 2.125, 2.150, 2.175),
    64: (2.200, 2.225, 2.250, 2.275),
    65: (2.300, 2.325, 2.350, 2.375),
    66: (2.400, 2.425, 2.450, 2.475),
    67: (2.500, 2.500, 2.500, 2.500),
}

_PLAN_TABLES = {
    'calpers_2_at_55': _CALPERS_2_AT_55,
    'calpers_2_at_60': _CALPERS_2_AT_60,
    'calpers_2_at_62': _CALPERS_2_AT_62,
}

_PLAN_LABELS = {
    'calpers_2_at_55': 'CalPERS 2% @ 55',
    'calpers_2_at_60': 'CalPERS 2% @ 60',
    'calpers_2_at_62': 'CalPERS 2% @ 62',
    'custom_flat': 'Custom Flat Rate',
}

_DEFAULTS = {
    'mode': 'simple',
    'annual_benefit': 55.0,     # $K
    'start_age': 53,
    'cola_rate': 2.0,
    'sepp_rate': 5.0,           # % — 72(t) SEPP interest rate for IRA early withdrawals
    # Formula mode
    'plan_type': 'calpers_2_at_55',
    'final_salary': 170.0,      # $K
    'service_start_age': 30,
    'service_end_age': 53,
    'custom_factor': 2.0,       # % for custom flat rate
}


def _get_benefit_factor(plan_type, retirement_age):
    """Look up benefit factor (%) for given plan and age."""
    if plan_type == 'custom_flat':
        return None  # handled separately
    table = _PLAN_TABLES.get(plan_type)
    if not table:
        return 2.0
    max_age = max(table.keys())
    if retirement_age >= max_age:
        return table[max_age][0]
    base_age = int(retirement_age)
    fraction = retirement_age - base_age
    quarter = round(fraction * 4)
    if quarter == 4:
        base_age += 1
        quarter = 0
    if base_age >= max_age:
        return table[max_age][0]
    min_age = min(table.keys())
    if base_age < min_age:
        return table[min_age][0]
    return table[base_age][quarter]


def _compute_pension(p):
    """Compute annual pension from formula parameters. Returns $ amount."""
    retirement_age = p['service_end_age']
    years_of_service = retirement_age - p['service_start_age']
    if years_of_service <= 0:
        return 0.0
    final_salary = p['final_salary'] * 1000.0

    if p['plan_type'] == 'custom_flat':
        factor = p.get('custom_factor', 2.0) / 100.0
    else:
        factor = _get_benefit_factor(p['plan_type'], retirement_age) / 100.0

    return factor * years_of_service * final_salary


class PensionDialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pension Configuration")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)

        # Mode selection
        mode_layout = QHBoxLayout()
        self.radio_simple = QRadioButton("Simple")
        self.radio_formula = QRadioButton("Formula")
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.radio_simple)
        mode_layout.addWidget(self.radio_formula)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Simple group
        simple_box = QGroupBox("Simple")
        simple_grid = QGridLayout()
        for i, (key, label) in enumerate([
            ('annual_benefit', 'Annual Benefit ($K)'),
            ('start_age', 'Start Age'),
            ('cola_rate', 'COLA Rate (%)'),
            ('sepp_rate', 'SEPP Rate (%)'),
        ]):
            simple_grid.addWidget(QLabel(label), i, 0)
            edit = QLineEdit(str(params.get(key, '')))
            edit.setFixedWidth(100)
            simple_grid.addWidget(edit, i, 1)
            self.fields[key] = edit
        simple_box.setLayout(simple_grid)
        layout.addWidget(simple_box)

        # Formula group
        formula_box = QGroupBox("Formula")
        formula_grid = QGridLayout()

        # Plan type combo
        formula_grid.addWidget(QLabel("Plan Type"), 0, 0)
        self.plan_combo = QComboBox()
        for plan_key, plan_label in _PLAN_LABELS.items():
            self.plan_combo.addItem(plan_label, plan_key)
        current_plan = params.get('plan_type', 'calpers_2_at_55')
        idx = list(_PLAN_LABELS.keys()).index(current_plan) if current_plan in _PLAN_LABELS else 0
        self.plan_combo.setCurrentIndex(idx)
        formula_grid.addWidget(self.plan_combo, 0, 1)

        for i, (key, label) in enumerate([
            ('final_salary', 'Final Salary ($K)'),
            ('service_start_age', 'Service Start Age'),
            ('service_end_age', 'Service End Age'),
            ('custom_factor', 'Custom Factor (%)'),
        ], start=1):
            formula_grid.addWidget(QLabel(label), i, 0)
            edit = QLineEdit(str(params.get(key, '')))
            edit.setFixedWidth(100)
            formula_grid.addWidget(edit, i, 1)
            self.fields[key] = edit

        # Computed benefit (read-only)
        formula_grid.addWidget(QLabel("Computed Benefit ($K/yr)"), 6, 0)
        self.computed_label = QLabel("--")
        formula_grid.addWidget(self.computed_label, 6, 1)

        formula_box.setLayout(formula_grid)
        layout.addWidget(formula_box)

        # Wire up mode radio and compute button
        if params.get('mode', 'simple') == 'formula':
            self.radio_formula.setChecked(True)
        else:
            self.radio_simple.setChecked(True)

        # Auto-compute on field changes
        for key in ('final_salary', 'service_start_age', 'service_end_age', 'custom_factor'):
            self.fields[key].textChanged.connect(self._update_computed)
        self.plan_combo.currentIndexChanged.connect(self._update_computed)
        self._update_computed()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_computed(self):
        try:
            p = {
                'plan_type': self.plan_combo.currentData(),
                'final_salary': float(self.fields['final_salary'].text()),
                'service_start_age': int(self.fields['service_start_age'].text()),
                'service_end_age': int(self.fields['service_end_age'].text()),
                'custom_factor': float(self.fields['custom_factor'].text()),
            }
            benefit = _compute_pension(p) / 1000.0
            self.computed_label.setText(f"${benefit:,.1f}K")
        except (ValueError, KeyError):
            self.computed_label.setText("--")

    def get_params(self):
        mode = 'formula' if self.radio_formula.isChecked() else 'simple'
        return {
            'mode': mode,
            'annual_benefit': float(self.fields['annual_benefit'].text()),
            'start_age': int(self.fields['start_age'].text()),
            'cola_rate': float(self.fields['cola_rate'].text()),
            'sepp_rate': float(self.fields['sepp_rate'].text()),
            'plan_type': self.plan_combo.currentData(),
            'final_salary': float(self.fields['final_salary'].text()),
            'service_start_age': int(self.fields['service_start_age'].text()),
            'service_end_age': int(self.fields['service_end_age'].text()),
            'custom_factor': float(self.fields['custom_factor'].text()),
        }


class PensionComponent(BaseComponent):
    def __init__(self):
        super().__init__("Pension", "pension.csv")
        self.p = _DEFAULTS.copy()
        self._base_pension = 0.0    # $ annual (computed at sim start)
        self._cumulative = 0.0

    def create_input_dialog(self, parent=None):
        return PensionDialog(self.p, parent)

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
        if self.p['mode'] == 'formula':
            self._base_pension = _compute_pension(self.p)
        else:
            self._base_pension = self.p['annual_benefit'] * 1000.0

    def calc_for_year(self, ctx):
        start_age = self.p['start_age'] if self.p['mode'] == 'simple' else self.p['service_end_age']
        if ctx.age >= start_age and self._base_pension > 0:
            cola = self.p['cola_rate'] / 100.0
            years_receiving = ctx.age - start_age
            annual = self._base_pension * ((1 + cola) ** years_receiving)
            ctx.pension_income = annual
            self._cumulative += annual
        else:
            ctx.pension_income = 0.0

        ctx.summary['pension'] = ctx.pension_income / 1000.0

    def get_csv_header(self):
        return ['year', 'age', 'annual_pension', 'cumulative']

    def get_csv_row(self, ctx):
        return {
            'year': ctx.year,
            'age': ctx.age,
            'annual_pension': f"{ctx.pension_income / 1000.0:.1f}",
            'cumulative': f"{self._cumulative / 1000.0:.1f}",
        }

    def get_summary_fields(self, ctx):
        return {'pension': ctx.pension_income / 1000.0}
