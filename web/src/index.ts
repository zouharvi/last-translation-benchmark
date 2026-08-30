import './assets/style.css';
import $ from 'jquery';

import { getContributors, getCookie, getMe, logout, User, handleNotifications } from './api';
import { esc as escHtml } from './utils';

$(async () => {

    if (getCookie('ltb_token')) {
        try {
            const user = await getMe();
            showRoleButtons(user);
            
            const params = new URLSearchParams(window.location.search);
            if (params.get('registered') != null) {
                const msg = $('<span style="color: #19632e;">Registration successful; please contribute below.</span><br>');
                $('#role-buttons').prepend(msg);
                
                const url = new URL(window.location.href);
                // url.searchParams.delete('registered');
                window.history.replaceState({}, document.title, url.toString());
            }
        } catch {
            $('#auth-error').show();
        }
    } else {
        $('#cta-info-unauth').show();
    }

    try {
        const data = await getContributors();

        const languages = data.languages.filter(x => x[1] > 1).map(x => escHtml(x[0].replace("(", "").replace(")", "")).replace(" ", "&nbsp;") + ` (${x[1]})`).join(', ');
        const languages_singular = data.languages.filter(x => x[1] === 1).length;
        
        $('#contributors-stats').html(`
            <div style="flex-wrap: wrap; display: flex; gap: 20px; text-align: justify;">
                <div><strong>Total Submissions:</strong> ${data.total_submissions}</div>
                <div><strong>Contributors:</strong> ${data.total_authors}</div>
                <div style="flex-basis: 100%;"><strong>Languages:</strong> ${languages}${languages_singular > 0 ? ` and ${languages_singular} languages with a single submission` : ''}</div>
            </div>
        `);

        if (!data.rows.length) {
            $('#contributors-body').html('<tr><td colspan="3" class="empty">No accepted submissions yet.</td></tr>');
        } else {
            $('#contributors-body').html(data.rows.map((row) => `
                <tr>
                  <td style="padding: 3px 3px 3px 0px; border-bottom:1px solid #f1f5f9; text-align: left;">${escHtml(row.name)}</td>
                  <td style="padding: 3px; border-bottom:1px solid #f1f5f9; text-align: left;">${escHtml(row.affiliation)}</td>
                  <td style="padding: 3px; border-bottom:1px solid #f1f5f9; text-align:right;">${row.accepted_submissions}</td>
                </tr>
            `).join(''));

            if (data.rows.length > 5) {
                $('#show-all-contributors').show().on('click', function() {
                    $('#contributors-table-container').css('max-height', 'none');
                    $('#contributors-fade').hide();
                    $(this).hide();
                });
            } else {
                $('#contributors-table-container').css('max-height', 'none');
                $('#contributors-fade').hide();
            }
        }
    } catch {
        $('#contributors-body').html('<tr><td colspan="3" class="empty">Failed to load contributors data.</td></tr>');
    }
});

function showRoleButtons(user: User): void {
    $('#register-btn').hide();
    $('#cta-info-unauth').hide();

    const container = $('#role-buttons');
    const actions1 = $('<div class="role-actions"></div>');
    const actions2 = $('<div class="role-actions" style="margin-top: 10px;"></div>');

    container.append(`<span>Hello ${escHtml(user.name)} from ${escHtml(user.affiliation)}!</span><br><br>`);

    if (user.roles.includes('contributor')) {
        actions1.append('<a href="contribute" class="btn btn-success">✍️&nbsp;Contribute examples</a>');
    }
    if (user.roles.includes('reviewer')) {
        actions1.append('<a href="review" class="btn btn-success">🔍&nbsp;Review examples</a>');
    }

    // actions1.append('<a href="leaderboard-results" class="btn btn-success">Leaderboard</a>');
    // actions1.append('<a href="leaderboard-submission" class="btn btn-success">Submit model</a>');
    if (user.roles.includes('admin')) {
        actions2.append('<a href="admin" class="btn btn-success">Admin</a>');
    }

    actions2.append('<a href="profile" class="btn btn-success">Profile</a>');

    const logoutBtn = $('<button class="btn btn-success">Logout</button>');
    logoutBtn.on('click', logout);
    actions2.append(logoutBtn);

    container.append(actions1);
    container.append(actions2);

    container.css('display', 'block');

    if (user.notifications.length > 0) {
        const notifBox = $('#notifications-box');
        notifBox.empty();
        
        const clearBtn = $('<button class="btn-underlined" style="font-size: 0.8em;">Clear Notifications</button>');
        clearBtn.on('click', async () => {
            await handleNotifications('clear');
            notifBox.hide();
        });
        
        user.notifications.reverse().forEach(n => {
            const item = $('<div>').css({
                padding: '10px', fontSize: '0.9em',
                background: n.status === 'unread' ? '#ddd' : 'transparent', textAlign: 'left',
            });
            item.html(`<strong>${escHtml(n.type)}</strong>: <span style="color:#444">${escHtml(n.content)}</span> <small style="color:#aaa; float:right;">${escHtml(n.created)}</small>`);
            notifBox.append(item);
        });
        notifBox.append(clearBtn);
        
        notifBox.show();

        const hasUnread = user.notifications.some(n => n.status === 'unread');
        if (hasUnread) {
            handleNotifications('view').catch(console.error);
        }
    }
}
