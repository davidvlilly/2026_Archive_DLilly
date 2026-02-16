# siglab_lib/calcHiguchi.py
import numpy as np
from scipy import stats

def calculate_higuchi_stats(magR, time_S):
    """
    Calculate Higuchi Fractal Dimension statistics for 1-second windows with 2-second lookback
    
    Parameters:
    - magR: Full signal data
    - time_S: Corresponding time data
    
    Returns:
    - Higuchi statistics array
    """
    # Sampling parameters
    samples_per_sec = 30
    two_sec_window = 2 * samples_per_sec
    
    # Initialize output arrays
    num_segments = len(magR) // samples_per_sec
    higuchi_stats = np.zeros((num_segments, 6))  # HFD for k=1,2,3,4,5 and slope
    
    for i in range(1, num_segments):
        # Current segment start and end indices 
        # Start 2 seconds back, but calculate for the current 1-second segment
        start_idx = (i-1) * samples_per_sec
        end_idx = start_idx + two_sec_window
        current_segment_start = i * samples_per_sec
        current_segment_end = current_segment_start + samples_per_sec
        
        # Ensure we don't go out of bounds
        end_idx = min(end_idx, len(magR))
        current_segment_end = min(current_segment_end, len(magR))
        
        window_data = magR[start_idx:end_idx]
        current_segment = magR[current_segment_start:current_segment_end]
        
        # Only calculate if we have full 2-second window
        if len(window_data) == two_sec_window and len(current_segment) == samples_per_sec:
            # Calculate Higuchi Fractal Dimension for k=1,2,3,4,5
            k_values = [1, 2, 3, 4, 5]
            hfd_values = []
            
            for k in k_values:
                N = len(window_data)
                lengths = []
                
                for m in range(k):
                    # Construct derived series from full 2-second window
                    derived_series = window_data[m::k]
                    
                    # Calculate length
                    curve_length = np.sum(np.abs(np.diff(derived_series)))
                    
                    # Normalize length
                    L = curve_length * (N / (((N - m) // k) * k))
                    lengths.append(L)
                
                # Average length for this interval
                hfd_values.append(np.mean(lengths))
            
            # Log-log regression
            x = np.log(k_values)
            y = np.log(hfd_values)
            
            # Linear regression
            slope, _, _, _, _ = stats.linregress(x, y)
            
            # Store results
            higuchi_stats[i] = [*hfd_values, slope]
        else:
            # Copy previous values if window is incomplete
            higuchi_stats[i] = higuchi_stats[i-1]
    
    return higuchi_stats