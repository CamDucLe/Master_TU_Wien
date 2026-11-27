import torch
import wandb
from datetime import datetime
from typing import Dict

wandb.login(key="TODO_ADD_KEY")
class WandBLogger:

    def __init__(self, enabled=True, 
                 model: torch.nn.modules=None, 
                 run_name: str=None) -> None:
        
        self.enabled = enabled



        if self.enabled:
            wandb.init(
                entity="ldcam2732001-tu-wien",
                project="DLVC Assignment 1",
            )
            if run_name is None:
                wandb.run.name = f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            else:
                wandb.run.name = run_name  

            wandb.define_metric("epoch")
            wandb.define_metric("train_loss", step_metric="epoch")
            wandb.define_metric("train_mean_accuracy", step_metric="epoch")
            wandb.define_metric("train_mean_per_class_accuracy", step_metric="epoch")
            wandb.define_metric("val_loss", step_metric="epoch")
            wandb.define_metric("val_mean_accuracy", step_metric="epoch")
            wandb.define_metric("val_mean_per_class_accuracy", step_metric="epoch")

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
