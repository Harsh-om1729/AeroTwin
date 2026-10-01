import torch
import torch.nn as nn
import numpy as np

class LSTMAE(nn.Module):
    def __init__(self, n_feat, hidden=64, latent=16):
        super().__init__()
        self.enc = nn.LSTM(n_feat, hidden, batch_first=True)
        self.to_lat = nn.Linear(hidden, latent)
        self.from_lat = nn.Linear(latent, hidden)
        self.dec = nn.LSTM(hidden, hidden, batch_first=True)
        self.out = nn.Linear(hidden, n_feat)

    def forward(self, x):                    # x: (B, T, F)
        _, (h, _) = self.enc(x)
        z = self.to_lat(h[-1])               # (B, latent)
        rep = self.from_lat(z).unsqueeze(1).repeat(1, x.size(1), 1)
        y, _ = self.dec(rep)
        return self.out(y)

class LSTMAEDetector:
    def __init__(self, n_feat, hidden=64, latent=16, device="cpu"):
        self.model = LSTMAE(n_feat, hidden, latent).to(device)
        self.device = device
        
    def fit(self, X_train, X_val, epochs=20, batch_size=64, lr=1e-3):
        """Fit LSTM Autoencoder on window sequences."""
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()
        
        train_loader = torch.utils.data.DataLoader(
            torch.FloatTensor(X_train), 
            batch_size=batch_size, 
            shuffle=True
        )
        
        # Simple training loop with early stopping placeholder
        self.model.train()
        for epoch in range(epochs):
            for batch in train_loader:
                batch = batch.to(self.device)
                optimizer.zero_grad()
                recon = self.model(batch)
                loss = criterion(recon, batch)
                loss.backward()
                optimizer.step()
                
    def score(self, X):
        """
        Returns reconstruction MSE score.
        Higher = more anomalous.
        """
        self.model.eval()
        with torch.no_grad():
            tensor_x = torch.FloatTensor(X).to(self.device)
            recon = self.model(tensor_x)
            
            # Mean Squared Error per window
            mse = ((recon - tensor_x) ** 2).mean(dim=(1, 2))
            return mse.cpu().numpy()
