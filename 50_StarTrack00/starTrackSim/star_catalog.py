"""Star catalog — load Hipparcos via skyfield, query stars in FOV."""

import numpy as np
from skyfield.api import load
from skyfield.data import hipparcos


def load_catalog(mag_limit=6.0):
    """Load Hipparcos star catalog, filtered by magnitude.

    Returns:
        stars_eci: (M, 3) unit direction vectors in ECI (J2000)
        magnitudes: (M,) visual magnitudes
        hip_ids: (M,) Hipparcos IDs
    """
    with load.open(hipparcos.URL) as f:
        df = hipparcos.load_dataframe(f)

    # Filter by magnitude
    df = df[df['magnitude'] <= mag_limit].copy()
    df = df.dropna(subset=['ra_degrees', 'dec_degrees'])

    ra_rad = np.deg2rad(df['ra_degrees'].values)
    dec_rad = np.deg2rad(df['dec_degrees'].values)
    magnitudes = df['magnitude'].values
    hip_ids = df.index.values

    # Convert RA/Dec to ECI unit vectors
    cos_dec = np.cos(dec_rad)
    stars_eci = np.column_stack([
        cos_dec * np.cos(ra_rad),
        cos_dec * np.sin(ra_rad),
        np.sin(dec_rad),
    ])

    return stars_eci, magnitudes, hip_ids


def query_stars_in_fov(stars_eci, magnitudes, q_true, fov_deg):
    """Find stars visible in the star tracker FOV.

    The boresight is assumed to be the body +Z axis.

    Args:
        stars_eci: (M, 3) star unit vectors in ECI
        magnitudes: (M,) magnitudes
        q_true: (4,) true attitude quaternion [w, x, y, z]
        fov_deg: full-cone field of view in degrees

    Returns:
        body_vectors: (K, 3) star unit vectors in body frame (visible stars)
        eci_vectors: (K, 3) corresponding ECI vectors
        mags: (K,) magnitudes of visible stars
        indices: (K,) indices into the original catalog
    """
    from .quaternion_utils import quat_to_dcm

    # Rotation from ECI to body frame
    R_eci2body = quat_to_dcm(q_true)  # R rotates ECI vectors into body frame

    # Transform all stars to body frame
    body_all = (R_eci2body @ stars_eci.T).T  # (M, 3)

    # Boresight is +Z in body frame
    cos_half_fov = np.cos(np.deg2rad(fov_deg / 2.0))
    # Star is in FOV if its body-frame Z component > cos(half_fov)
    in_fov = body_all[:, 2] > cos_half_fov

    indices = np.where(in_fov)[0]
    body_vectors = body_all[indices]
    eci_vectors = stars_eci[indices]
    mags = magnitudes[indices]

    return body_vectors, eci_vectors, mags, indices
