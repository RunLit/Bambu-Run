// 3D Printer Charts Initialization and Management
// Chart.js implementation for printer metrics visualization

let nozzleTempChart, bedTempChart, printProgressChart, fanSpeedsChart;
let wifiSignalChart, amsConditionsChart, layerProgressChart, filamentTimelineChart;

function showNoDataMessage(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const container = canvas.closest('.chart-container');
    if (!container) return;
    canvas.style.display = 'none';
    const msg = document.createElement('div');
    msg.className = 'no-data-message d-flex align-items-center justify-content-center h-100 text-body-secondary';
    msg.textContent = 'No data available for this period';
    container.appendChild(msg);
}

function initPrinterCharts(printerData, apiUrl) {
    // Apply filament card colors
    applyFilamentColors();

    // If no data, show placeholder messages and exit early
    if (!printerData.timestamps || printerData.timestamps.length === 0) {
        ['nozzleTempChart', 'bedTempChart', 'printProgressChart', 'fanSpeedsChart',
         'wifiSignalChart', 'amsConditionsChart', 'layerProgressChart', 'filamentTimelineChart'
        ].forEach(showNoDataMessage);
        return;
    }

    // Register the annotation plugin
    if (typeof Chart !== 'undefined' && typeof ChartAnnotation !== 'undefined') {
        Chart.register(ChartAnnotation);
    }

    // Detect current theme
    const isDarkMode = document.documentElement.getAttribute('data-coreui-theme') === 'dark';

    // Set colors based on theme
    const tickColor = isDarkMode ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    // Initialize Nozzle Temperature Chart
    const nozzleCtx = document.getElementById('nozzleTempChart').getContext('2d');
    nozzleTempChart = new Chart(nozzleCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'Actual Temp',
                    data: printerData.nozzle_temp,
                    borderColor: 'rgb(255, 159, 64)',
                    backgroundColor: 'rgba(255, 159, 64, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                },
                {
                    label: 'Target Temp',
                    data: printerData.nozzle_target_temp,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.05)',
                    borderDash: [5, 5],
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                }
            ]
        },
        options: getTemperatureChartOptions(tickColor, gridColor, '°C')
    });

    // Initialize Bed Temperature Chart
    const bedCtx = document.getElementById('bedTempChart').getContext('2d');
    bedTempChart = new Chart(bedCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'Actual Temp',
                    data: printerData.bed_temp,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                },
                {
                    label: 'Target Temp',
                    data: printerData.bed_target_temp,
                    borderColor: 'rgb(255, 159, 64)',
                    backgroundColor: 'rgba(255, 159, 64, 0.05)',
                    borderDash: [5, 5],
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                }
            ]
        },
        options: getTemperatureChartOptions(tickColor, gridColor, '°C')
    });

    // Initialize Print Progress Chart
    const progressCtx = document.getElementById('printProgressChart').getContext('2d');
    printProgressChart = new Chart(progressCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'Print Progress',
                    data: printerData.print_percent,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    fill: true
                }
            ]
        },
        options: getPercentageChartOptions(tickColor, gridColor, 'Print Progress')
    });

    // Initialize Fan Speeds Chart
    const fanCtx = document.getElementById('fanSpeedsChart').getContext('2d');
    fanSpeedsChart = new Chart(fanCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'Cooling Fan',
                    data: printerData.cooling_fan_speed,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                },
                {
                    label: 'Heatbreak Fan',
                    data: printerData.heatbreak_fan_speed,
                    borderColor: 'rgb(153, 102, 255)',
                    backgroundColor: 'rgba(153, 102, 255, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                }
            ]
        },
        options: getPercentageChartOptions(tickColor, gridColor, 'Fan Speed')
    });

    // Initialize WiFi Signal Chart
    const wifiCtx = document.getElementById('wifiSignalChart').getContext('2d');
    wifiSignalChart = new Chart(wifiCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'WiFi Signal',
                    data: printerData.wifi_signal_dbm,
                    borderColor: 'rgb(255, 205, 86)',
                    backgroundColor: 'rgba(255, 205, 86, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                annotation: {
                    annotations: {}
                },
                legend: {
                    position: 'top',
                    labels: {
                        color: tickColor
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Signal: ' + context.parsed.y + ' dBm';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: tickColor },
                    grid: { color: gridColor }
                },
                y: {
                    reverse: false,  // -30 dBm (better) should be higher than -40 dBm (worse)
                    ticks: {
                        color: tickColor,
                        callback: function(value) {
                            return value + ' dBm';
                        }
                    },
                    grid: { color: gridColor }
                }
            }
        }
    });

    // Initialize AMS Conditions Chart
    const amsCtx = document.getElementById('amsConditionsChart').getContext('2d');
    amsConditionsChart = new Chart(amsCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'Humidity (Raw)',
                    data: printerData.ams_humidity_raw,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    yAxisID: 'y',
                    spanGaps: true
                },
                {
                    label: 'Temperature',
                    data: printerData.ams_temp,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    yAxisID: 'y1',
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                annotation: {
                    annotations: {}
                },
                legend: {
                    position: 'top',
                    labels: {
                        color: tickColor
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: tickColor },
                    grid: { color: gridColor }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Humidity',
                        color: tickColor
                    },
                    ticks: {
                        color: 'rgb(54, 162, 235)',
                        callback: function(value) {
                            return value;
                        }
                    },
                    grid: { color: gridColor }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Temperature (°C)',
                        color: tickColor
                    },
                    ticks: {
                        color: 'rgb(255, 99, 132)',
                        callback: function(value) {
                            return value + '°C';
                        }
                    },
                    grid: {
                        drawOnChartArea: false,
                    }
                }
            }
        }
    });

    // Initialize Layer Progress Chart
    const layerCtx = document.getElementById('layerProgressChart').getContext('2d');
    layerProgressChart = new Chart(layerCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: [
                {
                    label: 'Current Layer',
                    data: printerData.layer_num,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    fill: true
                },
                {
                    label: 'Total Layers',
                    data: printerData.total_layer_num,
                    borderColor: 'rgb(201, 203, 207)',
                    backgroundColor: 'rgba(201, 203, 207, 0.05)',
                    borderDash: [5, 5],
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                annotation: {
                    annotations: {}
                },
                legend: {
                    position: 'top',
                    labels: {
                        color: tickColor
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: tickColor },
                    grid: { color: gridColor }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: tickColor,
                        stepSize: 1
                    },
                    grid: { color: gridColor }
                }
            }
        }
    });

    // Initialize Filament Timeline Chart
    const filamentCtx = document.getElementById('filamentTimelineChart').getContext('2d');
    const filamentDatasets = createFilamentDatasets(printerData.filament_timeline, printerData.timestamps);
    filamentTimelineChart = new Chart(filamentCtx, {
        type: 'line',
        data: {
            labels: printerData.timestamps,
            datasets: filamentDatasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                annotation: {
                    annotations: {}
                },
                legend: {
                    position: 'top',
                    labels: {
                        color: tickColor,
                        boxWidth: 12,
                        padding: 8
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const datasetLabel = context.dataset.label || '';
                            const value = context.parsed.y;
                            return datasetLabel + ': ' + value + '% remaining';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: tickColor },
                    grid: { color: gridColor }
                },
                y: {
                    min: -10,  // Allow for negative filament readings (e.g., -4%)
                    max: 110,  // 10% higher than 100% to make 100% line more visible
                    ticks: {
                        color: tickColor,
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    grid: { color: gridColor }
                }
            }
        }
    });

    // Set up theme observer for dynamic theme switching
    setupThemeObserver();
}

