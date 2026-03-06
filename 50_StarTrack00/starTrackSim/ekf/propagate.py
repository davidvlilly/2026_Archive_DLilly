"""EKF propagation (predict) step — quaternion kinematics + covariance prediction."""

import numpy as np
from ..quaternion_utils import (
    quat_multiply, quat_from_omega, quat_normalize, skew_symmetric,
)


def propagate(ekf_state, omega_meas, dt):
    """Run one EKF propagation step.

    Equations:
        ω = ω_meas - b_est                          (corrected angular velocity)
        q_ref(k+1) = q_ref(k) ⊗ δq(ω, dt)          (state prediction)
        P(k+1) = F · P · Fᵀ + Q                     (covariance prediction)

    Args:
        ekf_state: EKFState object (modified in place)
        omega_meas: (3,) gyro measurement (rad/s)
        dt: time step (seconds)
    """
    # Corrected angular velocity
    omega = omega_meas - ekf_state.bias_est

    # ── State prediction ──
    dq = quat_from_omega(omega, dt)
    ekf_state.q_ref = quat_normalize(quat_multiply(ekf_state.q_ref, dq))
    # Bias estimate unchanged during propagation

    # ── Covariance prediction ──
    # State transition Jacobian F (6×6)
    #   F = [ I - [ω×]dt    -I·dt ]
    #       [ 0              I    ]
    I3 = np.eye(3)
    omega_cross = skew_symmetric(omega)

    F = np.eye(6)
    F[0:3, 0:3] = I3 - omega_cross * dt  # attitude block
    F[0:3, 3:6] = -I3 * dt               # bias-to-attitude coupling
    # F[3:6, 3:6] = I3                    # already set by np.eye(6)

    # Process noise (discrete-time approximation)
    Q = ekf_state.Q_continuous * dt

    ekf_state.P = F @ ekf_state.P @ F.T + Q
