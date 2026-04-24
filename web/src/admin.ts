import './style.css';
import $ from 'jquery';
import { getToken, getMe, getAdminUsers, renderRoleSwitcher, AdminUser } from './api';

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    try {
        const user = await getMe();
        renderRoleSwitcher(user.roles);
        if (!user.roles.includes('admin')) {
            document.body.innerHTML = `<div style="padding: 2rem; text-align: center; font-family: sans-serif;">
                <h2>Access Denied</h2>
                <p>You need admin access to view this page.</p>
            </div>`;
            return;
        }
        $('#admin-info').text(`${user.username} · Admin`);
    } catch {
        window.location.href = '/';
        return;
    }

    try {
        const users = await getAdminUsers();
        renderTable(users);
    } catch {
        $('#user-table').html('<div class="empty">Failed to load users</div>');
    }
});

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function renderTable(users: AdminUser[]): void {
    if (!users.length) {
        $('#user-table').html('<div class="empty">No users found</div>');
        return;
    }
    const rows = users.map(u => {
        const roles = u.roles.map(r => `<span class="role-tag">${escHtml(r)}</span>`).join('');
        const hasProfile = u.name || u.email;
        const name = hasProfile
            ? escHtml(u.name)
            : '<span class="no-profile">—</span>';
        const affiliation = u.affiliation
            ? escHtml(u.affiliation)
            : '<span class="no-profile">—</span>';
        const email = u.email
            ? `<a href="mailto:${escHtml(u.email)}">${escHtml(u.email)}</a>`
            : '<span class="no-profile">—</span>';
        const credit = u.credit_consent
            ? '<span class="credit-yes">Yes</span>'
            : '<span class="credit-no">No</span>';
        return `<tr>
            <td>${escHtml(u.username)}</td>
            <td>${roles}</td>
            <td>${name}</td>
            <td>${affiliation}</td>
            <td>${email}</td>
            <td>${credit}</td>
        </tr>`;
    }).join('');

    $('#user-table').html(`<table>
        <thead><tr>
            <th>Username</th>
            <th>Roles</th>
            <th>Name</th>
            <th>Affiliation</th>
            <th>Email</th>
            <th>Credit consent</th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table>`);
}
