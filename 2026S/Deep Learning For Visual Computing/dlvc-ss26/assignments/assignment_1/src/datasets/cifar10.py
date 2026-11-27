import pickle
from typing import Tuple
import numpy as np


from assignment_1_code.datasets.dataset import Subset, ClassificationDataset


class CIFAR10Dataset(ClassificationDataset):
    """
    Custom CIFAR-10 Dataset.
    """

    def __init__(self, fdir: str, subset: Subset, transform=None):
        """
        Initializes the CIFAR-10 dataset.
        """
        self.classes = (
            "plane",
            "car",
            "bird",
            "cat",
            "deer",
            "dog",
            "frog",
            "horse",
            "ship",
            "truck",
        )

        self.fdir = fdir
        self.subset = subset
        self.transform = transform

        self.images, self.labels = self.load_cifar()

    def load_cifar(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Loads the dataset from a directory fdir that contains the Python version
        of the CIFAR-10, i.e. files "data_batch_1", "test_batch" and so on.
        Raises ValueError if fdir is not a directory or if a file inside it is missing.

        The subsets are defined as follows:
          - The training set contains all images from "data_batch_1" to "data_batch_4", in this order.
          - The validation set contains all images from "data_batch_5".
          - The test set contains all images from "test_batch".

        Depending on which subset is selected, the corresponding images and labels are returned.

        Images are loaded in the order they appear in the data files
        and returned as uint8 numpy arrays with shape (32, 32, 3), in RGB channel order.
        Labels should be returned either as a Python list of ints or as a
        numpy array with dtype int64.
        """

        # TODO implement
        # Check if fdir is a directory
        import os
        if not os.path.isdir(self.fdir):
            raise ValueError("fdir is not a directory")

        # Check if the required files exist
        required_files = []
        if self.subset == Subset.TRAINING:
            required_files = [f"data_batch_{i}" for i in range(1, 5)]
        elif self.subset == Subset.VALIDATION:
            required_files = ["data_batch_5"]
        elif self.subset == Subset.TEST:
            required_files = ["test_batch"]
        else:
            raise ValueError("Invalid subset")

        # Raise value error if any required file is missing
        for file in required_files:
            if not os.path.isfile(f"{self.fdir}/{file}"):
                raise ValueError(f"Missing file: {file}")

        # See the CIFAR-10 website on how to load the data files
        def unpickle(file):
            with open(file, "rb") as fo:
                dict = pickle.load(fo, encoding="bytes")
            return dict
    
        images = []  # list of numpy arrays of shape (N, 32, 32, 3)
        labels = []  # list of ints or numpy array of shape (N,)

        # Load the required files and concatenate the images and labels
        for file in required_files:
            data_dict = unpickle(f"{self.fdir}/{file}")
            images.append(data_dict[b"data"])
            labels += data_dict[b"labels"]
        
        # Convert images to numpy array and reshape to (N, 32, 32, 3)
        images = np.concatenate(images, axis=0)
        images = images.reshape(-1, 3, 32, 32).transpose(0, 2, 3, 1)
        labels = np.array(labels, dtype=np.int64)

        return images, labels

    def __len__(self) -> int:
        """
        Returns the number of samples in the dataset.
        """
        # TODO implement
        return len(self.images)

    def __getitem__(self, idx: int) -> Tuple:
        """
        Returns the idx-th sample in the dataset, which is a tuple,
        consisting of the image and labels.
        Applies transforms if not None.
        Raises IndexError if the index is out of bounds.
        """
        # TODO implement
        if idx < 0 or idx >= len(self.images):
            raise IndexError("Index out of bounds")

        image = self.images[idx]
        label = self.labels[idx]
        if self.transform:
            image = self.transform(image)

        return image, label

    def num_classes(self) -> int:
        """
        Returns the number of classes.
        """
        # TODO implement
        return len(self.classes)


if __name__ == "__main__":
    # Test the dataset implementation
    fdir = "cifar-10-batches-py"
    for subset in Subset:
        print(f"\n\nTesting subset: {subset}")

        dataset = CIFAR10Dataset(fdir=fdir, subset=subset)
        print(f"Number of samples: {len(dataset)}")
        print(f"Number of classes: {dataset.num_classes()}")
        print(f"Images type: {type(dataset.images)}, Labels type: {type(dataset.labels)}")

        image, label = dataset[0]
        print(f"Image shape: {image.shape}, Label: {label}")
        print(f"Image dtype: {image.dtype}, Label dtype: {type(label)}")
        print(f"Labels of the first 10 samples: {dataset.labels[:10]}")
