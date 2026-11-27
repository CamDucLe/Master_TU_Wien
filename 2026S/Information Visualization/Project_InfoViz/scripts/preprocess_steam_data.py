from __future__ import annotations

import argparse
import csv
import json
import math
import re
import tempfile
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable


COLUMN_ALIASES = {
    "name": ["name", "title", "game_name"],
    "release_date": ["release_date", "steam_release_date", "date_release", "realease_date"],
    "price": ["price", "initialprice", "final_price", "usd_price", "initial_price"],
    "genres": ["genres", "genre"],
    "tags": ["tags", "steamspy_tags", "popular_tags"],
    "estimated_owners": ["estimated_owners", "owners", "estimated owners"],
    "positive": ["positive", "positive_ratings", "positive_reviews"],
    "negative": ["negative", "negative_ratings", "negative_reviews"],
    "median_playtime": [
        "median_playtime_forever",
        "median_playtime",
        "median_playtime_hours",
        "median_playtime_minutes",
    ],
    "dlc_count": ["dlc_count", "dlc", "dlc_total"],
    "windows": ["windows", "win"],
    "mac": ["mac", "macos", "mac_os"],
    "linux": ["linux", "steam_linux"],
}

PRICE_TIER_ORDER = [
    "Free",
    "Under $5",
    "$5-$15",
    "$15-$30",
    "$30+",
]

NUMERIC_COLUMNS = ["price", "positive", "negative", "median_playtime", "dlc_count"]
PLATFORM_COLUMNS = ["windows", "mac", "linux"]


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def find_column(columns: Iterable[str], aliases: list[str]) -> str | None:
    normalized_map = {normalize_key(column): column for column in columns}
    for alias in aliases:
        match = normalized_map.get(normalize_key(alias))
        if match:
            return match
    return None


def resolve_schema(columns: Iterable[str]) -> dict[str, str | None]:
    return {field: find_column(columns, aliases) for field, aliases in COLUMN_ALIASES.items()}


def is_lfs_pointer(file_path: Path) -> bool:
    if not file_path.exists() or file_path.stat().st_size > 256:
        return False
    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        first_line = handle.readline().strip()
    return first_line == "version https://git-lfs.github.com/spec/v1"


