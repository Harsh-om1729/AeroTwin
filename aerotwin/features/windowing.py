import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

def create_windows(df, window_size=60, stride=10):
    """
    Slices a continuous dataframe into overlapping windows.
    Returns array of shape (N_windows, window_size, n_features).
    """
    # Assuming dataframe is sorted by time and contiguous
    data = df.values
    n_samples = len(data)
    
    if n_samples < window_size:
        return np.empty((0, window_size, data.shape[1]))
        
    n_windows = (n_samples - window_size) // stride + 1
    windows = np.array([data[i * stride : i * stride + window_size] for i in range(n_windows)])
    
    # We also return the time index of the end of each window for alerting purposes
    end_times = df.index[window_size - 1 :: stride][:n_windows]
    
    return windows, end_times

def extract_window_stats(windows):
    """
    Extracts mean, std, and slope for each feature in the window.
    Input: (N_windows, window_size, n_features)
    Output: (N_windows, n_features * 3)
    """
    N, W, F = windows.shape
    
    means = np.mean(windows, axis=1)
    stds = np.std(windows, axis=1)
    
    # Simple slope approximation: difference between last half and first half means
    half = W // 2
    slopes = np.mean(windows[:, half:, :], axis=1) - np.mean(windows[:, :half, :], axis=1)
    
    return np.hstack([means, stds, slopes])

class FeaturePipeline:
    def __init__(self):
        self.scaler = StandardScaler()
        
    def fit(self, df):
        """Fit the scaler on normal healthy residuals."""
        self.scaler.fit(df)
        
    def transform_to_stats(self, df, window_size=60, stride=10):
        scaled_data = self.scaler.transform(df)
        scaled_df = pd.DataFrame(scaled_data, index=df.index, columns=df.columns)
        
        windows, times = create_windows(scaled_df, window_size, stride)
        if len(windows) == 0:
            return np.empty((0, 0)), times
            
        stats = extract_window_stats(windows)
        return stats, times
        
    def transform_to_sequences(self, df, window_size=60, stride=10):
        scaled_data = self.scaler.transform(df)
        scaled_df = pd.DataFrame(scaled_data, index=df.index, columns=df.columns)
        
        return create_windows(scaled_df, window_size, stride)
