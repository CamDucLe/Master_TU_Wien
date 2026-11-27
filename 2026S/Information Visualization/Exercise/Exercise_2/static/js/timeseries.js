const timeseriesChart = {
    width: 660,
    height: 390,
    margin: { top: 24, right: 92, bottom: 50, left: 74 },
};

const timeseriesViewBoxWidth = timeseriesChart.width + timeseriesChart.margin.left + timeseriesChart.margin.right;
const timeseriesViewBoxHeight = timeseriesChart.height + timeseriesChart.margin.top + timeseriesChart.margin.bottom;

const timeseriesSvg = d3.select("#timeseries")
    .append("svg")
    .attr("viewBox", `0 0 ${timeseriesViewBoxWidth} ${timeseriesViewBoxHeight}`)
    .attr("class", "viz-svg");

const timeseriesRoot = timeseriesSvg.append("g")
    .attr("transform", `translate(${timeseriesChart.margin.left}, ${timeseriesChart.margin.top})`);

const timeseriesX = d3.scaleLinear()
    .domain(d3.extent(window.appData.years))
    .range([0, timeseriesChart.width]);

const timeseriesY = d3.scaleLinear()
    .range([timeseriesChart.height, 0]);

timeseriesRoot.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0, ${timeseriesChart.height})`)
    .call(d3.axisBottom(timeseriesX).ticks(6).tickFormat(d3.format("d")));

const timeseriesYAxis = timeseriesRoot.append("g")
    .attr("class", "axis axis-y");

timeseriesRoot.append("text")
    .attr("class", "axis-label")
    .attr("x", timeseriesChart.width / 2)
    .attr("y", timeseriesChart.height + 42)
    .attr("text-anchor", "middle")
    .text("Year");

const timeseriesYLabel = timeseriesRoot.append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -timeseriesChart.height / 2)
    .attr("y", -56)
    .attr("text-anchor", "middle");

const lineLayer = timeseriesRoot.append("g").attr("class", "timeseries-lines");
const markerLayer = timeseriesRoot.append("g").attr("class", "timeseries-markers");
const labelLayer = timeseriesRoot.append("g").attr("class", "timeseries-labels");

const yearRule = timeseriesRoot.append("line")
    .attr("class", "year-rule")
    .attr("y1", 0)
    .attr("y2", timeseriesChart.height);

const emptyMessage = timeseriesRoot.append("text")
    .attr("class", "empty-state")
    .attr("x", timeseriesChart.width / 2)
    .attr("y", timeseriesChart.height / 2)
    .attr("text-anchor", "middle")
    .text("Select or brush countries to inspect temporal trends.");

const timeseriesTooltip = d3.select("body")
    .append("div")
    .attr("class", "tooltip")
    .style("opacity", 0);

const lineGenerator = d3.line()
    .defined(point => Number.isFinite(point.value))
    .x(point => timeseriesX(point.year))
    .y(point => timeseriesY(point.value));

function resolveTimeseriesCountries(state) {
    if (state.brushedCountries.length || state.selectedCountries.length) {
        return window.uniqueCountries([
            ...state.brushedCountries,
            ...state.selectedCountries,
        ]);
    }

    return state.hoveredCountry ? [state.hoveredCountry] : [];
}

function countrySeriesData(countryName, indicator) {
    return {
        name: countryName,
        values: window.getCountrySeries(countryName)
            .map(record => ({
                year: record.Year,
                value: record[indicator],
            }))
            .filter(point => Number.isFinite(point.value)),
    };
}

function buildSeriesData(countryNames, indicator) {
    return countryNames
        .map(countryName => countrySeriesData(countryName, indicator))
        .filter(series => series.values.length);
}

function getSeriesValues(seriesData) {
    return seriesData.flatMap(series => series.values.map(point => point.value));
}

function updateTimeseriesDomain(values) {
    if (!values.length) {
        timeseriesY.domain([0, 1]);
        return;
    }

    let minValue = d3.min(values);
    let maxValue = d3.max(values);

    if (minValue === maxValue) {
        minValue -= 1;
        maxValue += 1;
    }

    const padding = (maxValue - minValue) * 0.08;
    timeseriesY.domain([minValue - padding, maxValue + padding]).nice();
}

function showTimeseriesTooltip(event, datum, state) {
    timeseriesTooltip
        .style("opacity", 1)
        .html(`
            <strong>${datum.name}</strong>
            <span>${state.selectedIndicator}</span>
            <span>${datum.point.year}: ${window.formatIndicatorValue(datum.point.value)}</span>
        `)
        .style("left", `${event.pageX + 14}px`)
        .style("top", `${event.pageY - 24}px`);
}

function hideTimeseriesTooltip() {
    timeseriesTooltip.style("opacity", 0);
}

function describeTimeseriesSubtitle(state, visibleCountries) {
    if (!visibleCountries.length) {
        return "No active country selection yet.";
    }

    const yearRuleText = `The vertical rule marks ${state.selectedYear}.`;

    if (state.brushedCountries.length && state.selectedCountries.length) {
        return `${state.brushedCountries.length} brushed and ${state.selectedCountries.length} selected countries. ${yearRuleText}`;
    }

    if (state.selectedCountries.length) {
        return `${visibleCountries.length} selected countries over time. ${yearRuleText}`;
    }

    if (state.brushedCountries.length) {
        return `${visibleCountries.length} brushed countries. ${yearRuleText}`;
    }

    return `${state.hoveredCountry} preview. ${yearRuleText}`;
}

function updateTimeseriesAxis(state) {
    timeseriesYAxis
        .transition()
        .duration(300)
        .call(d3.axisLeft(timeseriesY).ticks(6).tickFormat(window.formatIndicatorValue));

    timeseriesYLabel.text(state.selectedIndicator);
}

function updateYearRule(state, hasSeries) {
    yearRule
        .attr("opacity", hasSeries ? 1 : 0)
        .transition()
        .duration(250)
        .attr("x1", timeseriesX(state.selectedYear))
        .attr("x2", timeseriesX(state.selectedYear));
}

function getLineOpacity(series, state) {
    if (state.brushedCountries.length) {
        return state.brushedCountries.includes(series.name)
            || state.selectedCountries.includes(series.name)
            || state.hoveredCountry === series.name ? 1 : 0.28;
    }

    if (state.hoveredCountry) {
        return state.hoveredCountry === series.name ? 1 : 0.45;
    }

    return 0.92;
}

function getLineWidth(series, state, selectedCountries) {
    return state.hoveredCountry === series.name || selectedCountries.has(series.name) ? 3.6 : 2.4;
}

function updateLines(seriesData, state, colorScale, selectedCountries) {
    lineLayer
        .selectAll("path.country-line")
        .data(seriesData, series => series.name)
        .join(
            enter => enter.append("path")
                .attr("class", "country-line")
                .attr("fill", "none")
                .attr("d", series => lineGenerator(series.values)),
            update => update,
            exit => exit.remove()
        )
        .transition()
        .duration(300)
        .attr("stroke", series => colorScale(series.name))
        .attr("stroke-width", series => getLineWidth(series, state, selectedCountries))
        .attr("opacity", series => getLineOpacity(series, state))
        .attr("d", series => lineGenerator(series.values));
}

function selectedYearMarkers(seriesData, selectedYear) {
    return seriesData
        .map(series => ({
            name: series.name,
            point: series.values.find(point => point.year === selectedYear),
        }))
        .filter(datum => datum.point);
}

function updateMarkers(seriesData, state, colorScale) {
    markerLayer
        .selectAll("circle.year-marker")
        .data(selectedYearMarkers(seriesData, state.selectedYear), datum => datum.name)
        .join(
            enter => enter.append("circle")
                .attr("class", "year-marker")
                .attr("r", 0)
                .on("mouseover", (event, datum) => {
                    window.appState.update({ hoveredCountry: datum.name });
                    showTimeseriesTooltip(event, datum, window.appState.get());
                })
                .on("mousemove", (event, datum) => showTimeseriesTooltip(event, datum, window.appState.get()))
                .on("mouseout", () => {
                    window.appState.update({ hoveredCountry: null });
                    hideTimeseriesTooltip();
                })
                .call(enter => enter.transition().duration(220).attr("r", 5.5)),
            update => update,
            exit => exit.transition().duration(180).attr("r", 0).remove()
        )
        .transition()
        .duration(300)
        .attr("cx", datum => timeseriesX(datum.point.year))
        .attr("cy", datum => timeseriesY(datum.point.value))
        .attr("fill", datum => colorScale(datum.name))
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1.8);
}

function updateLineLabels(seriesData, colorScale) {
    labelLayer
        .selectAll("text.line-label")
        .data(seriesData, series => series.name)
        .join(
            enter => enter.append("text")
                .attr("class", "line-label")
                .attr("dy", "0.35em")
                .text(series => series.name),
            update => update,
            exit => exit.remove()
        )
        .transition()
        .duration(300)
        .attr("x", series => timeseriesX(series.values[series.values.length - 1].year) + 8)
        .attr("y", series => timeseriesY(series.values[series.values.length - 1].value))
        .attr("fill", series => colorScale(series.name))
        .text(series => series.name);
}

function updateTimeseries(state) {
    const visibleCountries = resolveTimeseriesCountries(state);
    const selectedCountries = new Set(state.selectedCountries);
    const seriesData = buildSeriesData(visibleCountries, state.selectedIndicator);
    const allValues = getSeriesValues(seriesData);
    const hasSeries = allValues.length > 0;
    const colorScale = d3.scaleOrdinal(d3.schemeTableau10).domain(visibleCountries);

    updateTimeseriesDomain(allValues);
    updateTimeseriesAxis(state);
    updateYearRule(state, hasSeries);
    updateLines(seriesData, state, colorScale, selectedCountries);
    updateMarkers(seriesData, state, colorScale);
    updateLineLabels(seriesData, colorScale);

    emptyMessage.attr("opacity", hasSeries ? 0 : 1);
    d3.select("#timeseries-subtitle").text(describeTimeseriesSubtitle(state, visibleCountries));
}

window.appState.subscribe(updateTimeseries);
