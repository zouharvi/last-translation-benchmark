import './style.css';
import $ from 'jquery';
import { getToken, getMe } from './api';

$(async () => {
    const token = getToken();
    if (token) {
        try {
            const user = await getMe();
            redirectByRole(user.role);
        } catch {
            $('#auth-error').show();
        }
    }
});

function redirectByRole(role: string): void {
    const search = window.location.search;
    window.location.href = (role === 'reviewer' ? '/reviewer.html' : '/contributor.html') + search;
}
