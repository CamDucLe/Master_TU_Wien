const scatterChart = {
    width: 520,
    height: 400,
    margin: { top: 24, right: 28, bottom: 64, left: 62 },
};

const scatterViewBoxWidth = scatterChart.width + scatterChart.margin.left + scatterChart.margin.right;
const scatterViewBoxHeight = scatterChart.height + scatterChart.margin.top + scatterChart.margin.bottom;

const scatterSvg = d3.select("#scatterplot")
    .append("svg")
    .attr("viewBox", `0 0 ${scatterViewBoxWidth} ${scatterViewBoxHeight}`)
    .attr("class", "viz-svg");

const scatterRoot = scatterSvg.append("g")
    .attr("transform", `translate(${scatterChart.margin.left}, ${scatterChart.margin.top})`);

const scatterX = d3.scaleLinear()
    .domain(d3.extent(window.appData.pcaData, point => point.x))
    .nice()
    .range([0, scatterChart.width]);

const scatterY = d3.scaleLinear()
    .domain(d3.extent(window.appData.pcaData, point => point.y))
    .nice()
    .range([scatterChart.height, 0]);

scatterRoot.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0, ${scatterChart.height})`)
    .call(d3.axisBottom(scatterX));

scatterRoot.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(scatterY));

scatterRoot.append("text")
    .attr("class", "axis-label")
    .attr("x", scatterChart.width / 2)
    .attr("y", scatterChart.height + 48)
    .attr("text-anchor", "middle")
    .text("Principal Component 1");

scatterRoot.append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -scatterChart.height / 2)
    .attr("y", -44)
    .attr("text-anchor", "middle")
    .text("Principal Component 2");

const scatterPointsLayer = scatterRoot.append("g").attr("class", "scatter-points");
const scatterLabelsLayer = scatterRoot.append("g").attr("class", "scatter-labels");
const scatterBrushLayer = scatterRoot.append("g").attr("class", "scatter-brush");
const scatterHighlightLayer = scatterRoot.append("g").attr("class", "scatter-highlights");

const brushedPointStroke = "#c2410c";
const selectedPointStroke = "#0f766e";
const pointerHoverRadius = 10;

const scatterTooltip = d3.select("body")
    .append("div")
    .attr("class", "tooltip")
    .style("opacity", 0);

function moveClearBrushButton() {
    const clearBrushButton = document.getElementById("clear-brush");
    const scatterHeader = document.querySelector(".chart-card--scatter .chart-header");

    if (!clearBrushButton || !scatterHeader) {
        return;
    }

    const actions = document.createElement("div");
    actions.className = "chart-actions";
    const hint = document.createElement("span");
    hint.className = "interaction-hint";
    hint.textContent = "Drag across dots to brush countries.";

    clearBrushButton.classList.add("chart-action");
    actions.appendChild(hint);
    actions.appendChild(clearBrushButton);
    scatterHeader.appendChild(actions);

    window.appState.subscribe(state => {
        const hasBrush = state.brushedCountries.length > 0;

        hint.textContent = hasBrush
            ? `${state.brushedCountries.length} countries brushed.`
            : "Drag across dots to brush countries.";
        hint.classList.toggle("is-active", hasBrush);
    });
}

function pointX(point) {
    return scatterX(point.x);
}

function pointY(point) {
    return scatterY(point.y);
}

function isInsideBrush(point, bounds) {
    const [[x0, y0], [x1, y1]] = bounds;
    const x = pointX(point);
    const y = pointY(point);

    return x0 <= x && x <= x1 && y0 <= y && y <= y1;
}

function getBrushedCountries(selection) {
    if (!selection) {
        return [];
    }

    return window.appData.pcaData
        .filter(point => isInsideBrush(point, selection))
        .map(point => point.name);
}

function handleBrush(event) {
    window.appState.update({
        brushedCountries: getBrushedCountries(event.selection),
    });
}

const scatterBrush = d3.brush()
    .extent([[0, 0], [scatterChart.width, scatterChart.height]])
    .on("brush end", handleBrush);

scatterBrushLayer.call(scatterBrush);

scatterBrushLayer
    .select(".overlay")
    .on("mousemove.hover-sync", syncHoverFromPointer)
    .on("mouseleave.hover-sync", clearScatterHover);

function clearScatterBrush() {
    scatterBrushLayer.call(scatterBrush.move, null);
}

scatterRoot.on("dblclick", clearScatterBrush);
window.clearScatterBrush = clearScatterBrush;

function getPointIndicatorValue(point, state) {
    const record = window.getCountryRecord(point.name, state.selectedYear);
    return record ? record[state.selectedIndicator] : null;
}

function showScatterTooltip(event, point, state) {
    const indicatorValue = getPointIndicatorValue(point, state);

    scatterTooltip
        .style("opacity", 1)
        .html(`
            <strong>${point.name}</strong>
            <span>${state.selectedIndicator}</span>
            <span>${state.selectedYear}: ${window.formatIndicatorValue(indicatorValue)}</span>
        `)
        .style("left", `${event.pageX + 14}px`)
        .style("top", `${event.pageY - 24}px`);
}

function hideScatterTooltip() {
    scatterTooltip.style("opacity", 0);
}

function hoverPoint(event, point) {
    window.appState.update({ hoveredCountry: point.name });
    showScatterTooltip(event, point, window.appState.get());
}

function clearScatterHover() {
    window.appState.update({ hoveredCountry: null });
    hideScatterTooltip();
}

function findHoveredPoint(event) {
    const [mouseX, mouseY] = d3.pointer(event, scatterRoot.node());
    let nearestPoint = null;
    let nearestDistanceSquared = pointerHoverRadius ** 2;

    window.appData.pcaData.forEach(point => {
        const dx = pointX(point) - mouseX;
        const dy = pointY(point) - mouseY;
        const distanceSquared = dx * dx + dy * dy;

        if (distanceSquared <= nearestDistanceSquared) {
            nearestPoint = point;
            nearestDistanceSquared = distanceSquared;
        }
    });

    return nearestPoint;
}

function syncHoverFromPointer(event) {
    if (event.buttons) {
        clearScatterHover();
        return;
    }

    const hoveredPoint = findHoveredPoint(event);

    if (!hoveredPoint) {
        clearScatterHover();
        return;
    }

    hoverPoint(event, hoveredPoint);
}

function getPointFill(point, state, colorScale) {
    const value = getPointIndicatorValue(point, state);
    return Number.isFinite(value) ? colorScale(value) : "#d6dce7";
}

function getPointOpacity(point, state, brushedCountries, selectedCountries) {
    if (brushedCountries.size) {
        return brushedCountries.has(point.name) || selectedCountries.has(point.name) || state.hoveredCountry === point.name ? 1 : 0.16;
    }

    if (state.hoveredCountry) {
        return state.hoveredCountry === point.name ? 1 : 0.32;
    }

    return 0.9;
}

function getPointRadius(point, state, brushedCountries, selectedCountries) {
    if (state.hoveredCountry === point.name) {
        return 10;
    }

    if (brushedCountries.has(point.name) || selectedCountries.has(point.name)) {
        return 7.5;
    }

    return 7;
}

function isActivePoint(point, state, brushedCountries, selectedCountries) {
    return state.hoveredCountry === point.name
        || brushedCountries.has(point.name)
        || selectedCountries.has(point.name);
}

function getPointStroke(point, state, brushedCountries, selectedCountries) {
    if (state.hoveredCountry === point.name) {
        return "#0f172a";
    }

    if (selectedCountries.has(point.name)) {
        return selectedPointStroke;
    }

    if (brushedCountries.has(point.name)) {
        return brushedPointStroke;
    }

    return "rgba(255, 255, 255, 0.9)";
}

function getPointStrokeWidth(point, state, brushedCountries, selectedCountries) {
    return isActivePoint(point, state, brushedCountries, selectedCountries) ? 2.2 : 1.2;
}

function getHighlightStroke(point, state, brushedCountries, selectedCountries) {
    if (state.hoveredCountry === point.name) {
        return "#0f172a";
    }

    if (selectedCountries.has(point.name)) {
        return selectedPointStroke;
    }

    return brushedPointStroke;
}

function getHighlightRadius(point, state, selectedCountries) {
    if (state.hoveredCountry === point.name) {
        return 10;
    }

    return selectedCountries.has(point.name) ? 10 : 9;
}

function getHighlightedPoints(state, brushedCountries, selectedCountries) {
    return window.appData.pcaData.filter(
        point => isActivePoint(point, state, brushedCountries, selectedCountries)
    );
}

function getLabeledPoints(state) {
    const countryNames = window.uniqueCountries([
        state.hoveredCountry,
        ...state.selectedCountries,
        ...state.brushedCountries.slice(0, 10),
    ]);

    return countryNames
        .map(country => window.appData.pcaByCountry.get(country))
        .filter(Boolean);
}

function updateHighlightRings(state, brushedCountries, selectedCountries) {
    scatterHighlightLayer
        .selectAll("circle.country-highlight")
        .data(getHighlightedPoints(state, brushedCountries, selectedCountries), point => point.name)
        .join(
            enter => enter.append("circle")
                .attr("class", "country-highlight")
                .attr("cx", pointX)
                .attr("cy", pointY)
                .attr("r", 0),
            update => update,
            exit => exit.transition().duration(150).attr("r", 0).remove()
        )
        .transition()
        .duration(220)
        .attr("cx", pointX)
        .attr("cy", pointY)
        .attr("r", point => getHighlightRadius(point, state, selectedCountries))
        .attr("fill", "none")
        .attr("stroke", point => getHighlightStroke(point, state, brushedCountries, selectedCountries))
        .attr("stroke-width", 2.8);
}

function updatePoints(state, colorScale, brushedCountries, selectedCountries) {
    scatterPointsLayer
        .selectAll("circle.country-dot")
        .data(window.appData.pcaData, point => point.name)
        .join(
            enter => enter.append("circle")
                .attr("class", "country-dot")
                .attr("cx", pointX)
                .attr("cy", pointY)
                .attr("r", 0)
                .on("mouseover", hoverPoint)
                .on("mousemove", (event, point) => showScatterTooltip(event, point, window.appState.get()))
                .on("mouseout", clearScatterHover)
                .on("click", (_, point) => window.toggleCountrySelection(point.name))
                .call(enter => enter.transition().duration(350).attr("r", 5)),
            update => update,
            exit => exit.transition().duration(200).attr("r", 0).remove()
        )
        .transition()
        .duration(250)
        .attr("fill", point => getPointFill(point, state, colorScale))
        .attr("opacity", point => getPointOpacity(point, state, brushedCountries, selectedCountries))
        .attr("r", point => getPointRadius(point, state, brushedCountries, selectedCountries))
        .attr("stroke", point => getPointStroke(point, state, brushedCountries, selectedCountries))
        .attr("stroke-width", point => getPointStrokeWidth(point, state, brushedCountries, selectedCountries));
}

function updateLabels(state) {
    scatterLabelsLayer
        .selectAll("text.country-label")
        .data(getLabeledPoints(state), point => point.name)
        .join(
            enter => enter.append("text")
                .attr("class", "country-label")
                .attr("x", point => pointX(point) + 8)
                .attr("y", point => pointY(point) - 10)
                .attr("opacity", 0)
                .text(point => point.name)
                .call(enter => enter.transition().duration(200).attr("opacity", 1)),
            update => update
                .attr("x", point => pointX(point) + 8)
                .attr("y", point => pointY(point) - 10)
                .text(point => point.name),
            exit => exit.transition().duration(150).attr("opacity", 0).remove()
        );
}

function updateScatterplot(state) {
    const colorScale = window.getIndicatorColorScale(state.selectedIndicator, state.selectedYear);
    const brushedCountries = new Set(state.brushedCountries);
    const selectedCountries = new Set(state.selectedCountries);

    updatePoints(state, colorScale, brushedCountries, selectedCountries);
    updateHighlightRings(state, brushedCountries, selectedCountries);
    updateLabels(state);

    d3.select("#scatterplot-subtitle").text(
        `${state.selectedIndicator} encoded by color for ${state.selectedYear}.`
    );
}

moveClearBrushButton();
window.appState.subscribe(updateScatterplot);
