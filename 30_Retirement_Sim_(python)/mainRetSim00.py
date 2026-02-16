"""
mainRetSim00.py - Retirement Simulation Tool with GUI

Generates year-by-year retirement projections based on input parameters.
Allows comparison of two plans with graphical output.
Generates PDF report with parameters and comparison plots.
"""

import sys
import csv
import io
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QGridLayout, QLabel, QLineEdit, 
                              QPushButton, QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from calc_year import calculate_year

# PDF imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors


def parse_stock_fixed(ratio_str):
    """Parse '70/30' format into stock_pct and fixed_pct."""
    if isinstance(ratio_str, str):
        parts = ratio_str.split('/')
        stock = float(parts[0])
        fixed = float(parts[1])
    else:
        stock = ratio_str
        fixed = 100 - stock
    return stock, fixed


def calc_ss_benefit(ss_base, ss_age):
    """
    Calculate SS benefit based on claiming age.
    ss_base is the benefit at age 69.
    Each year earlier reduces benefit by ~8%.
    """
    adjustments = {
        66: 0.76,
        67: 0.84,
        68: 0.92,
        69: 1.00
    }
    factor = adjustments.get(ss_age, 1.00)
    return ss_base * factor


def run_simulation(config):
    """
    Run retirement simulation from config dict.
    Config values for money are in $K units, converted to dollars internally.
    Returns: list of dicts, one per year (values in $K units)
    """
    stock_pct, fixed_pct = parse_stock_fixed(config['stock_fixed'])
    
    # Convert $K inputs to dollars for calculation
    K = 1000
    
    results = []
    
    prev_ira_end = config['ira_sav'] * K
    prev_std_end = config['std_sav'] * K
    prev_roth_end = config.get('roth_sav', 0) * K
    
    # stdPreTax is the unrealized gain (appreciation) in the stock portion
    # cost_basis = stock_value - stdPreTax
    std_pretax = config.get('std_pretax', 0) * K
    stock_pct_decimal = stock_pct / 100.0
    prev_std_cost_basis = config['std_sav'] * K * stock_pct_decimal - std_pretax
    
    draw = config['draw_start'] * K
    inflation = config['inflation'] / 100.0
    roth_conv_threshold = config.get('roth_conv_threshold', 0) * K
    
    ss_age = config['SS_age']
    ss_yr_start = config['year_start'] + (ss_age - config['age'])
    ss_inc_start = calc_ss_benefit(config['SS_base'], ss_age) * K
    
    SS_inc = ss_inc_start
    SS_cola = config.get('SS_cola', 2.5) / 100.0
    
    age = config['age']
    
    for year in range(config['year_start'], config['year_stop'] + 1):
        if year >= ss_yr_start:
            current_SS = SS_inc
        else:
            current_SS = 0
        
        params = {
            'year': year,
            'age': age,
            'draw': draw,
            'SS_inc': current_SS,
            'stock_ROR': config['stock_ROR'],
            'fixed_ROR': config['fixed_ROR'],
            'stock_pct': stock_pct,
            'fixed_pct': fixed_pct,
            'roth_conv_threshold': roth_conv_threshold
        }
        
        row = calculate_year(params, prev_ira_end, prev_std_end, prev_roth_end, prev_std_cost_basis)
        
        # Convert dollar values to $K for output
        row_k = {}
        dollar_fields = ['draw', 'ira_beg', 'std_beg', 'roth_beg', 'SS_inc', 'RMD', 
                         'ira_pull', 'roth_conv', 'roth_pull', 
                         'total_inc', 'ord_inc', 'pref_inc',
                         'ord_tax', 'pref_tax', 'ca_tax', 'total_tax',
                         'ira_end', 'std_end', 'roth_end', 'total_sav', 'amount_avail', 
                         'std_stock_gain', 'LTCapGn',
                         'total_gains', 'total_expenses', 'net_gain_loss']
        for k, v in row.items():
            if k in ('std_stock_basis', 'std_taxable_gain'):
                continue  # skip, we output std_pretax instead
            elif k in dollar_fields:
                row_k[k] = v / K
            else:
                row_k[k] = v
        
        # Add std_pretax: unrealized gain = stock_value_end - basis
        stock_value_end = row['std_end'] * (stock_pct / 100.0)
        row_k['std_pretax'] = (stock_value_end - row['std_stock_basis']) / K
        
        results.append(row_k)
        
        prev_ira_end = row['ira_end']
        prev_std_end = row['std_end']
        prev_roth_end = row['roth_end']
        prev_std_cost_basis = row['std_stock_basis']
        age += 1
        draw *= (1 + inflation)
        
        # Only apply COLA after SS payments have started
        if year >= ss_yr_start:
            SS_inc *= (1 + SS_cola)
        
        if prev_ira_end <= 0 and prev_std_end <= 0 and prev_roth_end <= 0:
            break
    
    return results


