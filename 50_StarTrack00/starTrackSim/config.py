"""Simulation configuration — all tuneable parameters in one place."""

import numpy as np


class Config:
    # ── Random seed ──
    seed = 42

    # ── Simulation timing ──
    sim_duration_s = 60.0          # total simulation time (seconds)
    gyro_rate_hz = 1000.0          # gyro sample / propagation rate
    star_tracker_rate_hz = 20.0    # star tracker update rate

    @property
    def dt_gyro(self):
        return 1.0 / self.gyro_rate_hz

    @property
    def dt_star_tracker(self):
        return 1.0 / self.star_tracker_rate_hz

    @property
    def gyro_ticks_per_st_update(self):
        return int(self.gyro_rate_hz / self.star_tracker_rate_hz)

    @property
    def num_gyro_ticks(self):
        return int(self.sim_duration_s * self.gyro_rate_hz)

    # ── Orbit ──
    orbit_altitude_km = 6371.0    # 1 Earth-radius above surface
    orbit_inclination_deg = 51.6  # ISS-like inclination
    earth_radius_km = 6371.0

    # ── Initial attitude ──
    # Initial quaternion [w, x, y, z] — near identity (nadir pointing)
    q_initial = np.array([1.0, 0.0, 0.0, 0.0])

    # ── Attitude trajectory ──
    # Rotation rate for truth trajectory (rad/s per axis)
    # ~0.1 deg/s in X gives ~6 deg over 60s = 30% of 20-deg FOV
    truth_rotation_rate = np.array([
        np.deg2rad(0.10),   # X cross-bore: 6 deg in 60s
        np.deg2rad(0.02),   # Y cross-bore: 1.2 deg in 60s
        np.deg2rad(0.005),  # Z roll: 0.3 deg in 60s
    ])

    # ── Gyro noise model ──
    gyro_bias_true = np.array([0.5, -0.3, 0.2]) * np.deg2rad(1.0 / 3600.0)
    # True bias per axis (rad/s) — converted from deg/hr
    gyro_white_noise_sigma = 0.001 * np.deg2rad(1.0 / 3600.0)
    # White noise std dev (rad/s) — ~0.001 deg/hr per sqrt(Hz)
    gyro_bias_drift_sigma = 0.0001 * np.deg2rad(1.0 / 3600.0)
    # Bias drift (random walk) std dev (rad/s/sqrt(s))

    # ── Star tracker ──
    star_tracker_fov_deg = 20.0   # full-cone field of view (degrees)
    star_tracker_mag_limit = 6.0  # limiting visual magnitude
    star_tracker_noise_arcsec = 5.0  # 1-sigma centroid noise (arcseconds)
    star_tracker_min_stars = 3    # minimum stars needed for attitude solution

    # ── Optical distortion (Brown-Conrady model) ──
    # True distortion coefficients (applied to star vectors)
    distortion_k1_true = 1.0e-4   # radial distortion coefficient
    distortion_k2_true = 5.0e-7   # radial distortion coefficient (higher order)
    distortion_p1_true = 1.0e-5   # tangential distortion coefficient
    distortion_p2_true = -1.0e-5  # tangential distortion coefficient

    # Correction coefficients (imperfect — slightly off from true)
    distortion_k1_corr = 0.95e-4
    distortion_k2_corr = 4.5e-7
    distortion_p1_corr = 1.1e-5
    distortion_p2_corr = -0.9e-5

    # ── EKF initial conditions ──
    ekf_attitude_init_sigma_arcsec = 600.0  # initial attitude uncertainty (arcsec)
    ekf_bias_init_sigma_deg_hr = 1.0        # initial bias uncertainty (deg/hr)

    # ── Position error injection ──
    position_error_enabled = False
    position_error_km = np.array([0.0, 0.0, 0.0])  # offset in ECI (km)
