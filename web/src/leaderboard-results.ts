import './assets/style.css';
import $ from 'jquery';
import { fetchLeaderboardResults, getMe, renderRoleSwitcher } from './api';
import { renderHeaderStatus } from './utils';

let languagesPopulated = false;
let chartModels: any[] = [];
let selectedChartYear: string | null = null;

async function loadLeaderboard() {
    $('#leaderboard-content').html('<div class="empty">Loading...</div>');
    $('#leaderboard-chart-container').hide();
    try {
        const filterMode = $('#filter-mode').val() as string;
        const filterTag = $('#filter-tag').val() as string;
        const filterLang = $('#filter-lang').val() as string;
        const filterSize = $('#filter-size').val() as string;
        const filterType = $('#filter-type').val() as string;
        
        let lang1 = '';
        let lang2 = '';
        if (filterLang && filterLang !== 'all') {
            if (filterLang.startsWith('from_')) {
                lang1 = filterLang.substring(5);
            } else if (filterLang.startsWith('into_')) {
                lang2 = filterLang.substring(5);
            }
        }

        const data = await fetchLeaderboardResults(filterMode, filterTag, lang1, lang2);
        
        if (!languagesPopulated && data.lang1s && data.lang2s) {
            const select = $('#filter-lang');
            for (const lang of data.lang1s) {
                select.append(`<option value="from_${lang}">From ${lang}</option>`);
            }
            for (const lang of data.lang2s) {
                select.append(`<option value="into_${lang}">Into ${lang}</option>`);
            }
            languagesPopulated = true;
        }
        
        let models = data.models || [];
        models = models.filter((m: any) => {
            const isHuman = !m.model_type || m.model_type === '';
            if (filterSize && filterSize !== 'all' && !isHuman) {
                let sizeVal = Infinity;
                if (m.model_size === '<1B') sizeVal = 1;
                else if (m.model_size === '<10B') sizeVal = 10;
                else if (m.model_size === '<100B') sizeVal = 100;
                else if (m.model_size === '<1T') sizeVal = 1000;
                else if (m.model_size === '<10T') sizeVal = 10000;
                else if (m.model_size === '<100T') sizeVal = 100000;
                // legacy values
                else if (m.model_size === '1B-3B') sizeVal = 3;
                else if (m.model_size === '3B-10B') sizeVal = 10;
                else if (m.model_size === '10B-30B') sizeVal = 30;
                else if (m.model_size === '30B-100B') sizeVal = 100;
                
                if (sizeVal > parseInt(filterSize)) return false;
            }
            if (filterType && filterType !== 'all' && m.model_type !== filterType && !isHuman) return false;
            return true;
        });

        if (models.length === 0) {
            $('#leaderboard-content').html('<div class="empty">No models match the selected filters.</div>');
            $('#leaderboard-chart-controls').prop('hidden', true).hide();
            $('#leaderboard-chart-container').hide();
            return;
        }

        let rows = '';
        for (const model of models) {
            const typeStr = model.model_type ? (model.model_type === 'open-source' ? 'Open Source' : (model.model_type === 'open-weight' ? 'Open Weight' : (model.model_type === 'closed' ? 'Closed' : model.model_type))) : '—';
            rows += `<tr>
                <td class="col-name">${model.model_name || '—'}</td>
                <td class="col-inst">${model.institution || '—'}</td>
                <td class="col-date">${model.model_release || '—'}</td>
                <td class="col-size">${model.model_size || '—'}</td>
                <td class="col-type">${typeStr}</td>
                <td class="col-desc" title="${(model.model_description || '').replace(/"/g, '&quot;')}">${model.model_description || '—'}</td>
                <td class="col-score">${(model.score * 100).toFixed(2)}%</td>
            </tr>`;
        }

        const tableHtml = `
            <table>
                <thead>
                    <tr>
                        <th class="col-name"></th>
                        <th class="col-inst"></th>
                        <th class="col-date"></th>
                        <th class="col-size"></th>
                        <th class="col-type"></th>
                        <th class="col-desc"></th>
                        <th class="col-score"></th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `;

        $('#leaderboard-content').html(tableHtml);
        chartModels = models;
        renderChart(models);
    } catch (e) {
        console.error(e);
        $('#leaderboard-content').html(`<div class="empty">Failed to load leaderboard data: ${e}</div>`);
    }
}

