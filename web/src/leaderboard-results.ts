import './assets/style.css';
import $ from 'jquery';
import { fetchLeaderboardResults, getMe, renderRoleSwitcher } from './api';
import { renderHeaderStatus } from './utils';

let languagesPopulated = false;

async function loadLeaderboard() {
    $('#leaderboard-content').html('<div class="empty">Loading...</div>');
    try {
        const filterMode = $('#filter-mode').val() as string;
        const filterTag = $('#filter-tag').val() as string;
        const filterLang = $('#filter-lang').val() as string;
        
        let lang1 = '';
        let lang2 = '';
        if (filterLang !== 'all') {
            const parts = filterLang.split(' → ');
            if (parts.length === 2) {
                lang1 = parts[0];
                lang2 = parts[1];
            }
        }

        const data = await fetchLeaderboardResults(filterMode, filterTag, lang1, lang2);
        
        if (!languagesPopulated && data.language_pairs) {
            const select = $('#filter-lang');
            for (const pair of data.language_pairs) {
                select.append(`<option value="${pair}">${pair}</option>`);
            }
            languagesPopulated = true;
        }
        
        const models = data.models || [];
        if (models.length === 0) {
            $('#leaderboard-content').html('<div class="empty">No models match the selected filters.</div>');
            return;
        }

        let rows = '';
        for (const model of models) {
            rows += `<tr>
                <td>${model.model_name || '—'}</td>
                <td>${model.model_size || '—'}</td>
                <td>${model.institution || '—'}</td>
                <td><strong>${(model.score * 100).toFixed(2)}%</strong></td>
            </tr>`;
        }

        const tableHtml = `
            <table>
                <thead>
                    <tr>
                        <th>Model Name</th>
                        <th>Size</th>
                        <th>Institution</th>
                        <th>Score</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `;

        $('#leaderboard-content').html(tableHtml);
    } catch (e) {
        console.error(e);
        $('#leaderboard-content').html(`<div class="empty">Failed to load leaderboard data: ${e}</div>`);
    }
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