function getTemperatureChartOptions(tickColor, gridColor, unit) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false
        },
        plugins: {
            annotation: {
                annotations: {}
            },
            legend: {
                position: 'top',
                labels: {
                    color: tickColor
                }
            },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += context.parsed.y.toFixed(1) + unit;
                        }
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                ticks: {
                    color: tickColor
                },
                grid: {
                    color: gridColor
                }
            },
            y: {
                beginAtZero: true,
                ticks: {
                    color: tickColor,
                    callback: function(value) {
                        return value + unit;
                    }
                },
                grid: {
                    color: gridColor
                }
            }
        }
    };
}

function getPercentageChartOptions(tickColor, gridColor, label) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false
        },
        plugins: {
            annotation: {
                annotations: {}
            },
            legend: {
                position: 'top',
                labels: {
                    color: tickColor
                }
            },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return label + ': ' + context.parsed.y + '%';
                    }
                }
            }
        },
        scales: {
            x: {
                ticks: {
                    color: tickColor
                },
                grid: {
                    color: gridColor
                }
            },
            y: {
                beginAtZero: true,
                max: 100,
                ticks: {
                    color: tickColor,
                    callback: function(value) {
                        return value + '%';
                    }
                },
                grid: {
                    color: gridColor
                }
            }
        }
    };
}

