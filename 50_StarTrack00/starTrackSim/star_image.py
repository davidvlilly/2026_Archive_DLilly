"""Star field image renderer — realistic appearance + movie generation."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.colors import LinearSegmentedColormap
import cv2
import os


# Star color by spectral class (approximation from B-V color index / magnitude)
# Brighter/hotter stars tend bluer, dimmer tend redder
def _star_color(mag):
    """Return an RGB tuple for a star based on magnitude (rough approximation)."""
    t = max(0.0, min(1.0, (6.5 - mag) / 6.0))
    if t > 0.7:
        # Bright stars: blue-white
        return (0.8 + 0.2*t, 0.85 + 0.15*t, 1.0)
    elif t > 0.4:
        # Medium: white-yellow
        return (1.0, 1.0, 0.85 + 0.15*t)
    else:
        # Dim: warm orange-white
        return (1.0, 0.8 + 0.2*t, 0.6 + 0.3*t)


def render_star_image(body_vectors, magnitudes, fov_deg, title="Star Field",
                      image_size=512, save_path=None):
    """Render a realistic star field image from body-frame star vectors.

    Features:
    - Black background with no axes/grid for realism
    - Star brightness and size scaled by magnitude
    - Gaussian glow around bright stars (diffraction/blooming)
    - Subtle star coloring based on magnitude

    Args:
        body_vectors: (K, 3) star unit vectors in body frame
        magnitudes: (K,) visual magnitudes
        fov_deg: field of view in degrees
        title: plot title
        image_size: pixel size of the image
        save_path: if set, save to this file
    """
    if len(body_vectors) == 0:
        print("No stars to render.")
        return

    fig, ax = plt.subplots(1, 1, figsize=(7, 7), facecolor='black')
    ax.set_facecolor('black')

    half_fov_deg = fov_deg / 2.0

    # Sort by magnitude (dim first, so bright stars render on top)
    order = np.argsort(-magnitudes)

    for idx in order:
        v = body_vectors[idx]
        mag = magnitudes[idx]

        if v[2] <= 0:
            continue

        # Gnomonic projection
        x_deg = np.degrees(v[0] / v[2])
        y_deg = np.degrees(v[1] / v[2])

        # Brightness and size
        brightness_factor = max(0.0, (7.0 - mag) / 6.0)
        brightness_factor = min(1.0, brightness_factor)

        # Core dot size (pixels in marker size)
        core_size = max(0.5, (6.5 - mag) * 1.5)

        color = _star_color(mag)
        alpha = 0.4 + 0.6 * brightness_factor

        # Glow for bright stars (mag < 3)
        if mag < 3.0:
            glow_size = core_size * 4
            glow_alpha = 0.08 + 0.12 * brightness_factor
            ax.plot(x_deg, y_deg, 'o', color=color, markersize=glow_size,
                    alpha=glow_alpha, zorder=1)
            # Secondary glow
            ax.plot(x_deg, y_deg, 'o', color=color, markersize=glow_size * 0.5,
                    alpha=glow_alpha * 2, zorder=2)

        # Diffraction spikes for very bright stars (mag < 1.5)
        if mag < 1.5:
            spike_len = 0.3 + (2.0 - mag) * 0.3  # degrees
            spike_alpha = 0.15 * brightness_factor
            for angle in [0, 90, 45, 135]:
                dx = spike_len * np.cos(np.radians(angle))
                dy = spike_len * np.sin(np.radians(angle))
                ax.plot([x_deg - dx, x_deg + dx], [y_deg - dy, y_deg + dy],
                        '-', color=color, linewidth=0.4, alpha=spike_alpha, zorder=1)

        # Core star point
        ax.plot(x_deg, y_deg, 'o', color=color, markersize=core_size,
                alpha=alpha, zorder=3)

    ax.set_xlim(-half_fov_deg, half_fov_deg)
    ax.set_ylim(-half_fov_deg, half_fov_deg)
    ax.set_aspect('equal')

    # Minimal labeling for realism
    ax.set_xlabel('Cross-bore X (deg)', color='gray', fontsize=8)
    ax.set_ylabel('Cross-bore Y (deg)', color='gray', fontsize=8)
    ax.tick_params(colors='gray', labelsize=7)
    for spine in ax.spines.values():
        spine.set_color('#333333')
    ax.set_title(title, color='white', fontsize=10, pad=8)

    # Thin FOV circle
    fov_circle = Circle((0, 0), half_fov_deg, fill=False,
                         edgecolor='#333333', linewidth=0.5, linestyle='--')
    ax.add_patch(fov_circle)

    # Crosshair at boresight
    ch_len = half_fov_deg * 0.05
    ax.plot([-ch_len, ch_len], [0, 0], '-', color='#444444', linewidth=0.5)
    ax.plot([0, 0], [-ch_len, ch_len], '-', color='#444444', linewidth=0.5)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, facecolor='black')
    plt.close(fig)


def render_star_frame_cv2(body_vectors, magnitudes, fov_deg,
                          image_size=800, time_label=None):
    """Render a star field frame as an OpenCV image (numpy array).

    Uses cv2 for fast rendering suitable for video generation.

    Returns:
        frame: (H, W, 3) uint8 BGR image
    """
    img = np.zeros((image_size, image_size, 3), dtype=np.uint8)
    half_fov_deg = fov_deg / 2.0
    center = image_size / 2.0
    scale = (image_size / 2.0) / half_fov_deg  # pixels per degree

    for v, mag in zip(body_vectors, magnitudes):
        if v[2] <= 0:
            continue

        x_deg = np.degrees(v[0] / v[2])
        y_deg = np.degrees(v[1] / v[2])

        # Pixel coordinates (Y flipped for image convention)
        px = int(center + x_deg * scale)
        py = int(center - y_deg * scale)

        if px < 0 or px >= image_size or py < 0 or py >= image_size:
            continue

        brightness = max(0.0, min(1.0, (7.0 - mag) / 6.0))
        radius = max(1, int((6.5 - mag) * 1.2))

        # Star color (BGR for OpenCV)
        r, g, b = _star_color(mag)
        color_bgr = (int(b * brightness * 255),
                     int(g * brightness * 255),
                     int(r * brightness * 255))

        # Glow for bright stars
        if mag < 3.5:
            glow_radius = radius * 3
            glow_brightness = brightness * 0.15
            glow_bgr = (int(b * glow_brightness * 255),
                        int(g * glow_brightness * 255),
                        int(r * glow_brightness * 255))
            cv2.circle(img, (px, py), glow_radius, glow_bgr, -1, cv2.LINE_AA)

        # Core
        cv2.circle(img, (px, py), radius, color_bgr, -1, cv2.LINE_AA)

    # Crosshair at center
    ch = int(image_size * 0.02)
    gray = (50, 50, 50)
    cv2.line(img, (image_size//2 - ch, image_size//2),
             (image_size//2 + ch, image_size//2), gray, 1)
    cv2.line(img, (image_size//2, image_size//2 - ch),
             (image_size//2, image_size//2 + ch), gray, 1)

    # FOV circle
    cv2.circle(img, (image_size//2, image_size//2),
               int(image_size * 0.48), (40, 40, 40), 1, cv2.LINE_AA)

    # Time label
    if time_label is not None:
        cv2.putText(img, time_label, (10, image_size - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)

    # Star count
    n_stars = sum(1 for v in body_vectors if v[2] > 0)
    cv2.putText(img, f"{n_stars} stars", (image_size - 100, image_size - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1, cv2.LINE_AA)

    return img


def generate_star_movie(q_true, stars_eci, magnitudes, fov_deg, cfg,
                        output_path='starTrackSim/output/star_field.mp4',
                        fps=10, image_size=800, frame_interval_s=0.5):
    """Generate a movie of the star field as the attitude changes.

    Args:
        q_true: (N, 4) truth quaternion array
        stars_eci: (M, 3) star catalog in ECI
        magnitudes: (M,) magnitudes
        fov_deg: field of view in degrees
        cfg: Config object
        output_path: path to save the MP4 file
        fps: frames per second in the video
        image_size: pixel size of each frame
        frame_interval_s: simulated seconds between video frames
    """
    from .star_catalog import query_stars_in_fov

    dt_gyro = cfg.dt_gyro
    ticks_per_frame = max(1, int(frame_interval_s / dt_gyro))
    N = q_true.shape[0]
    num_frames = N // ticks_per_frame

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps,
                             (image_size, image_size))

    print(f"  Generating {num_frames} frames ({frame_interval_s}s intervals, {fps} fps)...")

    for i in range(num_frames):
        k = i * ticks_per_frame
        t = k * dt_gyro

        body_vecs, _, mags, _ = query_stars_in_fov(
            stars_eci, magnitudes, q_true[k], fov_deg
        )

        frame = render_star_frame_cv2(
            body_vecs, mags, fov_deg,
            image_size=image_size,
            time_label=f"t = {t:.1f}s"
        )

        writer.write(frame)

        if (i + 1) % 20 == 0:
            print(f"    frame {i+1}/{num_frames}  t={t:.1f}s  ({len(body_vecs)} stars)")

    writer.release()
    print(f"  Saved: {output_path}")
    print(f"  Video: {num_frames} frames, {num_frames/fps:.1f}s playback at {fps} fps")
