const priceTierOrder = ["Free", "Under $5", "$5-$15", "$15-$30", "$30+"];
const comparisonColors = {
  Free: "#a3cf06",
  Paid: "#66c0f4",
};

const tooltip = d3.select("#tooltip");

const controls = {
  genre: document.getElementById("genre-filter"),
  platform: document.getElementById("platform-filter"),
  priceTier: document.getElementById("price-tier-filter"),
  monetization: document.getElementById("monetization-filter"),
  heatmapMode: document.getElementById("heatmap-mode"),
  yearMin: document.getElementById("year-min"),
  yearMax: document.getElementById("year-max"),
  alpha: document.getElementById("alpha-weight"),
  beta: document.getElementById("beta-weight"),
  gamma: document.getElementById("gamma-weight"),
  yearLabel: document.getElementById("year-range-label"),
  weightSummary: document.getElementById("weight-summary"),
  sourceMode: document.getElementById("source-mode"),
  activeFilters: document.getElementById("active-filters"),
  resetFilters: document.getElementById("reset-filters"),
  exportData: document.getElementById("export-data"),
};

const state = {
  genre: "All",
  platform: "All",
  priceTier: "All",
  tag: "All",
  monetization: "All",
  heatmapMode: "absolute",
  yearMin: null,
  yearMax: null,
  weights: {
    alpha: 1,
    beta: 1,
    gamma: 1,
  },
};

let dataset = null;
let resizeTimer = null;

function formatNumber(value) {
  return d3.format(",")(Math.round(value));
}

function formatCurrency(value) {
  return d3.format("$.2f")(value);
}

function formatPercent(value, digits = 0) {
  return d3.format(`.${digits}%`)(value);
}

