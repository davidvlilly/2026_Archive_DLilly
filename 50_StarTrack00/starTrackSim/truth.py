"""Generate truth attitude trajectory and angular velocity."""

import numpy as np
from .quaternion_utils import quat_multiply, quat_from_omega, quat_normalize


def generate_truth_trajectory(cfg):
    """Generate truth quaternion and angular velocity arrays.

    Uses a constant body-frame rotation rate to produce a smooth
    attitude trajectory. The angular velocity is constant (simplest case)
    but can be extended to time-varying profiles.

    Returns:
        q_true: (N, 4) array of truth quaternions [w, x, y, z]
        omega_true: (N, 3) array of true angular velocity (rad/s) in body frame
    """
    N = cfg.num_gyro_ticks
    dt = cfg.dt_gyro

    q_true = np.zeros((N, 4))
    omega_true = np.zeros((N, 3))

    q_true[0] = quat_normalize(cfg.q_initial.copy())
    omega_true[0] = cfg.truth_rotation_rate.copy()

    for k in range(1, N):
        omega = cfg.truth_rotation_rate
        dq = quat_from_omega(omega, dt)
        q_true[k] = quat_normalize(quat_multiply(q_true[k - 1], dq))
        omega_true[k] = omega.copy()

    return q_true, omega_true
