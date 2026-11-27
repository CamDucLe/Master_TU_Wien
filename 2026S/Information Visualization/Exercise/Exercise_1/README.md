# Information Visualization - Exercise 1

This repository contains the submission workspace for **Exercise 1** of the TU Wien course **Information Visualization VU (2026S)**.

The exercise focuses on getting familiar with:
- Python for data analysis
- Pandas data frames
- handling missing values in tabular data
- creating static visualizations with different Python plotting libraries

## Project Contents

- `Exercise1.ipynb`: main notebook for the exercise
- `agriRuralDevelopment.csv`: dataset used in the notebook
- `pyproject.toml`: project metadata and Python dependencies
- `uv.lock`: locked dependency versions for reproducible environments

## Dataset

The dataset is based on **World Bank world statistics** and covers:
- 13,908 observations
- 55 variables
- years from 1960 to 2020
- 215 countries plus 12 aggregate regions

The indicators include agriculture and rural development variables as well as measures such as:
- access to electricity
- GDP per capita
- literacy rate
- net migration
- birth and death rates
- infant mortality
- total population

A longer description is available in the parent directory file `../data_description.txt`.

## Workflow in the Notebook

The notebook currently follows this structure:
- load the CSV with Pandas
- remove unusable rows
- inspect and handle missing values
- compare imputation approaches
- remove columns with too many missing values
- check whether distributions remain reasonable after imputation
- create at least two visualizations using two different libraries
- export the cleaned table as CSV

## Requirements

The project is configured for:
- Python `>=3.14`
- `pandas`
- `matplotlib`
- `seaborn`
- `scikit-learn`

## Setup

If you use `uv`, install the environment with:

```bash
uv sync
```

To start Jupyter from the project directory:

```bash
uv run jupyter lab
```

If Jupyter is not already available in the environment, install it first, for example:

```bash
uv add --dev jupyterlab
```

Then open `Exercise1.ipynb` and run the notebook cells.

## Notes

- The notebook metadata currently points to a local `.venv` Python 3.14 kernel.
- The repository README was previously just a placeholder and has been replaced with a project-specific overview.
