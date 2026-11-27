const mapChart = {
    width: 820,
    height: 500,
};

const mapLegend = {
    width: 220,
    height: 12,
};

const missingCountryFill = "#edf2f7";
const missingValueFill = "#d6dce7";
const brushedCountryStroke = "#c2410c";
const selectedCountryStroke = "#0f766e";

function canonicalCountryName(name) {
    return window.normalizeCountryName ? window.normalizeCountryName(name) : name;
}

function countryName(feature) {
    return canonicalCountryName(feature.properties.name);
}

function hasCountryData(name) {
    return window.appData.recordsByCountry.has(name);
}

const mapSvg = d3.select("#choropleth")
    .append("svg")
    .attr("viewBox", `0 0 ${mapChart.width} ${mapChart.height}`)
    .attr("class", "viz-svg");

const projection = d3.geoNaturalEarth1()
    .scale(165)
    .translate([mapChart.width / 2, mapChart.height / 2 + 10]);

const geoPath = d3.geoPath().projection(projection);
const mapLayer = mapSvg.append("g").attr("class", "map-layer");

const legendGradient = mapSvg
    .append("defs")
    .append("linearGradient")
    .attr("id", "choropleth-gradient")
    .attr("x1", "0%")
    .attr("x2", "100%")
    .attr("y1", "0%")
    .attr("y2", "0%");

