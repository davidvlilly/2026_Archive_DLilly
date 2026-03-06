"""
MainWindow — PyQt5 GUI with menus, matplotlib plot area, and component dialogs.

Menu structure:
  File:    Open | Save | Exit
  Inputs:  Sim Settings | Work Income | Pension | Social Security |
           Property: Home | Property: Investment | IRA | Roth |
           Standard Acct | Tax Settings
  Plots:   Total Net Worth | Account Balances | Income Breakdown |
           Expense Breakdown | Income vs Expense
  Action:  Execute | Exe-Compare
"""

import os
import shutil
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QAction,
                              QFileDialog, QMessageBox)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import QTimer
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from retSim_Support.sim_config import SimConfig
from retSim_Support.sim_engine import run_simulation
from retSim_Support.comp_work_income import WorkIncomeComponent
from retSim_Support.comp_pension import PensionComponent
from retSim_Support.comp_social_security import SocialSecurityComponent
from retSim_Support.comp_property import PropertyComponent
from retSim_Support.comp_standard_account import StandardAccountComponent
from retSim_Support.comp_ira_account import IRAAccountComponent
from retSim_Support.comp_roth_account import RothAccountComponent
from retSim_Support.comp_tax_liability import TaxLiabilityComponent

PARAMS_FILE = 'sim_params.json'


class RetirementSimGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retirement Simulator")

        # Create config and register components
        self.config = SimConfig()

        self.work_inc = WorkIncomeComponent()
        self.pension = PensionComponent()
        self.ss = SocialSecurityComponent()
        self.prop_home = PropertyComponent("Property: Home", "property_home.csv")
        self.prop_inv = PropertyComponent("Property: Inv", "property_inv.csv")
        self.std_acct = StandardAccountComponent()
        self.ira_acct = IRAAccountComponent()
        self.roth_acct = RothAccountComponent()
        self.tax = TaxLiabilityComponent()

        self.config.components = [
            self.work_inc, self.pension, self.ss,
            self.prop_home, self.prop_inv,
            self.std_acct, self.ira_acct, self.roth_acct,
            self.tax,
        ]

        # Load saved parameters
        self.config.load(PARAMS_FILE)

        # Simulation results (for plotting)
        self.results = None
        # Previous NW plot data for Exe-Compare overlay
        self._prev_nw_plots = []

        # Build GUI
        self._create_menus()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.figure, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.resize(1000, 700)

        # Auto-run on startup
        QTimer.singleShot(0, self.execute)

    # ── Menus ──────────────────────────────────────────────────────────

    def _create_menus(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        open_act = QAction('Open', self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.open_params)
        file_menu.addAction(open_act)

        save_act = QAction('Save', self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self.save_params)
        file_menu.addAction(save_act)

        file_menu.addSeparator()

        exit_act = QAction('Exit', self)
        exit_act.setShortcut(QKeySequence.Quit)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Inputs menu
        inputs_menu = menubar.addMenu('Inputs')

        sim_act = QAction('Sim Settings', self)
        sim_act.triggered.connect(self.edit_sim_settings)
        inputs_menu.addAction(sim_act)

        inputs_menu.addSeparator()

        for comp in self.config.components:
            act = QAction(comp.name, self)
            act.triggered.connect(self._make_edit_handler(comp))
            inputs_menu.addAction(act)

        # Plots menu
        plots_menu = menubar.addMenu('Plots')

        plot_items = [
            ('Total Net Worth', 'total'),
            ('Account Balances', 'accounts'),
            ('Income Breakdown', 'income'),
            ('Expense Breakdown', 'expense'),
            ('Income vs Expense', 'compare_io'),
        ]
        for label, plot_type in plot_items:
            act = QAction(label, self)
            act.triggered.connect(self._make_plot_handler(plot_type))
            plots_menu.addAction(act)

        # Show menu (CSV files)
        show_menu = menubar.addMenu('Show')

        show_summary = QAction('Main Summary', self)
        show_summary.triggered.connect(lambda: self.show_csv('main_summary.csv'))
        show_menu.addAction(show_summary)

        show_menu.addSeparator()

        for comp in self.config.components:
            act = QAction(f'{comp.name} Data', self)
            act.triggered.connect(self._make_show_csv_handler(comp.csv_filename))
            show_menu.addAction(act)

        # Action menu
        action_menu = menubar.addMenu('Action')

        run_act = QAction('Execute', self)
        run_act.triggered.connect(self.execute)
        action_menu.addAction(run_act)

        cmp_act = QAction('Exe-Compare', self)
        cmp_act.triggered.connect(self.execute_compare)
        action_menu.addAction(cmp_act)

    def _make_edit_handler(self, comp):
        def handler():
            dlg = comp.create_input_dialog(self)
            dlg.accepted.connect(lambda: comp.apply_dialog(dlg))
            dlg.show()
            # Prevent garbage collection
            self._active_dlg = dlg
        return handler

    def _make_plot_handler(self, plot_type):
        def handler():
            self.update_plot(plot_type)
        return handler

    def _make_show_csv_handler(self, filename):
        def handler():
            self.show_csv(filename)
        return handler

    # ── Config dialogs ─────────────────────────────────────────────────

    def edit_sim_settings(self):
        dlg = self.config.create_input_dialog(self)
        dlg.accepted.connect(lambda: self.config.apply_dialog(dlg))
        dlg.show()
        self._active_dlg = dlg

    # ── File operations ────────────────────────────────────────────────

    def open_params(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Parameters", "", "JSON Files (*.json);;All Files (*)")
        if not filename:
            return
        try:
            self.config.load(filename)
            QMessageBox.information(self, "Loaded", f"Parameters loaded from {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Error loading: {e}")

    def save_params(self):
        try:
            self.config.save(PARAMS_FILE)
            QMessageBox.information(self, "Saved", f"Parameters saved to {PARAMS_FILE}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving: {e}")

    # ── Show CSV ───────────────────────────────────────────────────────

    def show_csv(self, filename):
        filepath = os.path.join('results', filename)
        filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            QMessageBox.warning(self, "File Not Found",
                                f"{filename} not found.\nRun the simulation first.")
            return
        os.startfile(filepath)

    # ── Plotting ───────────────────────────────────────────────────────

    def update_plot(self, plot_type):
        if self.results is None:
            QMessageBox.warning(self, "No Data", "Run simulation first.")
            return

        self.ax.clear()

        if plot_type == 'total':
            self._plot_total()
        elif plot_type == 'accounts':
            self._plot_accounts()
        elif plot_type == 'income':
            self._plot_income()
        elif plot_type == 'expense':
            self._plot_expense()
        elif plot_type == 'compare_io':
            self._plot_compare_io()

        self.canvas.draw()

    def _plot_total(self):
        """Total net worth: financial accounts + RE equity."""
        # Draw previous comparison overlays (gray) first, behind current lines
        for i, prev in enumerate(self._prev_nw_plots):
            lbl_suffix = f' (prev {i+1})' if len(self._prev_nw_plots) > 1 else ' (prev)'
            prev_label_used = False
            for line_data in prev:
                label = (line_data['label'] + lbl_suffix) if not prev_label_used else None
                prev_label_used = True
                self.ax.plot(line_data['years'], line_data['values'],
                             color='gray', linewidth=1, alpha=0.5,
                             linestyle=line_data.get('linestyle', '-'),
                             label=label)

        years = [r['year'] for r in self.results]
        total_sav = [r['total_sav'] for r in self.results]
        amount_avail = [r['amount_avail'] for r in self.results]

        # Property tax liabilities (only while property has equity)
        prop_tax = [r.get('property_home_tax', 0) + r.get('property_inv_tax', 0)
                    for r in self.results]

        # Add RE equity (gross)
        total_nw = []
        for r in self.results:
            nw = r['total_sav']
            nw += r.get('property_home_eq', 0)
            nw += r.get('property_inv_eq', 0)
            total_nw.append(nw)

        # After-tax NW: financial after-tax + property equity minus property tax
        after_tax_nw = [aa + r.get('property_home_eq', 0) + r.get('property_inv_eq', 0)
                        - r.get('property_home_tax', 0) - r.get('property_inv_tax', 0)
                        for aa, r in zip(amount_avail, self.results)]

        # Property equity (home + inv combined)
        prop_eq = [r.get('property_home_eq', 0) + r.get('property_inv_eq', 0)
                   for r in self.results]

        self.ax.plot(years, total_nw, 'b-', label='Total Net Worth', linewidth=2)
        self.ax.plot(years, after_tax_nw, 'b--', label='After-Tax NW', linewidth=1.5)
        self.ax.plot(years, total_sav, 'g-', label='Financial Accts', linewidth=1.5)
        self.ax.plot(years, prop_eq, color='orange', label='Property Equity', linewidth=1.5)

        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Amount ($K)')
        self.ax.set_title('Total Net Worth')
        self.ax.set_ylim(bottom=0)
        self.ax.legend(loc='upper left')
        self.ax.grid(True, alpha=0.3)

        # Summary text
        if total_nw:
            self.ax.text(0.02, 0.98, f"Final: ${total_nw[-1]:,.0f}K",
                         transform=self.ax.transAxes, verticalalignment='top',
                         fontsize=9, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    def _plot_accounts(self):
        """Individual account balances + RE equity."""
        years = [r['year'] for r in self.results]
        ira = [r['ira_end'] for r in self.results]
        std = [r['std_end'] for r in self.results]
        roth = [r['roth_end'] for r in self.results]

        self.ax.plot(years, ira, 'b-', label='IRA', linewidth=2)
        self.ax.plot(years, std, 'g-', label='Standard', linewidth=2)
        self.ax.plot(years, roth, 'r-', label='Roth', linewidth=2)

        # RE equity
        hm_eq = [r.get('property_home_eq', 0) for r in self.results]
        inv_eq = [r.get('property_inv_eq', 0) for r in self.results]
        if any(v > 0 for v in hm_eq):
            self.ax.plot(years, hm_eq, color='orange', label='Home Equity', linewidth=2)
        if any(v > 0 for v in inv_eq):
            self.ax.plot(years, inv_eq, color='purple', label='Inv Equity', linewidth=2)

        # Event markers: inv property sale (red) and home equity loan (blue)
        for r in self.results:
            if r.get('inv_sold'):
                self.ax.plot(r['year'], r['std_end'], 'ro', markersize=10,
                             label='Inv Property Sold')
            if r.get('hm_loan'):
                self.ax.plot(r['year'], r['std_end'], 'bo', markersize=10,
                             label='Home Equity Loan')

        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Balance ($K)')
        self.ax.set_title('Account Balances & RE Equity')
        self.ax.set_ylim(bottom=0)
        self.ax.legend(loc='upper right', ncol=2)
        self.ax.grid(True, alpha=0.3)

    def _plot_income(self):
        """Income breakdown: gains, SS, pension, work, property gain."""
        years = [r['year'] for r in self.results]
        gains = [r['total_gains'] for r in self.results]
        ss = [r['ss_income'] for r in self.results]
        pension = [r['pension_income'] for r in self.results]
        work = [r['work_income'] for r in self.results]
        prop_gain = [r.get('prop_gain', 0) for r in self.results]

        self.ax.plot(years, gains, 'b-', label='Inv Gains', linewidth=1.5)
        self.ax.plot(years, ss, 'g-', label='Social Sec', linewidth=1.5)
        self.ax.plot(years, pension, 'm-', label='Pension', linewidth=1.5)
        if any(v > 0 for v in work):
            self.ax.plot(years, work, 'c-', label='Work Income', linewidth=1.5)
        if any(v > 0 for v in prop_gain):
            self.ax.plot(years, prop_gain, color='orange', label='Prop Gain', linewidth=1.5)

        # Total
        total = [g + s + p + w + pg for g, s, p, w, pg
                 in zip(gains, ss, pension, work, prop_gain)]
        self.ax.plot(years, total, color='gray', label='Total', linewidth=2.5)

        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Income ($K)')
        self.ax.set_title('Income Breakdown')
        self.ax.set_ylim(bottom=0)
        self.ax.legend(loc='upper right')
        self.ax.grid(True, alpha=0.3)

    def _plot_expense(self):
        """Expense breakdown: draw, tax, property debt."""
        years = [r['year'] for r in self.results]
        draw = [r['draw'] for r in self.results]
        tax = [r['total_tax'] for r in self.results]

        self.ax.plot(years, draw, 'b-', label='Draw', linewidth=1.5)
        self.ax.plot(years, tax, 'r-', label='Tax', linewidth=1.5)

        # Property debt service
        hm_debt = [r.get('property_home_debt', 0) for r in self.results]
        inv_debt = [r.get('property_inv_debt', 0) for r in self.results]
        hel_debt = [r.get('hm_loan_debt', 0) for r in self.results]
        if any(v > 0 for v in hm_debt):
            self.ax.plot(years, hm_debt, color='orange', label='Hm Debt', linewidth=1.5)
        if any(v > 0 for v in inv_debt):
            self.ax.plot(years, inv_debt, color='purple', label='Inv Debt', linewidth=1.5)
        if any(v > 0 for v in hel_debt):
            self.ax.plot(years, hel_debt, color='brown', label='HEL Debt Svc', linewidth=1.5)

        # Total
        total = [d + t + h + iv + hel for d, t, h, iv, hel
                 in zip(draw, tax, hm_debt, inv_debt, hel_debt)]
        self.ax.plot(years, total, color='gray', label='Total', linewidth=2.5)

        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Expense ($K)')
        self.ax.set_title('Expense Breakdown')
        self.ax.set_ylim(bottom=0)
        self.ax.legend(loc='upper right')
        self.ax.grid(True, alpha=0.3)

    def _plot_compare_io(self):
        """Total income vs total expense."""
        years = [r['year'] for r in self.results]

        inc = [r['total_gains'] + r['ss_income'] + r['pension_income'] + r['work_income']
               + r.get('prop_gain', 0)
               for r in self.results]
        exp = [r['draw'] + r['total_tax']
               + r.get('property_home_debt', 0) + r.get('property_inv_debt', 0)
               + r.get('hm_loan_debt', 0)
               for r in self.results]

        self.ax.plot(years, inc, 'g-', label='Total Income', linewidth=2)
        self.ax.plot(years, exp, 'r-', label='Total Expense', linewidth=2)

        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Amount ($K)')
        self.ax.set_title('Income vs Expense')
        self.ax.set_ylim(bottom=0)
        self.ax.legend(loc='upper right')
        self.ax.grid(True, alpha=0.3)

    # ── Simulation ─────────────────────────────────────────────────────

    def _snapshot_nw_plots(self):
        """Capture current Total Net Worth plot data from self.results."""
        if not self.results:
            return None
        years = [r['year'] for r in self.results]
        total_nw = []
        for r in self.results:
            nw = r['total_sav']
            nw += r.get('property_home_eq', 0)
            nw += r.get('property_inv_eq', 0)
            total_nw.append(nw)
        total_sav = [r['total_sav'] for r in self.results]
        amount_avail = [r['amount_avail'] for r in self.results]
        after_tax_nw = [r['amount_avail']
                        + r.get('property_home_eq', 0) + r.get('property_inv_eq', 0)
                        - r.get('property_home_tax', 0) - r.get('property_inv_tax', 0)
                        for r in self.results]
        prop_eq = [r.get('property_home_eq', 0) + r.get('property_inv_eq', 0)
                   for r in self.results]
        return [
            {'years': years, 'values': total_nw, 'label': 'Total NW', 'linestyle': '-'},
            {'years': years, 'values': after_tax_nw, 'label': 'After-Tax NW', 'linestyle': '--'},
            {'years': years, 'values': total_sav, 'label': 'Fin Accts', 'linestyle': '-'},
            {'years': years, 'values': prop_eq, 'label': 'Prop Eq', 'linestyle': '-'},
        ]

    def execute(self):
        """Run simulation and display results."""
        # Clear comparison overlays on a normal Execute
        self._prev_nw_plots = []

        try:
            self.results = run_simulation(self.config)
        except Exception as e:
            QMessageBox.critical(self, "Simulation Error",
                                 f"Error during simulation:\n{str(e)}")
            import traceback
            traceback.print_exc()
            return

        # Show default plot
        self.ax.clear()
        self._plot_total()
        self.canvas.draw()

        # Print summary
        if self.results:
            r = self.results[-1]
            print(f"\nSimulation complete: {self.config.year_start}-{self.config.year_stop}")
            print(f"  Final Total Savings: ${r['total_sav']:,.0f}K")
            print(f"  Final IRA: ${r['ira_end']:,.0f}K  "
                  f"Std: ${r['std_end']:,.0f}K  "
                  f"Roth: ${r['roth_end']:,.0f}K")

    def execute_compare(self):
        """Snapshot current NW plots, re-run simulation, overlay previous as gray."""
        # Copy current results to results_prev, renaming files with _prev suffix
        results_dir = 'results'
        prev_dir = 'results_prev'
        if os.path.isdir(results_dir):
            if os.path.isdir(prev_dir):
                shutil.rmtree(prev_dir)
            os.makedirs(prev_dir)
            for fname in os.listdir(results_dir):
                src = os.path.join(results_dir, fname)
                if os.path.isfile(src):
                    base, ext = os.path.splitext(fname)
                    dst = os.path.join(prev_dir, f"{base}_prev{ext}")
                    shutil.copy2(src, dst)

        # Snapshot existing results before re-running
        snap = self._snapshot_nw_plots()
        if snap:
            self._prev_nw_plots.append(snap)

        try:
            self.results = run_simulation(self.config)
        except Exception as e:
            QMessageBox.critical(self, "Simulation Error",
                                 f"Error during simulation:\n{str(e)}")
            import traceback
            traceback.print_exc()
            return

        # Show Total Net Worth plot with gray overlay
        self.ax.clear()
        self._plot_total()
        self.canvas.draw()

        # Print summary
        if self.results:
            r = self.results[-1]
            print(f"\nCompare run complete: {self.config.year_start}-{self.config.year_stop}")
            print(f"  Final Total Savings: ${r['total_sav']:,.0f}K")
            print(f"  Final IRA: ${r['ira_end']:,.0f}K  "
                  f"Std: ${r['std_end']:,.0f}K  "
                  f"Roth: ${r['roth_end']:,.0f}K")
