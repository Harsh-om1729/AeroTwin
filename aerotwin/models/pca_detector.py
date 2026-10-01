from sklearn.decomposition import PCA
import numpy as np

class PCADetector:
    def __init__(self, variance_ratio=0.95):
        self.model = PCA(n_components=variance_ratio)
        self.mean = None
        
    def fit(self, X):
        """Fit PCA on window statistics."""
        self.model.fit(X)
        
    def score(self, X):
        """
        Returns SPE (Squared Prediction Error) also known as Q-statistic.
        Higher = more anomalous.
        """
        # Transform to principal components
        X_pca = self.model.transform(X)
        
        # Reconstruct back
        X_recon = self.model.inverse_transform(X_pca)
        
        # Calculate reconstruction error (SPE)
        spe = np.sum((X - X_recon) ** 2, axis=1)
        
        # We can also compute Hotelling's T^2 but SPE is usually better 
        # for detecting novel sensor faults. We'll use SPE.
        return spe
