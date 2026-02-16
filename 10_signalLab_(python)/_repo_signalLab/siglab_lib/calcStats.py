# siglab_lib/calcStats.py
import numpy as np

def compute_blood_stats(magR, time_S):
    """
    Compute blood statistics with robust update mechanism
    
    Parameters:
    - magR: Full signal data
    - time_S: Corresponding time data
    
    Returns:
    - Blood statistics array
    """
    # Sampling parameters
    samples_per_sec = 30
    segment_length = samples_per_sec  # 1-second segment
    
    # Initial blood estimates
    blood_est_val = 700.0
    blood_est_rng = 40.0
    
    # Flag to track when first valid blood segment is found
    first_valid_found = False
    
    # Initialize output arrays
    num_segments = len(magR) // samples_per_sec
    blood_stats = np.zeros((num_segments, 2))
    blood_stats[0] = [blood_est_val, blood_est_rng]
    
    for i in range(1, num_segments):
        # Current segment start and end indices
        start_idx = i * samples_per_sec
        end_idx = start_idx + samples_per_sec
        current_segment = magR[start_idx:end_idx]
        
        # Compute current segment statistics
        segment_mean = np.mean(current_segment)
        segment_range = np.max(current_segment) - np.min(current_segment)
        
        # Initial criteria before first valid segment:
        if not first_valid_found:
            # More relaxed criteria for initial blood estimate
            if segment_range <= 40:  # Tight range
                # Check neighboring segments for consistency
                if i > 1:
                    prev_segment = magR[(i-1)*samples_per_sec:i*samples_per_sec]
                    prev_mean = np.mean(prev_segment)
                    
                    # Check if means are close
                    if abs(segment_mean - prev_mean) <= 40:
                        # Update blood estimate
                        blood_est_val = blood_est_val * 0.9 + segment_mean * 0.1
                        blood_est_rng = blood_est_rng * 0.9 + segment_range * 0.1
                        first_valid_found = True
                        blood_stats[i] = [blood_est_val, blood_est_rng]
                    else:
                        # Copy previous value if no valid segment found
                        blood_stats[i] = blood_stats[i-1]
            else:
                # Copy previous value if no valid segment found
                blood_stats[i] = blood_stats[i-1]
        
        # After first valid segment is found
        else:
            # Check distance from current blood estimate
            mean_diff = segment_mean - blood_est_val
            
            # Limit update if farther than 60
            if abs(segment_mean - blood_est_val) > 60:
                # Copy previous value
                blood_stats[i] = blood_stats[i-1]
                continue
            
            # Limit movement to +/- 10, but preserve the direction
            if abs(mean_diff) > 10:
                mean_diff = 10 if mean_diff > 0 else -10
            
            # Update using exponential moving average to preserve overall trend
            blood_est_val = blood_est_val * 0.9 + (blood_est_val + mean_diff) * 0.1
            blood_est_rng = blood_est_rng * 0.9 + segment_range * 0.1
            
            # Store current blood estimates
            blood_stats[i] = [blood_est_val, blood_est_rng]
    
    return blood_stats




def compute_segment_stats(magR, time_S):
    """
    Compute statistics for 1 Hz segments
    
    Parameters:
    - magR: Full signal data
    - time_S: Corresponding time data
    
    Returns:
    - Dictionary with segment statistics
    """
    # Compute number of segments (1 Hz)
    total_samples = len(magR)
    samples_per_segment = 30  # 30 Hz sampling
    num_segments = total_samples // samples_per_segment

    # Initialize statistics arrays
    seg_stats_each = np.zeros((num_segments, 5))  # max, min, mean, range, std
    seg_stats_time = np.zeros(num_segments)

    # Compute statistics for each segment
    for i in range(num_segments):
        start = i * samples_per_segment
        end = start + samples_per_segment
        segment = magR[start:end]
        
        seg_stats_each[i, 0] = np.max(segment)     # max
        seg_stats_each[i, 1] = np.min(segment)     # min
        seg_stats_each[i, 2] = np.mean(segment)    # mean
        seg_stats_each[i, 3] = seg_stats_each[i, 0] - seg_stats_each[i, 1]  # range
        seg_stats_each[i, 4] = np.std(segment)     # std
        
        seg_stats_time[i] = time_S[start]  # time at start of segment

    return {
        'each': seg_stats_each,
        'time': seg_stats_time
    }

def calculate_segment_stats(app):
    """
    Calculate comprehensive signal statistics
    
    Parameters:
    - app: Main application instance with time_S and magR attributes
    
    Returns:
    - stats: Dictionary containing:
        - bloodEstRng: Blood range estimates
        - bloodEstVal: Blood mean estimates
        - segmentStats: 1-second interval statistics
    """
    # Compute segment statistics
    segment_stats = compute_segment_stats(app.magR, app.time_S)
    
    # Compute blood statistics
    blood_stats = compute_blood_stats(app.magR, app.time_S)
    
    # Prepare return structure
    stats = {
        'bloodEstRng': blood_stats[:, 1],     # Range column
        'bloodEstVal': blood_stats[:, 0],     # Mean column
        'segmentStats': {
            'each': segment_stats['each'],    # Segment-wise statistics
            'time': segment_stats['time']     # Corresponding times
        }
    }
    
    return stats