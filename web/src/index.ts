import './style.css';
import $ from 'jquery';

import { getCookie, getMe, logout, User } from './api';
import { setupInstructions } from './utils';

$(async () => {
    setupInstructions('all');

    if (getCookie('ltb_token')) {
        try {
            const user = await getMe();
            showRoleButtons(user);
        } catch {
            $('#auth-error').show();
        }
    }
});

function showRoleButtons(user: User): void {
    $('#register-btn').hide();
    $('#cta-info-unauth').hide();

    const container = $('#role-buttons');
    const actions = $('<div class="role-actions"></div>');

    container.append(`<span>Hello ${user.name} (${user.username}) from ${user.affiliation}!</span><br><br>`);

    if (user.roles.includes('contributor')) {
        actions.append('<a href="contribute" class="btn btn-secondary">✍️&nbsp;Contribute</a>');
    }
    if (user.roles.includes('reviewer')) {
        actions.append('<a href="review" class="btn btn-secondary">🔍&nbsp;Review</a>');
    }
    if (user.roles.includes('admin')) {
        actions.append('<a href="admin" class="btn btn-secondary">⚙️&nbsp;Admin</a>');
    }

    actions.append('<a href="profile" class="btn btn-secondary">📇&nbsp;Profile</a>');

    const logoutBtn = $('<button class="btn btn-secondary">Logout</button>');
    logoutBtn.on('click', logout);
    actions.append(logoutBtn);

    container.append(actions);

    container.css('display', 'block');
}