function median(values) {
  if (!values.length) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function nonZeroMedian(values) {
  return median(values.filter((value) => value > 0));
}

function measure(containerId, height) {
  const element = document.getElementById(containerId);
  const width = Math.max(element.clientWidth || 0, 320);
  return { element, width, height };
}

function clearContainer(containerId) {
  d3.select(`#${containerId}`).selectAll("*").remove();
}

function showTooltip(event, html) {
  tooltip
    .classed("visible", true)
    .attr("aria-hidden", "false")
    .html(html)
    .style("left", `${event.clientX + 16}px`)
    .style("top", `${event.clientY + 16}px`);
}

function moveTooltip(event) {
  tooltip.style("left", `${event.clientX + 16}px`).style("top", `${event.clientY + 16}px`);
}

function hideTooltip() {
  tooltip.classed("visible", false).attr("aria-hidden", "true");
}

function weightedScore(game) {
  const { alpha, beta, gamma } = state.weights;
  const total = alpha + beta + gamma;
  return (
    alpha * game.components.ownership +
    beta * game.components.review +
    gamma * game.components.engagement
  ) / total;
}

function enrichGames(games) {
  return games.map((game) => ({
    ...game,
    currentScore: weightedScore(game),
  }));
}

function filterGames() {
  return enrichGames(dataset.games).filter((game) => {
    const genreOk = state.genre === "All" || game.genres.includes(state.genre);
    const platformOk = state.platform === "All" || game.platforms.includes(state.platform);
    const priceTierOk = state.priceTier === "All" || game.priceTier === state.priceTier;
    const tagOk = state.tag === "All" || game.tags.includes(state.tag);
    const monetizationOk =
      state.monetization === "All" ||
      (state.monetization === "Free" && game.isFreeToPlay) ||
      (state.monetization === "Paid" && !game.isFreeToPlay);
    const yearOk = game.releaseYear >= state.yearMin && game.releaseYear <= state.yearMax;
    return genreOk && platformOk && priceTierOk && tagOk && monetizationOk && yearOk;
  });
}

function setYearRange(minYear, maxYear) {
  state.yearMin = Math.min(minYear, maxYear);
  state.yearMax = Math.max(minYear, maxYear);
  controls.yearMin.value = state.yearMin;
  controls.yearMax.value = state.yearMax;
}

function syncControlValues() {
  controls.genre.value = state.genre;
  controls.platform.value = state.platform;
  controls.priceTier.value = state.priceTier;
  controls.monetization.value = state.monetization;
  controls.heatmapMode.value = state.heatmapMode;
  controls.alpha.value = state.weights.alpha;
  controls.beta.value = state.weights.beta;
  controls.gamma.value = state.weights.gamma;
  setYearRange(state.yearMin, state.yearMax);
}

function resetFilters() {
  state.genre = "All";
  state.platform = "All";
  state.priceTier = "All";
  state.tag = "All";
  state.monetization = "All";
  state.heatmapMode = "absolute";
  state.weights.alpha = 1;
  state.weights.beta = 1;
  state.weights.gamma = 1;
  setYearRange(dataset.meta.yearRange[0], dataset.meta.yearRange[1]);
  syncControlValues();
  syncControlLabels();
  refreshDashboard();
}

function exportToCSV() {
  const filtered = filterGames();
  if (!filtered.length) {
    alert("No data meets the current filter criteria to export.");
    return;
  }

  const headers = [
    "name",
    "price",
    "releaseYear",
    "estimatedOwners",
    "reviewRatio",
    "medianPlaytime",
    "primaryGenre",
    "genres",
    "platforms",
    "tags",
    "isFreeToPlay",
    "priceTier",
    "currentScore"
  ];

  const csvRows = [];
  csvRows.push(headers.join(","));

  for (const game of filtered) {
    const values = headers.map(header => {
      let val = game[header];
      if (val === undefined || val === null) {
        return "";
      }
      if (Array.isArray(val)) {
        val = val.join(";");
      }
      let valStr = String(val);
      if (valStr.includes(",") || valStr.includes('"') || valStr.includes("\n") || valStr.includes(";")) {
        valStr = `"${valStr.replace(/"/g, '""')}"`;
      }
      return valStr;
    });
    csvRows.push(values.join(","));
  }

  const blob = new Blob([csvRows.join("\n")], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `steam_market_data_export_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function toggleGenre(genre) {
  state.genre = state.genre === genre ? "All" : genre;
  syncControlValues();
  syncControlLabels();
  refreshDashboard();
}

function toggleTag(tag) {
  state.tag = state.tag === tag ? "All" : tag;
  syncControlLabels();
  refreshDashboard();
}

function focusHeatmapCell(cell) {
  const sameSelection = state.genre === cell.genre && state.priceTier === cell.tier;
  state.genre = sameSelection ? "All" : cell.genre;
  state.priceTier = sameSelection ? "All" : cell.tier;
  syncControlValues();
  syncControlLabels();
  refreshDashboard();
}

function toggleYearFocus(year) {
  const isSameYear = state.yearMin === year && state.yearMax === year;
  if (isSameYear) {
    setYearRange(dataset.meta.yearRange[0], dataset.meta.yearRange[1]);
  } else {
    setYearRange(year, year);
  }
  syncControlLabels();
  refreshDashboard();
}

function renderActiveFilters() {
  const chips = [];
  if (state.genre !== "All") {
    chips.push({ key: "genre", label: "Genre", value: state.genre });
  }
  if (state.platform !== "All") {
    chips.push({ key: "platform", label: "Platform", value: state.platform });
  }
  if (state.priceTier !== "All") {
    chips.push({ key: "priceTier", label: "Price tier", value: state.priceTier });
  }
  if (state.monetization !== "All") {
    chips.push({ key: "monetization", label: "Business model", value: state.monetization });
  }
  if (state.tag !== "All") {
    chips.push({ key: "tag", label: "Tag", value: state.tag });
  }
  if (state.yearMin !== dataset.meta.yearRange[0] || state.yearMax !== dataset.meta.yearRange[1]) {
    chips.push({
      key: "year",
      label: "Years",
      value: state.yearMin === state.yearMax ? String(state.yearMin) : `${state.yearMin}-${state.yearMax}`,
    });
  }

  const selection = d3.select(controls.activeFilters);
  selection.selectAll("*").remove();

  if (!chips.length) {
    selection.append("div").attr("class", "filter-chip-empty").text("No drill-downs active. Click marks or use the controls above.");
    return;
  }

  const groups = selection
    .selectAll("div.filter-chip")
    .data(chips)
    .join("div")
    .attr("class", "filter-chip");

  groups.html((chip) => `<strong>${chip.label}</strong><span>${chip.value}</span><button type="button" data-key="${chip.key}" aria-label="Clear ${chip.label}">x</button>`);

  groups.select("button").on("click", (_, chip) => {
    if (chip.key === "year") {
      setYearRange(dataset.meta.yearRange[0], dataset.meta.yearRange[1]);
    } else {
      state[chip.key] = "All";
    }
    syncControlValues();
    syncControlLabels();
    refreshDashboard();
  });
}

function sampleGames(games, limit = 900) {
  if (games.length <= limit) {
    return games;
  }
  const sorted = [...games].sort((a, b) => b.estimatedOwners - a.estimatedOwners);
  const stride = sorted.length / limit;
  const sample = [];
  for (let index = 0; index < limit; index += 1) {
    sample.push(sorted[Math.floor(index * stride)]);
  }
  return sample;
}

function initControls(meta) {
  const genres = ["All", ...meta.genres];
  const platforms = ["All", ...meta.platforms];
  const priceTiers = ["All", ...meta.priceTiers];

  controls.genre.innerHTML = genres
    .map((genre) => `<option value="${genre}">${genre === "All" ? "All genres" : genre}</option>`)
    .join("");
  controls.platform.innerHTML = platforms
    .map((platform) => `<option value="${platform}">${platform === "All" ? "All platforms" : platform}</option>`)
    .join("");
  controls.priceTier.innerHTML = priceTiers
    .map((tier) => `<option value="${tier}">${tier === "All" ? "All price tiers" : tier}</option>`)
    .join("");

  setYearRange(meta.yearRange[0], meta.yearRange[1]);
  controls.yearMin.min = meta.yearRange[0];
  controls.yearMin.max = meta.yearRange[1];
  controls.yearMax.min = meta.yearRange[0];
  controls.yearMax.max = meta.yearRange[1];
  controls.sourceMode.textContent =
    meta.mode === "demo-fallback" ? "Bundled demo dataset" : "Primary Steam dataset";

  syncControlValues();
  syncControlLabels();

  controls.genre.addEventListener("change", (event) => {
    state.genre = event.target.value;
    refreshDashboard();
  });
  controls.platform.addEventListener("change", (event) => {
    state.platform = event.target.value;
    refreshDashboard();
  });
  controls.priceTier.addEventListener("change", (event) => {
    state.priceTier = event.target.value;
    refreshDashboard();
  });
  controls.monetization.addEventListener("change", (event) => {
    state.monetization = event.target.value;
    refreshDashboard();
  });
  controls.heatmapMode.addEventListener("change", (event) => {
    state.heatmapMode = event.target.value;
    refreshDashboard();
  });

  let yearTimer = null;
  [controls.yearMin, controls.yearMax].forEach((input) => {
    input.addEventListener("input", () => {
      const minValue = Number(controls.yearMin.value);
      const maxValue = Number(controls.yearMax.value);
      setYearRange(minValue, maxValue);
      syncControlLabels();
      clearTimeout(yearTimer);
      yearTimer = setTimeout(refreshDashboard, 100);
    });
  });

  let weightsTimer = null;
  [controls.alpha, controls.beta, controls.gamma].forEach((input) => {
    input.addEventListener("input", () => {
      state.weights.alpha = Number(controls.alpha.value);
      state.weights.beta = Number(controls.beta.value);
      state.weights.gamma = Number(controls.gamma.value);
      syncControlLabels();
      clearTimeout(weightsTimer);
      weightsTimer = setTimeout(refreshDashboard, 100);
    });
  });
}

function syncControlLabels() {
  controls.yearLabel.textContent = `${state.yearMin} to ${state.yearMax}`;
  controls.weightSummary.textContent = `${state.weights.alpha.toFixed(1)} / ${state.weights.beta.toFixed(
    1,
  )} / ${state.weights.gamma.toFixed(1)}`;
}

function renderSummary(games) {
  const cards = [
    {
      label: "Visible games",
      value: formatNumber(games.length),
      detail: "Current filtered subset across all linked views.",
    },
    {
      label: "Average success",
      value: games.length ? d3.format(".2f")(d3.mean(games, (game) => game.currentScore)) : "0.00",
      detail: "Weighted from ownership, review ratio, and engagement.",
    },
    {
      label: "Median price",
      value: games.length ? formatCurrency(median(games.map((game) => game.price))) : "$0.00",
      detail: state.priceTier === "All" ? "Useful for seeing how the current slice is monetized." : `Currently drilled into ${state.priceTier}.`,
    },
    {
      label: "Free-to-play share",
      value: games.length ? formatPercent(games.filter((game) => game.isFreeToPlay).length / games.length) : "0%",
      detail: state.tag === "All" ? "Share of the filtered games priced at zero." : `Tag focus: ${state.tag}.`,
    },
  ];

  d3.select("#summary-cards")
    .selectAll("article")
    .data(cards)
    .join("article")
    .attr("class", "summary-card")
    .html(
      (card) =>
        `<h3>${card.label}</h3><strong>${card.value}</strong><p>${card.detail}</p>`,
    );
}

function renderEmpty(containerId, message) {
  clearContainer(containerId);
  d3.select(`#${containerId}`)
    .append("div")
    .attr("class", "empty-state")
    .html(`<div>${message}</div>`);
}

function renderScatter(games) {
  const containerId = "scatter-chart";
  if (!games.length) {
    renderEmpty(containerId, "No games match the current filter combination.");
    return;
  }

  clearContainer(containerId);
  const sample = sampleGames(games, 650);
  const { width, height } = measure(containerId, 420);
  const margin = { top: 20, right: 24, bottom: 54, left: 58 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const svg = d3
    .select(`#${containerId}`)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);
  const chart = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3
    .scaleLinear()
    .domain([0, d3.max(sample, (game) => game.price) * 1.05 || 1])
    .range([0, innerWidth]);
  const y = d3.scaleLinear().domain([0.45, 1]).range([innerHeight, 0]);
  const size = d3
    .scaleSqrt()
    .domain(d3.extent(sample, (game) => game.estimatedOwners))
    .range([3, 18]);
  const genres = [...new Set(sample.map((game) => game.primaryGenre))];
  const steamGenreColors = [
    "#66c0f4", // Steam Blue
    "#a3cf06", // Steam Green
    "#f89406", // Orange
    "#bac7dd", // Muted Gray-Blue
    "#b8d6f2", // Light Blue
    "#82cfff", // Sky Blue
    "#accae6", // Soft Blue
    "#ffb4ab", // Soft Red
    "#c6e7ff", // Very Light Blue
    "#89929a"  // Neutral Gray
  ];
  const color = d3.scaleOrdinal().domain(genres).range(steamGenreColors);

  chart
    .append("g")
    .attr("class", "grid")
    .call(d3.axisLeft(y).ticks(5).tickSize(-innerWidth).tickFormat(() => ""))
    .call((group) => group.select(".domain").remove());

  chart
    .append("g")
    .selectAll("circle")
    .data(sample)
    .join("circle")
    .attr("cx", (game) => x(game.price))
    .attr("cy", (game) => y(game.reviewRatio))
    .attr("r", (game) => size(game.estimatedOwners))
    .attr("fill", (game) => color(game.primaryGenre))
    .attr("fill-opacity", 0.6)
    .attr("stroke", "rgba(255,255,255,0.4)")
    .attr("stroke-width", 0.8)
    .style("cursor", "pointer")
    .style("filter", (game) => `drop-shadow(0 0 2px ${color(game.primaryGenre)})`)
    .on("mouseenter", (event, game) => {
      showTooltip(
        event,
        `<strong>${game.name}</strong>${game.primaryGenre}<br />Price: ${formatCurrency(
          game.price,
        )}<br />Review ratio: ${formatPercent(game.reviewRatio, 1)}<br />Estimated owners: ${formatNumber(
          game.estimatedOwners,
        )}<br />Success score: ${d3.format(".2f")(game.currentScore)}<br />Click to isolate ${game.primaryGenre}.`,
      );
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip)
    .on("click", (_, game) => toggleGenre(game.primaryGenre));

  chart
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x).ticks(Math.min(8, width / 120)).tickFormat((value) => `$${value}`));

  chart.append("g").attr("class", "axis").call(d3.axisLeft(y).ticks(5).tickFormat(d3.format(".0%")));

  chart
    .append("text")
    .attr("class", "axis-label")
    .attr("x", innerWidth / 2)
    .attr("y", innerHeight + 42)
    .attr("text-anchor", "middle")
    .text("Price in USD");

  chart
    .append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -innerHeight / 2)
    .attr("y", -40)
    .attr("text-anchor", "middle")
    .text("Smoothed review ratio");

  const legend = svg.append("g").attr("transform", `translate(${margin.left},${height - 8})`);
  genres.slice(0, 6).forEach((genre, index) => {
    const item = legend.append("g").attr("transform", `translate(${index * 140},0)`);
    item.append("circle").attr("r", 5).attr("fill", color(genre));
    item.append("text").attr("class", "legend-text").attr("x", 12).attr("y", 4).text(genre);
  });
}

