// Filament Detail Chart — Usage History
// Depends on: chart.js, chartjs-plugin-annotation
// Config injected by template: FILAMENT_USAGE_API_URL

let usageChart = null;

// Register annotation plugin once it's available
if (typeof ChartAnnotation !== 'undefined') {
    Chart.register(ChartAnnotation);
}

// ── Time-select population ──────────────────────────────────────────────────

const startTimeSelect = document.getElementById('filamentStartTime');
const endTimeSelect   = document.getElementById('filamentEndTime');
if (startTimeSelect && endTimeSelect) {
    for (let h = 0; h < 24; h++) {
        for (let m = 0; m < 60; m += 30) {
            const t = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
            startTimeSelect.add(new Option(t, t));
            endTimeSelect.add(new Option(t, t));
        }
    }
    // End-time gets one extra option so the last minute of the day is reachable
    endTimeSelect.add(new Option('23:59', '23:59'));
    startTimeSelect.value = '00:00';
    endTimeSelect.value   = '23:59';
}

// ── Default date inputs (last 24 h) ────────────────────────────────────────

(function setDefaultDates() {
    const now       = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const sd = document.getElementById('filamentStartDate');
    const ed = document.getElementById('filamentEndDate');
    if (sd) sd.value = yesterday.toISOString().split('T')[0];
    if (ed) ed.value = now.toISOString().split('T')[0];
}());

// ── Full-day checkbox ───────────────────────────────────────────────────────

const fullDayCheckbox = document.getElementById('filamentFullDayCheckbox');
if (fullDayCheckbox) {
    fullDayCheckbox.addEventListener('change', function () {
        const isFullDay = this.checked;
        if (startTimeSelect) startTimeSelect.disabled = isFullDay;
        if (endTimeSelect)   endTimeSelect.disabled   = isFullDay;
    });
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Build date-separator annotations from "YYYY-MM-DD HH:MM" timestamp strings.
 * Places a vertical dotted line at each day boundary, label at the bottom.
 */
function buildFilamentDateSeparators(timestamps) {
    const annotations = {};
    if (!timestamps || timestamps.length < 2) return annotations;
    let count = 0;
    for (let i = 1; i < timestamps.length; i++) {
        const prevDate = timestamps[i - 1].split(' ')[0];
        const currDate = timestamps[i].split(' ')[0];
        if (currDate !== prevDate) {
            const d     = new Date(currDate + 'T00:00:00');
            const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            annotations['dateSep_' + count] = {
                type:       'line',
                scaleID:    'x',
                value:      i,
                borderColor: 'rgba(128, 128, 128, 0.45)',
                borderWidth: 1,
                borderDash:  [4, 4],
                drawTime:   'beforeDatasetsDraw',
                label: {
                    display:         true,
                    content:         label,
                    position:        'end',
                    backgroundColor: 'rgba(100, 100, 100, 0.65)',
                    color:           '#fff',
                    font:            { size: 9 },
                    padding:         { x: 4, y: 2 }
                }
            };
            count++;
        }
    }
    return annotations;
}

/**
 * Build x-axis tick options that adapt to the date span.
 *
 * autoSkip: true — Chart.js selects evenly-spaced tick positions.
 * maxTicksLimit  — caps how many ticks are drawn.
 * callback       — formats the label at each chosen tick position.
 *
 * ≤1 day  : up to 12 ticks, show "HH:MM"
 * 2–7 days: up to dayCount×4 ticks (≤28), show "Feb 22 06:00"
 * >7 days : up to min(dayCount, 20) ticks, show "Feb 22"
 */
function filamentXAxisTicks(isDarkMode, timestamps) {
    const tickColor = isDarkMode ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.8)';

    const dayCount = (timestamps && timestamps.length > 0)
        ? new Set(timestamps.map(t => t.split(' ')[0])).size
        : 1;

    let maxTicksLimit, formatCb;

    if (dayCount <= 1) {
        maxTicksLimit = 12;
        formatCb = function (val) {
            const label = this.getLabelForValue(val);
            return label ? label.slice(11, 16) : ''; // "HH:MM"
        };
    } else if (dayCount <= 7) {
        maxTicksLimit = Math.min(dayCount * 4, 28);
        formatCb = function (val) {
            const label = this.getLabelForValue(val);
            if (!label) return '';
            const datePart = label.split(' ')[0];
            const timePart = label.length >= 16 ? label.slice(11, 16) : '';
            const d = new Date(datePart + 'T00:00:00');
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + timePart;
        };
    } else {
        maxTicksLimit = Math.min(dayCount, 20);
        formatCb = function (val) {
            const label = this.getLabelForValue(val);
            if (!label) return '';
            const datePart = label.split(' ')[0];
            const d = new Date(datePart + 'T00:00:00');
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        };
    }

    return {
        color:         tickColor,
        autoSkip:      true,
        maxTicksLimit: maxTicksLimit,
        maxRotation:   45,
        minRotation:   0,
        callback:      formatCb
    };
}

// ── Chart fetch / render ────────────────────────────────────────────────────

