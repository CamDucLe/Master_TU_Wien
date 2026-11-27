# CIA World Factbook 2020 Explorer

An interactive Shiny application for exploring socio-economic and demographic indicators from the CIA World Factbook (2020).

## Overview

This application allows users to visualize and compare country-level statistics through interactive maps and plots. It supports both univariate and multivariate analysis of selected indicators.

Available indicators:

* Education expenditure (% of GDP)
* Youth unemployment rate
* Net migration rate
* Population growth rate
* Electricity generated from fossil fuels (%)
* Life expectancy at birth

Additional variables used in the multivariate analysis:

* Population
* Area (km²)

---

## Features

### Univariate Analysis

Select a variable and explore it through:

#### World Map

* Interactive choropleth map
* Countries colored according to the selected variable
* Hover tooltips displaying country names and values
* Missing values displayed in grey

#### Global Analysis

* Histogram with density curve
* Boxplot of the selected variable

#### Analysis by Continent

* Density plots grouped by continent
* Boxplots grouped by continent

#### Raw Data Table

* Displays country, continent, and the selected variable
* Appears when the **View Raw Data** button is pressed
* Pagination limited to 15 rows

---

### Multivariate Analysis

Compare two variables using an interactive scatterplot.

Features:

* Variable selection for X and Y axes
* Point size scaled by:

  * Population
  * Area
* Points colored by continent
* LOESS smoothing curves for each continent
* Interactive hover tooltips with country information

---

## Required Packages

```r
library(shiny)
library(plotly)
library(ggplot2)
library(dplyr)
library(DT)
library(jsonlite)
library(countrycode)
library(maps)
library(viridis)
```

---

## Data

The application uses the file:

```text
data_cia2.json
```

This file must be located in the same directory as `app.R`.

---

## Running the Application

1. Open RStudio.
2. Set the working directory to the project folder.
3. Ensure `data_cia2.json` is present.
4. Install any missing packages.
5. Run:

```r
shiny::runApp()
```

or open `app.R` and click **Run App** in RStudio.

---

## Project Structure

```text
project/
│
├── app.R
├── data_cia2.json
└── README.md
```

---

## Implementation Notes

* Built using Shiny's reactive programming model.
* Interactive visualizations created with Plotly (`ggplotly`).
* World map generated from `maps::map_data("world")`.
* Country names converted to ISO3 codes using the `countrycode` package.
* Color scales use the color-blind-friendly Viridis palette.