const legendGroup = mapSvg.append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${mapChart.width - mapLegend.width - 34}, ${mapChart.height - 52})`);

legendGroup.append("text")
    .attr("class", "legend-title")
    .attr("y", -10);

legendGroup.append("rect")
    .attr("width", mapLegend.width)
    .attr("height", mapLegend.height)
    .attr("rx", mapLegend.height / 2)
    .attr("fill", "url(#choropleth-gradient)");

legendGroup.append("g")
    .attr("class", "legend-axis")
    .attr("transform", `translate(0, ${mapLegend.height})`);

const mapTooltip = d3.select("body")
    .append("div")
    .attr("class", "tooltip tooltip--map")
    .style("opacity", 0);

function initClearSelectionButton() {
    const mapHeader = d3.select(".chart-card--map .chart-header");

    if (mapHeader.empty()) {
        return;
    }

    const actions = mapHeader
        .append("div")
        .attr("class", "chart-actions");

    const hint = actions
        .append("span")
        .attr("class", "interaction-hint")
        .text("Click countries to pin them.");

    const button = actions
        .append("button")
        .attr("class", "control-button chart-action")
        .attr("type", "button")
        .text("Clear selection")
        .on("click", window.clearCountrySelection);

    window.appState.subscribe(state => {
        const hasSelection = state.selectedCountries.length > 0;

        hint
            .classed("is-active", hasSelection)
            .text(hasSelection
                ? `${state.selectedCountries.length} countries selected.`
                : "Click countries to pin them.");
        button.property("disabled", !state.selectedCountries.length);
    });
}

function getTooltipIndicators(state) {
    return [
        state.selectedIndicator,
        ...window.detailIndicators.filter(indicator => indicator !== state.selectedIndicator),
    ].slice(0, window.detailIndicators.length);
}

function tooltipRow(record, indicator) {
    return `
        <div class="tooltip-row">
            <span>${indicator}</span>
            <strong>${window.formatIndicatorValue(record[indicator])}</strong>
        </div>
    `;
}

function showMapTooltip(event, name, state) {
    const latestRecord = window.getCountryRecord(name, window.appData.latestYear);

    if (!latestRecord) {
        hideMapTooltip();
        return;
    }

    const rows = getTooltipIndicators(state)
        .map(indicator => tooltipRow(latestRecord, indicator))
        .join("");

    mapTooltip
        .style("opacity", 1)
        .html(`
            <strong>${name}</strong>
            <span>Latest data: ${window.appData.latestYear}</span>
            ${rows}
        `)
        .style("left", `${event.pageX + 14}px`)
        .style("top", `${event.pageY - 20}px`);
}

function hideMapTooltip() {
    mapTooltip.style("opacity", 0);
}

function updateLegend(colorScale, state) {
    const [domainStart, domainEnd] = colorScale.domain();
    const legendScale = d3.scaleLinear()
        .domain([domainStart, domainEnd])
        .range([0, mapLegend.width]);

    const stops = d3.range(0, 1.01, 0.1).map(step => ({
        offset: `${step * 100}%`,
        color: colorScale(domainStart + step * (domainEnd - domainStart)),
    }));

    legendGradient.selectAll("stop")
        .data(stops)
        .join("stop")
        .attr("offset", stop => stop.offset)
        .attr("stop-color", stop => stop.color);

    legendGroup.select(".legend-title")
        .text(`${state.selectedIndicator} (${state.selectedYear})`);

    legendGroup.select(".legend-axis")
        .call(
            d3.axisBottom(legendScale)
                .ticks(4)
                .tickFormat(window.formatIndicatorValue)
        );
}

function getCountryValue(name, state) {
    const record = window.getCountryRecord(name, state.selectedYear);
    return record ? record[state.selectedIndicator] : null;
}

function getCountryFill(feature, state, colorScale) {
    const name = countryName(feature);

    if (!hasCountryData(name)) {
        return missingCountryFill;
    }

    const value = getCountryValue(name, state);
    return Number.isFinite(value) ? colorScale(value) : missingValueFill;
}

function getCountryOpacity(feature, state, brushedCountries, selectedCountries) {
    const name = countryName(feature);

    if (!hasCountryData(name)) {
        return 0.72;
    }

    if (brushedCountries.size) {
        return brushedCountries.has(name) || selectedCountries.has(name) || state.hoveredCountry === name ? 1 : 0.2;
    }

    if (selectedCountries.size) {
        return selectedCountries.has(name) || state.hoveredCountry === name ? 1 : 0.24;
    }

    if (state.hoveredCountry) {
        return state.hoveredCountry === name ? 1 : 0.42;
    }

    return 1;
}

function isHighlightedCountry(name, state, brushedCountries, selectedCountries) {
    return state.hoveredCountry === name
        || brushedCountries.has(name)
        || selectedCountries.has(name);
}

function getCountryStroke(feature, state, brushedCountries, selectedCountries) {
    const name = countryName(feature);

    if (state.hoveredCountry === name) {
        return "#0f172a";
    }

    if (selectedCountries.has(name)) {
        return selectedCountryStroke;
    }

    if (brushedCountries.has(name)) {
        return brushedCountryStroke;
    }

    return "rgba(255, 255, 255, 0.92)";
}

function getCountryStrokeWidth(feature, state, brushedCountries, selectedCountries) {
    const name = countryName(feature);

    if (state.hoveredCountry === name) {
        return 2.4;
    }

    if (isHighlightedCountry(name, state, brushedCountries, selectedCountries)) {
        return 1.9;
    }

    return 0.7;
}

function hoverCountry(event, feature) {
    const name = countryName(feature);

    if (!hasCountryData(name)) {
        return;
    }

    window.appState.update({ hoveredCountry: name });
    showMapTooltip(event, name, window.appState.get());
}

function moveCountryTooltip(event, feature) {
    const name = countryName(feature);

    if (hasCountryData(name)) {
        showMapTooltip(event, name, window.appState.get());
    }
}

function leaveCountry(event, feature) {
    const name = countryName(feature);

    if (hasCountryData(name)) {
        window.appState.update({ hoveredCountry: null });
    }

    hideMapTooltip();
}

function clickCountry(event, feature) {
    const name = countryName(feature);

    if (hasCountryData(name)) {
        window.toggleCountrySelection(name);
    }
}

function updateMap(features, state) {
    const colorScale = window.getIndicatorColorScale(state.selectedIndicator, state.selectedYear);
    const brushedCountries = new Set(state.brushedCountries);
    const selectedCountries = new Set(state.selectedCountries);

    // Separate enter (static, set once) from update (dynamic, runs on every state change).
    // Keeping event handlers out of the update selection prevents them from being
    // re-bound on every slider tick, and stops new transitions from interrupting
    // in-progress ones when the slider moves quickly.
    const paths = mapLayer
        .selectAll("path.country-shape")
        .data(features, feature => feature.id)
        .join(
            enter => enter.append("path")
                .attr("class", "country-shape")
                .attr("d", geoPath)
                .on("mouseover", hoverCountry)
                .on("mousemove", moveCountryTooltip)
                .on("mouseout", leaveCountry)
                .on("click", clickCountry),
            update => update,
            exit => exit.remove()
        );

    paths
        .transition()
        .duration(150)
        .attr("fill", feature => getCountryFill(feature, state, colorScale))
        .attr("opacity", feature => getCountryOpacity(feature, state, brushedCountries, selectedCountries))
        .attr("stroke", feature => getCountryStroke(feature, state, brushedCountries, selectedCountries))
        .attr("stroke-width", feature => getCountryStrokeWidth(feature, state, brushedCountries, selectedCountries));

    updateLegend(colorScale, state);

    d3.select("#choropleth-subtitle").text(
        `${state.selectedIndicator} for ${state.selectedYear}. Hover for latest-year details.`
    );
}

d3.json("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json").then(world => {
    const features = topojson.feature(world, world.objects.countries).features;
    window.appState.subscribe(state => updateMap(features, state));
});

initClearSelectionButton();