/**
 * Fetch and render the usage chart.
 *
 * @param {boolean} sendDates  When false (initial load / reset), no date params
 *                             are sent so the backend can apply its default
 *                             "last 24h or fallback to last available" logic.
 *                             When true (explicit Refresh), the current input
 *                             values are sent as-is.
 */
async function fetchFilamentUsageData(sendDates = true) {
    const startDate = document.getElementById('filamentStartDate').value;
    const endDate   = document.getElementById('filamentEndDate').value;
    const isFullDay = fullDayCheckbox ? fullDayCheckbox.checked : true;
    const startTime = isFullDay ? '00:00' : (startTimeSelect ? startTimeSelect.value : '00:00');
    const endTime   = isFullDay ? '23:59' : (endTimeSelect   ? endTimeSelect.value   : '23:59');

    const params = new URLSearchParams();
    if (sendDates) {
        if (startDate) params.append('start_date', startDate);
        if (endDate)   params.append('end_date',   endDate);
        if (startTime) params.append('start_time', startTime);
        if (endTime)   params.append('end_time',   endTime);
    }

    try {
        const response = await fetch(FILAMENT_USAGE_API_URL + '?' + params.toString());
        const data     = await response.json();

        // If the backend used the fallback window, sync the date inputs so the
        // user can see and extend the range from that starting point.
        if (data.fallback_used && data.timestamps && data.timestamps.length > 0) {
            const firstDate = data.timestamps[0].split(' ')[0];
            const lastDate  = data.timestamps[data.timestamps.length - 1].split(' ')[0];
            const sd = document.getElementById('filamentStartDate');
            const ed = document.getElementById('filamentEndDate');
            if (sd) sd.value = firstDate;
            if (ed) ed.value = lastDate;
        }

        // Update date-range label
        const dateRangeSpan = document.getElementById('filamentDateRange');
        if (dateRangeSpan) {
            if (data.fallback_used) {
                dateRangeSpan.textContent = '(Last available data — 24h window)';
            } else if (startDate && endDate && sendDates) {
                dateRangeSpan.textContent = `(${startDate} to ${endDate})`;
            } else {
                dateRangeSpan.textContent = '(Last 24 Hours)';
            }
        }

        const isDarkMode  = document.documentElement.getAttribute('data-coreui-theme') === 'dark';
        const tickColor   = isDarkMode ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.8)';
        const gridColor   = isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
        const sepAnnotations = buildFilamentDateSeparators(data.timestamps);
        const xTicks      = filamentXAxisTicks(isDarkMode, data.timestamps);

        if (usageChart) {
            usageChart.data.labels                                  = data.timestamps;
            usageChart.data.datasets[0].data                       = data.remaining;
            usageChart.options.plugins.annotation.annotations      = sepAnnotations;
            usageChart.options.scales.x.ticks                      = xTicks;
            usageChart.update();
        } else {
            const ctx = document.getElementById('usageChart').getContext('2d');
            usageChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.timestamps,
                    datasets: [{
                        label:           'Remaining %',
                        data:            data.remaining,
                        borderColor:     'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension:         0.3,
                        fill:            true,
                        pointRadius:     0,
                        pointHoverRadius: 3,
                        borderWidth:     2
                    }]
                },
                options: {
                    responsive:          true,
                    maintainAspectRatio: false,
                    interaction:         { mode: 'index', intersect: false },
                    plugins: {
                        annotation: { annotations: sepAnnotations },
                        legend: {
                            position: 'top',
                            labels:   { color: tickColor }
                        },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    return 'Remaining: ' + ctx.parsed.y + '%';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: xTicks,
                            grid:  { color: gridColor }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                color:    tickColor,
                                callback: function (v) { return v + '%'; }
                            },
                            grid: { color: gridColor }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching filament usage data:', error);
    }
}

// ── Event listeners ─────────────────────────────────────────────────────────

const refreshBtn = document.getElementById('refreshFilamentChart');
const resetBtn   = document.getElementById('resetFilamentChart');

if (refreshBtn) {
    // Refresh: honour whatever the user has typed in the date inputs
    refreshBtn.addEventListener('click', function () { fetchFilamentUsageData(true); });
}

if (resetBtn) {
    resetBtn.addEventListener('click', function () {
        // Reset inputs to "last 24 hours" defaults, then let the backend
        // decide (fallback if no recent data).
        const now       = new Date();
        const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        const sd = document.getElementById('filamentStartDate');
        const ed = document.getElementById('filamentEndDate');
        if (sd) sd.value = yesterday.toISOString().split('T')[0];
        if (ed) ed.value = now.toISOString().split('T')[0];
        if (fullDayCheckbox) fullDayCheckbox.checked = true;
        if (startTimeSelect) startTimeSelect.disabled = true;
        if (endTimeSelect)   endTimeSelect.disabled   = true;
        fetchFilamentUsageData(false);
    });
}

// ── Initial load — no dates so backend fallback can fire ───────────────────

fetchFilamentUsageData(false);
