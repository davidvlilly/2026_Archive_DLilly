"""Simple circular orbit model — satellite position in ECI."""

import numpy as np


def compute_orbit_positions(cfg, num_ticks, dt):
    """Compute satellite position in ECI for a circular orbit.

    Args:
        cfg: Config object (altitude, inclination)
        num_ticks: number of time steps
        dt: time step (seconds)

    Returns:
        positions_eci: (N, 3) satellite position in ECI (km)
    """
    r_orbit = cfg.earth_radius_km + cfg.orbit_altitude_km  # km
    mu_earth = 398600.4418  # km³/s² — Earth gravitational parameter
    omega_orbit = np.sqrt(mu_earth / r_orbit**3)  # rad/s (mean motion)
    inc = np.deg2rad(cfg.orbit_inclination_deg)

    positions = np.zeros((num_ticks, 3))
    for k in range(num_ticks):
        t = k * dt
        theta = omega_orbit * t  # true anomaly (= mean anomaly for circular)

        # Position in orbital plane
        x_orb = r_orbit * np.cos(theta)
        y_orb = r_orbit * np.sin(theta)

        # Rotate by inclination (RAAN = 0 for simplicity)
        positions[k, 0] = x_orb
        positions[k, 1] = y_orb * np.cos(inc)
        positions[k, 2] = y_orb * np.sin(inc)

    # Apply position error if enabled
    if cfg.position_error_enabled:
        positions += cfg.position_error_km[np.newaxis, :]

    return positions


def earth_angular_radius(position_eci, earth_radius_km=6371.0):
    """Compute angular radius of Earth as seen from the satellite.

    Used to check if stars are blocked by Earth limb.

    Args:
        position_eci: (3,) satellite position in ECI (km)

    Returns:
        angular_radius_rad: angular radius of Earth (radians)
    """
    r = np.linalg.norm(position_eci)
    if r <= earth_radius_km:
        return np.pi  # inside Earth (shouldn't happen)
    return np.arcsin(earth_radius_km / r)
