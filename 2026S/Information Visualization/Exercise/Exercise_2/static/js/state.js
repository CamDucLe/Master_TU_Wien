const bootstrapElement = document.getElementById("app-bootstrap");
const bootstrapPayload = JSON.parse(bootstrapElement.textContent);

const DETAIL_INDICATOR_LIMIT = 8;
const COUNTRY_NAME_MAP = {
    Egypt: "Egypt, Arab Rep.",
    Iran: "Iran, Islamic Rep.",
    Russia: "Russian Federation",
    Syria: "Syrian Arab Republic",
    Czechia: "Czech Republic",
    "Türkiye": "Turkey",
};

function toNumber(value) {
    return Number(value);
}

function normalizeCountryName(name) {
    return COUNTRY_NAME_MAP[name] || name;
}

function uniqueCountries(countries) {
    return [...new Set((countries || []).filter(Boolean).map(normalizeCountryName))];
}

function normalizeRecord(record) {
    return {
        ...record,
        Country: normalizeCountryName(record.Country),
        Year: toNumber(record.Year),
    };
}

function normalizePcaPoint(point) {
    return {
        ...point,
        name: normalizeCountryName(point.name),
        x: toNumber(point.x),
        y: toNumber(point.y),
    };
}

function buildYearCountryIndex(recordsByYear) {
    return new Map(
        [...recordsByYear.entries()].map(([year, records]) => [
            year,
            new Map(records.map(record => [record.Country, record])),
        ])
    );
}

function createAppData(payload) {
    const records = payload.data.map(normalizeRecord);
    const pcaData = payload.pcaData.map(normalizePcaPoint);
    const indicators = payload.indicators.slice();
    const years = payload.years.map(toNumber).sort((a, b) => a - b);
    const latestYear = toNumber(payload.latestYear);

    const recordsByCountry = d3.group(records, record => record.Country);
    const recordsByYear = d3.group(records, record => record.Year);

    return {
        records,
        pcaData,
        indicators,
        years,
        latestYear,
        recordsByCountry,
        recordsByYear,
        recordsByYearCountry: buildYearCountryIndex(recordsByYear),
        pcaByCountry: new Map(pcaData.map(point => [point.name, point])),
    };
}

const APP_DATA = createAppData(bootstrapPayload);

function getYearRecords(year) {
    return APP_DATA.recordsByYear.get(toNumber(year)) || [];
}

function getCountryRecord(countryName, year) {
    return APP_DATA.recordsByYearCountry.get(toNumber(year))?.get(countryName) || null;
}

function getCountrySeries(countryName) {
    return APP_DATA.recordsByCountry.get(countryName) || [];
}

function createSequentialScale(values) {
    const cleanValues = values.filter(Number.isFinite);

    if (!cleanValues.length) {
        return d3.scaleSequential([0, 1], d3.interpolateYlGnBu);
    }

    let minValue = d3.min(cleanValues);
    let maxValue = d3.max(cleanValues);

    if (minValue === maxValue) {
        minValue -= 1;
        maxValue += 1;
    }

    return d3.scaleSequential([minValue, maxValue], d3.interpolateYlGnBu);
}

function getIndicatorColorScale(indicator, year) {
    const values = getYearRecords(year).map(record => record[indicator]);
    return createSequentialScale(values);
}

function formatIndicatorValue(value) {
    if (value == null || Number.isNaN(value)) {
        return "N/A";
    }

    const absoluteValue = Math.abs(value);

    if (absoluteValue >= 1_000_000_000) {
        return d3.format(".3s")(value);
    }

    if (absoluteValue >= 1000) {
        return d3.format(",.0f")(value);
    }

    if (absoluteValue >= 1) {
        return d3.format(",.2f")(value);
    }

    return d3.format(".3f")(value);
}

function areArraysEqual(first, second) {
    if (!Array.isArray(first) || !Array.isArray(second)) {
        return false;
    }

    return first.length === second.length
        && first.every((value, index) => value === second[index]);
}

function areStateValuesEqual(first, second) {
    if (Array.isArray(first) || Array.isArray(second)) {
        return areArraysEqual(first, second);
    }

    return first === second;
}

function hasStateChanged(currentState, nextState) {
    return Object.keys(nextState).some(
        key => !areStateValuesEqual(currentState[key], nextState[key])
    );
}

