import torch
import torch.nn as nn
from pathlib import Path

class DeepClassifier(nn.Module):
    def __init__(self, net: nn.Module):
        super().__init__()
        self.net = net

    def forward(self, x):
        return self.net(x)
    

    def save(self, save_dir: Path, suffix=None):
        '''
        Saves the model, adds suffix to filename if given
        '''

        ## TODO implement
        # Create directory if it does not exist
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save state dict of the model to a file in save_dir, with an optional suffix in the filename
        filename = f"model{('_' + suffix) if suffix else ''}.pt"
        save_path = save_dir / filename
        torch.save(self.net.state_dict(), save_path)

    def load(self, path):
        '''
        Loads model from path
        Does not work with transfer model
        '''
        
        ## TODO implement
        # Load state dict of the model from the given path
        self.net.load_state_dict(torch.load(path))
