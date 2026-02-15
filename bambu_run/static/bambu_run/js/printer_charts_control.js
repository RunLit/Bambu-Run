// 3D Printer Charts Control - Date/Time Filtering and Project Markers
// Handles date range picker, time selection, and chart updates with annotations

// Global state
const printerChartControls = {
    isFullDay: true,
    isCustomRange: false,
    apiUrl: null
};

/**
 * Initialize on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    const apiUrlElement = document.getElementById('printerApiUrl');
    if (apiUrlElement) {
        printerChartControls.apiUrl = apiUrlElement.dataset.url;
        initializePrinterControls();
    }
});

/**
 * Initialize printer chart date/time controls
 */
function initializePrinterControls() {
    const startDateInput = document.getElementById('printerStartDate');
    const endDateInput = document.getElementById('printerEndDate');
    const startTimeSelect = document.getElementById('printerStartTime');
    const endTimeSelect = document.getElementById('printerEndTime');
    const fullDayCheckbox = document.getElementById('printerFullDayCheckbox');
    const refreshBtn = document.getElementById('refreshPrinterCharts');
    const resetBtn = document.getElementById('resetPrinterCharts');

    // Set max date to today
    const today = formatDate(new Date());
    startDateInput.max = today;
    endDateInput.max = today;

    // Populate time dropdowns with 30-minute intervals
    populateTimeDropdowns(startTimeSelect, endTimeSelect);

    // Set default values
    setDefaultPrinterDateTimeValues();

    // Date input change handling
    startDateInput.addEventListener('change', handlePrinterDateChange);
    endDateInput.addEventListener('change', handlePrinterDateChange);

    // Full Day checkbox toggle
    fullDayCheckbox.addEventListener('change', function() {
        printerChartControls.isFullDay = this.checked;
        togglePrinterTimeControls(!this.checked);
        updatePrinterDateRangeLabel();
    });

    // Refresh button
    refreshBtn.addEventListener('click', function() {
        refreshPrinterChartsData();
    });

    // Reset button
    resetBtn.addEventListener('click', function() {
        resetPrinterControls();
    });
}

/**
 * Populate time dropdowns with 30-minute intervals
 */
function populateTimeDropdowns(startSelect, endSelect) {
    const times = [];
    for (let hour = 0; hour < 24; hour++) {
        for (let minute = 0; minute < 60; minute += 30) {
            const timeStr = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
            times.push(timeStr);
        }
    }

    times.forEach(time => {
        const option1 = new Option(time, time);
        const option2 = new Option(time, time);
        startSelect.add(option1);
        endSelect.add(option2);
    });
}

/**
 * Toggle time picker controls
 */
function togglePrinterTimeControls(enabled) {
    document.getElementById('printerStartTime').disabled = !enabled;
    document.getElementById('printerEndTime').disabled = !enabled;
}

/**
 * Set default date/time values (last 24 hours)
 */
function setDefaultPrinterDateTimeValues() {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);

    document.getElementById('printerStartDate').value = formatDate(yesterday);
    document.getElementById('printerEndDate').value = formatDate(now);
    document.getElementById('printerStartTime').value = '00:00';
    document.getElementById('printerEndTime').value = '23:59';

    const fullDayCheckbox = document.getElementById('printerFullDayCheckbox');
    fullDayCheckbox.checked = true;
    printerChartControls.isFullDay = true;
    togglePrinterTimeControls(false);

    document.getElementById('printerDateRange').textContent = '(Last 24 Hours)';
}

/**
 * Handle date input changes
 */
function handlePrinterDateChange() {
    const startDate = document.getElementById('printerStartDate').value;
    const endDate = document.getElementById('printerEndDate').value;

    // Ensure end date is not before start date
    if (startDate && endDate && startDate > endDate) {
        document.getElementById('printerEndDate').value = startDate;
    }

    printerChartControls.isCustomRange = true;
    updatePrinterDateRangeLabel();
}

/**
 * Update the date range label
 */
function updatePrinterDateRangeLabel() {
    const startDate = document.getElementById('printerStartDate').value;
    const endDate = document.getElementById('printerEndDate').value;

    let label = '';
    if (startDate === endDate) {
        label = '(' + startDate + ')';
    } else {
        label = '(' + startDate + ' to ' + endDate + ')';
    }
    document.getElementById('printerDateRange').textContent = label;
}

