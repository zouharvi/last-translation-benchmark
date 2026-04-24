import './style.css';
import $ from 'jquery';
import { magicAuth, getToken, getMe, setToken } from './api';

$(async () => {
    // If already authenticated, redirect by role
    const existingToken = getToken();
    if (existingToken) {
        try {
            const user = await getMe();
            redirectByRole(user.role);
            return;
        } catch {
            // Token invalid — fall through to check magic link
        }
    }

    // Check for magic link params: ?user=...&token=...
    const params = new URLSearchParams(window.location.search);
    const username = params.get('user');
    const token = params.get('token');
    if (username && token) {
        try {
            const data = await magicAuth(username, token);
            setToken(data.token);
            // Clean the URL so the magic link isn't visible in the address bar
            history.replaceState(null, '', '/');
            redirectByRole(data.role);
        } catch {
            $('#auth-error').show();
        }
    }
});

function redirectByRole(role: string): void {
    window.location.href = role === 'reviewer' ? '/reviewer.html' : '/contributor.html';
}