def write_csv(results, filename):
    """Write results to CSV file."""
    if not results:
        return
    
    columns = [
        'year', 'age', 'draw', 'std_beg', 'ira_beg', 'roth_beg', 'SS_inc',
        'life_exp', 'RMD', 'ira_pull', 'roth_conv', 'roth_pull',
        'total_inc', 'ord_inc', 'pref_inc', 'ord_tax', 'pref_tax', 'ca_tax', 'total_tax',
        'std_end', 'ira_end', 'roth_end', 'total_sav', 'amount_avail',
        'std_stock_gain', 'std_pretax', 'LTCapGn',
        'total_gains', 'total_expenses', 'net_gain_loss',
        'marg_rate', 'tax_rate'
    ]
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in results:
            formatted = {}
            for k, v in row.items():
                if k in ['year', 'age']:
                    formatted[k] = v
                elif k in ['tax_rate', 'marg_rate']:
                    formatted[k] = f"{v:.0%}"
                elif k == 'life_exp':
                    formatted[k] = f"{v:.1f}"
                else:
                    formatted[k] = f"{v:.0f}"
            writer.writerow(formatted)
    
    print(f"Output written to {filename}")


def generate_pdf_report(config_a, config_b, results_a, results_b, filename='retirement_report.pdf'):
    """Generate PDF report with parameters and comparison plots."""
    
    doc = SimpleDocTemplate(filename, pagesize=letter,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=12)
    story.append(Paragraph("Retirement Simulation Report", title_style))
    story.append(Spacer(1, 12))
    
    # Parameters table
    story.append(Paragraph("Simulation Parameters", styles['Heading2']))
    story.append(Spacer(1, 6))
    
    # Build parameters comparison table
    param_labels = [
        ('age', 'Current Age'),
        ('year_start', 'Start Year'),
        ('year_stop', 'End Year'),
        ('std_sav', 'Standard Savings ($K)'),
        ('std_pretax', 'Std PreTax ($K)'),
        ('ira_sav', 'IRA Savings ($K)'),
        ('roth_sav', 'Roth Savings ($K)'),
        ('SS_base', 'SS Base @69 ($K/yr)'),
        ('SS_age', 'SS Claim Age'),
        ('SS_cola', 'SS COLA (%)'),
        ('draw_start', 'Initial Draw ($K/yr)'),
        ('stock_ROR', 'Stock ROR (%)'),
        ('fixed_ROR', 'Fixed ROR (%)'),
        ('stock_fixed', 'Stock/Fixed (%)'),
        ('inflation', 'Inflation (%)'),
        ('roth_conv_threshold', 'Roth Conv Threshold ($K)')
    ]
    
    # Create table data with header
    table_data = [['Parameter', 'Plan A', 'Plan B']]
    for key, label in param_labels:
        val_a = config_a.get(key, 'N/A')
        val_b = config_b.get(key, 'N/A')
        if isinstance(val_a, float):
            val_a = f"{val_a:.1f}" if val_a != int(val_a) else f"{int(val_a)}"
        if isinstance(val_b, float):
            val_b = f"{val_b:.1f}" if val_b != int(val_b) else f"{int(val_b)}"
        table_data.append([label, str(val_a), str(val_b)])
    
    param_table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
    param_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(param_table)
    story.append(PageBreak())
    
    # Helper function to save plot to buffer
    def save_plot_to_buffer(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        return buf
    
    # Extract data
    years_a = [r['year'] for r in results_a]
    years_b = [r['year'] for r in results_b]
    
    # Plot a) Total Savings & Amount Available
    story.append(Paragraph("a) Total Savings & Amount Available", styles['Heading2']))
    
    fig1, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(years_a, [r['total_sav'] for r in results_a], 'b-', label='A: Total Sav', linewidth=2)
    ax1.plot(years_b, [r['total_sav'] for r in results_b], 'b--', label='B: Total Sav', linewidth=2)
    ax1.plot(years_a, [r['amount_avail'] for r in results_a], 'g-', label='A: Avail', linewidth=1.5)
    ax1.plot(years_b, [r['amount_avail'] for r in results_b], 'g--', label='B: Avail', linewidth=1.5)
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Amount ($K)')
    ax1.set_title('Total Savings & Amount Available')
    ax1.set_ylim(bottom=0)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    buf1 = save_plot_to_buffer(fig1)
    plt.close(fig1)
    story.append(Image(buf1, width=6.5*inch, height=3.5*inch))
    story.append(Spacer(1, 12))
    
    # Plot b) Income Components (total_inc = ord_inc + pref_inc)
    # Note: ord_inc already includes SS_inc in the calculation
    story.append(Paragraph("b) Income Components", styles['Heading2']))
    
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    # For Plan A
    ss_a = [r['SS_inc'] for r in results_a]
    ord_a = [r['ord_inc'] for r in results_a]
    pref_a = [r['pref_inc'] for r in results_a]
    total_inc_a = [r['total_inc'] for r in results_a]
    
    # For Plan B
    ss_b = [r['SS_inc'] for r in results_b]
    ord_b = [r['ord_inc'] for r in results_b]
    pref_b = [r['pref_inc'] for r in results_b]
    total_inc_b = [r['total_inc'] for r in results_b]
    
    ax2.plot(years_a, ord_a, 'b-', label='A: ord_inc', linewidth=1.5)
    ax2.plot(years_b, ord_b, 'b--', label='B: ord_inc', linewidth=1.5)
    ax2.plot(years_a, pref_a, 'g-', label='A: pref_inc', linewidth=1.5)
    ax2.plot(years_b, pref_b, 'g--', label='B: pref_inc', linewidth=1.5)
    ax2.plot(years_a, ss_a, 'c-', label='A: SS_inc', linewidth=1.5)
    ax2.plot(years_b, ss_b, 'c--', label='B: SS_inc', linewidth=1.5)
    ax2.plot(years_a, total_inc_a, 'r-', label='A: total_inc', linewidth=2)
    ax2.plot(years_b, total_inc_b, 'r--', label='B: total_inc', linewidth=2)
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Amount ($K)')
    ax2.set_title('Income Components (total_inc = ord_inc + pref_inc)')
    ax2.set_ylim(bottom=0)
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    buf2 = save_plot_to_buffer(fig2)
    plt.close(fig2)
    story.append(Image(buf2, width=6.5*inch, height=3.5*inch))
    story.append(PageBreak())
    
    # Plot c) Spending Components
    story.append(Paragraph("c) Spending Components", styles['Heading2']))
    
    fig3, ax3 = plt.subplots(figsize=(7, 4))
    draw_a = [r['draw'] for r in results_a]
    draw_b = [r['draw'] for r in results_b]
    ord_tax_a = [r['ord_tax'] for r in results_a]
    ord_tax_b = [r['ord_tax'] for r in results_b]
    pref_tax_a = [r['pref_tax'] for r in results_a]
    pref_tax_b = [r['pref_tax'] for r in results_b]
    total_tax_a = [r['total_tax'] for r in results_a]
    total_tax_b = [r['total_tax'] for r in results_b]
    total_spent_a = [r['draw'] + r['total_tax'] for r in results_a]
    total_spent_b = [r['draw'] + r['total_tax'] for r in results_b]
    
    ax3.plot(years_a, draw_a, 'b-', label='A: draw', linewidth=1.5)
    ax3.plot(years_b, draw_b, 'b--', label='B: draw', linewidth=1.5)
    ax3.plot(years_a, ord_tax_a, 'g-', label='A: ord_tax', linewidth=1.5)
    ax3.plot(years_b, ord_tax_b, 'g--', label='B: ord_tax', linewidth=1.5)
    ax3.plot(years_a, pref_tax_a, 'c-', label='A: pref_tax', linewidth=1.5)
    ax3.plot(years_b, pref_tax_b, 'c--', label='B: pref_tax', linewidth=1.5)
    ax3.plot(years_a, total_tax_a, 'm-', label='A: total_tax', linewidth=1.5)
    ax3.plot(years_b, total_tax_b, 'm--', label='B: total_tax', linewidth=1.5)
    ax3.plot(years_a, total_spent_a, 'r-', label='A: total_spent', linewidth=2)
    ax3.plot(years_b, total_spent_b, 'r--', label='B: total_spent', linewidth=2)
    ax3.set_xlabel('Year')
    ax3.set_ylabel('Amount ($K)')
    ax3.set_title('Spending Components (total_spent = draw + total_tax)')
    ax3.set_ylim(bottom=0)
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    
    buf3 = save_plot_to_buffer(fig3)
    plt.close(fig3)
    story.append(Image(buf3, width=6.5*inch, height=3.5*inch))
    story.append(Spacer(1, 12))
    
    # Plot d) Total Gains vs Total Spent
    story.append(Paragraph("d) Total Gains vs Total Spent", styles['Heading2']))
    
    fig4, ax4 = plt.subplots(figsize=(7, 4))
    total_gains_a = [r['total_gains'] for r in results_a]
    total_gains_b = [r['total_gains'] for r in results_b]
    ax4.plot(years_a, total_gains_a, 'g-', label='A: total_gains', linewidth=2)
    ax4.plot(years_b, total_gains_b, 'g--', label='B: total_gains', linewidth=2)
    ax4.plot(years_a, total_spent_a, 'r-', label='A: total_spent', linewidth=2)
    ax4.plot(years_b, total_spent_b, 'r--', label='B: total_spent', linewidth=2)
    ax4.set_xlabel('Year')
    ax4.set_ylabel('Amount ($K)')
    ax4.set_title('Total Gains vs Total Spent')
    ax4.set_ylim(bottom=0)
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.3)
    
    buf4 = save_plot_to_buffer(fig4)
    plt.close(fig4)
    story.append(Image(buf4, width=6.5*inch, height=3.5*inch))
    story.append(PageBreak())
    
    # Plot e) Net Gain/Loss (total_gains - total_expenses)
    story.append(Paragraph("e) Net Gain/Loss (total_gains - total_expenses)", styles['Heading2']))
    
    fig5, ax5 = plt.subplots(figsize=(7, 4))
    net_a = [r['total_gains'] - r['total_expenses'] for r in results_a]
    net_b = [r['total_gains'] - r['total_expenses'] for r in results_b]
    
    ax5.plot(years_a, net_a, 'b-', label='A: net', linewidth=2)
    ax5.plot(years_b, net_b, 'r--', label='B: net', linewidth=2)
    ax5.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax5.set_xlabel('Year')
    ax5.set_ylabel('Amount ($K)')
    ax5.set_title('Net Gain/Loss (total_gains - total_expenses)')
    ax5.legend(loc='upper left')
    ax5.grid(True, alpha=0.3)
    
    buf5 = save_plot_to_buffer(fig5)
    plt.close(fig5)
    story.append(Image(buf5, width=6.5*inch, height=3.5*inch))
    story.append(Spacer(1, 12))
    
    # Plot f) Account Balances (ira_end, std_end, roth_end)
    story.append(Paragraph("f) Account Balances", styles['Heading2']))
    
    fig6, ax6 = plt.subplots(figsize=(7, 4))
    ira_a = [r['ira_end'] for r in results_a]
    ira_b = [r['ira_end'] for r in results_b]
    std_a = [r['std_end'] for r in results_a]
    std_b = [r['std_end'] for r in results_b]
    roth_a = [r['roth_end'] for r in results_a]
    roth_b = [r['roth_end'] for r in results_b]
    
    ax6.plot(years_a, ira_a, 'b-', label='A: IRA', linewidth=2)
    ax6.plot(years_b, ira_b, 'b--', label='B: IRA', linewidth=2)
    ax6.plot(years_a, std_a, 'g-', label='A: Std', linewidth=2)
    ax6.plot(years_b, std_b, 'g--', label='B: Std', linewidth=2)
    ax6.plot(years_a, roth_a, 'r-', label='A: Roth', linewidth=2)
    ax6.plot(years_b, roth_b, 'r--', label='B: Roth', linewidth=2)
    ax6.set_xlabel('Year')
    ax6.set_ylabel('Balance ($K)')
    ax6.set_title('Account Balances (ira_end, std_end, roth_end)')
    ax6.set_ylim(bottom=0)
    ax6.legend(loc='upper left', fontsize=8)
    ax6.grid(True, alpha=0.3)
    
    buf6 = save_plot_to_buffer(fig6)
    plt.close(fig6)
    story.append(Image(buf6, width=6.5*inch, height=3.5*inch))
    story.append(PageBreak())
    
    # Plot g) Tax Rates (aggregate and marginal)
    story.append(Paragraph("g) Tax Rates", styles['Heading2']))
    
    fig7, ax7 = plt.subplots(figsize=(7, 4))
    tax_rate_a = [r['tax_rate'] * 100 for r in results_a]  # Convert to percentage
    tax_rate_b = [r['tax_rate'] * 100 for r in results_b]
    marg_rate_a = [r['marg_rate'] * 100 for r in results_a]
    marg_rate_b = [r['marg_rate'] * 100 for r in results_b]
    
    ax7.plot(years_a, tax_rate_a, 'b-', label='A: eff_rate', linewidth=2)
    ax7.plot(years_b, tax_rate_b, 'b--', label='B: eff_rate', linewidth=2)
    ax7.plot(years_a, marg_rate_a, 'r-', label='A: marg_rate', linewidth=2)
    ax7.plot(years_b, marg_rate_b, 'r--', label='B: marg_rate', linewidth=2)
    ax7.set_xlabel('Year')
    ax7.set_ylabel('Rate (%)')
    ax7.set_title('Tax Rates (Effective & Marginal)')
    ax7.set_ylim(bottom=0)
    ax7.legend(loc='upper left')
    ax7.grid(True, alpha=0.3)
    
    buf7 = save_plot_to_buffer(fig7)
    plt.close(fig7)
    story.append(Image(buf7, width=6.5*inch, height=3.5*inch))
    
    # Build PDF
    doc.build(story)
    print(f"PDF report written to {filename}")


class RetirementSimGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retirement Simulation - Plan Comparison")
        
        # Default parameters (in $1000 units)
        self.defaults = {
            'age': 66,
            'year_start': 2026,
            'year_stop': 2060,
            'std_sav': 1500,
            'std_pretax': 300,
            'ira_sav': 1700,
            'roth_sav': 100,
            'SS_base': 50,
            'SS_age': 68,
            'SS_cola': 2.5,
            'draw_start': 140,
            'stock_ROR': 7,
            'fixed_ROR': 4,
            'stock_pct': 70,
            'inflation': 2.5,
            'roth_conv_threshold': 100
        }
        
        # Store results for plot switching
        self.results_a = None
        self.results_b = None
        self.config_a = None
        self.config_b = None
        
        # Main widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Plans layout
        plans_layout = QHBoxLayout()
        
        # Plan A
        plan_a_group = QGroupBox("Plan A")
        plan_a_layout = QGridLayout()
        self.plan_a_fields = self.create_param_fields(plan_a_layout)
        plan_a_group.setLayout(plan_a_layout)
        plans_layout.addWidget(plan_a_group)
        
        # Plan B
        plan_b_group = QGroupBox("Plan B")
        plan_b_layout = QGridLayout()
        self.plan_b_fields = self.create_param_fields(plan_b_layout)
        plan_b_group.setLayout(plan_b_layout)
        plans_layout.addWidget(plan_b_group)
        
        main_layout.addLayout(plans_layout)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        execute_btn = QPushButton("Execute")
        execute_btn.clicked.connect(self.execute)
        button_layout.addWidget(execute_btn)
        
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.clicked.connect(self.reset_defaults)
        button_layout.addWidget(reset_btn)
        
        copy_btn = QPushButton("Copy A → B")
        copy_btn.clicked.connect(self.copy_a_to_b)
        button_layout.addWidget(copy_btn)
        
        pdf_btn = QPushButton("Generate PDF")
        pdf_btn.clicked.connect(self.generate_pdf)
        button_layout.addWidget(pdf_btn)
        
        button_layout.addStretch()
        
        # Plot type buttons
        total_btn = QPushButton("Total Savings")
        total_btn.clicked.connect(lambda: self.update_plot('total'))
        button_layout.addWidget(total_btn)
        
        accounts_btn = QPushButton("Accounts")
        accounts_btn.clicked.connect(lambda: self.update_plot('accounts'))
        button_layout.addWidget(accounts_btn)
        
        delta_btn = QPushButton("Gains/Expenses")
        delta_btn.clicked.connect(lambda: self.update_plot('delta'))
        button_layout.addWidget(delta_btn)
        
        main_layout.addLayout(button_layout)
        
        # Plot area
        self.figure, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)
        
        self.resize(1000, 700)
    
    def create_param_fields(self, layout):
        """Create parameter input fields in 2-column layout."""
        fields_dict = {}
        
        field_defs = [
            ('age', 'Age'),
            ('year_start', 'Start Year'),
            ('year_stop', 'End Year'),
            ('std_sav', 'Std Sav ($K)'),
            ('std_pretax', 'stdPreTax'),
            ('ira_sav', 'IRA Sav ($K)'),
            ('roth_sav', 'Roth Sav ($K)'),
            ('SS_base', 'SS @69 ($K)'),
            ('SS_age', 'SS Age'),
            ('SS_cola', 'SS COLA (%)'),
            ('draw_start', 'Draw ($K/yr)'),
            ('stock_ROR', 'Stock ROR (%)'),
            ('fixed_ROR', 'Fixed ROR (%)'),
            ('stock_pct', 'Stock (%)'),
            ('inflation', 'Inflation (%)'),
            ('roth_conv_threshold', 'Roth Cvrt Thresh')
        ]
        
        # 2 columns, 8 rows
        num_fields = len(field_defs)
        rows_per_col = (num_fields + 1) // 2
        
        for i, (key, label) in enumerate(field_defs):
            row = i % rows_per_col
            col_offset = (i // rows_per_col) * 2  # 0 for first column, 2 for second
            
            lbl = QLabel(label)
            layout.addWidget(lbl, row, col_offset)
            
            edit = QLineEdit(str(self.defaults[key]))
            edit.setFixedWidth(80)
            layout.addWidget(edit, row, col_offset + 1)
            fields_dict[key] = edit
        
        return fields_dict
    
    def get_config(self, fields_dict):
        """Extract config dict from QLineEdit widgets."""
        config = {}
        for key, edit in fields_dict.items():
            val = edit.text()
            if key in ['age', 'year_start', 'year_stop', 'SS_age']:
                config[key] = int(val)
            else:
                config[key] = float(val)
        
        stock_pct = config.pop('stock_pct')
        config['stock_fixed'] = f"{int(stock_pct)}/{int(100-stock_pct)}"
        
        return config
    
    def reset_defaults(self):
        """Reset both plans to default values."""
        for key, val in self.defaults.items():
            self.plan_a_fields[key].setText(str(val))
            self.plan_b_fields[key].setText(str(val))
    
    def copy_a_to_b(self):
        """Copy Plan A values to Plan B."""
        for key in self.plan_a_fields:
            self.plan_b_fields[key].setText(self.plan_a_fields[key].text())
    
    def update_plot(self, plot_type):
        """Update the plot based on selected type."""
        if self.results_a is None or self.results_b is None:
            QMessageBox.warning(self, "No Data", "Run Execute first to generate data.")
            return
        
        self.ax.clear()
        
        if plot_type == 'total':
            self.plot_total()
        elif plot_type == 'accounts':
            self.plot_accounts()
        elif plot_type == 'delta':
            self.plot_delta()
        
        self.canvas.draw()
    
    def plot_total(self):
        """Plot total savings comparison (original plot)."""
        years_a = [r['year'] for r in self.results_a]
        total_sav_a = [r['total_sav'] for r in self.results_a]
        amount_avail_a = [r['amount_avail'] for r in self.results_a]
        
        years_b = [r['year'] for r in self.results_b]
        total_sav_b = [r['total_sav'] for r in self.results_b]
        amount_avail_b = [r['amount_avail'] for r in self.results_b]
        
        self.ax.plot(years_a, total_sav_a, 'b-', label='Plan A', linewidth=2)
        self.ax.plot(years_b, total_sav_b, 'r--', label='Plan B', linewidth=2)
        self.ax.plot(years_a, amount_avail_a, color='gray', linestyle='-', label='A after-tax', linewidth=1.5)
        self.ax.plot(years_b, amount_avail_b, color='gray', linestyle='--', label='B after-tax', linewidth=1.5)
        
        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Total Savings ($K)')
        self.ax.set_title('Total Savings Comparison')
        self.ax.set_ylim(bottom=0)
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        summary_a = f"Plan A Final: ${self.results_a[-1]['total_sav']:,.0f}K"
        summary_b = f"Plan B Final: ${self.results_b[-1]['total_sav']:,.0f}K"
        self.ax.text(0.02, 0.98, f"{summary_a}\n{summary_b}", transform=self.ax.transAxes,
                     verticalalignment='top', fontsize=10,
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    def plot_accounts(self):
        """Plot individual account balances."""
        years_a = [r['year'] for r in self.results_a]
        years_b = [r['year'] for r in self.results_b]
        
        # Plan A - solid lines
        ira_a = [r['ira_end'] for r in self.results_a]
        std_a = [r['std_end'] for r in self.results_a]
        roth_a = [r['roth_end'] for r in self.results_a]
        
        # Plan B - dotted lines
        ira_b = [r['ira_end'] for r in self.results_b]
        std_b = [r['std_end'] for r in self.results_b]
        roth_b = [r['roth_end'] for r in self.results_b]
        
        # Plot with distinct colors: blue=IRA, green=Std, red=Roth
        self.ax.plot(years_a, ira_a, 'b-', label='A: IRA', linewidth=2)
        self.ax.plot(years_b, ira_b, 'b--', label='B: IRA', linewidth=2)
        
        self.ax.plot(years_a, std_a, 'g-', label='A: Standard', linewidth=2)
        self.ax.plot(years_b, std_b, 'g--', label='B: Standard', linewidth=2)
        
        self.ax.plot(years_a, roth_a, 'r-', label='A: Roth', linewidth=2)
        self.ax.plot(years_b, roth_b, 'r--', label='B: Roth', linewidth=2)
        
        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Account Balance ($K)')
        self.ax.set_title('Individual Account Balances')
        self.ax.set_ylim(bottom=0)
        self.ax.legend(loc='upper right', ncol=2)
        self.ax.grid(True, alpha=0.3)
    
    def plot_delta(self):
        """Plot total gains and total expenses."""
        years_a = [r['year'] for r in self.results_a]
        years_b = [r['year'] for r in self.results_b]
        
        # Plan A
        gains_a = [r['total_gains'] for r in self.results_a]
        expenses_a = [r['total_expenses'] for r in self.results_a]
        
        # Plan B
        gains_b = [r['total_gains'] for r in self.results_b]
        expenses_b = [r['total_expenses'] for r in self.results_b]
        
        # Green for gains, red for expenses
        self.ax.plot(years_a, gains_a, 'g-', label='A: Total Gains', linewidth=2)
        self.ax.plot(years_b, gains_b, 'g--', label='B: Total Gains', linewidth=2)
        
        self.ax.plot(years_a, expenses_a, 'r-', label='A: Total Expenses', linewidth=2)
        self.ax.plot(years_b, expenses_b, 'r--', label='B: Total Expenses', linewidth=2)
        
        self.ax.set_xlabel('Year')
        self.ax.set_ylabel('Amount ($K)')
        self.ax.set_title('Total_Gain & Total_Expense')
        self.ax.set_ylim(bottom=0)
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
    
    def generate_pdf(self):
        """Generate PDF report."""
        if self.results_a is None or self.results_b is None:
            QMessageBox.warning(self, "No Data", "Run Execute first to generate data.")
            return
        
        try:
            generate_pdf_report(self.config_a, self.config_b, 
                              self.results_a, self.results_b, 
                              'retirement_report.pdf')
            QMessageBox.information(self, "PDF Generated", 
                                   "Report saved to retirement_report.pdf")
        except Exception as e:
            QMessageBox.critical(self, "PDF Error", f"Error generating PDF: {str(e)}")
    
    def execute(self):
        """Run both simulations and display results."""
        try:
            self.config_a = self.get_config(self.plan_a_fields)
            self.config_b = self.get_config(self.plan_b_fields)
        except ValueError as e:
            QMessageBox.critical(self, "Input Error", f"Invalid input: {e}")
            return
        
        try:
            # Run simulations
            self.results_a = run_simulation(self.config_a)
            self.results_b = run_simulation(self.config_b)
            
            # Write CSV files
            write_csv(self.results_a, 'plan_A.csv')
            write_csv(self.results_b, 'plan_B.csv')
            
            # Clear and show default plot
            self.ax.clear()
            self.plot_total()
            self.canvas.draw()
            
            # Print summary
            print("\n" + "="*50)
            print("Plan A Summary:")
            self.print_config(self.config_a)
            print(f"Final Total Savings: ${self.results_a[-1]['total_sav']:,.0f}K")
            
            print("\n" + "="*50)
            print("Plan B Summary:")
            self.print_config(self.config_b)
            print(f"Final Total Savings: ${self.results_b[-1]['total_sav']:,.0f}K")
        
        except Exception as e:
            QMessageBox.critical(self, "Simulation Error", f"Error during simulation: {str(e)}")
    
    def print_config(self, config):
        """Print configuration parameters compactly."""
        ss_age = config['SS_age']
        ss_inc = calc_ss_benefit(config['SS_base'], ss_age)
        print(f"  Age:{config['age']} Yrs:{config['year_start']}-{config['year_stop']} " +
              f"IRA:{config['ira_sav']:.0f}K Std:{config['std_sav']:.0f}K Roth:{config.get('roth_sav',0):.0f}K")
        print(f"  Draw:{config['draw_start']:.0f}K/yr Infl:{config['inflation']}% " +
              f"Stock/Fix:{config['stock_fixed']} ROR:{config['stock_ROR']}/{config['fixed_ROR']}%")
        print(f"  SS@{ss_age}:{ss_inc:.0f}K/yr COLA:{config['SS_cola']}% " +
              f"RothThresh:{config.get('roth_conv_threshold',0):.0f}K")


def main():
    app = QApplication(sys.argv)
    window = RetirementSimGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
