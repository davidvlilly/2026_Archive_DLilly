"""
retSim_Main.py — Retirement Simulator entry point.
"""

import sys
from PyQt5.QtWidgets import QApplication
from retSim_Support.main_window import RetirementSimGUI


def main():
    app = QApplication(sys.argv)
    window = RetirementSimGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
