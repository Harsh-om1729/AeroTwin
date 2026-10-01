from sklearn.ensemble import IsolationForest
import numpy as np

class IFDetector:
    def __init__(self, contamination=0.01, random_state=42):
        self.model = IsolationForest(
            contamination=contamination, 
            random_state=random_state,
            n_jobs=-1
        )
        
    def fit(self, X):
        """Fit IF on window statistics."""
        self.model.fit(X)
        
    def score(self, X):
        """
        Returns anomaly scores. Higher = more anomalous.
        scikit-learn decision_function returns lower values for anomalies (negative).
        We invert it so higher is worse.
        """
        # decision_function: <0 is anomaly, >0 is normal
        return -self.model.decision_function(X)