def parse_list_field(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    items = re.split(r"\s*[;,|/]\s*", text)
    cleaned = []
    for item in items:
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def parse_ownership_midpoint(value: object) -> float:
    if value is None:
        return 0.0
    text = str(value)
    numbers = [float(part.replace(",", "")) for part in re.findall(r"\d[\d,]*", text)]
    if not numbers:
        return 0.0
    if len(numbers) == 1:
        return numbers[0]
    return (numbers[0] + numbers[1]) / 2


def parse_float(value: object) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    cleaned = text.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def repair_shifted_games_clean_row(
    row: dict[str, str],
    schema: dict[str, str | None],
) -> tuple[object, object, object]:
    release_key = schema.get("release_date")
    price_key = schema.get("price")
    owners_key = schema.get("estimated_owners")

    release_raw = row.get(release_key, "") if release_key else ""
    price_raw = row.get(price_key, 0) if price_key else 0
    owners_raw = row.get(owners_key, 0) if owners_key else 0

    corrected_release = row.get("Realease date", "")
    # In corrupted games_clean.csv, Release date contains owners ranges, while
    # Realease date contains the true date.
    if corrected_release and parse_date(release_raw) is None and parse_date(corrected_release):
        release_raw = corrected_release
        if release_key:
            owners_raw = row.get(release_key, owners_raw)
        if "Required age" in row and str(row.get("Required age", "")).strip():
            price_raw = row.get("Required age", price_raw)

    return release_raw, price_raw, owners_raw


def normalize_prices(values: list[float]) -> list[float]:
    positive_values = [value for value in values if value > 0]
    if positive_values and median(positive_values) > 200:
        return [round(value / 100, 2) for value in values]
    return [round(value, 2) for value in values]


def choose_price_tier(price: float) -> str:
    if price <= 0:
        return "Free"
    if price < 5:
        return "Under $5"
    if price < 15:
        return "$5-$15"
    if price < 30:
        return "$15-$30"
    return "$30+"


def minmax(values: list[float]) -> list[float]:
    minimum = min(values) if values else 0.0
    maximum = max(values) if values else 0.0
    if math.isclose(minimum, maximum):
        return [0.5 for _ in values]
    return [(value - minimum) / (maximum - minimum) for value in values]


def parse_date(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b, %Y",
        "%d %B, %Y",
        "%Y-%m",
    ]
    for date_format in formats:
        try:
            parsed = datetime.strptime(text, date_format)
            if date_format == "%Y-%m":
                return parsed.replace(day=1)
            return parsed
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_raw_dataset(input_path: Path, fallback_path: Path) -> tuple[Iterable[dict[str, str]], list[str], dict[str, str]]:
    source_meta = {
        "requestedInput": str(input_path),
        "resolvedInput": str(input_path),
        "mode": "primary",
    }
    if not input_path.exists() or is_lfs_pointer(input_path):
        if not fallback_path.exists():
            raise FileNotFoundError(
                f"Input dataset is unavailable and fallback demo file was not found: {fallback_path}"
            )
        source_meta["resolvedInput"] = str(fallback_path)
        source_meta["mode"] = "demo-fallback"
        source_meta["warning"] = (
            "The main data/games.csv file is missing or still a Git LFS pointer. "
            "Using the bundled demo dataset instead."
        )
        input_path = fallback_path
    # Return a streaming CSV reader (iterator) and the header names so callers
    # can process rows without loading the entire file into memory.
    handle = input_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
        handle.close()
        raise ValueError(f"CSV file has no header row: {input_path}")
    return reader, list(reader.fieldnames), source_meta


def build_games_rows(
    rows: Iterable[dict[str, str]],
    columns: list[str],
    source_meta: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    schema = resolve_schema(columns)
    missing_required = [field for field in ["name", "release_date", "price", "genres", "estimated_owners"] if not schema[field]]
    if missing_required:
        raise ValueError(f"Missing required columns: {', '.join(missing_required)}")

    name_col = str(schema["name"])
    genres_col = str(schema["genres"])
    tags_col = schema.get("tags")
    positive_col = schema.get("positive")
    negative_col = schema.get("negative")
    median_playtime_col = schema.get("median_playtime")
    dlc_count_col = schema.get("dlc_count")
    windows_col = schema.get("windows")
    mac_col = schema.get("mac")
    linux_col = schema.get("linux")

    # To support very large CSV inputs, process rows in streaming passes and
    # stage parsed rows to a temporary JSONL file so we never hold the raw CSV
    # data in memory all at once.
    temp_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
    temp_path = Path(temp_file.name)

    raw_prices: list[float] = []
    # First pass: parse rows and write minimal staged records to temp JSONL
    for row in rows:
        release_raw, price_raw, owners_raw = repair_shifted_games_clean_row(row, schema)
        release_date = parse_date(release_raw)
        genres = parse_list_field(row.get(genres_col, ""))
        # Prefer explicit tags column when present, otherwise derive tags
        # from genres and any categories-like columns so the frontend's
        # tag/bubble view can still be populated for datasets without
        # a dedicated `tags` column (like games_clean.csv).
        tags: list[str] = []
        if tags_col:
            tags = parse_list_field(row.get(str(tags_col), ""))
        if not tags:
            derived: list[str] = []
            for g in genres:
                if g and g not in derived:
                    derived.append(g)
            # Some datasets use a `categories` field; try common variants.
            for ckey in ("categories", "category", "Categories", "Category"):
                if ckey in row:
                    for t in parse_list_field(row.get(ckey, "")):
                        if t and t not in derived:
                            derived.append(t)
            tags = derived
        staged = {
            "name": str(row.get(name_col, "")).strip(),
            "release_date": release_date.strftime("%Y-%m-%d") if release_date else "",
            "release_year": release_date.year if release_date else 0,
            "raw_price": parse_float(price_raw),
            "genre_list": genres,
            "primary_genre": genres[0] if genres else "Unknown",
            "tag_list": tags[:8],
            "estimated_owners": parse_ownership_midpoint(owners_raw),
            "positive": parse_float(row.get(str(positive_col), 0)) if positive_col else 0.0,
            "negative": parse_float(row.get(str(negative_col), 0)) if negative_col else 0.0,
            "median_playtime": parse_float(row.get(str(median_playtime_col), 0)) if median_playtime_col else 0.0,
            "dlc_count": parse_float(row.get(str(dlc_count_col), 0)) if dlc_count_col else 0.0,
            "windows": parse_bool(row.get(str(windows_col), "")) if windows_col else True,
            "mac": parse_bool(row.get(str(mac_col), "")) if mac_col else False,
            "linux": parse_bool(row.get(str(linux_col), "")) if linux_col else False,
        }
        temp_file.write(json.dumps(staged, ensure_ascii=False) + "\n")
        raw_prices.append(staged["raw_price"])

    temp_file.close()

    normalized_prices = normalize_prices(raw_prices)

    # Second pass: read staged records, filter invalid rows, and collect stats
    valid_games: list[dict[str, Any]] = []
    ownership_vals: list[float] = []
    engagement_vals: list[float] = []
    review_total = 0.0
    positive_total = 0.0

    with temp_path.open("r", encoding="utf-8") as fh:
        for index, line in enumerate(fh):
            staged = json.loads(line)
            if not staged.get("name") or not staged.get("release_year"):
                continue
            price = normalized_prices[index]
            staged["price"] = price
            staged["price_tier"] = choose_price_tier(price)
            staged["is_free_to_play"] = price <= 0
            staged["platforms"] = [
                label
                for label, field in [("Windows", "windows"), ("Mac", "mac"), ("Linux", "linux")]
                if staged.get(field)
            ]
            staged["review_count"] = staged.get("positive", 0.0) + staged.get("negative", 0.0)
            valid_games.append(staged)
            review_total += staged["review_count"]
            positive_total += staged.get("positive", 0.0)
            ownership_vals.append(staged.get("estimated_owners", 0.0))
            engagement_vals.append(staged.get("median_playtime", 0.0))

    # Clean up temp file
    try:
        temp_path.unlink()
    except Exception:
        pass

    overall_rate = positive_total / max(review_total, 1)
    phantom_reviews = 50

    ownership_components = minmax([math.log1p(v) for v in ownership_vals]) if ownership_vals else []
    engagement_components = minmax([math.log1p(v) for v in engagement_vals]) if engagement_vals else []

    for index, game in enumerate(valid_games):
        game["review_ratio"] = (game.get("positive", 0.0) + phantom_reviews * overall_rate) / (
            game.get("review_count", 0.0) + phantom_reviews
        )
        game["ownership_component"] = ownership_components[index] if ownership_components else 0.0
        game["review_component"] = min(max(game["review_ratio"], 0), 1)
        game["engagement_component"] = engagement_components[index] if engagement_components else 0.0
        game["success_score"] = (
            game["ownership_component"] + game["review_component"] + game["engagement_component"]
        ) / 3

    meta = {
        **source_meta,
        "recordCount": len(valid_games),
        "yearRange": [min(game["release_year"] for game in valid_games), max(game["release_year"] for game in valid_games)],
        "genres": sorted({game["primary_genre"] for game in valid_games}),
        "priceTiers": PRICE_TIER_ORDER,
        "platforms": ["Windows", "Mac", "Linux"],
        "successFormula": "(alpha * log_ownership_norm + beta * review_ratio + gamma * log_playtime_norm) / (alpha + beta + gamma)",
    }

    return valid_games, meta


def build_payload(games: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    records = []
    for record in games:
        records.append(
            {
                "name": record["name"],
                "releaseDate": (
                    record["release_date"]
                    if isinstance(record["release_date"], str)
                    else record["release_date"].strftime("%Y-%m-%d")
                ),
                "releaseYear": int(record["release_year"]),
                "price": round(float(record["price"]), 2),
                "priceTier": record["price_tier"],
                "genres": record["genre_list"],
                "primaryGenre": record["primary_genre"],
                "tags": record["tag_list"],
                "estimatedOwners": int(round(float(record["estimated_owners"]))),
                "positive": int(round(float(record["positive"]))),
                "negative": int(round(float(record["negative"]))),
                "reviewCount": int(round(float(record["review_count"]))),
                "reviewRatio": round(float(record["review_ratio"]), 4),
                "medianPlaytime": int(round(float(record["median_playtime"]))),
                "dlcCount": int(round(float(record["dlc_count"]))),
                "platforms": record["platforms"],
                "isFreeToPlay": bool(record["is_free_to_play"]),
                "components": {
                    "ownership": round(float(record["ownership_component"]), 4),
                    "review": round(float(record["review_component"]), 4),
                    "engagement": round(float(record["engagement_component"]), 4),
                },
                "successScore": round(float(record["success_score"]), 4),
            }
        )

    return {"meta": meta, "games": records}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Steam dashboard data for the D3 interface.")
    parser.add_argument(
        "--input",
        default="data/processed/games_clean.csv",
        help="Path to the raw Steam CSV. If missing or a Git LFS pointer, the demo CSV is used.",
    )
    parser.add_argument(
        "--demo-fallback",
        default="data/demo_games.csv",
        help="Fallback CSV used when the main dataset is unavailable.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/dashboard_data.json",
        help="Where to write the processed dashboard JSON.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    fallback_path = Path(args.demo_fallback)
    output_path = Path(args.output)

    rows, columns, source_meta = load_raw_dataset(input_path, fallback_path)
    games, meta = build_games_rows(rows, columns, source_meta)
    payload = build_payload(games, meta)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {meta['recordCount']} records to {output_path}")
    if source_meta.get("warning"):
        print(source_meta["warning"])


if __name__ == "__main__":
    main()
