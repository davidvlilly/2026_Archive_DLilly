"""Star Tracker EKF Simulation — Main Entry Point.

Runs a multi-rate EKF simulation:
  - Propagation at gyro rate (1000 Hz) using quaternion kinematics
  - Update at star tracker rate (20 Hz) using star vector measurements

Plots performance against truth in arcseconds.
"""

import os
import sys
import time
import numpy as np

# Add project root to path so starTrackSim package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starTrackSim.config import Config
from starTrackSim.truth import generate_truth_trajectory
from starTrackSim.sensors.gyro import generate_gyro_measurements
from starTrackSim.sensors.star_tracker import generate_star_tracker_measurement
from starTrackSim.star_catalog import load_catalog
from starTrackSim.ekf.state import EKFState
from starTrackSim.ekf.propagate import propagate
from starTrackSim.ekf.update import update
from starTrackSim.quaternion_utils import quat_error_angles
from starTrackSim.plotting import plot_results, plot_innovations
from starTrackSim.star_image import render_star_image, generate_star_movie
from starTrackSim.star_catalog import query_stars_in_fov


def main():
    cfg = Config()
    rng = np.random.default_rng(cfg.seed)

    # Create output directory
    os.makedirs('starTrackSim/output', exist_ok=True)

    # ── Load star catalog ──
    print("Loading star catalog...")
    stars_eci, magnitudes, hip_ids = load_catalog(cfg.star_tracker_mag_limit)
    print(f"  Loaded {len(stars_eci)} stars (mag <= {cfg.star_tracker_mag_limit})")

    # ── Generate truth trajectory ──
    print("Generating truth trajectory...")
    q_true, omega_true = generate_truth_trajectory(cfg)
    print(f"  {cfg.num_gyro_ticks} ticks, {cfg.sim_duration_s}s duration")

    # ── Generate gyro measurements ──
    print("Generating gyro measurements...")
    omega_meas, bias_true = generate_gyro_measurements(omega_true, cfg, rng)
    b0 = np.rad2deg(bias_true[0]) * 3600.0
    print(f"  True bias: [{b0[0]:.2f}, {b0[1]:.2f}, {b0[2]:.2f}] arcsec/s")

    # ── Render initial star field image ──
    print("Rendering initial star field...")
    body_vecs, eci_vecs, mags, _ = query_stars_in_fov(
        stars_eci, magnitudes, q_true[0], cfg.star_tracker_fov_deg
    )
    print(f"  {len(body_vecs)} stars in FOV at t=0")
    render_star_image(body_vecs, mags, cfg.star_tracker_fov_deg,
                      title=f"Star Field at t=0 ({len(body_vecs)} stars)",
                      save_path='starTrackSim/output/star_field_t0.png')

    # ── Generate star field movie ──
    print("Generating star field movie...")
    generate_star_movie(q_true, stars_eci, magnitudes, cfg.star_tracker_fov_deg, cfg,
                        output_path='starTrackSim/output/star_field.mp4',
                        fps=15, image_size=800, frame_interval_s=0.5)

    # ── Initialize EKF ──
    ekf = EKFState(cfg)

    # ── Storage ──
    N = cfg.num_gyro_ticks
    att_errors = np.zeros((N, 3))
    bias_errors = np.zeros((N, 3))
    P_diag_history = np.zeros((N, 6))
    st_update_times = []
    innovations = []

    ticks_per_update = cfg.gyro_ticks_per_st_update
    dt = cfg.dt_gyro

    # ── Main loop ──
    print(f"\nRunning EKF ({cfg.sim_duration_s}s, "
          f"propagate @ {cfg.gyro_rate_hz:.0f} Hz, "
          f"update @ {cfg.star_tracker_rate_hz:.0f} Hz)...")
    t_start = time.time()

    num_updates = 0
    num_missed = 0

    for k in range(N):
        # ── PROPAGATE (every tick) ──
        propagate(ekf, omega_meas[k], dt)

        # ── UPDATE (every ticks_per_update ticks) ──
        if (k + 1) % ticks_per_update == 0:
            q_st, num_stars = generate_star_tracker_measurement(
                q_true[k], stars_eci, magnitudes, cfg, rng
            )
            if q_st is not None:
                # Compute innovation before update (for plotting)
                innov = quat_error_angles(q_st, ekf.q_ref)
                innovations.append((k * dt, innov))

                update(ekf, q_st)
                num_updates += 1
                st_update_times.append(k * dt)
            else:
                num_missed += 1

        # ── Record errors ──
        att_errors[k] = quat_error_angles(q_true[k], ekf.q_ref)
        bias_errors[k] = bias_true[k] - ekf.bias_est
        P_diag_history[k] = np.diag(ekf.P)

        # Progress
        if (k + 1) % (N // 10) == 0:
            pct = 100.0 * (k + 1) / N
            rss_arcsec = np.linalg.norm(att_errors[k]) * 3600.0 * np.degrees(1.0)
            print(f"  {pct:5.1f}%  t={k*dt:6.1f}s  RSS={rss_arcsec:8.2f} arcsec  "
                  f"updates={num_updates}")

    elapsed = time.time() - t_start
    print(f"\nDone in {elapsed:.1f}s  "
          f"({num_updates} updates, {num_missed} missed)")

    # ── Plot results ──
    time_s = np.arange(N) * dt
    print("\nGenerating plots...")
    plot_results(time_s, att_errors, bias_errors, P_diag_history,
                 st_update_times, innovations)
    plot_innovations(innovations)

    # ── Summary statistics (steady state — last 25%) ──
    ss_start = int(0.75 * N)
    ss_att = att_errors[ss_start:]
    ss_rss = np.linalg.norm(ss_att, axis=1)
    rad_to_arcsec = 3600.0 * np.degrees(1.0)

    print("\n-- Steady-State Performance (last 25%) --")
    print(f"  Cross-bore X:  {np.std(ss_att[:, 0]) * rad_to_arcsec:.2f} arcsec (1-sigma)")
    print(f"  Cross-bore Y:  {np.std(ss_att[:, 1]) * rad_to_arcsec:.2f} arcsec (1-sigma)")
    print(f"  About-bore Z:  {np.std(ss_att[:, 2]) * rad_to_arcsec:.2f} arcsec (1-sigma)")
    print(f"  RSS:           {np.mean(ss_rss) * rad_to_arcsec:.2f} arcsec (mean)")
    print(f"  RSS:           {np.max(ss_rss) * rad_to_arcsec:.2f} arcsec (max)")

    ss_bias = bias_errors[ss_start:]
    print(f"\n  Bias X error:  {np.std(ss_bias[:, 0]) * rad_to_arcsec:.4f} arcsec/s (1-sigma)")
    print(f"  Bias Y error:  {np.std(ss_bias[:, 1]) * rad_to_arcsec:.4f} arcsec/s (1-sigma)")
    print(f"  Bias Z error:  {np.std(ss_bias[:, 2]) * rad_to_arcsec:.4f} arcsec/s (1-sigma)")


if __name__ == '__main__':
    main()
