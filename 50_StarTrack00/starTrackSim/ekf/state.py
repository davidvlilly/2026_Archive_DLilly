"""EKF state container — holds the filter state, covariance, and noise matrices."""

import numpy as np
from ..quaternion_utils import quat_normalize


class EKFState:
    """Multi-rate EKF state for attitude determination.

    State vector (error-state formulation):
        x = [δθ(3), δb(3)]   — attitude error angles + bias error
        But we maintain the full reference quaternion separately.

    Attributes:
        q_ref: (4,) reference quaternion [w, x, y, z]
        bias_est: (3,) estimated gyro bias (rad/s)
        P: (6, 6) error covariance matrix
        Q: (6, 6) process noise covariance (per second, scaled by dt in propagation)
        R: (3, 3) star tracker measurement noise covariance
    """

    def __init__(self, cfg):
        # Reference quaternion — start at initial attitude
        self.q_ref = quat_normalize(cfg.q_initial.copy())

        # Bias estimate — start at zero (we don't know the bias yet)
        self.bias_est = np.zeros(3)

        # Initial covariance
        att_sigma = np.deg2rad(cfg.ekf_attitude_init_sigma_arcsec / 3600.0)
        bias_sigma = cfg.ekf_bias_init_sigma_deg_hr * np.deg2rad(1.0 / 3600.0)
        self.P = np.diag([
            att_sigma**2, att_sigma**2, att_sigma**2,
            bias_sigma**2, bias_sigma**2, bias_sigma**2,
        ])

        # Process noise Q (continuous-time spectral density, will be scaled by dt)
        q_gyro = cfg.gyro_white_noise_sigma**2
        q_bias = cfg.gyro_bias_drift_sigma**2
        self.Q_continuous = np.diag([
            q_gyro, q_gyro, q_gyro,
            q_bias, q_bias, q_bias,
        ])

        # Measurement noise R — star tracker attitude error
        st_sigma = np.deg2rad(cfg.star_tracker_noise_arcsec / 3600.0)
        self.R = np.eye(3) * st_sigma**2
