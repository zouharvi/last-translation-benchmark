import './style.css';
import $ from 'jquery';

import { getToken, getUsername, getMe } from './api';
import { setupInstructions } from './utils';

$(async () => {
    setupInstructions('all');
    
    $('#register-btn').on('click', () => {
        window.location.href = 'profile.html';
    });
    
    const token = getToken();
    const username = getUsername();
    if (token && username) {
        try {
            const user = await getMe();
            redirectByRoles(user.roles);
        } catch {
            $('#auth-error').show();
        }
    }
});

function redirectByRoles(roles: string[]): void {
    const search = window.location.search;
    if (roles.includes('admin')) {
        window.location.href = 'admin.html' + search;
    } else if (roles.includes('reviewer')) {
        window.location.href = 'reviewer.html' + search;
    } else if (roles.includes('contributor')) {
        window.location.href = 'contributor.html' + search;
    }
}
