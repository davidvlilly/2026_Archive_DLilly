"""Star Tracker EKF Simulation — PyQt5 GUI Application."""

import os
import sys
import json
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QMenuBar, QMenu, QAction,
    QDialog, QFormLayout, QDoubleSpinBox, QCheckBox,
    QDialogButtonBox, QFileDialog, QGroupBox, QStatusBar,
    QLineEdit, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from starTrackSim.config import Config
from starTrackSim.truth import generate_truth_trajectory
from starTrackSim.sensors.gyro import generate_gyro_measurements
from starTrackSim.sensors.star_tracker import generate_star_tracker_measurement
from starTrackSim.star_catalog import load_catalog, query_stars_in_fov
from starTrackSim.ekf.state import EKFState
from starTrackSim.ekf.propagate import propagate
from starTrackSim.ekf.update import update
from starTrackSim.quaternion_utils import quat_error_angles, quat_to_dcm
from starTrackSim.star_image import render_star_frame_cv2

RAD_TO_ARCSEC = 3600.0 * np.degrees(1.0)


# ─── Conversion helpers (config stores rad/s internally) ───

def bias_to_arcsec_s(val_rad_s):
    return val_rad_s / np.deg2rad(1.0 / 3600.0)

def arcsec_s_to_bias(val_arcsec_s):
    return val_arcsec_s * np.deg2rad(1.0 / 3600.0)


# ═══════════════════════════════════════════════════════════
#  Simulation Worker (runs in QThread)
# ═══════════════════════════════════════════════════════════

