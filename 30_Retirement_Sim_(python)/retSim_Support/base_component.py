"""
BaseComponent — abstract base class for all financial components.

Every income source, asset account, and cost element inherits from this class
and implements its own parameter dialog, yearly calculation, and CSV output.
"""

from abc import ABC, abstractmethod


class BaseComponent(ABC):
    """Abstract base for all simulation components."""

    def __init__(self, name, csv_filename):
        self.name = name
        self.csv_filename = csv_filename

    @abstractmethod
    def create_input_dialog(self, parent):
        """Return a QDialog for editing this component's parameters."""
        pass

    @abstractmethod
    def load_params(self, config):
        """Load parameters from a dict (one section of sim_params.json)."""
        pass

    @abstractmethod
    def save_params(self):
        """Return parameters as a dict for JSON serialization."""
        pass

    @abstractmethod
    def calc_for_year(self, ctx):
        """Perform this component's calculation for one year.
        Reads from and writes to the YearContext.
        """
        pass

    @abstractmethod
    def get_csv_header(self):
        """Return list of column names for this component's CSV."""
        pass

    @abstractmethod
    def get_csv_row(self, ctx):
        """Return dict of values for this year's CSV row."""
        pass

    def get_summary_fields(self, ctx):
        """Return dict of {column_name: value} for main_summary.csv.
        Override in subclasses to contribute columns.
        """
        return {}

    def reset(self):
        """Reset internal state for a new simulation run.
        Override in subclasses that carry state year-to-year (e.g. accounts).
        """
        pass
