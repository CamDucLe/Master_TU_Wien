import torch
import wandb
from datetime import datetime

wandb.login(key="YOUR_KEY_HERE")
class WandBLogger:

    def __init__(self, enabled=True, 
                 model: torch.nn.modules=None,  # type: ignore
                 run_name: str=None) -> None:  # type: ignore
        
        self.enabled = enabled

        if self.enabled:
            wandb.init(
                entity="ldcam2732001-tu-wien",  # change to your wandb entity
                project="DLVC Assignment 1",  # change to your wandb project name
            )
            if run_name is None:
                wandb.run.name = f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            else:
                wandb.run.name = run_name  # type: ignore

            if model is not None:
                self.watch(model)         
            
    def watch(self, model, log_freq: int=1):
        wandb.watch(model, log="all", log_freq=log_freq)
            

    def log(self, log_dict: dict, commit=True, step=None):
        if self.enabled:
            if step:
                wandb.log(log_dict, commit=commit, step=step)
            else:
                wandb.log(log_dict, commit=commit)
 

    def finish(self):
        if self.enabled:
            wandb.finish()
