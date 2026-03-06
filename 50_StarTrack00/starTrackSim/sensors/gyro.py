"""Gyro simulator — true angular velocity + bias + white noise."""

import numpy as np


def generate_gyro_measurements(omega_true, cfg, rng):
    """Generate simulated gyro measurements.

    Model:
        omega_meas(k) = omega_true(k) + bias(k) + noise(k)
        bias(k+1) = bias(k) + drift_noise(k)

    Args:
        omega_true: (N, 3) true angular velocity in body frame (rad/s)
        cfg: Config object
        rng: numpy random Generator

    Returns:
        omega_meas: (N, 3) measured angular velocity (rad/s)
        bias_true: (N, 3) true bias at each time step (rad/s)
    """
    N = omega_true.shape[0]
    dt = cfg.dt_gyro

    bias_true = np.zeros((N, 3))
    omega_meas = np.zeros((N, 3))

    # Initial bias
    bias_true[0] = cfg.gyro_bias_true.copy()

    for k in range(N):
        # White noise
        noise = rng.normal(0.0, cfg.gyro_white_noise_sigma, size=3)

        # Measurement = truth + bias + noise
        omega_meas[k] = omega_true[k] + bias_true[k] + noise

        # Propagate bias with random walk drift
        if k < N - 1:
            drift = rng.normal(0.0, cfg.gyro_bias_drift_sigma * np.sqrt(dt), size=3)
            bias_true[k + 1] = bias_true[k] + drift

    return omega_meas, bias_true