function renderHeatmap(games) {
  const containerId = "heatmap-chart";
  if (!games.length) {
    renderEmpty(containerId, "No heatmap cells are available for the current selection.");
    return;
  }

  clearContainer(containerId);
  const { width, height } = measure(containerId, 420);
  const margin = { top: 20, right: 20, bottom: 50, left: 92 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const svg = d3
    .select(`#${containerId}`)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);
  const chart = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const genreCounts = d3.rollups(
    games,
    (items) => items.length,
    (game) => game.primaryGenre,
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([genre]) => genre);

  const globalMean = d3.mean(games, (game) => game.currentScore);
  const cells = [];
  genreCounts.forEach((genre) => {
    priceTierOrder.forEach((tier) => {
      const bucket = games.filter((game) => game.primaryGenre === genre && game.priceTier === tier);
      cells.push({
        genre,
        tier,
        count: bucket.length,
        meanScore: bucket.length ? d3.mean(bucket, (game) => game.currentScore) : null,
      });
    });
  });

  const x = d3.scaleBand().domain(priceTierOrder).range([0, innerWidth]).padding(0.08);
  const y = d3.scaleBand().domain(genreCounts).range([0, innerHeight]).padding(0.08);
  const validScores = cells.filter((cell) => cell.meanScore !== null).map((cell) => cell.meanScore);
  const maxDelta = d3.max(validScores, (value) => Math.abs(value - globalMean)) || 0.01;

  const fill =
    state.heatmapMode === "relative"
      ? d3.scaleLinear().domain([-maxDelta, 0, maxDelta]).range(["#ff5500", "#0e141b", "#a3cf06"])
      : d3.scaleLinear().domain(d3.extent(validScores)).range(["#0e141b", "#66c0f4"]);

  const isCellActive = (cell) => state.genre === cell.genre && state.priceTier === cell.tier;

  chart
    .selectAll("rect")
    .data(cells)
    .join("rect")
    .attr("x", (cell) => x(cell.tier))
    .attr("y", (cell) => y(cell.genre))
    .attr("width", x.bandwidth())
    .attr("height", y.bandwidth())
    .attr("rx", 4)
    .attr("stroke", (cell) => (isCellActive(cell) ? "#66c0f4" : "rgba(255, 255, 255, 0.1)"))
    .attr("stroke-width", (cell) => (isCellActive(cell) ? 2 : 1))
    .attr("fill", (cell) => {
      if (cell.meanScore === null) {
        return "rgba(255, 255, 255, 0.03)";
      }
      return state.heatmapMode === "relative" ? fill(cell.meanScore - globalMean) : fill(cell.meanScore);
    })
    .style("cursor", "pointer")
    .on("mouseenter", (event, cell) => {
      const detail =
        cell.meanScore === null
          ? "No games in the current slice"
          : `Mean success: ${d3.format(".2f")(cell.meanScore)}<br />Games: ${cell.count}<br />Click to link this segment.`;
      showTooltip(event, `<strong>${cell.genre} · ${cell.tier}</strong>${detail}`);
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip)
    .on("click", (_, cell) => {
      if (cell.count > 0) {
        focusHeatmapCell(cell);
      }
    });

  chart
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x));

  chart.append("g").attr("class", "axis").call(d3.axisLeft(y));

  svg
    .append("text")
    .attr("class", "note-text")
    .attr("x", margin.left)
    .attr("y", height - 10)
    .text(
      state.heatmapMode === "relative"
        ? "Colors show distance from the filtered mean success score."
        : "Colors show absolute average success score per segment.",
    );
}