function createFilamentDatasets(filamentTimeline, timestamps) {
    const datasets = [];
    const filamentKeys = Object.keys(filamentTimeline);

    // Convert to array for sorting
    const filamentEntries = filamentKeys.map(key => ({
        key: key,
        data: filamentTimeline[key]
    }));

    // Sort by tray_id (numeric first, External last), then by start_idx (chronological)
    filamentEntries.sort((a, b) => {
        const trayA = a.data.tray_id;
        const trayB = b.data.tray_id;

        // Handle External vs numeric
        if (trayA === 'External' && trayB !== 'External') return 1;
        if (trayB === 'External' && trayA !== 'External') return -1;
        if (trayA === 'External' && trayB === 'External') {
            return a.data.start_idx - b.data.start_idx;
        }

        // Both numeric - sort by tray_id first, then by start_idx
        const trayNumA = parseInt(trayA);
        const trayNumB = parseInt(trayB);
        if (trayNumA !== trayNumB) {
            return trayNumA - trayNumB;
        }
        return a.data.start_idx - b.data.start_idx;
    });

    // Create datasets
    filamentEntries.forEach(entry => {
        const filament = entry.data;
        const color = '#' + filament.color.substring(0, 6);

        // Build descriptive label
        let displayLabel;
        if (filament.tray_id === 'External') {
            displayLabel = `External (${filament.type})`;
        } else {
            displayLabel = `Tray ${filament.tray_id} (${filament.type})`;
        }

        // Add brand if it's different from type (avoid redundancy)
        if (filament.brand && filament.brand !== filament.type && filament.brand !== 'External') {
            displayLabel += ` - ${filament.brand}`;
        }

        datasets.push({
            label: displayLabel,
            data: filament.remain_data,
            borderColor: color,
            backgroundColor: hexToRgba(color, 0.1),
            tension: 0.3,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            spanGaps: false  // Don't connect across null values (filament changes)
        });
    });

    return datasets;
}

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function applyFilamentColors() {
    // Apply colors to filament cards
    document.querySelectorAll('.filament-card').forEach(card => {
        const colorHex = card.getAttribute('data-filament-color');
        if (colorHex) {
            const color = '#' + colorHex;

            // Set card background with gradient
            card.style.background = `linear-gradient(135deg, ${hexToRgba(color, 0.12)} 0%, ${hexToRgba(color, 0.03)} 100%)`;
            card.style.borderLeft = `4px solid ${color}`;

            // Set badge color
            const badge = card.querySelector('.filament-badge');
            if (badge) {
                badge.style.backgroundColor = color;
                badge.style.color = getContrastColor(color);
            }

            // Set progress bar color
            const progressBar = card.querySelector('.filament-progress');
            if (progressBar) {
                progressBar.style.backgroundColor = color;
            }
        }
    });
}

function getContrastColor(hexColor) {
    // Convert hex to RGB
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);

    // Calculate luminance
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;

    // Return black or white based on luminance
    return luminance > 0.5 ? '#000000' : '#ffffff';
}

function updateChartTheme() {
    const isDarkMode = document.documentElement.getAttribute('data-coreui-theme') === 'dark';
    const tickColor = isDarkMode ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    // Update all charts
    const charts = [
        nozzleTempChart, bedTempChart, printProgressChart, fanSpeedsChart,
        wifiSignalChart, amsConditionsChart, layerProgressChart, filamentTimelineChart
    ];

    charts.forEach(chart => {
        if (chart) {
            // Update legend colors
            chart.options.plugins.legend.labels.color = tickColor;

            // Update x-axis colors
            chart.options.scales.x.ticks.color = tickColor;
            chart.options.scales.x.grid.color = gridColor;

            // Update y-axis colors
            if (chart.options.scales.y) {
                chart.options.scales.y.ticks.color = tickColor;
                chart.options.scales.y.grid.color = gridColor;
            }

            // Update y1-axis if exists (for dual-axis charts)
            if (chart.options.scales.y1) {
                if (chart.options.scales.y1.title) {
                    chart.options.scales.y1.title.color = tickColor;
                }
            }

            chart.update();
        }
    });
}

function setupThemeObserver() {
    // Watch for theme changes
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'data-coreui-theme') {
                updateChartTheme();
            }
        });
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-coreui-theme']
    });
}
