"""
Property component — real estate (home or investment).

Instantiate once per property. Tracks value appreciation, loan amortization,
debt service, rental income, and equity. Reports net cost (debt - rental)
into YearContext for the engine to incorporate into the draw.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt
from retSim_Support.base_component import BaseComponent


_DEFAULTS = {
    'prop_value': 0.0,          # $K
    'equity': 0.0,              # $K
    'loan_service': 0.0,        # $K/yr
    'year_paid_off': 0,
    'rental_income': 0.0,       # $K/yr (0 for primary home)
    'appreciation_rate': 3.0,   # %
    'rental_cola': 2.5,         # % annual rental increase
    'tax_liability': 0.0,       # $K — estimated tax owed if property is sold
}


def _find_implied_rate(loan, annual_payment, years):
    """Find implied annual interest rate via bisection."""
    if loan <= 0 or annual_payment <= 0 or years <= 0:
        return 0
    if annual_payment * years <= loan:
        return 0
    lo, hi = 0.001, 0.20
    for _ in range(100):
        mid = (lo + hi) / 2
        pmt = loan * mid / (1 - (1 + mid) ** (-years))
        if pmt < annual_payment:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class PropertyDialog(QDialog):
    def __init__(self, title, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        field_defs = [
            ('prop_value', 'Property Value ($K)'),
            ('equity', 'Equity ($K)'),
            ('loan_service', 'Loan Service ($K/yr)'),
            ('year_paid_off', 'Year Paid Off'),
            ('rental_income', 'Rental Income ($K/yr)'),
            ('appreciation_rate', 'Appreciation (%)'),
            ('rental_cola', 'Rental COLA (%)'),
            ('tax_liability', 'Tax Liability ($K)'),
        ]
        for i, (key, label) in enumerate(field_defs):
            grid.addWidget(QLabel(label), i, 0)
            edit = QLineEdit(str(params.get(key, _DEFAULTS.get(key, ''))))
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
            'prop_value': float(self.fields['prop_value'].text()),
            'equity': float(self.fields['equity'].text()),
            'loan_service': float(self.fields['loan_service'].text()),
            'year_paid_off': int(self.fields['year_paid_off'].text()),
            'rental_income': float(self.fields['rental_income'].text()),
            'appreciation_rate': float(self.fields['appreciation_rate'].text()),
            'rental_cola': float(self.fields['rental_cola'].text()),
            'tax_liability': float(self.fields['tax_liability'].text()),
        }


class PropertyComponent(BaseComponent):
    """Real estate component. Instantiate with unique name/csv per property."""

    def __init__(self, name="Property: Home", csv_filename="property_home.csv"):
        super().__init__(name, csv_filename)
        self.p = _DEFAULTS.copy()

        # Internal state (carried year to year)
        self._prop_value = 0.0      # $ current value
        self._loan_balance = 0.0    # $ remaining loan
        self._loan_rate = 0.0       # Implied interest rate
        self._rental = 0.0          # $ current annual rental
        self._debt_service = 0.0    # $ this year's debt service
        self._equity = 0.0          # $ current equity
        self._appreciation = 0.0    # $ this year's appreciation
        self._hel_balance = 0.0     # $ home equity loan remaining
        self._hel_debt_service = 0.0  # $ this year's HEL payment

    def create_input_dialog(self, parent=None):
        return PropertyDialog(self.name, self.p, parent)

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
        self._prop_value = self.p['prop_value'] * K
        self._loan_balance = (self.p['prop_value'] - self.p['equity']) * K
        self._rental = self.p['rental_income'] * K

        # Compute implied rate for amortization schedule
        # Need year_start from sim config — will be set by engine before first calc
        self._loan_rate = 0.0
        self._debt_service = 0.0
        self._equity = self.p['equity'] * K
        self._hel_balance = 0.0
        self._hel_debt_service = 0.0

    def init_amortization(self, year_start):
        """Called by engine after reset to compute implied loan rate."""
        K = 1000.0
        loan = (self.p['prop_value'] - self.p['equity']) * K
        svc = self.p['loan_service'] * K
        years = self.p['year_paid_off'] - year_start
        self._loan_rate = _find_implied_rate(loan, svc, years)

    def calc_for_year(self, ctx):
        K = 1000.0
        appr_rate = self.p['appreciation_rate'] / 100.0
        rental_cola = self.p['rental_cola'] / 100.0
        self._hel_debt_service = 0.0  # Reset; set later by engine if HEL active

        # Debt service
        if ctx.year < self.p['year_paid_off'] and self._loan_balance > 0:
            self._debt_service = self.p['loan_service'] * K
            # Amortization: interest then principal
            interest = self._loan_balance * self._loan_rate
            principal = max(0, self._debt_service - interest)
            self._loan_balance = max(0, self._loan_balance - principal)
        else:
            self._debt_service = 0.0
            self._loan_balance = 0.0

        # Rental income
        current_rental = self._rental if self._prop_value > 0 else 0.0

        # Appreciate property
        self._appreciation = self._prop_value * appr_rate
        self._prop_value += self._appreciation

        # Equity (reduced by any home equity loan outstanding)
        self._equity = self._prop_value - self._loan_balance - self._hel_balance

        # Report to context
        ctx.rental_income += current_rental
        ctx.property_debt_service += self._debt_service
        ctx.property_net_cost += (self._debt_service - current_rental)

        # Summary: report equity for this property
        summary_key = self.csv_filename.replace('.csv', '_eq')
        ctx.summary[summary_key] = self._equity / K

        # Advance rental for next year
        self._rental *= (1 + rental_cola)

    def mark_sold(self):
        """Zero out all internal state after property is sold."""
        self._prop_value = 0.0
        self._loan_balance = 0.0
        self._rental = 0.0
        self._debt_service = 0.0
        self._equity = 0.0
        self._hel_balance = 0.0
        self._hel_debt_service = 0.0

    def take_equity_loan(self, amount):
        """Record a home equity loan taken against this property."""
        self._hel_balance += amount

    def apply_hel_payment(self, total_payment, rate):
        """Amortize home equity loan for one year."""
        if self._hel_balance <= 0:
            self._hel_debt_service = 0.0
            return
        self._hel_debt_service = total_payment
        interest = self._hel_balance * rate
        principal = total_payment - interest
        self._hel_balance = max(0, self._hel_balance - principal)

    def recalc_equity(self):
        """Recalculate equity after HEL amortization."""
        self._equity = self._prop_value - self._loan_balance - self._hel_balance

    def get_appreciation(self):
        """Return this year's appreciation in dollars."""
        return self._appreciation

    def get_equity(self):
        """Return current equity in dollars."""
        return self._equity

    def get_tax_liability(self):
        """Return estimated tax liability on sale in dollars."""
        return self.p.get('tax_liability', 0) * 1000.0

    def get_prop_value(self):
        """Return current property value in dollars."""
        return self._prop_value

    def get_debt_service(self):
        """Return this year's debt service in dollars."""
        return self._debt_service

    def get_csv_header(self):
        return ['year', 'prop_value', 'equity', 'remaining_loan',
                'debt_service', 'rental_income', 'hel_debt_service']

    def get_csv_row(self, ctx):
        K = 1000.0
        return {
            'year': ctx.year,
            'prop_value': f"{self._prop_value / K:.1f}",
            'equity': f"{self._equity / K:.1f}",
            'remaining_loan': f"{self._loan_balance / K:.1f}",
            'debt_service': f"{self._debt_service / K:.1f}",
            'rental_income': f"{(ctx.rental_income if self.p['rental_income'] > 0 else 0) / K:.1f}",
            'hel_debt_service': f"{self._hel_debt_service / K:.1f}",
        }

    def get_summary_fields(self, ctx):
        K = 1000.0
        key = self.csv_filename.replace('.csv', '_eq')
        return {key: self._equity / K}
