"""EKF update (correct) step — star tracker measurement incorporation."""

import numpy as np
from ..quaternion_utils import quat_error_angles, apply_error_angles, quat_normalize


def update(ekf_state, q_measured):
    """Run one EKF measurement update step.

    Equations:
        y = z - h(x)                     (innovation)
        S = H · P · Hᵀ + R              (innovation covariance)
        K = P · Hᵀ · S⁻¹                (Kalman gain)
        δx = K · y                       (state correction)
        P = (I - K·H) · P               (covariance update)

    For the MEKF, the measurement is the attitude error between the
    star tracker quaternion and the EKF reference quaternion.
    H = [I₃, 0₃ₓ₃] — star tracker directly observes attitude error.

    Args:
        ekf_state: EKFState object (modified in place)
        q_measured: (4,) star tracker attitude quaternion [w, x, y, z]
    """
    # ── Innovation ──
    # y = error angle between measured and predicted attitude
    y = quat_error_angles(q_measured, ekf_state.q_ref)  # (3,)

    # ── Measurement model ──
    # H = [I₃ | 0₃ₓ₃] — star tracker measures attitude directly
    H = np.zeros((3, 6))
    H[0:3, 0:3] = np.eye(3)

    # ── Innovation covariance ──
    S = H @ ekf_state.P @ H.T + ekf_state.R  # (3×3)

    # ── Kalman gain ──
    K = ekf_state.P @ H.T @ np.linalg.inv(S)  # (6×3)

    # ── State correction ──
    dx = K @ y  # (6,)
    dtheta = dx[0:3]  # attitude correction
    dbias = dx[3:6]   # bias correction

    # Apply attitude correction to reference quaternion
    ekf_state.q_ref = quat_normalize(apply_error_angles(ekf_state.q_ref, dtheta))

    # Apply bias correction
    ekf_state.bias_est = ekf_state.bias_est + dbias

    # ── Covariance update ──
    I6 = np.eye(6)
    ekf_state.P = (I6 - K @ H) @ ekf_state.P

    # Symmetrize P to prevent numerical drift
    ekf_state.P = 0.5 * (ekf_state.P + ekf_state.P.T)