class SimulationWorker(QThread):
    progress = pyqtSignal(int, str)
    frame_ready = pyqtSignal(object)  # QImage
    finished = pyqtSignal(dict)

    def __init__(self, cfg, stars_eci, magnitudes):
        super().__init__()
        self.cfg = cfg
        self.stars_eci = stars_eci
        self.magnitudes = magnitudes

    def run(self):
        cfg = self.cfg
        rng = np.random.default_rng(cfg.seed)

        self.progress.emit(0, "Generating truth trajectory...")
        q_true, omega_true = generate_truth_trajectory(cfg)

        self.progress.emit(5, "Generating gyro measurements...")
        omega_meas, bias_true = generate_gyro_measurements(omega_true, cfg, rng)

        self.progress.emit(10, "Initializing EKF...")
        ekf = EKFState(cfg)

        N = cfg.num_gyro_ticks
        att_errors = np.zeros((N, 3))
        bias_errors = np.zeros((N, 3))
        P_diag_history = np.zeros((N, 6))
        innovations = []
        ticks_per_update = cfg.gyro_ticks_per_st_update
        dt = cfg.dt_gyro

        # Frame generation: produce ~120 frames spread across the sim
        frame_interval_ticks = max(1, N // 120)
        image_size = 600

        num_updates = 0

        for k in range(N):
            # Propagate
            propagate(ekf, omega_meas[k], dt)

            # Update
            if (k + 1) % ticks_per_update == 0:
                q_st, num_stars = generate_star_tracker_measurement(
                    q_true[k], self.stars_eci, self.magnitudes, cfg, rng
                )
                if q_st is not None:
                    innov = quat_error_angles(q_st, ekf.q_ref)
                    innovations.append((k * dt, innov))
                    update(ekf, q_st)
                    num_updates += 1

            # Record
            att_errors[k] = quat_error_angles(q_true[k], ekf.q_ref)
            bias_errors[k] = bias_true[k] - ekf.bias_est
            P_diag_history[k] = np.diag(ekf.P)

            # Emit frame
            if k % frame_interval_ticks == 0:
                body_vecs, _, mags, _ = query_stars_in_fov(
                    self.stars_eci, self.magnitudes, q_true[k],
                    cfg.star_tracker_fov_deg
                )
                frame_bgr = render_star_frame_cv2(
                    body_vecs, mags, cfg.star_tracker_fov_deg,
                    image_size=image_size,
                    time_label=f"t = {k*dt:.1f}s"
                )
                # Convert BGR to RGB for QImage
                frame_rgb = frame_bgr[:, :, ::-1].copy()
                h, w, ch = frame_rgb.shape
                qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
                self.frame_ready.emit(qimg.copy())

            # Progress
            if (k + 1) % (N // 20) == 0:
                pct = int(10 + 85 * (k + 1) / N)
                rss = np.linalg.norm(att_errors[k]) * RAD_TO_ARCSEC
                self.progress.emit(pct, f"t={k*dt:.0f}s  RSS={rss:.2f}\"  updates={num_updates}")

        self.progress.emit(98, "Simulation complete.")

        # Compute steady-state stats
        time_s = np.arange(N) * dt
        ss_start = int(0.75 * N)
        ss_rss = np.linalg.norm(att_errors[ss_start:], axis=1) * RAD_TO_ARCSEC

        results = {
            'time_s': time_s,
            'att_errors': att_errors,
            'bias_errors': bias_errors,
            'P_diag_history': P_diag_history,
            'innovations': innovations,
            'rss_mean': float(np.mean(ss_rss)),
            'rss_max': float(np.max(ss_rss)),
            'num_updates': num_updates,
        }
        self.finished.emit(results)


# ═══════════════════════════════════════════════════════════
#  Plot Window
# ═══════════════════════════════════════════════════════════

class PlotWindow(QDialog):
    def __init__(self, title, parent=None, show_toolbar=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1100, 750)

        self.figure = Figure(figsize=(14, 10), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout = QVBoxLayout()
        if show_toolbar:
            layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)


def _find_index_after(time_s, t_start):
    idx = np.searchsorted(time_s, t_start)
    return min(idx, len(time_s) - 1)


def show_kalman_track(results, parent=None):
    win = PlotWindow("Kalman Track", parent)
    fig = win.figure
    time_s = results['time_s']
    att_errors = results['att_errors']
    bias_errors = results['bias_errors']
    P_diag = results['P_diag_history']
    t_crop = 1.0
    i_crop = _find_index_after(time_s, t_crop)

    axes = fig.subplots(3, 2)
    fig.suptitle('Star Tracker EKF Performance', fontsize=12)

    # Cross-bore
    ax = axes[0, 0]
    ex = att_errors[:, 0] * RAD_TO_ARCSEC
    ey = att_errors[:, 1] * RAD_TO_ARCSEC
    sig = np.sqrt(P_diag[:, 0]) * RAD_TO_ARCSEC
    ax.plot(time_s, ex, 'b-', lw=0.5, label='X')
    ax.plot(time_s, ey, 'r-', lw=0.5, label='Y')
    ax.plot(time_s, sig, 'k--', lw=0.8, label='1-sig')
    ax.plot(time_s, -sig, 'k--', lw=0.8)
    vals = np.concatenate([ex[i_crop:], ey[i_crop:], sig[i_crop:], -sig[i_crop:]])
    m = (vals.max() - vals.min()) * 0.2
    ax.set_ylim(vals.min() - m, vals.max() + m)
    ax.set_ylabel('arcsec'); ax.set_title('Cross-Bore Error'); ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # About-bore
    ax = axes[0, 1]
    ez = att_errors[:, 2] * RAD_TO_ARCSEC
    sr = np.sqrt(P_diag[:, 2]) * RAD_TO_ARCSEC
    ax.plot(time_s, ez, 'g-', lw=0.5, label='Z')
    ax.plot(time_s, sr, 'k--', lw=0.8); ax.plot(time_s, -sr, 'k--', lw=0.8)
    vals = np.concatenate([ez[i_crop:], sr[i_crop:], -sr[i_crop:]])
    m = (vals.max() - vals.min()) * 0.2
    ax.set_ylim(vals.min() - m, vals.max() + m)
    ax.set_ylabel('arcsec'); ax.set_title('About-Bore (Roll) Error'); ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # RSS
    ax = axes[1, 0]
    rss = np.linalg.norm(att_errors, axis=1) * RAD_TO_ARCSEC
    ax.plot(time_s, rss, 'm-', lw=0.5)
    rc = rss[i_crop:]
    ax.set_ylim(0, rc.max() * 1.2)
    ax.set_ylabel('arcsec'); ax.set_title('RSS Attitude Error'); ax.grid(True, alpha=0.3)

    # Bias error
    ax = axes[1, 1]
    be = bias_errors * RAD_TO_ARCSEC
    ax.plot(time_s, be[:, 0], 'b-', lw=0.5, label='X')
    ax.plot(time_s, be[:, 1], 'r-', lw=0.5, label='Y')
    ax.plot(time_s, be[:, 2], 'g-', lw=0.5, label='Z')
    ax.set_ylabel('arcsec/s'); ax.set_title('Bias Estimation Error'); ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # P attitude
    ax = axes[2, 0]
    for i, (lbl, c) in enumerate(zip(['X', 'Y', 'Z'], ['b', 'r', 'g'])):
        v = np.sqrt(P_diag[:, i]) * RAD_TO_ARCSEC
        ax.plot(time_s, v, c, lw=0.8, label=lbl)
    ac = np.column_stack([np.sqrt(P_diag[i_crop:, i]) * RAD_TO_ARCSEC for i in range(3)])
    ax.set_ylim(0, ac.max() * 1.2)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('arcsec'); ax.set_title('Attitude Covariance'); ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # P bias
    ax = axes[2, 1]
    for i, (lbl, c) in enumerate(zip(['X', 'Y', 'Z'], ['b', 'r', 'g'])):
        ax.plot(time_s, np.sqrt(P_diag[:, 3+i]) * RAD_TO_ARCSEC, c, lw=0.8, label=lbl)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('arcsec/s'); ax.set_title('Bias Covariance'); ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    fig.tight_layout()
    win.canvas.draw()
    win.show()
    return win


def show_innovations(results, parent=None):
    win = PlotWindow("Innovation Sequence", parent)
    fig = win.figure
    innovations = results['innovations']
    if not innovations:
        return win

    times = [t for t, _ in innovations]
    innov = np.array([v for _, v in innovations])

    ax = fig.add_subplot(111)
    ax.plot(times, innov[:, 0] * RAD_TO_ARCSEC, 'b.', ms=2, label='X')
    ax.plot(times, innov[:, 1] * RAD_TO_ARCSEC, 'r.', ms=2, label='Y')
    ax.plot(times, innov[:, 2] * RAD_TO_ARCSEC, 'g.', ms=2, label='Z')
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Innovation (arcsec)')
    ax.set_title('Star Tracker Innovation Sequence')
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    fig.tight_layout()
    win.canvas.draw()
    win.show()
    return win


def show_overview(cfg, parent=None):
    win = PlotWindow("Mission Overview", parent, show_toolbar=False)
    fig = win.figure
    fig.clear()
    ax = fig.add_subplot(111, projection='3d')

    R_e = cfg.earth_radius_km
    r_orb = R_e + cfg.orbit_altitude_km
    inc = np.deg2rad(cfg.orbit_inclination_deg)

    # ── Earth sphere ──
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 25)
    xe = R_e * np.outer(np.cos(u), np.sin(v))
    ye = R_e * np.outer(np.sin(u), np.sin(v))
    ze = R_e * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(xe, ye, ze, color='#4682B4', alpha=0.30, zorder=0)
    ax.plot_wireframe(xe, ye, ze, color='#1E3A5F', alpha=0.12,
                      rstride=5, cstride=5, lw=0.5)

    # ── Orbit path ──
    theta = np.linspace(0, 2 * np.pi, 300)
    xo = r_orb * np.cos(theta)
    yo = r_orb * np.sin(theta) * np.cos(inc)
    zo = r_orb * np.sin(theta) * np.sin(inc)
    ax.plot(xo, yo, zo, color='#00cc44', ls='--', lw=1.5, alpha=0.8, label='Orbit')

    # ── Satellite (placed at top of orbit so it appears above Earth) ──
    t0 = np.pi / 2
    sat = np.array([r_orb * np.cos(t0),
                    r_orb * np.sin(t0) * np.cos(inc),
                    r_orb * np.sin(t0) * np.sin(inc)])
    ax.scatter(*sat, color='red', s=120, zorder=10, label='Satellite',
               edgecolors='white', linewidths=0.5)

    # ── Nadir line (satellite down to Earth surface) ──
    sat_dir = sat / np.linalg.norm(sat)
    surface_pt = sat_dir * R_e
    ax.plot([sat[0], surface_pt[0]], [sat[1], surface_pt[1]], [sat[2], surface_pt[2]],
            color='#c0c0c0', lw=3.0, ls='-', alpha=0.9, label='Nadir')

    # ── Boresight direction (angled 45 deg from zenith, away from viewer) ──
    up = sat_dir
    # "away" direction: camera is at azim=-90 (along +X), so away = -X
    away = np.array([-1.0, 0.0, 0.0])
    # Remove any component along up, then normalize
    away = away - np.dot(away, up) * up
    away /= np.linalg.norm(away)
    # Boresight: 45 deg from zenith toward away
    boresight_eci = up * np.cos(np.deg2rad(45)) + away * np.sin(np.deg2rad(45))
    boresight_eci /= np.linalg.norm(boresight_eci)
    # Body X/Y axes for FOV cone (perpendicular to boresight)
    body_x_eci = np.cross(boresight_eci, up)
    body_x_eci /= np.linalg.norm(body_x_eci)
    body_y_eci = np.cross(boresight_eci, body_x_eci)

    arrow_len = r_orb * 0.55
    bore_tip = sat + boresight_eci * arrow_len
    ax.plot([sat[0], bore_tip[0]], [sat[1], bore_tip[1]], [sat[2], bore_tip[2]],
            color='gold', lw=2.5, label='Boresight', zorder=8)

    # ── FOV cone ──
    half_fov = np.deg2rad(cfg.star_tracker_fov_deg / 2.0)
    cone_len = arrow_len * 0.9
    n_cone = 48
    phi = np.linspace(0, 2 * np.pi, n_cone)
    cone_pts = np.zeros((n_cone, 3))
    for i, p in enumerate(phi):
        edge = (boresight_eci * np.cos(half_fov)
                + (body_x_eci * np.cos(p) + body_y_eci * np.sin(p)) * np.sin(half_fov))
        edge /= np.linalg.norm(edge)
        cone_pts[i] = sat + edge * cone_len
    ax.plot(cone_pts[:, 0], cone_pts[:, 1], cone_pts[:, 2],
            color='gold', lw=0.8, alpha=0.5)
    for i in range(0, n_cone, n_cone // 8):
        ax.plot([sat[0], cone_pts[i, 0]], [sat[1], cone_pts[i, 1]],
                [sat[2], cone_pts[i, 2]], color='gold', lw=0.5, alpha=0.3)

    # ── Background stars ──
    rng = np.random.default_rng(123)
    n_bg = 250
    dirs = rng.standard_normal((n_bg, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    star_pts = dirs * r_orb * 2.3
    ax.scatter(star_pts[:, 0], star_pts[:, 1], star_pts[:, 2],
               color='white', s=1, alpha=0.4, zorder=0)

    # ── Formatting ──
    ax.set_facecolor('#0a0a1a')
    fig.patch.set_facecolor('#0a0a1a')
    ax.set_title('Mission Overview', color='white', fontsize=12, pad=10)
    ax.legend(loc='upper left', fontsize=8, facecolor='#1a1a2e',
              edgecolor='gray', labelcolor='white')

    # Remove axes, ticks, grid, and pane backgrounds
    ax.set_axis_off()

    # Center view on the satellite
    lim = r_orb * 1.3 / 3.0
    ax.set_xlim(sat[0] - lim, sat[0] + lim)
    ax.set_ylim(sat[1] - lim, sat[1] + lim)
    ax.set_zlim(sat[2] - lim, sat[2] + lim)
    ax.set_box_aspect([1, 1, 1])
    ax.view_init(elev=15, azim=-90)

    # Mouse-wheel zoom
    def _on_scroll(event):
        factor = 0.8 if event.button == 'up' else 1.25
        for getter, setter in [(ax.get_xlim, ax.set_xlim),
                                (ax.get_ylim, ax.set_ylim),
                                (ax.get_zlim, ax.set_zlim)]:
            lo, hi = getter()
            mid = (lo + hi) / 2.0
            half = (hi - lo) / 2.0 * factor
            setter(mid - half, mid + half)
        win.canvas.draw_idle()

    win._scroll_cid = win.canvas.mpl_connect('scroll_event', _on_scroll)

    fig.tight_layout()
    win.canvas.draw()
    win.show()
    return win


# ═══════════════════════════════════════════════════════════
#  Scientific notation spin box
# ═══════════════════════════════════════════════════════════

class SciSpinBox(QLineEdit):
    """Line edit that accepts scientific notation floats."""
    def __init__(self, value=0.0, parent=None):
        super().__init__(parent)
        self.setValue(value)
        self.setFixedWidth(140)

    def setValue(self, val):
        self.setText(f"{val:.6e}")

    def value(self):
        try:
            return float(self.text())
        except ValueError:
            return 0.0


# ═══════════════════════════════════════════════════════════
#  System Noise Dialog
# ═══════════════════════════════════════════════════════════

class SystemNoiseDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Noise Configuration")
        self.cfg = cfg
        self.resize(400, 550)

        layout = QVBoxLayout()

        # Distortion true
        grp = QGroupBox("Optical Distortion (True)")
        form = QFormLayout()
        self.dk1t = SciSpinBox(cfg.distortion_k1_true)
        self.dk2t = SciSpinBox(cfg.distortion_k2_true)
        self.dp1t = SciSpinBox(cfg.distortion_p1_true)
        self.dp2t = SciSpinBox(cfg.distortion_p2_true)
        form.addRow("k1:", self.dk1t)
        form.addRow("k2:", self.dk2t)
        form.addRow("p1:", self.dp1t)
        form.addRow("p2:", self.dp2t)
        grp.setLayout(form)
        layout.addWidget(grp)

        # Distortion correction
        grp = QGroupBox("Optical Distortion (Correction)")
        form = QFormLayout()
        self.dk1c = SciSpinBox(cfg.distortion_k1_corr)
        self.dk2c = SciSpinBox(cfg.distortion_k2_corr)
        self.dp1c = SciSpinBox(cfg.distortion_p1_corr)
        self.dp2c = SciSpinBox(cfg.distortion_p2_corr)
        form.addRow("k1:", self.dk1c)
        form.addRow("k2:", self.dk2c)
        form.addRow("p1:", self.dp1c)
        form.addRow("p2:", self.dp2c)
        grp.setLayout(form)
        layout.addWidget(grp)

        # Gyro bias
        grp = QGroupBox("Gyro Bias True (arcsec/s)")
        form = QFormLayout()
        self.bx = QDoubleSpinBox(); self.bx.setRange(-100, 100); self.bx.setDecimals(4)
        self.by = QDoubleSpinBox(); self.by.setRange(-100, 100); self.by.setDecimals(4)
        self.bz = QDoubleSpinBox(); self.bz.setRange(-100, 100); self.bz.setDecimals(4)
        self.bx.setValue(bias_to_arcsec_s(cfg.gyro_bias_true[0]))
        self.by.setValue(bias_to_arcsec_s(cfg.gyro_bias_true[1]))
        self.bz.setValue(bias_to_arcsec_s(cfg.gyro_bias_true[2]))
        form.addRow("X:", self.bx)
        form.addRow("Y:", self.by)
        form.addRow("Z:", self.bz)
        grp.setLayout(form)
        layout.addWidget(grp)

        # Position error
        grp = QGroupBox("Position Error Injection")
        form = QFormLayout()
        self.pos_en = QCheckBox("Enable")
        self.pos_en.setChecked(cfg.position_error_enabled)
        self.px = QDoubleSpinBox(); self.px.setRange(-1000, 1000); self.px.setDecimals(2)
        self.py = QDoubleSpinBox(); self.py.setRange(-1000, 1000); self.py.setDecimals(2)
        self.pz = QDoubleSpinBox(); self.pz.setRange(-1000, 1000); self.pz.setDecimals(2)
        self.px.setValue(cfg.position_error_km[0])
        self.py.setValue(cfg.position_error_km[1])
        self.pz.setValue(cfg.position_error_km[2])
        form.addRow(self.pos_en)
        form.addRow("X (km):", self.px)
        form.addRow("Y (km):", self.py)
        form.addRow("Z (km):", self.pz)
        grp.setLayout(form)
        layout.addWidget(grp)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.apply_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.setLayout(layout)

    def apply_and_accept(self):
        c = self.cfg
        c.distortion_k1_true = self.dk1t.value()
        c.distortion_k2_true = self.dk2t.value()
        c.distortion_p1_true = self.dp1t.value()
        c.distortion_p2_true = self.dp2t.value()
        c.distortion_k1_corr = self.dk1c.value()
        c.distortion_k2_corr = self.dk2c.value()
        c.distortion_p1_corr = self.dp1c.value()
        c.distortion_p2_corr = self.dp2c.value()
        c.gyro_bias_true = np.array([
            arcsec_s_to_bias(self.bx.value()),
            arcsec_s_to_bias(self.by.value()),
            arcsec_s_to_bias(self.bz.value()),
        ])
        c.position_error_enabled = self.pos_en.isChecked()
        c.position_error_km = np.array([self.px.value(), self.py.value(), self.pz.value()])
        self.accept()


# ═══════════════════════════════════════════════════════════
#  Gaussian Noise Dialog
# ═══════════════════════════════════════════════════════════

class GaussianNoiseDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gaussian Noise Configuration")
        self.cfg = cfg
        self.resize(380, 350)

        layout = QVBoxLayout()

        # Gyro noise
        grp = QGroupBox("Gyro Noise")
        form = QFormLayout()
        self.gwn = SciSpinBox(bias_to_arcsec_s(cfg.gyro_white_noise_sigma))
        self.gbd = SciSpinBox(bias_to_arcsec_s(cfg.gyro_bias_drift_sigma))
        form.addRow("White noise sigma (arcsec/s):", self.gwn)
        form.addRow("Bias drift sigma:", self.gbd)
        grp.setLayout(form)
        layout.addWidget(grp)

        # Star tracker
        grp = QGroupBox("Star Tracker")
        form = QFormLayout()
        self.stn = QDoubleSpinBox(); self.stn.setRange(0.01, 1000); self.stn.setDecimals(2)
        self.stn.setValue(cfg.star_tracker_noise_arcsec)
        form.addRow("Centroid noise (arcsec):", self.stn)
        grp.setLayout(form)
        layout.addWidget(grp)

        # EKF init
        grp = QGroupBox("EKF Initial Uncertainty")
        form = QFormLayout()
        self.ea = QDoubleSpinBox(); self.ea.setRange(1, 100000); self.ea.setDecimals(1)
        self.ea.setValue(cfg.ekf_attitude_init_sigma_arcsec)
        self.eb = QDoubleSpinBox(); self.eb.setRange(0.001, 100); self.eb.setDecimals(3)
        self.eb.setValue(cfg.ekf_bias_init_sigma_deg_hr)
        form.addRow("Attitude (arcsec):", self.ea)
        form.addRow("Bias (deg/hr):", self.eb)
        grp.setLayout(form)
        layout.addWidget(grp)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.apply_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def apply_and_accept(self):
        c = self.cfg
        c.gyro_white_noise_sigma = arcsec_s_to_bias(self.gwn.value())
        c.gyro_bias_drift_sigma = arcsec_s_to_bias(self.gbd.value())
        c.star_tracker_noise_arcsec = self.stn.value()
        c.ekf_attitude_init_sigma_arcsec = self.ea.value()
        c.ekf_bias_init_sigma_deg_hr = self.eb.value()
        self.accept()


# ═══════════════════════════════════════════════════════════
#  Config JSON save/load
# ═══════════════════════════════════════════════════════════

def config_to_dict(cfg):
    return {
        'distortion_k1_true': cfg.distortion_k1_true,
        'distortion_k2_true': cfg.distortion_k2_true,
        'distortion_p1_true': cfg.distortion_p1_true,
        'distortion_p2_true': cfg.distortion_p2_true,
        'distortion_k1_corr': cfg.distortion_k1_corr,
        'distortion_k2_corr': cfg.distortion_k2_corr,
        'distortion_p1_corr': cfg.distortion_p1_corr,
        'distortion_p2_corr': cfg.distortion_p2_corr,
        'gyro_bias_true': [bias_to_arcsec_s(v) for v in cfg.gyro_bias_true],
        'gyro_white_noise_sigma': bias_to_arcsec_s(cfg.gyro_white_noise_sigma),
        'gyro_bias_drift_sigma': bias_to_arcsec_s(cfg.gyro_bias_drift_sigma),
        'star_tracker_noise_arcsec': cfg.star_tracker_noise_arcsec,
        'ekf_attitude_init_sigma_arcsec': cfg.ekf_attitude_init_sigma_arcsec,
        'ekf_bias_init_sigma_deg_hr': cfg.ekf_bias_init_sigma_deg_hr,
        'position_error_enabled': cfg.position_error_enabled,
        'position_error_km': cfg.position_error_km.tolist(),
    }


def dict_to_config(d, cfg):
    cfg.distortion_k1_true = d.get('distortion_k1_true', cfg.distortion_k1_true)
    cfg.distortion_k2_true = d.get('distortion_k2_true', cfg.distortion_k2_true)
    cfg.distortion_p1_true = d.get('distortion_p1_true', cfg.distortion_p1_true)
    cfg.distortion_p2_true = d.get('distortion_p2_true', cfg.distortion_p2_true)
    cfg.distortion_k1_corr = d.get('distortion_k1_corr', cfg.distortion_k1_corr)
    cfg.distortion_k2_corr = d.get('distortion_k2_corr', cfg.distortion_k2_corr)
    cfg.distortion_p1_corr = d.get('distortion_p1_corr', cfg.distortion_p1_corr)
    cfg.distortion_p2_corr = d.get('distortion_p2_corr', cfg.distortion_p2_corr)
    if 'gyro_bias_true' in d:
        cfg.gyro_bias_true = np.array([arcsec_s_to_bias(v) for v in d['gyro_bias_true']])
    if 'gyro_white_noise_sigma' in d:
        cfg.gyro_white_noise_sigma = arcsec_s_to_bias(d['gyro_white_noise_sigma'])
    if 'gyro_bias_drift_sigma' in d:
        cfg.gyro_bias_drift_sigma = arcsec_s_to_bias(d['gyro_bias_drift_sigma'])
    cfg.star_tracker_noise_arcsec = d.get('star_tracker_noise_arcsec', cfg.star_tracker_noise_arcsec)
    cfg.ekf_attitude_init_sigma_arcsec = d.get('ekf_attitude_init_sigma_arcsec', cfg.ekf_attitude_init_sigma_arcsec)
    cfg.ekf_bias_init_sigma_deg_hr = d.get('ekf_bias_init_sigma_deg_hr', cfg.ekf_bias_init_sigma_deg_hr)
    cfg.position_error_enabled = d.get('position_error_enabled', cfg.position_error_enabled)
    if 'position_error_km' in d:
        cfg.position_error_km = np.array(d['position_error_km'])


# ═══════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════

class StarTrackerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Star Tracker EKF Simulation")
        self.resize(700, 700)

        self.cfg = Config()
        self.results = None
        self.worker = None
        self.stars_eci = None
        self.magnitudes = None
        self.plot_windows = []  # keep references so they don't get GC'd

        self._build_menus()
        self._build_ui()

        # Load catalog on startup
        self.status_label.setText("Loading star catalog...")
        QTimer.singleShot(100, self._load_catalog_and_show_initial)

    def _build_menus(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(
            "QMenuBar { color: black; }"
            "QMenuBar::item { color: black; }"
            "QMenu { color: black; }"
            "QMenu::item { color: black; }"
        )

        # File
        file_menu = menubar.addMenu("File")
        act = QAction("Open...", self); act.triggered.connect(self._file_open); file_menu.addAction(act)
        act = QAction("Save...", self); act.triggered.connect(self._file_save); file_menu.addAction(act)
        file_menu.addSeparator()
        act = QAction("Exit", self); act.triggered.connect(self.close); file_menu.addAction(act)

        # Configure
        cfg_menu = menubar.addMenu("Configure")
        act = QAction("System Noise...", self); act.triggered.connect(self._cfg_system_noise); cfg_menu.addAction(act)
        act = QAction("Gaussian Noise...", self); act.triggered.connect(self._cfg_gaussian_noise); cfg_menu.addAction(act)

        # Plot
        self.plot_menu = menubar.addMenu("Plot")
        self.act_kalman = QAction("Kalman Track", self); self.act_kalman.triggered.connect(self._plot_kalman)
        self.act_innov = QAction("Innovation", self); self.act_innov.triggered.connect(self._plot_innovation)
        self.act_overview = QAction("Overview", self); self.act_overview.triggered.connect(self._plot_overview)
        self.plot_menu.addAction(self.act_overview)
        self.plot_menu.addSeparator()
        self.plot_menu.addAction(self.act_kalman)
        self.plot_menu.addAction(self.act_innov)
        self.act_kalman.setEnabled(False)
        self.act_innov.setEnabled(False)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()

        # Top bar: Run button + status
        top = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.run_btn.setFixedWidth(80)
        self.run_btn.setStyleSheet("background-color: lightblue;")
        self.run_btn.clicked.connect(self._run_simulation)
        top.addWidget(self.run_btn)
        top.addStretch()
        self.status_label = QLabel("Ready")
        top.addWidget(self.status_label)
        layout.addLayout(top)

        # Star field display
        self.display = QLabel()
        self.display.setAlignment(Qt.AlignCenter)
        self.display.setMinimumSize(600, 600)
        self.display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.display.setStyleSheet("background-color: black;")
        layout.addWidget(self.display)

        central.setLayout(layout)

    def _load_catalog_and_show_initial(self):
        self.stars_eci, self.magnitudes, _ = load_catalog(self.cfg.star_tracker_mag_limit)
        self.status_label.setText(f"Catalog loaded: {len(self.stars_eci)} stars.  Ready.")
        self._show_initial_star_field()

    def _show_initial_star_field(self):
        if self.stars_eci is None:
            return
        body_vecs, _, mags, _ = query_stars_in_fov(
            self.stars_eci, self.magnitudes,
            self.cfg.q_initial, self.cfg.star_tracker_fov_deg
        )
        frame_bgr = render_star_frame_cv2(
            body_vecs, mags, self.cfg.star_tracker_fov_deg,
            image_size=600, time_label="t = 0.0s"
        )
        self._display_frame_bgr(frame_bgr)

    def _display_frame_bgr(self, frame_bgr):
        frame_rgb = frame_bgr[:, :, ::-1].copy()
        h, w, ch = frame_rgb.shape
        qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(self.display.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.display.setPixmap(scaled)

    # ── Menu handlers ──

    def _file_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Config", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r') as f:
                d = json.load(f)
            dict_to_config(d, self.cfg)
            self.status_label.setText(f"Config loaded from {os.path.basename(path)}")
            self._show_initial_star_field()

    def _file_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Config", "config.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w') as f:
                json.dump(config_to_dict(self.cfg), f, indent=2)
            self.status_label.setText(f"Config saved to {os.path.basename(path)}")

    def _cfg_system_noise(self):
        dlg = SystemNoiseDialog(self.cfg, self)
        dlg.exec_()

    def _cfg_gaussian_noise(self):
        dlg = GaussianNoiseDialog(self.cfg, self)
        dlg.exec_()

    def _plot_kalman(self):
        if self.results:
            win = show_kalman_track(self.results, self)
            self.plot_windows.append(win)

    def _plot_innovation(self):
        if self.results:
            win = show_innovations(self.results, self)
            self.plot_windows.append(win)

    def _plot_overview(self):
        win = show_overview(self.cfg, self)
        self.plot_windows.append(win)

    # ── Simulation ──

    def _run_simulation(self):
        if self.stars_eci is None:
            return

        self.run_btn.setEnabled(False)
        self.act_kalman.setEnabled(False)
        self.act_innov.setEnabled(False)
        self.status_label.setText("Running simulation...")

        self.worker = SimulationWorker(self.cfg, self.stars_eci, self.magnitudes)
        self.worker.progress.connect(self._on_progress)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, pct, msg):
        self.status_label.setText(f"[{pct}%] {msg}")

    def _on_frame(self, qimg):
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(self.display.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.display.setPixmap(scaled)

    def _on_finished(self, results):
        self.results = results
        self.run_btn.setEnabled(True)
        self.act_kalman.setEnabled(True)
        self.act_innov.setEnabled(True)
        rss = results['rss_mean']
        self.status_label.setText(
            f"Complete - RSS: {rss:.2f} arcsec (mean), "
            f"{results['rss_max']:.2f} arcsec (max), "
            f"{results['num_updates']} updates"
        )


# ═══════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = StarTrackerGUI()
    window.show()
    sys.exit(app.exec_())
