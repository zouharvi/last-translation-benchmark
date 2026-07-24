import './assets/style.css';
import $ from 'jquery';

import { getPublicDashboard, getCookie, getMe, renderRoleSwitcher } from './api';
import { esc as escHtml, renderHeaderStatus } from './utils';

$(async () => {
    if (getCookie('ltb_token')) {
        try {
            const user = await getMe();
            renderHeaderStatus(user);
            renderRoleSwitcher(user.roles);
        } catch {
            // Ignore and just show dashboard for unauthenticated / bad token
        }
    }

    try {
        const data = await getPublicDashboard();
        
        $('#dashboard-stats').html(`
            <div style="flex-wrap: wrap; display: flex; gap: 12px; text-align: justify;">
                <div><strong>Total Submissions:</strong> ${data.total_submissions}</div>
                <div><strong>Contributors:</strong> ${data.total_authors}</div>
                ${data.data_source === 'live_public_dashboard'
                    ? '<div><strong>Data source:</strong> Live public dashboard</div>'
                    : ''}
                <div style="flex-basis: 100%;"><strong>Languages:</strong> ${data.languages.map(x=> escHtml(x[0]).replace(" ", "&nbsp;").replace("(", "").replace(")", "") + ` (${x[1]})`).join(', ')}</div>
            </div>
        `);

        const { initializeAffiliationMap } = await import('./affiliation-map');
        initializeAffiliationMap(
            data.affiliation_places ?? [],
            data.total_submissions,
            data.total_authors,
        );

        if (!data.rows.length) {
            $('#dashboard-body').html('<tr><td colspan="3" class="empty">No accepted submissions yet.</td></tr>');
            return;
        }
        $('#dashboard-body').html(data.rows.map((row) => `
            <tr>
              <td style="padding:8px 6px; border-bottom:1px solid #f1f5f9;">${escHtml(row.name)}</td>
              <td style="padding:8px 6px; border-bottom:1px solid #f1f5f9;">${escHtml(row.affiliation)}</td>
              <td style="padding:8px 6px; border-bottom:1px solid #f1f5f9; text-align:right;">${row.accepted_submissions}</td>
            </tr>
        `).join(''));
    } catch {
        $('#affiliation-map-loading').addClass('error').text('Failed to load affiliation map.');
        $('#dashboard-body').html('<tr><td colspan="3" class="empty">Failed to load dashboard data.</td></tr>');
    }
});
