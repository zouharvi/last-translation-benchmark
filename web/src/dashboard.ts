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
        const rows = await getPublicDashboard();
        if (!rows.length) {
            $('#dashboard-body').html('<tr><td colspan="3" class="empty">No accepted submissions yet.</td></tr>');
            return;
        }
        $('#dashboard-body').html(rows.map((row) => `
            <tr>
              <td style="padding:8px 6px; border-bottom:1px solid #f1f5f9;">${escHtml(row.name)}</td>
              <td style="padding:8px 6px; border-bottom:1px solid #f1f5f9;">${escHtml(row.affiliation)}</td>
              <td style="padding:8px 6px; border-bottom:1px solid #f1f5f9; text-align:right;">${row.accepted_submissions}</td>
            </tr>
        `).join(''));
    } catch {
        $('#dashboard-body').html('<tr><td colspan="3" class="empty">Failed to load dashboard data.</td></tr>');
    }
});
