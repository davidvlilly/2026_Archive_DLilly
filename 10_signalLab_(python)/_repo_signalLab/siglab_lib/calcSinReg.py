# siglab_lib/calcSinReg.py
import numpy as np
from scipy.optimize import minimize

def fit_sin_segment(segment, time_segment):
    """
    Fit a sinusoidal model with DC offset and slope to a segment of data.
    
    Model: y = A*sin(2*pi*f*t + phi) + slope*t + dc_offset
    
    Parameters:
    - segment: Data segment to fit
    - time_segment: Corresponding time values
    
    Returns:
    - Dictionary with fit parameters: freq, amp, phase, slope, dc_offset, mean_error
    """
    # Normalize time to start at 0 for numerical stability
    t = time_segment - time_segment[0]
    y = segment.copy()
    
    # Initial estimates
    # DC offset: mean of the signal
    dc_init = np.mean(y)
    
    # Slope: linear regression
    slope_init = (y[-1] - y[0]) / (t[-1] - t[0]) if t[-1] != t[0] else 0.0
    
    # Remove linear trend for frequency estimation
    y_detrend = y - (dc_init + slope_init * t)
    
    # Amplitude: half the range of detrended signal
    amp_init = (np.max(y_detrend) - np.min(y_detrend)) / 2.0
    
    # Frequency estimation using zero crossings or FFT
    # Use FFT for better frequency estimation
    n = len(y_detrend)
    dt = t[1] - t[0] if len(t) > 1 else 1/30.0
    freqs = np.fft.fftfreq(n, dt)
    fft_vals = np.abs(np.fft.fft(y_detrend))
    
    # Find dominant frequency (excluding DC component)
    positive_freqs = freqs[:n//2]
    positive_fft = fft_vals[:n//2]
    
    # Skip very low frequencies (< 0.5 Hz) to avoid DC leakage
    min_freq_idx = np.searchsorted(positive_freqs, 0.5)
    if min_freq_idx < len(positive_freqs) - 1:
        peak_idx = min_freq_idx + np.argmax(positive_fft[min_freq_idx:])
        freq_init = positive_freqs[peak_idx]
    else:
        freq_init = 1.0  # Default to 1 Hz
    
    # Clamp frequency to reasonable range (0.5 to 10 Hz for physiological signals)
    freq_init = np.clip(freq_init, 0.5, 10.0)
    
    # Phase estimation
    phase_init = 0.0
    
    def model(params):
        """Sinusoidal model with linear trend"""
        freq, amp, phase, slope, dc = params
        return amp * np.sin(2 * np.pi * freq * t + phase) + slope * t + dc
    
    def objective(params):
        """Mean squared error objective"""
        residuals = y - model(params)
        return np.mean(residuals**2)
    
    # Initial parameters: [freq, amp, phase, slope, dc_offset]
    x0 = [freq_init, amp_init, phase_init, slope_init, dc_init]
    
    # Bounds for parameters
    bounds = [
        (0.1, 15.0),      # freq: 0.1 to 15 Hz
        (0.0, 500.0),     # amp: non-negative, reasonable max
        (-np.pi, np.pi),  # phase: -pi to pi
        (-100.0, 100.0),  # slope: reasonable range
        (0.0, 2000.0)     # dc_offset: reasonable range for impedance signals
    ]
    
    # Optimize
    try:
        result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds)
        opt_params = result.x
        
        # Calculate mean absolute error
        fitted = model(opt_params)
        mean_error = np.mean(np.abs(y - fitted))
        
        return {
            'freq': opt_params[0],
            'amp': opt_params[1],
            'phase': opt_params[2],
            'slope': opt_params[3],
            'dc_offset': opt_params[4],
            'mean_error': mean_error
        }
    except Exception as e:
        # Return default values on optimization failure
        return {
            'freq': freq_init,
            'amp': amp_init,
            'phase': phase_init,
            'slope': slope_init,
            'dc_offset': dc_init,
            'mean_error': np.std(y)  # Use std as error estimate
        }


def calculate_sin_regression(magR, time_S):
    """
    Calculate sinusoidal regression for 2-second windows with 50% overlap (1 Hz output).
    
    Model: y = A*sin(2*pi*f*t + phi) + slope*t + dc_offset
    
    Parameters:
    - magR: Full signal data (30 Hz sampling)
    - time_S: Corresponding time data
    
    Returns:
    - sin_reg: Dictionary containing:
        - sinFrq: Estimated frequency for each segment
        - sinAmp: Estimated amplitude for each segment
        - sinPhs: Estimated phase for each segment
        - meanErr: Mean absolute error for each segment
        - slope: Linear slope for each segment
        - dcOffset: DC offset for each segment
        - time: Time stamp for each segment
    """
    # Sampling parameters
    samples_per_sec = 30
    window_samples = 2 * samples_per_sec  # 2-second window = 60 samples
    hop_samples = samples_per_sec          # 50% overlap = 1-second hop = 30 samples
    
    # Calculate number of output segments
    total_samples = len(magR)
    num_segments = (total_samples - window_samples) // hop_samples + 1
    
    # Ensure we have at least one segment
    num_segments = max(1, num_segments)
    
    # Initialize output arrays
    sin_frq = np.zeros(num_segments)
    sin_amp = np.zeros(num_segments)
    sin_phs = np.zeros(num_segments)
    mean_err = np.zeros(num_segments)
    slope = np.zeros(num_segments)
    dc_offset = np.zeros(num_segments)
    seg_time = np.zeros(num_segments)
    
    for i in range(num_segments):
        # Calculate window indices
        start_idx = i * hop_samples
        end_idx = start_idx + window_samples
        
        # Handle edge case for last segment
        if end_idx > total_samples:
            end_idx = total_samples
            start_idx = max(0, end_idx - window_samples)
        
        # Extract segment
        segment = magR[start_idx:end_idx]
        time_segment = time_S[start_idx:end_idx]
        
        # Skip if segment is too short
        if len(segment) < samples_per_sec:
            if i > 0:
                # Copy previous values
                sin_frq[i] = sin_frq[i-1]
                sin_amp[i] = sin_amp[i-1]
                sin_phs[i] = sin_phs[i-1]
                mean_err[i] = mean_err[i-1]
                slope[i] = slope[i-1]
                dc_offset[i] = dc_offset[i-1]
            seg_time[i] = time_S[start_idx] if start_idx < len(time_S) else seg_time[i-1]
            continue
        
        # Fit sinusoidal model
        fit_result = fit_sin_segment(segment, time_segment)
        
        # Store results
        sin_frq[i] = fit_result['freq']
        sin_amp[i] = fit_result['amp']
        sin_phs[i] = fit_result['phase']
        mean_err[i] = fit_result['mean_error']
        slope[i] = fit_result['slope']
        dc_offset[i] = fit_result['dc_offset']
        seg_time[i] = time_segment[0] + (time_segment[-1] - time_segment[0]) / 2  # Center of window
    
    return {
        'sinFrq': sin_frq,
        'sinAmp': sin_amp,
        'sinPhs': sin_phs,
        'meanErr': mean_err,
        'slope': slope,
        'dcOffset': dc_offset,
        'time': seg_time
    }
