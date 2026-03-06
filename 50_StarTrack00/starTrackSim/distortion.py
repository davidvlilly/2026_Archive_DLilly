"""Optical distortion model (Brown-Conrady) — apply and imperfect correction."""

import numpy as np


def body_vector_to_focal(v_body):
    """Project body-frame unit vector onto focal plane (gnomonic projection).

    Boresight is +Z. Returns (x, y) in the focal plane (normalized, unitless).
    """
    # Avoid division by zero for stars behind the sensor
    if v_body[2] <= 0:
        return None
    x = v_body[0] / v_body[2]
    y = v_body[1] / v_body[2]
    return np.array([x, y])


def focal_to_body_vector(xy):
    """Convert focal plane coordinates back to unit body vector."""
    x, y = xy
    v = np.array([x, y, 1.0])
    return v / np.linalg.norm(v)


def apply_distortion(xy, k1, k2, p1, p2):
    """Apply Brown-Conrady distortion to focal plane coordinates.

    Args:
        xy: (2,) focal plane point [x, y]
        k1, k2: radial distortion coefficients
        p1, p2: tangential distortion coefficients

    Returns:
        xy_distorted: (2,) distorted focal plane point
    """
    x, y = xy
    r2 = x*x + y*y
    r4 = r2 * r2

    # Radial distortion
    radial = 1.0 + k1 * r2 + k2 * r4

    # Tangential distortion
    dx_tang = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x*x)
    dy_tang = p1 * (r2 + 2.0 * y*y) + 2.0 * p2 * x * y

    x_dist = x * radial + dx_tang
    y_dist = y * radial + dy_tang

    return np.array([x_dist, y_dist])


def remove_distortion(xy_distorted, k1, k2, p1, p2, iterations=5):
    """Remove distortion using iterative correction (imperfect if coefficients are wrong).

    Uses iterative undistortion since the inverse doesn't have a closed form.

    Args:
        xy_distorted: (2,) distorted focal plane point
        k1, k2, p1, p2: correction coefficients (may differ from true)
        iterations: number of refinement iterations

    Returns:
        xy_corrected: (2,) corrected focal plane point
    """
    # Start with the distorted point as initial guess
    x, y = xy_distorted

    for _ in range(iterations):
        r2 = x*x + y*y
        r4 = r2 * r2
        radial = 1.0 + k1 * r2 + k2 * r4
        dx_tang = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x*x)
        dy_tang = p1 * (r2 + 2.0 * y*y) + 2.0 * p2 * x * y

        x = (xy_distorted[0] - dx_tang) / radial
        y = (xy_distorted[1] - dy_tang) / radial

    return np.array([x, y])


def apply_distortion_to_vectors(body_vectors, k1, k2, p1, p2):
    """Apply distortion to an array of body-frame star vectors.

    Returns distorted body vectors (still unit vectors).
    """
    distorted = []
    for v in body_vectors:
        xy = body_vector_to_focal(v)
        if xy is None:
            continue
        xy_dist = apply_distortion(xy, k1, k2, p1, p2)
        distorted.append(focal_to_body_vector(xy_dist))
    return np.array(distorted) if distorted else np.empty((0, 3))


def correct_distortion_on_vectors(body_vectors, k1, k2, p1, p2):
    """Remove distortion from an array of body-frame star vectors.

    Uses the (possibly imperfect) correction coefficients.
    """
    corrected = []
    for v in body_vectors:
        xy = body_vector_to_focal(v)
        if xy is None:
            continue
        xy_corr = remove_distortion(xy, k1, k2, p1, p2)
        corrected.append(focal_to_body_vector(xy_corr))
    return np.array(corrected) if corrected else np.empty((0, 3))
