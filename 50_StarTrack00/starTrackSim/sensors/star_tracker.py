"""Star tracker measurement simulator.

Generates attitude quaternion measurements from star observations,
including optical distortion and centroiding noise.
"""

import numpy as np
from ..quaternion_utils import quat_to_dcm, dcm_to_quat, quat_normalize
from ..star_catalog import query_stars_in_fov
from ..distortion import (
    apply_distortion_to_vectors,
    correct_distortion_on_vectors,
)


def _solve_attitude_svd(body_vectors, ref_vectors):
    """Solve Wahba's problem using SVD method.

    Finds the rotation R that minimizes sum of |b_i - R * r_i|^2.

    Args:
        body_vectors: (K, 3) measured star vectors in body frame
        ref_vectors: (K, 3) catalog star vectors in ECI

    Returns:
        q: (4,) attitude quaternion [w, x, y, z]
    """
    # Build the attitude profile matrix B = sum(b_i * r_i^T)
    B = np.zeros((3, 3))
    for b, r in zip(body_vectors, ref_vectors):
        B += np.outer(b, r)

    U, _, Vt = np.linalg.svd(B)

    # Ensure proper rotation (det = +1)
    d = np.linalg.det(U) * np.linalg.det(Vt)
    D = np.diag([1.0, 1.0, d])

    R = U @ D @ Vt
    return dcm_to_quat(R)


def generate_star_tracker_measurement(q_true, stars_eci, magnitudes, cfg, rng):
    """Generate a single star tracker attitude measurement.

    Pipeline:
        1. Find stars in FOV using true attitude
        2. Apply true optical distortion to body vectors
        3. Apply imperfect distortion correction
        4. Add centroiding noise
        5. Solve attitude from noisy body vectors vs catalog vectors

    Args:
        q_true: (4,) true attitude quaternion
        stars_eci: (M, 3) full star catalog in ECI
        magnitudes: (M,) star magnitudes
        cfg: Config object
        rng: numpy random Generator

    Returns:
        q_meas: (4,) measured attitude quaternion, or None if insufficient stars
        num_stars: number of stars used
    """
    # 1. Find stars in FOV
    body_true, eci_vis, mags, indices = query_stars_in_fov(
        stars_eci, magnitudes, q_true, cfg.star_tracker_fov_deg
    )

    if len(body_true) < cfg.star_tracker_min_stars:
        return None, 0

    # 2. Apply true optical distortion
    body_distorted = apply_distortion_to_vectors(
        body_true,
        cfg.distortion_k1_true, cfg.distortion_k2_true,
        cfg.distortion_p1_true, cfg.distortion_p2_true,
    )

    if len(body_distorted) < cfg.star_tracker_min_stars:
        return None, 0

    # 3. Apply imperfect distortion correction
    body_corrected = correct_distortion_on_vectors(
        body_distorted,
        cfg.distortion_k1_corr, cfg.distortion_k2_corr,
        cfg.distortion_p1_corr, cfg.distortion_p2_corr,
    )

    if len(body_corrected) < cfg.star_tracker_min_stars:
        return None, 0

    # 4. Add centroiding noise (angular noise on each star vector)
    noise_sigma_rad = np.deg2rad(cfg.star_tracker_noise_arcsec / 3600.0)
    body_noisy = np.zeros_like(body_corrected)
    for i, v in enumerate(body_corrected):
        # Add small random rotation to each vector
        noise_angles = rng.normal(0.0, noise_sigma_rad, size=3)
        # Rodrigues rotation for small angles: v' ≈ v + noise × v
        body_noisy[i] = v + np.cross(noise_angles, v)
        body_noisy[i] /= np.linalg.norm(body_noisy[i])

    # 5. Solve attitude from noisy body vectors vs catalog (ECI) vectors
    # Use only the first len(body_noisy) ECI vectors (matching indices)
    eci_matched = eci_vis[:len(body_noisy)]
    q_meas = _solve_attitude_svd(body_noisy, eci_matched)

    return q_meas, len(body_noisy)
