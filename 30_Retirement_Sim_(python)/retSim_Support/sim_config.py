"""
SimConfig — global simulation parameters and component registry.

Owns the top-level settings (year range, birth year, draw, inflation, returns)
and the list of active components. Handles JSON load/save for the entire config.
"""

import json
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt


# Field definitions: (key, label, type)
_SIM_FIELDS = [
    ('year_start', 'Start Year', int),
    ('year_stop', 'End Year', int),
    ('birth_year', 'Birth Year', int),
    ('draw_start', 'Draw ($K/yr)', float),
    ('draw_cola', 'Draw COLA (%)', float),
    ('inflation', 'Inflation (%)', float),
    ('stock_ror', 'Stock ROR (%)', float),
    ('fixed_ror', 'Fixed ROR (%)', float),
    ('stock_pct', 'Stock Alloc (%)', float),
]

_SIM_DEFAULTS = {
    'year_start': 2028,
    'year_stop': 2070,
    'birth_year': 1975,
    'draw_start': 190.0,
    'draw_cola': 2.5,
    'inflation': 2.5,
    'stock_ror': 7.0,
    'fixed_ror': 4.0,
    'stock_pct': 70.0,
}


class SimConfigDialog(QDialog):
    """Dialog for editing global simulation parameters."""

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simulation Settings")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.fields = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        for i, (key, label, _) in enumerate(_SIM_FIELDS):
            lbl = QLabel(label)
            grid.addWidget(lbl, i, 0)
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
        result = {}
        for key, label, typ in _SIM_FIELDS:
            result[key] = typ(self.fields[key].text())
        return result


class SimConfig:
    """Global simulation configuration and component registry."""

    def __init__(self):
        self.params = _SIM_DEFAULTS.copy()
        self.components = []        # list of BaseComponent instances

    # ── Properties for convenience ──

    @property
    def year_start(self):
        return self.params['year_start']

    @property
    def year_stop(self):
        return self.params['year_stop']

    @property
    def birth_year(self):
        return self.params['birth_year']

    @property
    def draw_start(self):
        return self.params['draw_start']

    @property
    def draw_cola(self):
        return self.params['draw_cola'] / 100.0

    @property
    def inflation(self):
        return self.params['inflation'] / 100.0

    @property
    def stock_ror(self):
        return self.params['stock_ror'] / 100.0

    @property
    def fixed_ror(self):
        return self.params['fixed_ror'] / 100.0

    @property
    def stock_pct(self):
        return self.params['stock_pct'] / 100.0

    def age_at(self, year):
        return year - self.birth_year

    # ── Component registry ──

    def get_component(self, name):
        """Find a component by name."""
        for c in self.components:
            if c.name == name:
                return c
        return None

    def get_components_by_type(self, cls):
        """Find all components of a given class."""
        return [c for c in self.components if isinstance(c, cls)]

    # ── Dialog ──

    def create_input_dialog(self, parent=None):
        return SimConfigDialog(self.params, parent)

    def apply_dialog(self, dlg):
        self.params = dlg.get_params()

    # ── JSON load/save ──

    def load(self, filepath):
        """Load config from JSON file. Components must already be registered."""
        if not os.path.exists(filepath):
            return False
        with open(filepath, 'r') as f:
            data = json.load(f)

        if 'sim' in data:
            for key in _SIM_DEFAULTS:
                if key in data['sim']:
                    self.params[key] = data['sim'][key]

        # Load each component's section
        for comp in self.components:
            section_key = comp.csv_filename.replace('.csv', '')
            if section_key in data:
                comp.load_params(data[section_key])

        return True

    def save(self, filepath):
        """Save entire config to JSON file."""
        data = {'sim': self.params.copy()}
        for comp in self.components:
            section_key = comp.csv_filename.replace('.csv', '')
            data[section_key] = comp.save_params()

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
