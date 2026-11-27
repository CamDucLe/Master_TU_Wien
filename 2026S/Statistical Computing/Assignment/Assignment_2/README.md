# AKSTA Statistical Computing – Case Study 2

This repository contains the solution to **Case Study 2** for the course *AKSTA Statistical Computing (TU Wien)*.  
The project focuses on the integration, cleaning, and statistical analysis of global socio-economic indicators using real-world datasets.

## Project Overview

The analysis is based on data from the **CIA World Factbook (2020)** and additional external sources. The goal is to construct a unified dataset of countries and analyze relationships between:

- Education expenditure (% of GDP)
- Youth unemployment rate (15–24 years)
- Net migration rate
- Income classification (World Bank)
- Geographic regions (continent & subregion)

## Methodology

### 1. Data Import & Cleaning
- Manual parsing of `.txt` files using `readLines()` and `strsplit()`
- CSV ingestion with `read.csv()`
- Standardization of country names and numeric variables
- Removal of missing or malformed entries

### 2. Data Integration
- Merging datasets using `dplyr::full_join()`
- Harmonization through **ISO3 country codes**
- Integration of income classification (World Bank)
- Addition of geographic information (UN M49 regions)

### 3. Exploratory Data Analysis
- Frequency tables for income groups
- Cross-tabulations by continent and income status
- Identification of unique country–income–continent combinations

### 4. Statistical Analysis
- Mean, median, standard deviation, and IQR comparisons
- Grouped summaries by income status and continent
- Identification of top-performing countries

### 5. Probability Analysis
- Conditional probability estimation (Bayesian interpretation)
- Analysis of unemployment and migration relationships

### 6. Advanced Analysis
- Detection of potential Simpson’s Paradox in unemployment rates
- Comparison of global vs. continent-level trends

## Key Insights

- Income groups show strong structural differences in all three indicators.
- Migration patterns and unemployment rates are highly region-dependent.
- Aggregated statistics can be misleading due to **Simpson’s Paradox**.
- ISO codes are essential for reliable cross-dataset merging.

## Technologies Used

- R (tidyverse)
  - dplyr
  - tidyr
  - readr
  - readxl
- R Markdown
- Data sources: CIA World Factbook, World Bank, UN M49
