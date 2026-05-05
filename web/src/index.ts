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

    container.append(`<span>Hello ${user.name} (${user.username}) from ${user.affiliation}!</span><br><br>`);

    if (user.roles.includes('contributor')) {
        container.append(`<a href="contribute" class="btn btn-secondary">✍️ Contribute</a>`);
    }
    if (user.roles.includes('reviewer')) {
        container.append(`<a href="review" class="btn btn-secondary">🔍 Review</a>`);
    }
    if (user.roles.includes('admin')) {
        container.append(`<a href="admin" class="btn btn-secondary">⚙️ Admin</a>`);
    }

    const logoutBtn = $('<button class="btn btn-secondary">Logout</button>');
    logoutBtn.on('click', logout);
    container.append(logoutBtn);

    container.css('display', 'block');
}