/**
 * Refresh printer charts data from API
 */
async function refreshPrinterChartsData() {
    const startDate = document.getElementById('printerStartDate').value;
    const endDate = document.getElementById('printerEndDate').value;
    const isFullDay = printerChartControls.isFullDay;

    const startTime = isFullDay ? '00:00' : document.getElementById('printerStartTime').value;
    const endTime = isFullDay ? '23:59' : document.getElementById('printerEndTime').value;

    // Show loading state (you can add a spinner here if needed)
    console.log('Refreshing printer charts...');

    try {
        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate,
            start_time: startTime,
            end_time: endTime
        });

        const response = await fetch(printerChartControls.apiUrl + '?' + params.toString());

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // Update all charts with new data and project markers
        updateAllPrinterCharts(data);
        updatePrinterDateRangeLabel();

    } catch (error) {
        console.error('Error refreshing printer charts:', error);
        alert('Error loading chart data: ' + error.message);
    }
}

/**
 * Update all printer charts with new data
 */
function updateAllPrinterCharts(data) {
    // Update chart data
    updateChartData(nozzleTempChart, data.timestamps, [
        { data: data.nozzle_temp, datasetIndex: 0 },
        { data: data.nozzle_target_temp, datasetIndex: 1 }
    ]);

    updateChartData(bedTempChart, data.timestamps, [
        { data: data.bed_temp, datasetIndex: 0 },
        { data: data.bed_target_temp, datasetIndex: 1 }
    ]);

    updateChartData(printProgressChart, data.timestamps, [
        { data: data.print_percent, datasetIndex: 0 }
    ]);

    updateChartData(fanSpeedsChart, data.timestamps, [
        { data: data.cooling_fan_speed, datasetIndex: 0 },
        { data: data.heatbreak_fan_speed, datasetIndex: 1 }
    ]);

    updateChartData(wifiSignalChart, data.timestamps, [
        { data: data.wifi_signal_dbm, datasetIndex: 0 }
    ]);

    updateChartData(amsConditionsChart, data.timestamps, [
        { data: data.ams_humidity_raw, datasetIndex: 0 },
        { data: data.ams_temp, datasetIndex: 1 }
    ]);

    updateChartData(layerProgressChart, data.timestamps, [
        { data: data.layer_num, datasetIndex: 0 },
        { data: data.total_layer_num, datasetIndex: 1 }
    ]);

    // Update filament timeline chart
    if (data.filament_timeline) {
        const filamentDatasets = createFilamentDatasets(data.filament_timeline, data.timestamps);
        filamentTimelineChart.data.labels = data.timestamps;
        filamentTimelineChart.data.datasets = filamentDatasets;
        filamentTimelineChart.update();
    }

    // Add project markers to all charts
    if (data.project_markers) {
        addProjectMarkersToCharts(data.project_markers, data.timestamps);
    }
}

/**
 * Helper to update chart data
 */
function updateChartData(chart, labels, datasets) {
    if (!chart) return;

    chart.data.labels = labels;
    datasets.forEach(({ data, datasetIndex }) => {
        if (chart.data.datasets[datasetIndex]) {
            chart.data.datasets[datasetIndex].data = data;
        }
    });
    chart.update();
}

/**
 * Add project markers (start/end lines) to all charts
 */
