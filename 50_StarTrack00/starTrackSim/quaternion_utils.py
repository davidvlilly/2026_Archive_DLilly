"""Quaternion utilities — convention: q = [w, x, y, z] (scalar-first)."""

import numpy as np


def quat_multiply(q1, q2):
    """Multiply two quaternions: q_result = q1 ⊗ q2."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])


def quat_conjugate(q):
    """Quaternion conjugate (inverse for unit quaternions)."""
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quat_normalize(q):
    """Normalize quaternion to unit length."""
    n = np.linalg.norm(q)
    if n < 1e-15:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return q / n


def quat_to_dcm(q):
    """Convert quaternion to 3x3 direction cosine (rotation) matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - w*z),     2*(x*z + w*y)],
        [    2*(x*y + w*z), 1 - 2*(x*x + z*z),     2*(y*z - w*x)],
        [    2*(x*z - w*y),     2*(y*z + w*x), 1 - 2*(x*x + y*y)],
    ])


def dcm_to_quat(R):
    """Convert 3x3 rotation matrix to quaternion (Shepperd's method)."""
    tr = np.trace(R)
    if tr > 0:
        s = 2.0 * np.sqrt(tr + 1.0)
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    if q[0] < 0:
        q = -q  # enforce positive scalar part
    return quat_normalize(q)


def quat_from_angle_axis(angle_rad, axis):
    """Create quaternion from rotation angle (rad) and unit axis vector."""
    axis = axis / np.linalg.norm(axis)
    ha = angle_rad / 2.0
    return np.array([np.cos(ha), *(axis * np.sin(ha))])


def quat_from_omega(omega, dt):
    """Create incremental rotation quaternion from angular velocity and time step.

    This is the δq used in propagation: q(k+1) = q(k) ⊗ δq(ω, dt)
    """
    angle = np.linalg.norm(omega) * dt
    if angle < 1e-12:
        # Small angle approximation
        return quat_normalize(np.array([1.0, *(omega * dt / 2.0)]))
    axis = omega / np.linalg.norm(omega)
    return quat_from_angle_axis(angle, axis)


def quat_error_angles(q_meas, q_ref):
    """Compute small error angle vector between two quaternions.

    Returns 3-vector δθ (radians) such that q_meas ≈ δq(δθ) ⊗ q_ref.
    """
    dq = quat_multiply(q_meas, quat_conjugate(q_ref))
    if dq[0] < 0:
        dq = -dq  # ensure short rotation
    # For small errors: δθ ≈ 2 * [x, y, z] of the error quaternion
    return 2.0 * dq[1:4]


def apply_error_angles(q_ref, dtheta):
    """Apply small error angle correction to a reference quaternion.

    q_corrected = δq(dtheta) ⊗ q_ref
    """
    half = dtheta / 2.0
    dq = quat_normalize(np.array([1.0, half[0], half[1], half[2]]))
    return quat_normalize(quat_multiply(dq, q_ref))


def skew_symmetric(v):
    """Build 3x3 skew-symmetric (cross-product) matrix from vector v."""
    return np.array([
        [   0, -v[2],  v[1]],
        [ v[2],    0, -v[0]],
        [-v[1],  v[0],    0],
    ])


def rotate_vector(q, v):
    """Rotate vector v by quaternion q: v' = R(q) · v."""
    R = quat_to_dcm(q)
    return R @ v