function renderTimeseries(games) {
  const containerId = "timeseries-chart";
  if (!games.length) {
    renderEmpty(containerId, "No temporal trend is available for the current slice.");
    return;
  }

  clearContainer(containerId);
  const yearly = d3
    .rollups(
      games,
      (items) => ({
        avgSuccess: d3.mean(items, (game) => game.currentScore),
        medianPrice: median(items.map((game) => game.price)),
        count: items.length,
      }),
      (game) => game.releaseYear,
    )
    .sort((a, b) => a[0] - b[0])
    .map(([year, values]) => ({ year, ...values }));

  const { width, height } = measure(containerId, 420);
  const margin = { top: 20, right: 56, bottom: 64, left: 52 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const svg = d3
    .select(`#${containerId}`)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);
  const chart = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scalePoint().domain(yearly.map((item) => item.year)).range([0, innerWidth]).padding(0.35);
  const maxTicks = 8;
  const tickStep = Math.max(1, Math.ceil(yearly.length / maxTicks));
  const tickValues = yearly.filter((_, index) => index % tickStep === 0 || index === yearly.length - 1).map((item) => item.year);
  const ySuccess = d3.scaleLinear().domain([0, 1]).nice().range([innerHeight, 0]);
  const yPrice = d3.scaleLinear().domain([0, d3.max(yearly, (item) => item.medianPrice) * 1.1 || 1]).nice().range([innerHeight, 0]);
  const yCount = d3.scaleLinear().domain([0, d3.max(yearly, (item) => item.count) || 1]).range([innerHeight, 0]);
  const selectedSingleYear = state.yearMin === state.yearMax ? state.yearMin : null;

  chart
    .append("g")
    .selectAll("rect")
    .data(yearly)
    .join("rect")
    .attr("x", (item) => x(item.year) - 10)
    .attr("y", (item) => yCount(item.count))
    .attr("width", 20)
    .attr("height", (item) => innerHeight - yCount(item.count))
    .attr("fill", (item) => (selectedSingleYear === item.year ? "rgba(102, 192, 244, 0.3)" : "rgba(255, 255, 255, 0.06)"))
    .style("cursor", "pointer")
    .on("click", (_, item) => toggleYearFocus(item.year));

  const successLine = d3
    .line()
    .x((item) => x(item.year))
    .y((item) => ySuccess(item.avgSuccess));

  const priceLine = d3
    .line()
    .x((item) => x(item.year))
    .y((item) => yPrice(item.medianPrice));

  chart
    .append("path")
    .datum(yearly)
    .attr("fill", "none")
    .attr("stroke", "#a3cf06")
    .attr("stroke-width", 3)
    .attr("d", successLine);

  chart
    .append("path")
    .datum(yearly)
    .attr("fill", "none")
    .attr("stroke", "#f89406")
    .attr("stroke-width", 3)
    .attr("stroke-dasharray", "6 5")
    .attr("d", priceLine);

  chart
    .selectAll(".success-dot")
    .data(yearly)
    .join("circle")
    .attr("class", "success-dot")
    .attr("cx", (item) => x(item.year))
    .attr("cy", (item) => ySuccess(item.avgSuccess))
    .attr("r", 5)
    .attr("fill", (item) => (selectedSingleYear === item.year ? "#f89406" : "#a3cf06"))
    .style("cursor", "pointer")
    .on("mouseenter", (event, item) => {
      showTooltip(
        event,
        `<strong>${item.year}</strong>Average success: ${d3.format(".2f")(item.avgSuccess)}<br />Median price: ${formatCurrency(
          item.medianPrice,
        )}<br />Releases: ${item.count}<br />Click to focus this year.`,
      );
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip)
    .on("click", (_, item) => toggleYearFocus(item.year));

  chart
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x).tickValues(tickValues))
    .selectAll("text")
    .attr("transform", "rotate(-25)")
    .style("text-anchor", "end");

  chart.append("g").attr("class", "axis").call(d3.axisLeft(ySuccess).ticks(5));
  chart
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${innerWidth},0)`)
    .call(d3.axisRight(yPrice).ticks(5).tickFormat((value) => `$${value}`));

  svg
    .append("text")
    .attr("class", "legend-text")
    .attr("x", margin.left)
    .attr("y", 14)
    .text("Green: average success score");

  svg
    .append("text")
    .attr("class", "legend-text")
    .attr("x", margin.left + 190)
    .attr("y", 14)
    .text("Orange dashed: median price");
}

function renderTagBubbles(games) {
  const containerId = "tag-chart";
  if (!games.length) {
    renderEmpty(containerId, "No tag profiles are available for the current selection.");
    return;
  }

  clearContainer(containerId);
  const tagMap = new Map();
  games.forEach((game) => {
    game.tags.forEach((tag) => {
      if (!tagMap.has(tag)) {
        tagMap.set(tag, { tag, count: 0, scoreSum: 0, reviewSum: 0, f2pCount: 0 });
      }
      const entry = tagMap.get(tag);
      entry.count += 1;
      entry.scoreSum += game.currentScore;
      entry.reviewSum += game.reviewRatio;
      entry.f2pCount += game.isFreeToPlay ? 1 : 0;
    });
  });

  const nodes = [...tagMap.values()]
    .map((entry) => ({
      name: entry.tag,
      value: entry.count,
      avgScore: entry.scoreSum / entry.count,
      avgReview: entry.reviewSum / entry.count,
      f2pShare: entry.f2pCount / entry.count,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 18);

  if (!nodes.length) {
    renderEmpty(containerId, "No tag data is available in this dataset (games_clean.csv has no tags column).");
    return;
  }

  const { width, height } = measure(containerId, 420);
  const svg = d3
    .select(`#${containerId}`)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);

  const root = d3.pack().size([width, height]).padding(8)(
    d3
      .hierarchy({ children: nodes })
      .sum((node) => node.value)
      .sort((a, b) => b.value - a.value),
  );

  const color = d3.scaleLinear()
    .domain(d3.extent(nodes, (node) => node.avgScore))
    .range(["#2a475e", "#66c0f4"]);

  function contrastTextColor(value) {
    const fill = d3.color(color(value));
    if (!fill) return "#ffffff";
    const luminance = (0.2126 * fill.r + 0.7152 * fill.g + 0.0722 * fill.b) / 255;
    return luminance < 0.55 ? "#ffffff" : "#121a23";
  }

  const leaves = svg.append("g").selectAll("g").data(root.leaves()).join("g").attr("transform", (node) => `translate(${node.x},${node.y})`);

  leaves
    .append("circle")
    .attr("r", (node) => node.r)
    .attr("fill", (node) => color(node.data.avgScore))
    .attr("stroke", (node) => (state.tag === node.data.name ? "#66c0f4" : "rgba(255, 255, 255, 0.15)"))
    .attr("stroke-width", (node) => (state.tag === node.data.name ? 2.5 : 1))
    .style("cursor", "pointer")
    .on("mouseenter", (event, node) => {
      showTooltip(
        event,
        `<strong>${node.data.name}</strong>Games: ${node.data.value}<br />Avg success: ${d3.format(".2f")(
          node.data.avgScore,
        )}<br />Avg review ratio: ${formatPercent(node.data.avgReview, 1)}<br />F2P share: ${formatPercent(
          node.data.f2pShare,
        )}<br />Click to link this tag.`,
      );
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip)
    .on("click", (_, node) => toggleTag(node.data.name));

  leaves
    .append("text")
    .attr("text-anchor", "middle")
    .attr("dy", "0.35em")
    .style("font-size", (node) => `${Math.max(10, Math.min(node.r / 2.3, 18))}px`)
    .style("font-family", '"Inter", sans-serif')
    .style("font-weight", "600")
    .style("fill", (node) => contrastTextColor(node.data.avgScore))
    .text((node) => String(node.data.name ?? ""))
    .each(function clipText(node) {
      const maxCharacters = Math.max(6, Math.floor(node.r / 3));
      const text = String(node.data.name ?? "");
      if (text.length > maxCharacters) {
        d3.select(this).text(`${text.slice(0, maxCharacters - 1)}…`);
      }
    });
}

