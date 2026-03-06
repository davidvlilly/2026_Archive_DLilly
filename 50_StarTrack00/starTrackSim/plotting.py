"""Performance plotting — error analysis in arcseconds."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


RAD_TO_ARCSEC = 3600.0 * np.degrees(1.0)


def _find_index_after(time_s, t_start):
    """Find first index where time_s >= t_start."""
    idx = np.searchsorted(time_s, t_start)
    return min(idx, len(time_s) - 1)


def plot_results(time_s, att_errors, bias_errors, P_diag_history,
                 st_update_times, innovations, t_crop=1.0):
    """Generate all performance plots.

    Plots are auto-scaled using data after t_crop seconds to avoid
    the initial transient dominating the Y axis.

    Args:
        time_s: (N,) time array in seconds
        att_errors: (N, 3) attitude error [cross1, cross2, about_bore] in radians
        bias_errors: (N, 3) bias estimation error (rad/s)
        P_diag_history: (N, 6) diagonal of P at each step
        st_update_times: list of times when star tracker updates occurred
        innovations: list of (time, innovation_vector) tuples
        t_crop: time (seconds) after which to auto-scale Y axis
    """
    i_crop = _find_index_after(time_s, t_crop)

    fig, axes = plt.subplots(3, 2, figsize=(14, 10))
    fig.suptitle('Star Tracker EKF Performance', fontsize=14)

    # ── Cross-boresight error (arcsec) ──
    ax = axes[0, 0]
    err_x = att_errors[:, 0] * RAD_TO_ARCSEC
    err_y = att_errors[:, 1] * RAD_TO_ARCSEC
    sigma_att = np.sqrt(P_diag_history[:, 0]) * RAD_TO_ARCSEC
    ax.plot(time_s, err_x, 'b-', linewidth=0.5, label='X (cross-bore)')
    ax.plot(time_s, err_y, 'r-', linewidth=0.5, label='Y (cross-bore)')
    ax.plot(time_s, sigma_att, 'k--', linewidth=0.8, label='1-sigma (P)')
    ax.plot(time_s, -sigma_att, 'k--', linewidth=0.8)
    # Auto-scale from cropped data
    cropped_vals = np.concatenate([err_x[i_crop:], err_y[i_crop:],
                                   sigma_att[i_crop:], -sigma_att[i_crop:]])
    margin = (cropped_vals.max() - cropped_vals.min()) * 0.2
    ax.set_ylim(cropped_vals.min() - margin, cropped_vals.max() + margin)
    ax.set_xlim(time_s[0], time_s[-1])
    ax.set_ylabel('Cross-bore error (arcsec)')
    ax.set_title(f'Cross-Boresight Attitude Error (scaled from t={t_crop}s)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── About-boresight (roll) error ──
    ax = axes[0, 1]
    err_z = att_errors[:, 2] * RAD_TO_ARCSEC
    sigma_roll = np.sqrt(P_diag_history[:, 2]) * RAD_TO_ARCSEC
    ax.plot(time_s, err_z, 'g-', linewidth=0.5, label='Z (about-bore)')
    ax.plot(time_s, sigma_roll, 'k--', linewidth=0.8, label='1-sigma (P)')
    ax.plot(time_s, -sigma_roll, 'k--', linewidth=0.8)
    cropped_vals = np.concatenate([err_z[i_crop:], sigma_roll[i_crop:],
                                   -sigma_roll[i_crop:]])
    margin = (cropped_vals.max() - cropped_vals.min()) * 0.2
    ax.set_ylim(cropped_vals.min() - margin, cropped_vals.max() + margin)
    ax.set_xlim(time_s[0], time_s[-1])
    ax.set_ylabel('About-bore error (arcsec)')
    ax.set_title(f'About-Boresight (Roll) Error (scaled from t={t_crop}s)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── RSS attitude error ──
    ax = axes[1, 0]
    rss = np.linalg.norm(att_errors, axis=1) * RAD_TO_ARCSEC
    ax.plot(time_s, rss, 'm-', linewidth=0.5)
    rss_crop = rss[i_crop:]
    margin = (rss_crop.max() - rss_crop.min()) * 0.2
    ax.set_ylim(0, rss_crop.max() + margin)
    ax.set_xlim(time_s[0], time_s[-1])
    ax.set_ylabel('RSS error (arcsec)')
    ax.set_title(f'RSS Attitude Error (scaled from t={t_crop}s)')
    ax.grid(True, alpha=0.3)

    # ── Gyro bias estimation error ──
    ax = axes[1, 1]
    bias_err_as = bias_errors * RAD_TO_ARCSEC  # rad/s to arcsec/s
    ax.plot(time_s, bias_err_as[:, 0], 'b-', linewidth=0.5, label='X bias err')
    ax.plot(time_s, bias_err_as[:, 1], 'r-', linewidth=0.5, label='Y bias err')
    ax.plot(time_s, bias_err_as[:, 2], 'g-', linewidth=0.5, label='Z bias err')
    ax.set_ylabel('Bias error (arcsec/s)')
    ax.set_title('Gyro Bias Estimation Error')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── P diagonal (attitude) ──
    ax = axes[2, 0]
    colors = ['b', 'r', 'g']
    for i, (label, c) in enumerate(zip(['X', 'Y', 'Z'], colors)):
        vals = np.sqrt(P_diag_history[:, i]) * RAD_TO_ARCSEC
        ax.plot(time_s, vals, color=c, linewidth=0.8, label=f'{label} att')
    # Auto-scale from cropped data
    all_crop = np.column_stack([
        np.sqrt(P_diag_history[i_crop:, i]) * RAD_TO_ARCSEC for i in range(3)
    ])
    margin = all_crop.max() * 0.2
    ax.set_ylim(0, all_crop.max() + margin)
    ax.set_xlim(time_s[0], time_s[-1])
    ax.set_ylabel('1-sigma (arcsec)')
    ax.set_xlabel('Time (s)')
    ax.set_title(f'Attitude Covariance (scaled from t={t_crop}s)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── P diagonal (bias) ──
    ax = axes[2, 1]
    for i, (label, c) in enumerate(zip(['X', 'Y', 'Z'], colors)):
        ax.plot(time_s, np.sqrt(P_diag_history[:, 3 + i]) * RAD_TO_ARCSEC,
                color=c, linewidth=0.8, label=f'{label} bias')
    ax.set_ylabel('1-sigma (arcsec/s)')
    ax.set_xlabel('Time (s)')
    ax.set_title('Bias Covariance (sqrt P diagonal)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('starTrackSim/output/ekf_performance.png', dpi=150)
    plt.close(fig)


def plot_innovations(innovations):
    """Plot innovation sequence for filter health check."""
    if not innovations:
        return

    times = [t for t, _ in innovations]
    innov = np.array([v for _, v in innovations])

    fig, ax = plt.subplots(1, 1, figsize=(12, 4))
    ax.plot(times, innov[:, 0] * RAD_TO_ARCSEC, 'b.', markersize=2, label='X')
    ax.plot(times, innov[:, 1] * RAD_TO_ARCSEC, 'r.', markersize=2, label='Y')
    ax.plot(times, innov[:, 2] * RAD_TO_ARCSEC, 'g.', markersize=2, label='Z')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Innovation (arcsec)')
    ax.set_title('Star Tracker Innovation Sequence')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('starTrackSim/output/innovations.png', dpi=150)
    plt.close(fig)
