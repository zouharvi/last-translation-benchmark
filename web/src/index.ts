import './assets/style.css';
import $ from 'jquery';

import { getCookie, getMe, logout, User, handleNotifications } from './api';
import instructionsHtml from './assets/instructions.html';
import { esc as escHtml } from './utils';

$(async () => {
    $('#instructions-box').html(instructionsHtml);

    if (getCookie('ltb_token')) {
        try {
            const user = await getMe();
            showRoleButtons(user);
        } catch {
            $('#auth-error').show();
        }
    } else {
        $('#cta-info-unauth').show();
    }
});

function showRoleButtons(user: User): void {
    $('#register-btn').hide();
    $('#cta-info-unauth').hide();

    const container = $('#role-buttons');
    const actions = $('<div class="role-actions"></div>');

    container.append(`<span>Hello ${escHtml(user.name)} (${escHtml(user.username)}) from ${escHtml(user.affiliation)}!</span><br><br>`);

    if (user.roles.includes('contributor')) {
        actions.append('<a href="contribute" class="btn btn-success">✍️&nbsp;Contribute</a>');
    }
    if (user.roles.includes('reviewer')) {
        actions.append('<a href="review" class="btn btn-success">🔍&nbsp;Review</a>');
    }
    if (user.roles.includes('admin')) {
        actions.append('<a href="admin" class="btn btn-success">⚙️&nbsp;Admin</a>');
    }

    actions.append('<a href="dashboard" class="btn btn-success">📊&nbsp;Public Dashboard</a>');
    actions.append('<a href="profile" class="btn btn-success">📇&nbsp;Profile</a>');

    const logoutBtn = $('<button class="btn btn-success">Logout</button>');
    logoutBtn.on('click', logout);
    actions.append(logoutBtn);

    container.append(actions);

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