function renderComparison(games) {
  const container = d3.select("#comparison-panel");
  container.selectAll("*").remove();
  if (!games.length) {
    container.append("div").attr("class", "empty-state").text("No comparison metrics are available for the current filters.");
    return;
  }

  const groups = {
    Free: games.filter((game) => game.isFreeToPlay),
    Paid: games.filter((game) => !game.isFreeToPlay),
  };

  const metrics = [
    {
      label: "Average success score",
      values: {
        Free: groups.Free.length ? d3.mean(groups.Free, (game) => game.currentScore) : 0,
        Paid: groups.Paid.length ? d3.mean(groups.Paid, (game) => game.currentScore) : 0,
      },
      format: (value) => d3.format(".2f")(value),
    },
    {
      label: "Average review ratio",
      values: {
        Free: groups.Free.length ? d3.mean(groups.Free, (game) => game.reviewRatio) : 0,
        Paid: groups.Paid.length ? d3.mean(groups.Paid, (game) => game.reviewRatio) : 0,
      },
      format: (value) => formatPercent(value, 1),
    },
    {
      label: "Median playtime",
      values: {
        Free: groups.Free.length ? nonZeroMedian(groups.Free.map((game) => game.medianPlaytime)) : 0,
        Paid: groups.Paid.length ? nonZeroMedian(groups.Paid.map((game) => game.medianPlaytime)) : 0,
      },
      format: (value) => `${formatNumber(value)} min`,
      note: "Among games with recorded playtime.",
    },
    {
      label: "Median owners",
      values: {
        Free: groups.Free.length ? nonZeroMedian(groups.Free.map((game) => game.estimatedOwners)) : 0,
        Paid: groups.Paid.length ? nonZeroMedian(groups.Paid.map((game) => game.estimatedOwners)) : 0,
      },
      format: (value) => formatNumber(value),
      note: "Among games with non-zero owner estimates.",
    },
  ];

  const cards = container.selectAll("article").data(metrics).join("article").attr("class", "comparison-metric");

  cards.each(function renderMetric(metric) {
    const element = d3.select(this);
    element.append("h4").text(metric.label);
    const maxValue = Math.max(metric.values.Free, metric.values.Paid, 1);
    ["Free", "Paid"].forEach((groupName) => {
      const row = element.append("div").attr("class", "comparison-row");
      row
        .append("div")
        .attr("class", "comparison-label")
        .html(`<span>${groupName === "Free" ? "Free-to-play" : "Paid"}</span><strong>${metric.format(metric.values[groupName])}</strong>`);
      row
        .append("div")
        .attr("class", "comparison-track")
        .append("div")
        .attr("class", "comparison-fill")
        .style("width", `${(metric.values[groupName] / maxValue) * 100}%`)
        .style("background", comparisonColors[groupName]);
      if (metric.note) {
        row.append("div").attr("class", "comparison-note").text(metric.note);
      }
    });
  });
}

