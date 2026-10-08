import './assets/style.css';
import $ from 'jquery';
import { fetchLeaderboardResults, getMe, renderRoleSwitcher } from './api';
import type { LeaderboardModel } from './api';
import { renderHeaderStatus } from './utils';

let languagesPopulated = false;
let chartModels: any[] = [];
let chartHumanScore: number | null = null;
let selectedChartYear: string | null = null;
let chartKeyByModel = new Map<any, string>();
let chartModelByKey = new Map<string, any>();

type ChartableModel = LeaderboardModel & { model_release: string };

function isChartableModel(model: LeaderboardModel): model is ChartableModel {
    const visibility = (model as LeaderboardModel & { visibility?: string }).visibility;
    if (!model.model_release || visibility !== 'highlight') return false;
    return !isNaN(new Date(model.model_release).getTime());
}

function isHumanReferenceModel(model: LeaderboardModel): boolean {
    return (model.model_name || '').trim().toLowerCase() === 'human ltb contributors';
}

async function loadLeaderboard() {
    $('#leaderboard-content').html('<div class="empty">Loading...</div>');
    $('#leaderboard-human-summary').html('<h3>Human benchmark</h3><div>Loading human reference...</div>');
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
        
        let models = (data.models || []).filter(model => !isHumanReferenceModel(model));
        models = models.filter((m: any) => {
            const isHuman = !m.model_type || m.model_type === '';
            if (filterSize && filterSize !== 'all' && !isHuman) {
                let sizeVal = Infinity;
                if (m.model_size === '<1B') sizeVal = 1;
                else if (m.model_size === '<10B') sizeVal = 10;
                else if (m.model_size === '<30B') sizeVal = 30;
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

        chartHumanScore = typeof data.human_score === 'number' && Number.isFinite(data.human_score)
            ? Math.max(0, Math.min(1, data.human_score))
            : null;
        chartModels = models;
        renderHumanSummary(models, chartHumanScore);

        if (models.length === 0) {
            $('#leaderboard-content').html('<div class="empty">No models match the selected filters.</div>');
            $('#leaderboard-chart-controls').prop('hidden', true).hide();
            $('#leaderboard-chart-container').hide();
            chartKeyByModel.clear();
            chartModelByKey.clear();
            renderChart(models, chartHumanScore);
            return;
        }

        chartKeyByModel = new Map();
        chartModelByKey = new Map();
        const chartableModels = models.filter(isChartableModel).slice().sort((left, right) => {
            const releaseOrder = new Date(left.model_release).getTime() - new Date(right.model_release).getTime();
            return releaseOrder || String(left.model_name || '').localeCompare(String(right.model_name || ''));
        });
        chartableModels.forEach((model, index) => {
            const key = String(index + 1).padStart(2, '0');
            chartKeyByModel.set(model, key);
            chartModelByKey.set(key, model);
        });

        let rows = '';
        for (const model of models) {
            const chartKey = chartKeyByModel.get(model);
            const keyCell = chartKey
                ? `<button type="button" class="leaderboard-chart-key" data-chart-key="${chartKey}" aria-label="Highlight ${escapeMarkup(model.model_name || 'Unknown model')} in chart">${chartKey}</button>`
                : '';
            const typeStr = model.model_type ? (model.model_type === 'open-source' ? 'Open Source' : (model.model_type === 'open-weight' ? 'Open Weight' : (model.model_type === 'closed' ? 'Closed' : model.model_type))) : '—';
            rows += `<tr class="${chartKey ? 'leaderboard-model-row' : ''}" data-chart-key="${chartKey || ''}">
                <td class="col-key">${keyCell}</td>
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
                        <th class="col-key">Key</th>
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
        renderChart(models, chartHumanScore);
    } catch (e) {
        console.error(e);
        $('#leaderboard-content').html(`<div class="empty">Failed to load leaderboard data: ${e}</div>`);
        $('#leaderboard-human-summary').html('<h3>Human benchmark</h3><div>Human comparison is unavailable right now.</div>');
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

function renderHumanSummary(models: LeaderboardModel[], humanScore: number | null): void {
    const summary = $('#leaderboard-human-summary');
    const rankedModels = models
        .map((model, index) => ({ model, index }))
        .filter(({ model }) => Number.isFinite(model.score))
        .sort((left, right) => right.model.score - left.model.score || left.index - right.index)
        .slice(0, 3);
    const bestModel = rankedModels[0]?.model;
    let gapHtml = '<div class="human-reference-gap">Best-model gap is unavailable for these filters.</div>';

    if (humanScore !== null && bestModel) {
        const difference = (humanScore - bestModel.score) * 100;
        const absoluteDifference = Math.abs(difference).toFixed(2);
        const gapText = difference > 0.005
            ? `Top model trails human performance by ${absoluteDifference} percentage points.`
            : difference < -0.005
                ? `Top model leads the human reference by ${absoluteDifference} percentage points.`
                : 'Top model and human performance are neck and neck.';
        gapHtml = `<div class="human-reference-gap">${escapeMarkup(gapText)}</div>`;
    }

    const podiumHtml = rankedModels.length > 0
        ? `<h4>Today\'s podium</h4><ol class="leaderboard-podium">${rankedModels.map(({ model }, index) => {
            const medal = ['🥇', '🥈', '🥉'][index];
            const name = escapeMarkup(model.model_name || 'Unknown model');
            const score = `${(model.score * 100).toFixed(2)}%`;
            return `<li><span class="podium-rank">${medal} ${index + 1}</span><span class="podium-score">${score}</span><br><strong>${name}</strong></li>`;
        }).join('')}</ol>`
        : '<h4>Podium</h4><div>No model entries for these filters yet.</div>';

    const humanScoreHtml = humanScore === null
        ? '<span class="human-reference-score">Unavailable</span><div>No verified human translations were returned for this filter.</div>'
        : `<span class="human-reference-score">${(humanScore * 100).toFixed(2)}%</span>`;

    summary.html(`
        <h3>Human benchmark</h3>
        <div class="human-reference-legend"><span class="human-reference-swatch" aria-hidden="true"></span>Verified human translations</div>
        ${humanScoreHtml}
        ${gapHtml}
        ${podiumHtml}
    `);
}

function renderChart(models: any[], humanScore: number | null) {
    const container = $('#leaderboard-chart-container');
    const controls = $('#leaderboard-chart-controls');
    const yearSelect = $('#leaderboard-year');
    const hint = $('#leaderboard-chart-hint');
    container.empty();
    hint.prop('hidden', true);
    
    // Filter models that have valid dates
    const datedModels = models.filter(isChartableModel);

    if (datedModels.length === 0) {
        controls.prop('hidden', true).hide();
        if (humanScore === null) {
            container.hide();
            return;
        }

        container.show();
        const viewportW = container.parent().width() || 800;
        const h = container.height() || 450;
        const padding = { top: 40, right: 40, bottom: 60, left: 80 };
        const mainW = viewportW - padding.left;
        const innerW = mainW - padding.right;
        const innerH = h - padding.top - padding.bottom;
        const humanY = padding.top + innerH - (humanScore * innerH);

        let axisSvg = `<svg width="${padding.left}" height="${h}" style="background: #ddd;" viewBox="0 0 ${padding.left} ${h}" aria-hidden="true">`;
        axisSvg += `<line x1="${padding.left - 1}" y1="${padding.top}" x2="${padding.left - 1}" y2="${padding.top + innerH}" stroke="black" stroke-width="2"/>`;
        axisSvg += `<text x="25" y="${padding.top + innerH / 2}" text-anchor="middle" font-size="14" font-weight="bold" fill="black" transform="rotate(-90 25 ${padding.top + innerH / 2})">Score</text>`;
        for (const tick of [0, 0.2, 0.4, 0.6, 0.8, 1.0]) {
            const tickY = padding.top + innerH - (tick * innerH);
            axisSvg += `<line x1="${padding.left - 6}" y1="${tickY}" x2="${padding.left - 1}" y2="${tickY}" stroke="black" stroke-width="1"/>`;
            axisSvg += `<text x="${padding.left - 10}" y="${tickY + 4}" text-anchor="end" font-size="12" fill="black">${Math.round(tick * 100)}%</text>`;
        }
        axisSvg += '</svg>';

        const svg = `<svg width="${mainW}" height="${h}" style="background: #ddd;" viewBox="0 0 ${mainW} ${h}" role="img" aria-label="Human benchmark score ${(humanScore * 100).toFixed(2)} percent; no models match these filters">
            <line x1="0" y1="${padding.top + innerH}" x2="${innerW}" y2="${padding.top + innerH}" stroke="black" stroke-width="2"/>
            <g class="human-reference" role="img" aria-label="Human benchmark score ${(humanScore * 100).toFixed(2)} percent"><line class="human-reference-line" x1="8" y1="${humanY}" x2="${innerW - 8}" y2="${humanY}"/><text class="human-reference-label" x="14" y="${Math.max(padding.top + 13, humanY - 7)}">HUMAN ${(humanScore * 100).toFixed(2)}%</text></g>
            <text x="${innerW / 2}" y="${padding.top + innerH / 2}" text-anchor="middle" font-size="14" fill="#64748b">No model results for these filters</text>
        </svg>`;

        container.html(`
            <div class="leaderboard-chart-axis" style="width: ${padding.left}px;">${axisSvg}</div>
            <div class="leaderboard-chart-scroll" style="margin-left: ${padding.left}px;">${svg}</div>
        `);
        hint.text('No model results for these filters. Human performance remains visible for reference.');
        hint.prop('hidden', false);
        return;
    }

    const years = Array.from(new Set(datedModels.map(m => new Date(m.model_release).getUTCFullYear())))
        .sort((a, b) => b - a);
    const availableSelections = new Set(['all', ...years.map(year => String(year))]);
    if (!selectedChartYear || !availableSelections.has(selectedChartYear)) {
        selectedChartYear = 'all';
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
    const latestRelease = new Date(Math.max(...validModels.map(m => new Date(m.model_release).getTime())));
    const actualMaxX = Date.UTC(latestRelease.getUTCFullYear(), latestRelease.getUTCMonth() + 1, 1);
    const dayMs = 24 * 60 * 60 * 1000;
    
    // Keep a little room before the first release; end at the next month boundary after the latest release.
    const minX = selectedYear === null ? actualMinX - (30 * dayMs) : actualMinX;
    const maxX = actualMaxX;
    const timelineMonths = selectedYear === null ? Math.max(1, Math.ceil((maxX - minX) / (30 * dayMs))) : 12;

    const modelsByMonth = new Map<string, any[]>();
    validModels.forEach(model => {
        const release = new Date(model.model_release);
        const monthKey = `${release.getUTCFullYear()}-${release.getUTCMonth()}`;
        const monthModels = modelsByMonth.get(monthKey) || [];
        monthModels.push(model);
        modelsByMonth.set(monthKey, monthModels);
    });
    const maxModelsPerMonth = Math.max(1, ...Array.from(modelsByMonth.values(), monthModels => monthModels.length));
    const xEdgePadding = 28;

    // Give dense timelines more pixels and let the native scrollbar provide navigation.
    const baseChartW = selectedYear === null ? Math.max(viewportW, Math.min(3200, 960 + timelineMonths * 100)) : viewportW;
    const minimumMonthWidth = maxModelsPerMonth > 1 ? 20 + ((maxModelsPerMonth - 1) * 22) : 0;
    const densityChartW = padding.left + padding.right + (xEdgePadding * 2) + (timelineMonths * minimumMonthWidth);
    const chartW = Math.max(baseChartW, Math.min(3200, densityChartW));
    const innerW = chartW - padding.left - padding.right;
    const mainW = innerW + padding.right;
    const innerH = h - padding.top - padding.bottom;

    hint.text(chartW > viewportW
        ? 'The latest releases are at the right edge. Scroll left to see older releases. Point keys match the model list below; hover or focus a point or key for details.'
        : 'Point keys match the model list below. Same-month releases are spread horizontally. Hover or focus a point or key for details.');
    hint.prop('hidden', false);

    const minY = 0;
    const maxY = 1;

    // Simple linear scale functions, preventing division by zero if all values are identical.
    const scaleX = (val: number) => {
        if (maxX === minX) return innerW / 2;
        return xEdgePadding + ((val - minX) / (maxX - minX)) * (innerW - xEdgePadding * 2);
    };
    
    const scaleY = (val: number) => {
        // SVG y-axis is inverted (0 at bottom).
        return padding.top + innerH - ((val - minY) / (maxY - minY)) * innerH;
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

    if (humanScore !== null) {
        const humanY = scaleY(humanScore);
        const humanLabelY = Math.max(padding.top + 13, humanY - 7);
        svg += `<g class="human-reference" role="img" aria-label="Human benchmark score ${(humanScore * 100).toFixed(2)} percent"><line class="human-reference-line" x1="${xEdgePadding}" y1="${humanY}" x2="${innerW - xEdgePadding}" y2="${humanY}"/><text class="human-reference-label" x="${xEdgePadding + 6}" y="${humanLabelY}">HUMAN ${(humanScore * 100).toFixed(2)}%</text></g>`;
    }

    const pointPositions = new Map<string, { cx: number; cy: number }>();
    modelsByMonth.forEach(monthModels => {
        const orderedModels = monthModels.slice().sort((left, right) => {
            const releaseOrder = new Date(left.model_release).getTime() - new Date(right.model_release).getTime();
            return releaseOrder || String(chartKeyByModel.get(left)).localeCompare(String(chartKeyByModel.get(right)));
        });
        const firstRelease = new Date(orderedModels[0].model_release);
        const year = firstRelease.getUTCFullYear();
        const month = firstRelease.getUTCMonth();
        const isNewestMonth = year === latestRelease.getUTCFullYear() && month === latestRelease.getUTCMonth();
        const monthStartX = scaleX(Date.UTC(year, month, 1));
        const nextMonthX = scaleX(Date.UTC(year, month + 1, 1));
        const left = Math.max(xEdgePadding + 8, monthStartX + 10);
        const right = Math.min(innerW - xEdgePadding - 8, nextMonthX - 10);

        orderedModels.forEach((model, index) => {
            const key = chartKeyByModel.get(model);
            if (!key) return;
            const cx = orderedModels.length === 1 && isNewestMonth
                ? innerW - xEdgePadding
                : orderedModels.length === 1 || right <= left
                    ? scaleX(new Date(model.model_release).getTime())
                    : left + ((right - left) * index / (orderedModels.length - 1));
            pointPositions.set(key, { cx, cy: scaleY(model.score) });
        });
    });

    let circleSvg = '';

    // Give each point a short key; the full name remains in the linked table.
    validModels.forEach(m => {
        const chartKey = chartKeyByModel.get(m);
        const position = chartKey ? pointPositions.get(chartKey) : undefined;
        if (!chartKey || !position) return;
        const { cx, cy } = position;
        let color = 'black';
        if (m.model_type === 'closed') {
            color = '#a33';
        } else if (m.model_type === 'open-weight') {
            color = '#9a5c00';
        } else if (m.model_type === 'open-source') {
            color = '#267b37';
        }
        const label = String(m.model_name || 'Unknown model');
        const score = `${(m.score * 100).toFixed(2)}%`;
        const release = String(m.model_release || 'Unknown release');
        circleSvg += `<g class="chart-point" data-chart-key="${chartKey}" tabindex="0" role="img" aria-label="${escapeMarkup(`${chartKey}: ${label}, ${score}, released ${release}`)}"><circle class="chart-point-marker" cx="${cx}" cy="${cy}" r="10" fill="${color}"/><text class="chart-point-label" x="${cx}" y="${cy}">${chartKey}</text><title>${escapeMarkup(label)}</title></g>`;
    });

    svg += circleSvg + `</svg>`;
    axisSvg += `</svg>`;
    container.html(`
        <div class="leaderboard-chart-axis" style="width: ${padding.left}px;">${axisSvg}</div>
        <div class="leaderboard-chart-scroll" style="margin-left: ${padding.left}px;">${svg}</div>
    `);
    const chartScroller = container.find('.leaderboard-chart-scroll').get(0);
    if (chartScroller) chartScroller.scrollLeft = chartScroller.scrollWidth;

    // Keep a linked highlight between the chart point and its full-name row.
    const tooltip = $('#leaderboard-tooltip');
    const chartPoints = container.find('.chart-point');
    const tableKeys = $('#leaderboard-content .leaderboard-chart-key');

    const clearLinkedModel = () => {
        chartPoints.removeClass('is-linked');
        $('#leaderboard-content [data-chart-key]').removeClass('is-linked');
        tooltip.hide();
    };

    const highlightLinkedModel = (key: string) => {
        chartPoints.filter(`[data-chart-key="${key}"]`).addClass('is-linked');
        $('#leaderboard-content [data-chart-key]').filter(`[data-chart-key="${key}"]`).addClass('is-linked');
    };

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

    chartPoints.off('.leaderboardChart')
        .on('mouseenter.leaderboardChart', function(e) {
            const key = String($(this).attr('data-chart-key') || '');
            const model = chartModelByKey.get(key);
            if (!model) return;
            highlightLinkedModel(key);
            showTooltip(model, e.clientX, e.clientY);
        }).on('mousemove.leaderboardChart', function(e) {
            tooltip.css({
                left: e.clientX + 'px',
                top: (e.clientY + 20) + 'px'
            });
        }).on('mouseleave.leaderboardChart blur.leaderboardChart', clearLinkedModel)
        .on('focus.leaderboardChart', function() {
            const key = String($(this).attr('data-chart-key') || '');
            const model = chartModelByKey.get(key);
            if (!model) return;
            const point = this.getBoundingClientRect();
            highlightLinkedModel(key);
            showTooltip(model, point.right, point.top);
        });

    tableKeys.off('.leaderboardChart')
        .on('mouseenter.leaderboardChart', function(e) {
            const key = String($(this).attr('data-chart-key') || '');
            const model = chartModelByKey.get(key);
            if (!model) return;
            highlightLinkedModel(key);
            showTooltip(model, e.clientX, e.clientY);
        }).on('focus.leaderboardChart', function() {
            const key = String($(this).attr('data-chart-key') || '');
            const model = chartModelByKey.get(key);
            if (!model) return;
            const button = this.getBoundingClientRect();
            highlightLinkedModel(key);
            showTooltip(model, button.right, button.top);
        }).on('mouseleave.leaderboardChart blur.leaderboardChart', clearLinkedModel)
        .on('click.leaderboardChart', function() {
            const key = String($(this).attr('data-chart-key') || '');
            const model = chartModelByKey.get(key);
            if (!model) return;
            const modelYear = String(new Date(model.model_release).getUTCFullYear());
            if (selectedChartYear !== 'all' && selectedChartYear !== modelYear) {
                selectedChartYear = modelYear;
                yearSelect.val(selectedChartYear);
                renderChart(chartModels, chartHumanScore);
            }
            const point = container.find(`.chart-point[data-chart-key="${key}"]`).get(0);
            if (point) {
                point.scrollIntoView({ block: 'nearest', inline: 'nearest' });
                point.focus();
            }
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
        renderChart(chartModels, chartHumanScore);
    });
    loadLeaderboard();
});
