import './assets/style.css';
import $ from 'jquery';
import { fetchLeaderboardResults, getMe, renderRoleSwitcher } from './api';
import { renderHeaderStatus } from './utils';

let languagesPopulated = false;

async function loadLeaderboard() {
    $('#leaderboard-content').html('<div class="empty">Loading...</div>');
    $('#leaderboard-chart-container').hide();
    try {
        const filterMode = $('#filter-mode').val() as string;
        const filterTag = $('#filter-tag').val() as string;
        const filterLang = $('#filter-lang').val() as string;
        
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
        
        const models = data.models || [];
        if (models.length === 0) {
            $('#leaderboard-content').html('<div class="empty">No models match the selected filters.</div>');
            $('#leaderboard-chart-container').hide();
            return;
        }

        let rows = '';
        for (const model of models) {
            const typeStr = model.model_type ? (model.model_type === 'open' ? 'Open' : (model.model_type === 'closed' ? 'Closed' : model.model_type)) : '—';
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
        renderChart(models);
    } catch (e) {
        console.error(e);
        $('#leaderboard-content').html(`<div class="empty">Failed to load leaderboard data: ${e}</div>`);
    }
}

function renderChart(models: any[]) {
    const container = $('#leaderboard-chart-container');
    container.empty();
    
    // Filter models that have valid dates
    const validModels = models.filter(m => {
        if (!m.model_release) return false;
        const ts = new Date(m.model_release).getTime();
        return !isNaN(ts);
    });

    if (validModels.length === 0) {
        container.hide();
        return;
    }
    
    container.show();

    const w = container.width() || 800;
    const h = container.height() || 500;
    const padding = { top: 40, right: 40, bottom: 60, left: 80 };

    const innerW = w - padding.left - padding.right;
    const innerH = h - padding.top - padding.bottom;

    const actualMinX = Math.min(...validModels.map(m => new Date(m.model_release).getTime()));
    const actualMaxX = Math.max(...validModels.map(m => new Date(m.model_release).getTime()));
    
    // Add 1 month gap on the left
    const minX = actualMinX - (30 * 24 * 60 * 60 * 1000);
    // Add 2 months gap on the right
    const maxX = actualMaxX + (60 * 24 * 60 * 60 * 1000);
    
    const minY = 0;
    const maxY = 1;

    // simple linear scale functions, preventing division by zero if all values are identical
    const scaleX = (val: number) => {
        if (maxX === minX) return padding.left + innerW / 2;
        return padding.left + ((val - minX) / (maxX - minX)) * innerW;
    };
    
    const scaleY = (val: number) => {
        // SVG y-axis is inverted (0 at top)
        // add tiny offset for better readability
        return padding.top + innerH - ((val + 0.01 - minY) / (maxY - minY)) * innerH;
    };

    let svg = `<svg width="100%" height="100%" style="background: #ddd;" viewBox="0 0 ${w} ${h}">`;
    
    // Axes
    svg += `<line x1="${padding.left}" y1="${padding.top + innerH}" x2="${padding.left + innerW}" y2="${padding.top + innerH}" stroke="black" stroke-width="2"/>`; // Bottom
    svg += `<line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${padding.top + innerH}" stroke="black" stroke-width="2"/>`; // Left

    // Axis Labels
    svg += `<text x="${padding.left + innerW / 2}" y="${h - 15}" text-anchor="middle" font-size="14" font-weight="bold" fill="black">Released</text>`;
    svg += `<text x="25" y="${padding.top + innerH / 2}" text-anchor="middle" font-size="14" font-weight="bold" fill="black" transform="rotate(-90 25 ${padding.top + innerH / 2})">Score</text>`;

    // Y-axis ticks
    const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];
    for (const tick of yTicks) {
        const ty = scaleY(tick);
        svg += `<line x1="${padding.left - 5}" y1="${ty}" x2="${padding.left}" y2="${ty}" stroke="black" stroke-width="1"/>`;
        svg += `<text x="${padding.left - 10}" y="${ty + 4}" text-anchor="end" font-size="12" fill="black">${Math.round(tick * 100)}%</text>`;
    }

    // X-axis ticks (Years)
    const startYear = new Date(minX).getFullYear();
    const endYear = new Date(maxX).getFullYear();
    for (let y = startYear; y <= endYear + 1; y++) {
        const yearTs = new Date(`${y}-01-01`).getTime();
        if (yearTs >= minX && yearTs <= maxX) {
            const tx = scaleX(yearTs);
            svg += `<line x1="${tx}" y1="${padding.top + innerH}" x2="${tx}" y2="${padding.top + innerH + 5}" stroke="black" stroke-width="1"/>`;
            svg += `<text x="${tx}" y="${padding.top + innerH + 20}" text-anchor="middle" font-size="12" fill="black">${y}</text>`;
        }
    }

    const parseDisplayProp = (val: string, defaultAlign: string) => {
        if (!val) return { offset: 0, align: defaultAlign };
        let offset = 0;
        let align = defaultAlign;
        const parts = val.split(',');
        for (const p of parts) {
            const t = p.trim();
            if (t.endsWith('px')) {
                offset = parseInt(t.substring(0, t.length - 2), 10) || 0;
            } else if (t) {
                align = t;
            }
        }
        return { offset, align };
    };

    let textSvg = '';
    let circleSvg = '';

    // Points
    validModels.forEach((m, i) => {
        const cx = scaleX(new Date(m.model_release).getTime());
        const cy = scaleY(m.score);
        let color = 'black';
        if (m.model_type === 'closed') {
            color = '#a33';
        } else if (m.model_type === 'open') {
            color = '#2a2';
        }
        circleSvg += `<circle class="chart-point" data-idx="${i}" cx="${cx}" cy="${cy}" r="5" fill="${color}" style="cursor: pointer;" />`;
        
        const haParsed = parseDisplayProp(m.display_ha, 'center');
        const vaParsed = parseDisplayProp(m.display_va, 'top');
        
        let ha = haParsed.align;
        let va = vaParsed.align;
        
        let textAnchor = 'middle';
        let labelX = cx;
        if (ha === 'left') {
            textAnchor = 'end';
            labelX = cx - 8;
        } else if (ha === 'right') {
            textAnchor = 'start';
            labelX = cx + 8;
        }
        labelX += haParsed.offset;

        let labelY = cy - 10;
        if (va === 'bottom') {
            labelY = cy + 15;
        } else if (va === 'horizon') {
            labelY = cy + 4;
        }
        labelY += vaParsed.offset;

        textSvg += `<text x="${labelX}" y="${labelY}" text-anchor="${textAnchor}" font-size="10" fill="black" pointer-events="none">${m.model_name || '?'}</text>`;
    });

    svg += textSvg + circleSvg + `</svg>`;
    container.html(svg);

    // Hover logic
    const tooltip = $('#leaderboard-tooltip');
    
    container.find('.chart-point').on('mouseenter', function(e) {
        const idx = parseInt($(this).attr('data-idx') || '0');
        const m = validModels[idx];
        const desc = m.model_description || 'No description provided.';
        const size = m.model_size || 'Unknown size';
        const typeStr = m.model_type ? (m.model_type === 'open' ? 'Open' : (m.model_type === 'closed' ? 'Closed' : m.model_type)) : 'Unknown type';
        const date = m.model_release || 'Unknown date';
        
        tooltip.html(`
            <strong>${m.model_name}</strong><br>
            <div style="margin-top: 5px; margin-bottom: 5px;">${desc}</div>
            <hr style="margin: 5px 0; border-color: #444;">
            Size: ${size}<br>
            Type: ${typeStr}<br>
            Released: ${date}<br>
            Score: ${(m.score * 100).toFixed(2)}%
        `);
        
        tooltip.show();
        
        tooltip.css({
            left: e.clientX + 'px',
            top: (e.clientY + 20) + 'px'
        });
    }).on('mousemove', function(e) {
        tooltip.css({
            left: e.clientX + 'px',
            top: (e.clientY + 20) + 'px'
        });
    }).on('mouseleave', function() {
        tooltip.hide();
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

    $('#filter-mode, #filter-tag, #filter-lang').on('change', loadLeaderboard);
    loadLeaderboard();
});