function renderScoreDistribution(games) {
  const containerId = "distribution-chart";
  if (!games.length) {
    renderEmpty(containerId, "No score distribution can be computed for the current filters.");
    return;
  }

  clearContainer(containerId);
  const freeScores = games.filter((game) => game.isFreeToPlay).map((game) => game.currentScore);
  const paidScores = games.filter((game) => !game.isFreeToPlay).map((game) => game.currentScore);
  const binsGenerator = d3.bin().domain([0, 1]).thresholds(12);
  const freeBins = binsGenerator(freeScores);
  const paidBins = binsGenerator(paidScores);

  const bins = freeBins.map((bin, index) => ({
    x0: bin.x0,
    x1: bin.x1,
    free: bin.length,
    paid: paidBins[index]?.length || 0,
  }));

  const { width, height } = measure(containerId, 340);
  const margin = { top: 24, right: 24, bottom: 50, left: 48 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const svg = d3
    .select(`#${containerId}`)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);
  const chart = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, 1]).range([0, innerWidth]);
  const y = d3
    .scaleLinear()
    .domain([0, d3.max(bins, (bin) => Math.max(bin.free, bin.paid)) || 1])
    .nice()
    .range([innerHeight, 0]);

  const bucketGap = 2;
  const bucketWidth = Math.max(4, x(bins[0].x1) - x(bins[0].x0) - bucketGap);
  const half = bucketWidth / 2;

  chart
    .append("g")
    .attr("class", "grid")
    .call(d3.axisLeft(y).ticks(4).tickSize(-innerWidth).tickFormat(() => ""))
    .call((group) => group.select(".domain").remove());

  const freeRects = chart
    .append("g")
    .selectAll("rect")
    .data(bins)
    .join("rect")
    .attr("x", (bin) => x(bin.x0) + bucketGap / 2)
    .attr("y", (bin) => y(bin.free))
    .attr("width", half)
    .attr("height", (bin) => innerHeight - y(bin.free))
    .attr("fill", comparisonColors.Free)
    .attr("fill-opacity", 0.75)
    .on("mouseenter", (event, bin) => {
      showTooltip(
        event,
        `<strong>Score ${bin.x0.toFixed(2)}-${bin.x1.toFixed(2)}</strong>Free-to-play games: ${formatNumber(
          bin.free,
        )}`,
      );
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip);

  const paidRects = chart
    .append("g")
    .selectAll("rect")
    .data(bins)
    .join("rect")
    .attr("x", (bin) => x(bin.x0) + bucketGap / 2 + half)
    .attr("y", (bin) => y(bin.paid))
    .attr("width", half)
    .attr("height", (bin) => innerHeight - y(bin.paid))
    .attr("fill", comparisonColors.Paid)
    .attr("fill-opacity", 0.75)
    .on("mouseenter", (event, bin) => {
      showTooltip(
        event,
        `<strong>Score ${bin.x0.toFixed(2)}-${bin.x1.toFixed(2)}</strong>Paid games: ${formatNumber(bin.paid)}`,
      );
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip);

  chart
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x).ticks(6));
  chart.append("g").attr("class", "axis").call(d3.axisLeft(y).ticks(4));

  chart
    .append("text")
    .attr("class", "axis-label")
    .attr("x", innerWidth / 2)
    .attr("y", innerHeight + 40)
    .attr("text-anchor", "middle")
    .text("Success score");

  chart
    .append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -innerHeight / 2)
    .attr("y", -34)
    .attr("text-anchor", "middle")
    .text("Game count");

  const legend = svg.append("g").attr("transform", `translate(${margin.left},${height - 10})`);
  legend.append("rect").attr("width", 10).attr("height", 10).attr("fill", comparisonColors.Free);
  legend.append("text").attr("class", "legend-text").attr("x", 16).attr("y", 9).text("Free-to-play");
  legend.append("rect").attr("width", 10).attr("height", 10).attr("x", 120).attr("fill", comparisonColors.Paid);
  legend.append("text").attr("class", "legend-text").attr("x", 136).attr("y", 9).text("Paid");

  freeRects.raise();
  paidRects.raise();
}

