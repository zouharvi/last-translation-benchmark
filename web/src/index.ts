import './style.css';
import $ from 'jquery';
import { getToken, getMe } from './api';

$(async () => {
    const token = getToken();
    if (token) {
        try {
            const user = await getMe();
            if (!user.name || !user.email) {
                window.location.href = '/profile.html' + window.location.search;
                return;
            }
            redirectByRoles(user.roles);
        } catch {
            $('#auth-error').show();
        }
    }
});

function redirectByRoles(roles: string[]): void {
    const search = window.location.search;
    if (roles.includes('reviewer') && !roles.includes('contributor')) {
        window.location.href = '/reviewer.html' + search;
    } else {
        window.location.href = '/contributor.html' + search;
    }
}
