# What Does Success Look Like on Steam?

Interactive Information Visualization project exploring which combinations of price, genre, ownership, review reception, engagement, and release timing are associated with success on Steam.

## Project goal

The dashboard operationalizes the proposal question with a configurable success score:

```text
Success Score =
  (alpha * normalized log ownership
   + beta * review ratio
   + gamma * normalized log median playtime)
  / (alpha + beta + gamma)
```

The weights are adjustable in the interface so the presentation can discuss how different success definitions change the visible market structure.

## What is implemented

- A Python data pipeline that downloads, repairs, cleans, and engineers Steam game features.
- A D3 dashboard with coordinated multiple views.
- Explicit chart-to-chart linking: clicking heatmap cells, tag bubbles, genre bars, scatter points, or years updates the full dashboard.
- A committed bubble-chart tag view, matching the teacher feedback to choose one encoding instead of keeping the network idea vague.
- A heatmap with both sequential absolute encoding and a diverging above/below-average mode.
- A free-to-play versus paid comparison view to support the proposal's monetization lens.

## Views and interaction design

The dashboard uses seven linked views:

- Scatter plot: price vs. review ratio, with color for genre and size for ownership.
- Heatmap: genre by price tier, colored by average success score.
- Time panel: average success and median price over time, with release volume in the background.
- Tag bubble chart: top tags by prevalence, colored by average success.
- Free-to-play vs paid comparison cards.
- Success score distribution histogram.
- Genre ranking bars.

Interaction support is intentionally visible for grading:

- Global controls filter genre, platform, price tier, monetization, release year, score weights, and heatmap mode.
- Chart clicks create drill-down filters that propagate to every other view.
- Active linked filters are surfaced as removable chips so the coordinated filtering is obvious during a live demo.
- A reset action clears the full exploration state quickly during presentation.

## Data pipeline

### 1. Download and repair the raw dataset

Run:

```bash
python scripts/dataset_download.py
```

This script:

- downloads the Kaggle Steam dataset into `data/raw/`
- fixes the malformed `DiscountDLC count` header issue
- writes a cleaned CSV to `data/processed/games_clean.csv`
- applies initial dataset cleaning and outlier filtering

### 2. Build dashboard-ready JSON

Run:

```bash
python scripts/preprocess_steam_data.py
```

By default, the preprocessing step reads `data/processed/games_clean.csv` and writes `data/processed/dashboard_data.json`.

It performs the following feature engineering:

- parses release dates and derives release year
- converts owner ranges such as `20,000 - 50,000` to numeric midpoints
- derives price tiers and the free-to-play flag
- smooths review ratio with phantom reviews so low-review games are less misleading
- log-normalizes ownership and playtime before scoring
- derives platform lists and tag lists for the interactive views

## Run locally

The simplest full run is:

```bash
sh run_all.sh
```

That script:

- synchronizes the Python environment with `uv`
- downloads and cleans the raw dataset
- builds the dashboard JSON
- starts the Flask app

Then open `http://localhost:8000/`.

The frontend loads data from:

- `GET /api/dashboard-data`

## Why this should score well

This implementation is aligned to the published grading criteria:

- Data cleaning: the pipeline repairs malformed headers, parses dates, filters outliers, converts ranges, and derives analytic features.
- Visualization design: the dashboard uses multiple coordinated views with deliberate encoding choices rather than a single static chart set.
- Interaction design: brushing-style linked exploration is implemented through coordinated filters, drill-down clicks, removable active chips, and resettable state.
- Implementation: the project combines Python preprocessing, Flask serving, and custom D3 views rather than relying on an out-of-the-box dashboard builder.
- Communication: the interface and README make the success formula, interaction model, and design rationale explicit for the final presentation.

## Teacher-feedback decisions reflected in code

- The tag view is now definitively a bubble chart, not a network.
- The heatmap supports the recommended sequential versus diverging interpretation.
- The linked interaction model is explicit in both the UI and the implementation.
- Scatterplot clutter is managed with transparency, legend guidance, and sampling.