function renderGenreRanking(games) {
  const containerId = "genre-rank-chart";
  if (!games.length) {
    renderEmpty(containerId, "No genre ranking can be computed for the current filters.");
    return;
  }

  clearContainer(containerId);
  const genres = d3
    .rollups(
      games,
      (items) => ({
        count: items.length,
        avgScore: d3.mean(items, (game) => game.currentScore),
      }),
      (game) => game.primaryGenre,
    )
    .filter(([, values]) => values.count >= 8)
    .sort((a, b) => b[1].avgScore - a[1].avgScore)
    .slice(0, 10)
    .map(([genre, values]) => ({
      genre,
      count: values.count,
      avgScore: values.avgScore,
    }));

  if (!genres.length) {
    renderEmpty(containerId, "Not enough data for stable genre ranking after filtering.");
    return;
  }

  const { width, height } = measure(containerId, 360);
  const margin = { top: 18, right: 74, bottom: 36, left: 130 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const svg = d3
    .select(`#${containerId}`)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);
  const chart = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, d3.max(genres, (row) => row.avgScore) * 1.08 || 1]).range([0, innerWidth]);
  const y = d3
    .scaleBand()
    .domain(genres.map((row) => row.genre))
    .range([0, innerHeight])
    .padding(0.14);
  const color = d3
    .scaleLinear()
    .domain(d3.extent(genres, (row) => row.count))
    .range(["#476882", "#66c0f4"]);

  chart
    .append("g")
    .attr("class", "grid")
    .call(d3.axisBottom(x).ticks(5).tickSize(innerHeight).tickFormat(() => ""))
    .call((group) => group.select(".domain").remove());

  chart
    .selectAll("rect")
    .data(genres)
    .join("rect")
    .attr("x", 0)
    .attr("y", (row) => y(row.genre))
    .attr("width", (row) => x(row.avgScore))
    .attr("height", y.bandwidth())
    .attr("rx", 4)
    .attr("fill", (row) => color(row.count))
    .attr("stroke", (row) => (state.genre === row.genre ? "#66c0f4" : "none"))
    .attr("stroke-width", (row) => (state.genre === row.genre ? 2 : 0))
    .style("cursor", "pointer")
    .on("mouseenter", (event, row) => {
      showTooltip(
        event,
        `<strong>${row.genre}</strong>Average success: ${d3.format(".2f")(row.avgScore)}<br />Games: ${formatNumber(row.count)}<br />Click to pin this genre.`,
      );
    })
    .on("mousemove", moveTooltip)
    .on("mouseleave", hideTooltip)
    .on("click", (_, row) => toggleGenre(row.genre));

  chart
    .selectAll("text.value")
    .data(genres)
    .join("text")
    .attr("class", "legend-text")
    .attr("x", (row) => x(row.avgScore) + 8)
    .attr("y", (row) => y(row.genre) + y.bandwidth() / 2 + 4)
    .text((row) => `${row.avgScore.toFixed(2)} (${row.count})`);

  chart.append("g").attr("class", "axis").call(d3.axisLeft(y));
  chart
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x).ticks(5));
}