function escapeMarkup(value: unknown): string {
    const entities: Record<string, string> = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };
    return String(value ?? '').replace(/[&<>"']/g, character => entities[character]);
}

function renderChart(models: any[]) {
    const container = $('#leaderboard-chart-container');
    const controls = $('#leaderboard-chart-controls');
    const yearSelect = $('#leaderboard-year');
    const hint = $('#leaderboard-chart-hint');
    container.empty();
    hint.prop('hidden', true);
    
    // Filter models that have valid dates
    const datedModels = models.filter(m => {
        if (!m.model_release) return false;
        if (m.visibility !== 'highlight') return false;
        const ts = new Date(m.model_release).getTime();
        return !isNaN(ts);
    });

    if (datedModels.length === 0) {
        controls.prop('hidden', true).hide();
        container.hide();
        return;
    }

    const years = Array.from(new Set(datedModels.map(m => new Date(m.model_release).getUTCFullYear())))
        .sort((a, b) => b - a);
    const availableSelections = new Set(['all', ...years.map(year => String(year))]);
    if (!selectedChartYear || !availableSelections.has(selectedChartYear)) {
        selectedChartYear = String(years[0]);
    }
    const yearOptions = [
        '<option value="all">All years</option>',
        ...years.map(year => `<option value="${year}">${year}</option>`)
    ].join('');
    if (yearSelect.html() !== yearOptions) {
        yearSelect.html(yearOptions);
    }
    yearSelect.val(selectedChartYear);
    controls.prop('hidden', false).show();

    const selectedYear = selectedChartYear === 'all' ? null : Number(selectedChartYear);
    const validModels = selectedYear === null
        ? datedModels
        : datedModels.filter(m => new Date(m.model_release).getUTCFullYear() === selectedYear);
    
    container.show();

    const viewportW = container.width() || 800;
    const h = container.height() || 450;
    const padding = { top: 40, right: 40, bottom: 60, left: 80 };

    const actualMinX = selectedYear === null
        ? Math.min(...validModels.map(m => new Date(m.model_release).getTime()))
        : Date.UTC(selectedYear, 0, 1);
    const actualMaxX = selectedYear === null
        ? Math.max(...validModels.map(m => new Date(m.model_release).getTime()))
        : Date.UTC(selectedYear + 1, 0, 1);
    const dayMs = 24 * 60 * 60 * 1000;
    
    // Add a little breathing room around the first and last release.
    const minX = selectedYear === null ? actualMinX - (30 * dayMs) : actualMinX;
    const maxX = selectedYear === null ? actualMaxX + (60 * dayMs) : actualMaxX;
    const timelineMonths = selectedYear === null ? Math.max(1, Math.ceil((maxX - minX) / (30 * dayMs))) : 12;

    // Give dense timelines more pixels and let the native scrollbar provide navigation.
    const chartW = selectedYear === null ? Math.max(viewportW, Math.min(3200, 960 + timelineMonths * 100)) : viewportW;
    const innerW = chartW - padding.left - padding.right;
    const mainW = innerW + padding.right;
    const innerH = h - padding.top - padding.bottom;

    hint.text(chartW > viewportW
        ? 'Hover or focus a point to see model details. Scroll horizontally to inspect the full timeline.'
        : 'Hover or focus a point to see model details.');
    hint.prop('hidden', false);

    const minY = 0;
    const maxY = 1;
    const xEdgePadding = 28;

    // Simple linear scale functions, preventing division by zero if all values are identical.
    const scaleX = (val: number) => {
        if (maxX === minX) return innerW / 2;
        return xEdgePadding + ((val - minX) / (maxX - minX)) * (innerW - xEdgePadding * 2);
    };
    
    const scaleY = (val: number) => {
        // SVG y-axis is inverted (0 at top).
        return padding.top + innerH - ((val + 0.01 - minY) / (maxY - minY)) * innerH;
    };

    let axisSvg = `<svg width="${padding.left}" height="${h}" style="background: #ddd;" viewBox="0 0 ${padding.left} ${h}" aria-hidden="true">`;
    axisSvg += `<line x1="${padding.left - 1}" y1="${padding.top}" x2="${padding.left - 1}" y2="${padding.top + innerH}" stroke="black" stroke-width="2"/>`;
    axisSvg += `<text x="25" y="${padding.top + innerH / 2}" text-anchor="middle" font-size="14" font-weight="bold" fill="black" transform="rotate(-90 25 ${padding.top + innerH / 2})">Score</text>`;

    let svg = `<svg width="${mainW}" height="${h}" style="background: #ddd;" viewBox="0 0 ${mainW} ${h}" role="img" aria-label="Leaderboard scores by model release date">`;
    
    // Main plot axes. The y-axis is rendered separately so it stays fixed while this SVG scrolls.
    svg += `<line x1="0" y1="${padding.top + innerH}" x2="${innerW}" y2="${padding.top + innerH}" stroke="black" stroke-width="2"/>`;

    // Axis Labels
    svg += `<text x="${innerW / 2}" y="${h - 15}" text-anchor="middle" font-size="14" font-weight="bold" fill="black">Released</text>`;

    // Y-axis ticks
    const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];
    for (const tick of yTicks) {
        const ty = scaleY(tick);
        axisSvg += `<line x1="${padding.left - 6}" y1="${ty}" x2="${padding.left - 1}" y2="${ty}" stroke="black" stroke-width="1"/>`;
        axisSvg += `<text x="${padding.left - 10}" y="${ty + 4}" text-anchor="end" font-size="12" fill="black">${Math.round(tick * 100)}%</text>`;
    }

    // Use monthly or quarterly ticks so the wider chart exposes the time scale.
    const tickStepMonths = timelineMonths > 30 ? 3 : (timelineMonths > 18 ? 2 : 1);
    const firstTick = selectedYear === null ? new Date(minX) : new Date(Date.UTC(selectedYear, 0, 1));
    if (selectedYear === null) {
        firstTick.setUTCDate(1);
        firstTick.setUTCMonth(firstTick.getUTCMonth() + 1);
    }
    for (const tickDate = firstTick; tickDate.getTime() < maxX; tickDate.setUTCMonth(tickDate.getUTCMonth() + tickStepMonths)) {
        const tickTs = tickDate.getTime();
        const tx = scaleX(tickTs);
        const month = tickDate.toLocaleString('en', { month: 'short', timeZone: 'UTC' });
        const tickLabel = selectedYear === null && timelineMonths > 30 ? `${month} ${tickDate.getUTCFullYear()}` : `${month}`;
        svg += `<line x1="${tx}" y1="${padding.top + innerH}" x2="${tx}" y2="${padding.top + innerH + 5}" stroke="black" stroke-width="1"/>`;
        svg += `<text x="${tx}" y="${padding.top + innerH + 20}" text-anchor="middle" font-size="12" fill="black">${tickLabel}</text>`;
    }

    const pointPositions = validModels.map(m => ({
        cx: scaleX(new Date(m.model_release).getTime()),
        cy: scaleY(m.score)
    }));
    let circleSvg = '';

    // Keep the plot readable at a glance. Model names are available through the
    // focused point tooltip and the detailed table below the chart.
    validModels.forEach((m, i) => {
        const { cx, cy } = pointPositions[i];
        let color = 'black';
        if (m.model_type === 'closed') {
            color = '#a33';
        } else if (m.model_type === 'open-weight') {
            color = '#f90';
        } else if (m.model_type === 'open-source') {
            color = '#2a2';
        }
        const label = String(m.model_name || 'Unknown model');
        const score = `${(m.score * 100).toFixed(2)}%`;
        const release = String(m.model_release || 'Unknown release');
        circleSvg += `<circle class="chart-point" data-idx="${i}" cx="${cx}" cy="${cy}" r="6" fill="${color}" tabindex="0" role="img" aria-label="${escapeMarkup(`${label}, ${score}, released ${release}`)}" style="cursor: pointer;"><title>${escapeMarkup(label)}</title></circle>`;
    });

    svg += circleSvg + `</svg>`;
    axisSvg += `</svg>`;
    container.html(`
        <div class="leaderboard-chart-axis" style="width: ${padding.left}px;">${axisSvg}</div>
        <div class="leaderboard-chart-scroll" style="margin-left: ${padding.left}px;">${svg}</div>
    `);

    // Hover logic
    const tooltip = $('#leaderboard-tooltip');

    const showTooltip = (m: any, left: number, top: number) => {
        const desc = m.model_description || 'No description provided.';
        const size = m.model_size || 'Unknown size';
        const typeStr = m.model_type ? (m.model_type === 'open-source' ? 'Open Source' : (m.model_type === 'open-weight' ? 'Open Weight' : (m.model_type === 'closed' ? 'Closed' : m.model_type))) : 'Unknown type';
        const date = m.model_release || 'Unknown date';
        
        tooltip.html(`
            <strong>${escapeMarkup(m.model_name)}</strong><br>
            <div style="margin-top: 5px; margin-bottom: 5px;">${escapeMarkup(desc)}</div>
            <hr style="margin: 5px 0; border-color: #444;">
            Size: ${escapeMarkup(size)}<br>
            Type: ${escapeMarkup(typeStr)}<br>
            Released: ${escapeMarkup(date)}<br>
            Score: ${(m.score * 100).toFixed(2)}%
        `);
        tooltip.show();
        tooltip.css({
            left: `${left}px`,
            top: `${top + 20}px`
        });
    };

    container.find('.chart-point').on('mouseenter', function(e) {
        const idx = parseInt($(this).attr('data-idx') || '0');
        showTooltip(validModels[idx], e.clientX, e.clientY);
    }).on('mousemove', function(e) {
        tooltip.css({
            left: e.clientX + 'px',
            top: (e.clientY + 20) + 'px'
        });
    }).on('mouseleave blur', function() {
        tooltip.hide();
    }).on('focus', function() {
        const point = this.getBoundingClientRect();
        const idx = parseInt($(this).attr('data-idx') || '0');
        showTooltip(validModels[idx], point.right, point.top);
    });
}

$(async () => {
    try {
        const user = await getMe();
        if (user) {
            renderHeaderStatus(user);
            renderRoleSwitcher(user.roles);
        }
    } catch (e) {
        // Not logged in, ignore
    }

    $('#filter-mode, #filter-tag, #filter-lang, #filter-size, #filter-type').on('change', loadLeaderboard);
    $('#leaderboard-year').on('change', function() {
        selectedChartYear = $(this).val() as string;
        renderChart(chartModels);
    });
    loadLeaderboard();
});
