from itertools import chain
from pathlib import Path

import kagglehub
import pandas as pd
import csv



def download_dataset_from_kaggle() -> str:
    # Download latest version
    path = kagglehub.dataset_download(
        "fronkongames/steam-games-dataset",
        output_dir="data/raw",
        force_download=False,
    )

    path = path + "/games.csv"
    print("Path to dataset files:", path)

    return path


def fix_dataset_column_problem(
    raw_csv_path: str,
    output_csv_path: str,
) -> str:

    correct_columns = [
        "Name", "Release date", "Estimated owners", "Peak CCU",
        "Required age", "Price", "Discount", "DLC count", "About the game",
        "Supported languages", "Full audio languages", "Reviews",
        "Header image", "Website", "Support url", "Support email", "Windows",
        "Mac", "Linux", "Metacritic score", "Metacritic url", "User score",
        "Positive", "Negative", "Score rank", "Achievements", "Recommendations",
        "Notes", "Average playtime forever", "Average playtime two weeks",
        "Median playtime forever", "Median playtime two weeks", "Developers",
        "Publishers", "Categories", "Genres", "Tags", "Screenshots", "Movies"
    ]

    all_columns = ["AppID"] + correct_columns


    rows = {}  # keyed by AppID

    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)  

    with open(raw_csv_path, "r", encoding="utf-8", newline="") as infile, \
        open(output_csv_path, "w", encoding="utf-8", newline="") as outfile:

        header = infile.readline().replace("DiscountDLC count", "Discount,DLC count")
        reader = csv.DictReader(chain([header], infile))

        if reader.fieldnames is None:
            raise ValueError("No header row found")

        if len(reader.fieldnames) != len(all_columns):
            raise ValueError(
                f"Column count mismatch: file has {len(reader.fieldnames)}, "
                f"expected {len(all_columns)}"
            )

        reader.fieldnames = list(all_columns)

        writer = csv.DictWriter(outfile, fieldnames=correct_columns)
        writer.writeheader()

        for i, row in enumerate(reader):
            # drop None keys from stray commas
            clean_row = {k: v for k, v in row.items() if k is not None}

            app_id = clean_row.pop("AppID")

            writer.writerow(clean_row)
            rows[app_id] = clean_row

            if i % 10000 == 0:
                print(f"Processing row {i}...")

        print(f"CSV saved to {output_csv_path} ({len(rows)} rows)")

    return output_csv_path

def remove_outliers(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["Price"] <= 100]
    df = df[(df["Required age"] >= 0) & (df["Required age"] <= 27)]
    df = df[(df["Discount"] >= 0) & (df["Discount"] <= 100)]

    return df


def preprocess_dataset(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Only keep columns we care about
    necessary_columns = [
        "Name", "Release date", "Estimated owners", "Required age",
        "Price", "Discount", "DLC count",
        "Supported languages", "Full audio languages",
        "Windows", "Mac", "Linux",
        "Metacritic score", "Peak CCU",
        "User score", "Positive", "Negative", "Achievements", "Recommendations",
        "Average playtime forever", "Average playtime two weeks", "Median playtime forever", "Median playtime two weeks",
        "Developers", "Publishers",
        "Categories", "Genres",
    ]
    df = df[necessary_columns]
    
    # Drop rows with missing values in any of the necessary columns
    df.dropna(inplace=True)

    # Proceed datetime conversion and sorting
    df["Release date"] = pd.to_datetime(df["Release date"], errors="coerce")
    df.dropna(subset=["Release date"], inplace=True)
    df.sort_values("Release date", inplace=True)

    # Remove outliers from the dataset
    df = remove_outliers(df)

    # Save it back to disk for future use
    df.to_csv("data/processed/games_clean.csv", index=False)

    return df


if __name__ == "__main__":
    raw_csv_path = download_dataset_from_kaggle()
    processed_csv_path = fix_dataset_column_problem(raw_csv_path, "data/processed/games_clean.csv")
    df = preprocess_dataset(processed_csv_path)
    print(f"Processed dataset shape: {df.shape}")
    print(f"NA values in dataset: {df.isna().sum().sum()}")