function refreshDashboard() {
  const games = filterGames();
  renderActiveFilters();
  renderSummary(games);
  renderScatter(games);
  renderHeatmap(games);
  renderTimeseries(games);
  renderTagBubbles(games);
  renderComparison(games);
  renderScoreDistribution(games);
  renderGenreRanking(games);
}

async function init() {
  dataset = await d3.json("/api/dashboard-data");
  initControls(dataset.meta);
  controls.resetFilters.addEventListener("click", resetFilters);
  if (controls.exportData) {
    controls.exportData.addEventListener("click", exportToCSV);
  }
  refreshDashboard();

  if (dataset.meta.warning) {
    const warning = document.createElement("div");
    warning.className = "meta-card";
    warning.innerHTML = `<span class="meta-label">Data note</span><strong>${dataset.meta.warning}</strong>`;
    document.querySelector(".hero-meta").appendChild(warning);
  }

  // About Modal Interactive Handlers
  const aboutLink = document.getElementById("about-link");
  const aboutModal = document.getElementById("about-modal");
  const closeModal = document.getElementById("close-modal");
  const aboutCloseBtn = document.getElementById("about-close-btn");

  if (aboutLink && aboutModal) {
    aboutLink.addEventListener("click", (event) => {
      event.preventDefault();
      aboutModal.classList.add("active");
      aboutModal.setAttribute("aria-hidden", "false");
    });
  }

  function hideAboutModal() {
    if (aboutModal) {
      aboutModal.classList.remove("active");
      aboutModal.setAttribute("aria-hidden", "true");
    }
  }

  if (closeModal) {
    closeModal.addEventListener("click", hideAboutModal);
  }
  if (aboutCloseBtn) {
    aboutCloseBtn.addEventListener("click", hideAboutModal);
  }
  if (aboutModal) {
    aboutModal.addEventListener("click", (event) => {
      if (event.target === aboutModal) {
        hideAboutModal();
      }
    });
  }

  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => refreshDashboard(), 120);
  });
}

init().catch((error) => {
  console.error(error);
  const detail = error && error.message ? `<br />${error.message}` : "";
  renderEmpty(
    "scatter-chart",
    `Dashboard data could not be loaded. Run \`python3 scripts/preprocess_steam_data.py\` first.${detail}`,
  );
});
