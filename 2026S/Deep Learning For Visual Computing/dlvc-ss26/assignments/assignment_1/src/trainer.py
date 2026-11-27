import torch
from typing import Tuple
from abc import ABCMeta, abstractmethod
from pathlib import Path
from tqdm import tqdm

# for wandb users:
from assignment_1_code.wandb_logger import WandBLogger


class BaseTrainer(metaclass=ABCMeta):
    """
    Base class of all Trainers.
    """

    @abstractmethod
    def train(self) -> None:
        """
        Holds training logic.
        """

        pass

    @abstractmethod
    def _val_epoch(self) -> Tuple[float, float, float]:
        """
        Holds validation logic for one epoch.
        """

        pass

    @abstractmethod
    def _train_epoch(self) -> Tuple[float, float, float]:
        """
        Holds training logic for one epoch.
        """

        pass


class ImgClassificationTrainer(BaseTrainer):
    """
    Class that stores the logic for training a model for image classification.
    """

    def __init__(
        self,
        model,
        optimizer,
        loss_fn,
        lr_scheduler,
        train_metric,
        val_metric,
        train_data,
        val_data,
        device,
        num_epochs: int,
        training_save_dir: Path,
        batch_size: int = 4,
        val_frequency: int = 5,
    ) -> None:
        """
        Args and Kwargs:
            model (nn.Module): Deep Network to train
            optimizer (torch.optim): optimizer used to train the network
            loss_fn (torch.nn): loss function used to train the network
            lr_scheduler (torch.optim.lr_scheduler): learning rate scheduler used to train the network
            train_metric (dlvc.metrics.Accuracy): Accuracy class to get mAcc and mPCAcc of training set
            val_metric (dlvc.metrics.Accuracy): Accuracy class to get mAcc and mPCAcc of validation set
            train_data (dlvc.datasets.cifar10.CIFAR10Dataset): Train dataset
            val_data (dlvc.datasets.cifar10.CIFAR10Dataset): Validation dataset
            device (torch.device): cuda or cpu - device used to train the network
            num_epochs (int): number of epochs to train the network
            training_save_dir (Path): the path to the folder where the best model is stored
            batch_size (int): number of samples in one batch
            val_frequency (int): how often validation is conducted during training (if it is 5 then every 5th
                                epoch we evaluate model on validation set)

        What does it do:
            - Stores given variables as instance variables for use in other class methods e.g. self.model = model.
            - Creates data loaders for the train and validation datasets
            - Optionally use weights & biases for tracking metrics and loss: initializer W&B logger

        """

        ## TODO implement
        self.model = model
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.lr_scheduler = lr_scheduler
        self.train_metric = train_metric
        self.val_metric = val_metric
        self.train_data = train_data
        self.val_data = val_data
        self.device = device
        self.num_epochs = num_epochs
        self.training_save_dir = training_save_dir
        self.batch_size = batch_size
        self.val_frequency = val_frequency
        self.wandb_logger = WandBLogger(enabled=True, model=self.model)

    def _train_epoch(self, epoch_idx: int) -> Tuple[float, float, float]:
        """
        Training logic for one epoch.
        Prints current metrics at end of epoch.
        Returns loss, mean accuracy and mean per class accuracy for this epoch.

        epoch_idx (int): Current epoch number
        """
        ## TODO implement
        epoch_loss = 0.0
        self.model.train()
        for batch in tqdm(self.train_data, desc=f"Epoch {epoch_idx}"):
            # Move images and labels of the current batch to the device
            images, labels = batch
            images, labels = images.to(self.device), labels.to(self.device)

            # Set gradients to zero
            self.optimizer.zero_grad()

            # Forward pass
            outputs = self.model(images)

            # Compute loss
            loss = self.loss_fn(outputs, labels)

            # Backward pass and optimization step
            loss.backward()
            self.optimizer.step()

            # Update epoch loss and metrics
            epoch_loss += loss.item()
            self.train_metric.update(outputs.detach(), labels.detach())
        
        # Compute mean accuracy and mean per class accuracy for this epoch
        epoch_loss /= len(self.train_data)
        mean_accuracy = self.train_metric.accuracy()
        mean_per_class_accuracy = self.train_metric.per_class_accuracy()

        print(f"______epoch {epoch_idx}")
        print(self.train_metric)

        return epoch_loss, mean_accuracy, mean_per_class_accuracy

    def _val_epoch(self, epoch_idx: int) -> Tuple[float, float, float]:
        """
        Validation logic for one epoch.
        Prints current metrics at end of epoch.
        Returns loss, mean accuracy and mean per class accuracy for this epoch on the validation data set.

        epoch_idx (int): Current epoch number
        """
        ## TODO implement
        epoch_loss = 0.0
        self.model.eval()
        with torch.no_grad():
            for batch in tqdm(self.val_data, desc=f"Validation Epoch {epoch_idx}"):
                # Move images and labels of the current batch to the device
                images, labels = batch
                images, labels = images.to(self.device), labels.to(self.device)

                # Forward pass
                outputs = self.model(images)

                # Compute loss
                loss = self.loss_fn(outputs, labels)
                epoch_loss += loss.item()

                # Update metrics
                self.val_metric.update(outputs.detach(), labels.detach())

        # Compute mean accuracy and mean per class accuracy for this epoch
        epoch_loss /= len(self.val_data)
        mean_accuracy = self.val_metric.accuracy()
        mean_per_class_accuracy = self.val_metric.per_class_accuracy()

        print(f"______Validation Epoch {epoch_idx}")
        print(self.val_metric)

        return epoch_loss, mean_accuracy, mean_per_class_accuracy

    def train(self) -> None:
        """
        Full training logic that loops over num_epochs and
        uses the _train_epoch and _val_epoch methods.
        Save the model if mean per class accuracy on validation data set is higher
        than currently saved best mean per class accuracy.
        Depending on the val_frequency parameter, validation is not performed every epoch.
        """
        ## TODO implement
        best_val_mpcacc = 0.0
        for epoch in range(self.num_epochs):
            # Reset metrics at the beginning of each epoch
            self.train_metric.reset()

            train_loss, train_macc, train_mpacc = self._train_epoch(epoch)
            self.wandb_logger.log(
                {
                    "epoch": epoch,
                    "train_loss": train_loss,
                    "train_mean_accuracy": train_macc,
                    "train_mean_per_class_accuracy": train_mpacc,
                }
            )

            # Do validation every val_frequency epochs
            if epoch % self.val_frequency == 0:
                self.val_metric.reset()
                val_loss, val_macc, val_mpacc = self._val_epoch(epoch)

                self.wandb_logger.log(
                    {
                        "epoch": epoch,
                        "val_loss": val_loss,
                        "val_mean_accuracy": val_macc,
                        "val_mean_per_class_accuracy": val_mpacc,
                    }
                )

                # Save the model if mean per class accuracy on validation data set is higher than currently saved best mean per class accuracy
                if val_mpacc > best_val_mpcacc:
                    best_val_mpcacc = val_mpacc
                    self.model.save(
                        self.training_save_dir,
                        # suffix=f"epoch_{epoch}_mpacc_{val_mpacc:.4f}",
                    )

        self.wandb_logger.finish()

        return