function addProjectMarkersToCharts(markers, timestamps) {
    console.log('Adding project markers:', markers);

    const charts = [
        nozzleTempChart, bedTempChart, printProgressChart, fanSpeedsChart,
        wifiSignalChart, amsConditionsChart, layerProgressChart, filamentTimelineChart
    ];

    charts.forEach(chart => {
        if (!chart) return;

        // Initialize annotations plugin if not already
        if (!chart.options.plugins.annotation) {
            chart.options.plugins.annotation = { annotations: {} };
        }

        // Clear existing project markers
        chart.options.plugins.annotation.annotations = {};

        // Track active tooltip
        let activeMarkerTooltip = null;

        // Add markers
        markers.forEach((marker, idx) => {
            const isStart = marker.type === 'start';
            const xValue = marker.index; // Use the index directly, not the timestamp string

            const projectName = marker.project_name || 'Unknown';
            const markerId = `marker_${idx}`;

            chart.options.plugins.annotation.annotations[markerId] = {
                type: 'line',
                scaleID: 'x',
                value: xValue,
                borderColor: isStart ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)',
                borderWidth: 2,
                borderDash: [5, 5],
                drawTime: 'beforeDatasetsDraw',
                // Tighter hit detection - only trigger when very close to the line
                borderDashOffset: 0,
                display: true,
                enter: (ctx, event) => {
                    // Verify we're actually hovering over THIS specific annotation line
                    // Check if mouse X position is close to the line's X position
                    if (event && event.native) {
                        const chartArea = chart.chartArea;
                        const xScale = chart.scales.x;
                        const lineXPixel = xScale.getPixelForValue(xValue);
                        const mouseX = event.native.offsetX;

                        // Only show tooltip if mouse is within 10 pixels of the line
                        const distance = Math.abs(mouseX - lineXPixel);
                        if (distance > 10) {
                            return; // Too far from this line, don't show tooltip
                        }
                    }

                    // Only show tooltip if not already showing from another marker
                    if (activeMarkerTooltip && activeMarkerTooltip !== markerId) {
                        return;
                    }

                    activeMarkerTooltip = markerId;

                    const tooltipText = isStart
                        ? `Print Start: ${projectName}`
                        : `Print End: ${projectName}`;

                    // Change line appearance on hover
                    ctx.element.options.borderWidth = 3;
                    ctx.element.options.borderColor = isStart ? 'rgba(34, 197, 94, 1)' : 'rgba(239, 68, 68, 1)';
                    chart.update('none');

                    // Create or update tooltip element
                    let tooltip = document.getElementById('annotation-tooltip');
                    if (!tooltip) {
                        tooltip = document.createElement('div');
                        tooltip.id = 'annotation-tooltip';
                        tooltip.style.position = 'fixed';
                        tooltip.style.backgroundColor = 'rgba(0, 0, 0, 0.85)';
                        tooltip.style.color = 'white';
                        tooltip.style.padding = '6px 10px';
                        tooltip.style.borderRadius = '4px';
                        tooltip.style.fontSize = '13px';
                        tooltip.style.pointerEvents = 'none';
                        tooltip.style.zIndex = '9999';
                        tooltip.style.display = 'none';
                        tooltip.style.whiteSpace = 'nowrap';
                        document.body.appendChild(tooltip);
                    }
                    tooltip.textContent = tooltipText;
                    tooltip.style.display = 'block';
                    tooltip.dataset.markerId = markerId;

                    // Position at mouse location
                    if (event && event.native) {
                        tooltip.style.left = (event.native.clientX + 12) + 'px';
                        tooltip.style.top = (event.native.clientY - 10) + 'px';
                    }
                },
                leave: (ctx) => {
                    // Only hide if this is the active marker
                    if (activeMarkerTooltip === markerId) {
                        activeMarkerTooltip = null;

                        // Restore line appearance
                        ctx.element.options.borderWidth = 2;
                        ctx.element.options.borderColor = isStart ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)';
                        chart.update('none');

                        const tooltip = document.getElementById('annotation-tooltip');
                        if (tooltip && tooltip.dataset.markerId === markerId) {
                            tooltip.style.display = 'none';
                            tooltip.dataset.markerId = '';
                        }
                    }
                }
            };
        });

        chart.update();
    });
}

/**
 * Reset printer controls to default
 */
function resetPrinterControls() {
    setDefaultPrinterDateTimeValues();

    // Clear annotations and reload with original data
    const charts = [
        nozzleTempChart, bedTempChart, printProgressChart, fanSpeedsChart,
        wifiSignalChart, amsConditionsChart, layerProgressChart, filamentTimelineChart
    ];

    charts.forEach(chart => {
        if (chart && chart.options.plugins.annotation) {
            chart.options.plugins.annotation.annotations = {};
            chart.update();
        }
    });

    // Reload page to get default data
    location.reload();
}

/**
 * Format date as YYYY-MM-DD
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

