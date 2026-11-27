from abc import ABCMeta, abstractmethod
import torch
from typing import Dict


class PerformanceMeasure(metaclass=ABCMeta):
    """
    A performance measure.
    """

    @abstractmethod
    def reset(self):
        """
        Resets internal state.
        """

        pass

    @abstractmethod
    def update(self, prediction: torch.Tensor, target: torch.Tensor):
        """
        Update the measure by comparing predicted data with ground-truth target data.
        Raises ValueError if the data shape or values are unsupported.
        """

        pass

    @abstractmethod
    def __str__(self) -> str:
        """
        Return a string representation of the performance.
        """

        pass


class Accuracy(PerformanceMeasure):
    """
    Average classification accuracy.
    """

    def __init__(self, classes) -> None:
        self.classes = classes

        self.reset()

    def reset(self) -> None:
        """
        Resets the internal state.
        """
        self.correct_pred = {classname: 0 for classname in self.classes}
        self.total_pred = {classname: 0 for classname in self.classes}
        self.n_matching = 0  # number of correct predictions
        self.n_total = 0
        self.per_class_accuracies = {classname: 0.0 for classname in self.classes}  # dict mapping class name to accuracy

    def update(self, prediction: torch.Tensor, target: torch.Tensor) -> None:
        """
        Update the measure by comparing predicted data with ground-truth target data.
        prediction must have shape (batchsize,n_classes) with each row being a class-score vector.
        target must have shape (batchsize,) and values between 0 and c-1 (true class labels).
        Raises ValueError if the data shape or values are unsupported.
        [len(prediction.shape) should be equal to 2, and len(target.shape) should be equal to 1.]
        """

        # TODO implement
        # Check validity of intputs and values of target
        if len(prediction.shape) != 2:
            raise ValueError("Prediction must have shape (batchsize, n_classes)")
        if len(target.shape) != 1:
            raise ValueError("Target must have shape (batchsize,)")
        if prediction.shape[0] != target.shape[0]:
            raise ValueError("Batch size of prediction and target must be the same")
        if not torch.all((target >= 0) & (target <= len(self.classes)-1)):
            raise ValueError("Target values must be between 0 and n_classes-1")

        # Get predicted class labels
        predicted_labels = torch.argmax(prediction, dim=1)  # shape (batchsize,)

        # Create a mask for correct predictions
        mask_correct_predictions = (predicted_labels == target)  # shape (batchsize,)

        for i in range(mask_correct_predictions.size(0)):
            class_index = target[i].item()
            class_name = self.classes[class_index]

            # Update total predictions for the predicted class
            self.total_pred[class_name] = self.total_pred.get(class_name, 0) + 1

            # Update correct predictions for the true class
            if mask_correct_predictions[i].item():
                self.correct_pred[class_name] = self.correct_pred.get(class_name, 0) + 1

        # Update overall accuracy
        self.n_matching += (predicted_labels == target).sum().item()
        self.n_total += target.size(0)

        return

    def __str__(self):
        """
        Return a string representation of the performance including:
        - overall accuracy
        - mean per-class accuracy
        - individual per-class accuracies for all classes
        """

        # TODO implement
        overall_accuracy = self.accuracy()
        mean_per_class_accuracy = self.per_class_accuracy()

        per_class_accuracies_str = ""
        for class_name, class_accuracy in self.per_class_accuracies.items():  # type: ignore
            per_class_accuracies_str += f"Accuracy for class: {class_name} is {class_accuracy:.2f}\n"

        final_str = f"\
accuracy: {overall_accuracy:.4f}\n\
per class accuracy: {mean_per_class_accuracy:.4f}\n\
{per_class_accuracies_str}"

        return final_str

    def accuracy(self) -> float:
        """
        Compute and return the accuracy as a float between 0 and 1.
        Returns 0 if no data is available (after resets).
        """

        # TODO implement
        # Check if n_total is 0 to avoid division by zero
        if self.n_total == 0:
            return 0.0

        return self.n_matching / self.n_total

    def per_class_accuracy(self) -> float:
        """
        Compute and return the mean per-class accuracy as a float between 0 and 1.
        Returns 0 if no data is available (after resets).
        Saves the individual per-class accuracies in self.per_class_accuracies as a dict mapping class name to accuracy.
        """
        # TODO implement
        if not self.classes:
            return 0.0

        # Compute per-class accuracies and store in self.per_class_accuracies
        self.per_class_accuracies = {}
        for classname in self.classes:
            if self.total_pred[classname] == 0:  # No predictions for this class
                self.per_class_accuracies[classname] = 0.0
            else:
                self.per_class_accuracies[classname] = self.correct_pred[classname] / self.total_pred[classname]

        # Compute mean per-class accuracy
        mean_per_class_accuracy = sum(self.per_class_accuracies.values()) / len(self.classes)

        return mean_per_class_accuracy