function normalizeStatePatch(currentState, patch) {
    return {
        ...currentState,
        ...patch,
        selectedYear: patch.selectedYear === undefined
            ? currentState.selectedYear
            : toNumber(patch.selectedYear),
        hoveredCountry: patch.hoveredCountry === undefined
            ? currentState.hoveredCountry
            : normalizeCountryName(patch.hoveredCountry),
        selectedCountries: patch.selectedCountries === undefined
            ? currentState.selectedCountries
            : uniqueCountries(patch.selectedCountries),
        brushedCountries: patch.brushedCountries === undefined
            ? currentState.brushedCountries
            : uniqueCountries(patch.brushedCountries),
    };
}

function createAppState() {
    let currentState = {
        selectedIndicator: APP_DATA.indicators[0],
        selectedYear: APP_DATA.latestYear,
        hoveredCountry: null,
        selectedCountries: [],
        brushedCountries: [],
    };

    const listeners = new Set();

    function notify() {
        listeners.forEach(listener => listener(currentState));
    }

    return {
        get() {
            return currentState;
        },
        subscribe(listener) {
            listeners.add(listener);
            listener(currentState);
            return () => listeners.delete(listener);
        },
        update(patch) {
            const nextState = normalizeStatePatch(currentState, patch);

            if (!hasStateChanged(currentState, nextState)) {
                return;
            }

            currentState = nextState;
            notify();
        },
    };
}

const appState = createAppState();
const detailIndicators = APP_DATA.indicators.slice(0, DETAIL_INDICATOR_LIMIT);

function describeSelection(state) {
    if (state.hoveredCountry) {
        return `Hovering ${state.hoveredCountry}`;
    }

    return "";
}

function toggleCountrySelection(countryName) {
    const selectedCountries = new Set(appState.get().selectedCountries);

    if (selectedCountries.has(countryName)) {
        selectedCountries.delete(countryName);
    } else {
        selectedCountries.add(countryName);
    }

    appState.update({ selectedCountries: [...selectedCountries] });
}

function clearCountrySelection() {
    appState.update({ selectedCountries: [] });
}

function tagChartCards() {
    [
        ["scatterplot", "chart-card--scatter"],
        ["timeseries", "chart-card--timeseries"],
        ["choropleth", "chart-card--map"],
    ].forEach(([hostId, className]) => {
        document.getElementById(hostId)?.closest(".chart-card")?.classList.add(className);
    });
}

function populateIndicatorOptions(indicatorSelect) {
    indicatorSelect
        .selectAll("option")
        .data(APP_DATA.indicators)
        .join("option")
        .attr("value", indicator => indicator)
        .text(indicator => indicator);
}

function configureYearSlider(yearSlider) {
    yearSlider
        .attr("min", APP_DATA.years[0])
        .attr("max", APP_DATA.years[APP_DATA.years.length - 1])
        .attr("step", 1);
}

function initControls() {
    const indicatorSelect = d3.select("#indicator-select");
    const yearSlider = d3.select("#year-slider");
    const yearValue = d3.select("#year-value");
    const selectionSummary = d3.select("#selection-summary");
    const selectionPanel = d3.select(".selection-panel");
    const clearBrushButton = d3.select("#clear-brush");

    populateIndicatorOptions(indicatorSelect);
    configureYearSlider(yearSlider);

    indicatorSelect.on("change", event => {
        appState.update({ selectedIndicator: event.currentTarget.value });
    });

    yearSlider.on("input", event => {
        appState.update({ selectedYear: event.currentTarget.value });
    });

    clearBrushButton.on("click", () => {
        if (typeof window.clearScatterBrush === "function") {
            window.clearScatterBrush();
        }
    });

    appState.subscribe(state => {
        const selectionText = describeSelection(state);

        indicatorSelect.property("value", state.selectedIndicator);
        yearSlider.property("value", state.selectedYear);
        yearValue.text(state.selectedYear);
        selectionSummary.text(selectionText);
        selectionPanel.classed("is-empty", !selectionText);
        clearBrushButton.property("disabled", !state.brushedCountries.length);
    });
}

window.appData = APP_DATA;
window.appState = appState;
window.detailIndicators = detailIndicators;
window.normalizeCountryName = normalizeCountryName;
window.uniqueCountries = uniqueCountries;
window.getYearRecords = getYearRecords;
window.getCountryRecord = getCountryRecord;
window.getCountrySeries = getCountrySeries;
window.getIndicatorColorScale = getIndicatorColorScale;
window.formatIndicatorValue = formatIndicatorValue;
window.toggleCountrySelection = toggleCountrySelection;
window.clearCountrySelection = clearCountrySelection;

tagChartCards();
initControls();
