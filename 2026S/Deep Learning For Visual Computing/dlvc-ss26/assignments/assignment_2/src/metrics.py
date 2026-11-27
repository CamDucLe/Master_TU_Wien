from abc import ABCMeta, abstractmethod
import torch

class PerformanceMeasure(metaclass=ABCMeta):
    '''
    A performance measure.
    '''

    @abstractmethod
    def reset(self):
        '''
        Resets internal state.
        '''

        pass

    @abstractmethod
    def update(self, prediction: torch.Tensor, target: torch.Tensor):
        '''
        Update the measure by comparing predicted data with ground-truth target data.
        Raises ValueError if the data shape or values are unsupported.
        '''

        pass

    @abstractmethod
    def __str__(self) -> str:
        '''
        Return a string representation of the performance.
        '''

        pass


class SegMetrics(PerformanceMeasure):
    '''
    Mean Intersection over Union.
    '''

    def __init__(self, classes):
        self.classes = classes

        self.reset()

    def reset(self) -> None:
        '''
        Resets the internal state.
        '''
        ## TODO implement
        self.num_classes = len(self.classes)
        self.confusion_matrix = torch.zeros(
            size=(self.num_classes, self.num_classes),
            dtype=torch.int64,
        )



    def update(
        self,
        prediction: torch.Tensor, 
        target: torch.Tensor,
    ) -> None:
        '''
        Update the measure by comparing predicted data with ground-truth target data.
        prediction must have shape (b,c,h,w) where b=batchsize, c=num_classes, h=height, w=width.
        target must have shape (b,h,w) and values between 0 and c-1 (true class labels).
        Raises ValueError if the data shape or values are unsupported.
        Make sure to not include pixels of value 255 in the calculation since those are to be ignored. 
        '''
        ## TODO implement
        # Check input types and shapes
        if not isinstance(prediction, torch.Tensor) or not isinstance(target, torch.Tensor):
            raise ValueError("prediction and target must be torch.Tensor instances")
        if prediction.ndim != 4:
            raise ValueError("prediction must have shape (b, c, h, w)")
        if target.ndim != 3:
            raise ValueError("target must have shape (b, h, w)")

        # Get dimensions and validate
        batch_size, num_classes, height, width = prediction.shape
        if num_classes != self.num_classes:
            raise ValueError("prediction channel dimension must match the number of classes")
        if target.shape != (batch_size, height, width):
            raise ValueError("target shape must match prediction batch and spatial dimensions")

        # Ignore pixels with value 255
        valid_mask = target != 255
        valid_targets = target[valid_mask]

        if valid_targets.numel() == 0:
            return

        if (valid_targets < 0).any() or (valid_targets >= self.num_classes).any():
            raise ValueError("target values must be in [0, c-1] or equal to 255")

        # Get predicted class labels and filter by valid mask
        predicted_labels = prediction.argmax(dim=1)  # Shape: (b, h, w)

        # Filter predictions and targets by valid mask
        valid_predictions = predicted_labels[valid_mask].to(torch.int64)  # Shape: (b, h,w) -> (n_valid_pixels,)
        valid_targets = valid_targets.to(torch.int64)  # Shape: (b, h, w) -> (n_valid_pixels,)

        # Compute confusion matrix for the batch and accumulate
        flat_indices = valid_targets * self.num_classes + valid_predictions  # Like row*num_classes + col for 2D confusion matrix
        batch_confusion = torch.bincount(
            flat_indices,
            minlength=self.num_classes * self.num_classes,
        )  # Shape: (num_classes * num_classes,)
        batch_confusion = batch_confusion.reshape(self.num_classes, self.num_classes)  # Shape: (num_classes, num_classes)

        # Accumulate batch confusion matrix into the overall confusion matrix
        self.confusion_matrix += batch_confusion

        return
   

    def __str__(self):
        '''
        Return a string representation of the performance, mean IoU.
        e.g. "mIou: 0.54"
        '''
        ## TODO implement
        return f"mIou: {self.mIoU():.2f}"
          

    
    def mIoU(self) -> float:
        '''
        Compute and return the mean IoU as a float between 0 and 1.
        Returns 0 if no data is available (after resets).
        If the denominator for IoU calculation for one of the classes is 0,
        use 0 as IoU for this class.
        '''
        ## TODO implement
        if self.confusion_matrix.sum() == 0:
            return 0.0

        # Calculate true positives, false positives, and false negatives for each class
        true_positives = torch.diag(self.confusion_matrix).to(torch.float32)  # Shape: (num_classes,)
        false_positives = self.confusion_matrix.sum(dim=0).to(torch.float32) - true_positives  # Shape: (num_classes,)
        false_negatives = self.confusion_matrix.sum(dim=1).to(torch.float32) - true_positives  # Shape: (num_classes,)

        denominator = true_positives + false_positives + false_negatives

        iou = torch.zeros_like(true_positives)  # Shape: (num_classes,)
        valid = denominator > 0  # Shape: (num_classes,)
        iou[valid] = true_positives[valid] / denominator[valid]

        mean_iou = iou.mean().item()

        return mean_iou





