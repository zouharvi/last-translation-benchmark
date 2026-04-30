import './style.css';
import $ from 'jquery';
import {
    getToken, getUsername, getMe, getAdminUsers, deleteAdminUser,
    rotateAdminToken, adjustAdminQuota, updateAdminRoles, renderRoleSwitcher, AdminUser,
} from './api';

import { esc, showToast, accessDenied } from './utils';

let allUsers: AdminUser[] = [];
let adminName: string = '';

function renderTable(users: AdminUser[]): void {
    if (!users.length) {
        $('#user-table').html('<div class="empty">No users found</div>');
        return;
    }
    const rows = users.map(u => {
        const allRoles = ['admin', 'reviewer', 'contributor'];
        const rolesHtml = allRoles.map(r => {
            const active = u.roles.includes(r);
            return `<span class="role-tag role-${r} ${active ? '' : 'role-inactive'}" data-role="${r}">${esc(r)}</span>`;
        }).join('');
        return `<tr data-uid="${u.id}">
            <td><span class="uname">${esc(u.username)}</span></td>
            <td>${rolesHtml}</td>
            <td>${u.name ? esc(u.name) : '<span class="muted">—</span>'}</td>
            <td>${u.affiliation ? esc(u.affiliation) : '<span class="muted">—</span>'}</td>
            <td>${u.email ? `<a href="mailto:${esc(u.email)}">${esc(u.email)}</a>` : '<span class="muted">—</span>'}</td>
            <td style="text-align:right;color:#64748b;white-space:nowrap">${u.quota_used} / ${u.quota}</td>
            <td>
              <div class="action-btns">
                <a class="act-btn act-copy" data-uid="${u.id}" title="Login link" href="index.html?user=${encodeURIComponent(u.username)}&token=${encodeURIComponent(u.magic_token)}">🔗</a>
                ${u.email ? (() => {
                    const link = window.location.origin + window.location.pathname.replace('admin.html', 'index.html') + '?user=' + encodeURIComponent(u.username) + '&token=' + encodeURIComponent(u.magic_token);
                    const subject = 'Your Last Translation Benchmark Login Link';
                    const body = `Dear ${u.name || u.username},\n\nThank you for your interest in Last Translation Benchmark. You can submit hard-to-translate inputs via this link (do not share with anyone):\n\n${link}\n\nPlease make sure that you read the instructions in detail.\nLet us know if you have any questions or need to increase your submission quota.\n\nOn behalf of LTB organizers,\n${adminName}`;
                    return `<a class="act-btn" title="Send magic link via email" href="mailto:${encodeURIComponent(u.email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}" style="background:#e0e7ff;color:#4338ca;text-decoration:none;">📧</a>`;
                })() : `<button class="act-btn act-email" title="Send magic link via email" style="background:#e0e7ff;color:#4338ca;">📧</button>`}
                <button class="act-btn act-rotate" data-uid="${u.id}" title="Rotate magic token">🔄</button>
                <button class="act-btn act-quota" data-uid="${u.id}" title="Adjust quota">±</button>
                <button class="act-btn act-delete" data-uid="${u.id}" title="Remove user">✕</button>
              </div>
            </td>
        </tr>`;
    }).join('');

    $('#user-table').html(`<table>
        <thead><tr><th>Username</th><th>Roles</th><th>Name</th><th>Affiliation</th><th>Email</th><th style="text-align:right">Used / Quota</th><th>Actions</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>`);

    $('.role-tag').on('click', async function () {
        const uid = $(this).closest('tr').data('uid');
        const role = $(this).data('role');
        const u = allUsers.find(u => u.id === uid);
        if (!u) return;

        let newRoles = [...u.roles];
        if (newRoles.includes(role)) {
            newRoles = newRoles.filter(r => r !== role);
        } else {
            newRoles.push(role);
        }

        try {
            const res = await updateAdminRoles(uid, newRoles);
            u.roles = res.roles;
            applyFilter();
            showToast('Roles updated');
        } catch (e) { alert(e); }
    });

    $('.act-rotate').on('click', async function () {
        const uid = $(this).data('uid');
        if (!confirm('Rotate magic token?')) return;
        try {
            const res = await rotateAdminToken(uid);
            allUsers.find(u => u.id === uid)!.magic_token = res.magic_token;
            showToast('Token rotated');
        } catch (e) { alert(e); }
    });

    $('.act-email').on('click', function () {
        alert('User does not have an email address set.');
    });

    $('.act-delete').on('click', async function () {
        const uid = $(this).data('uid');
        if (!confirm('Delete user?')) return;
        try {
            await deleteAdminUser(uid);
            allUsers = allUsers.filter(u => u.id !== uid);
            applyFilter();
            showToast('User deleted');
        } catch (e) { alert(e); }
    });

    $('.act-quota').on('click', async function () {
        const uid = $(this).data('uid');
        const u = allUsers.find(u => u.id === uid);
        const raw = prompt(`Adjust quota (current: ${u?.quota}, used: ${u?.quota_used}).\nUse + or - to adjust (e.g. +50 or -10):`);
        if (raw === null) return;
        if (!/^[+-]\d+$/.test(raw.trim())) { alert('Invalid input. Must start with + or - followed by a number.'); return; }
        const delta = parseInt(raw.trim(), 10);
        try {
            const res = await adjustAdminQuota(uid, delta);
            if (u) { u.quota = res.quota; u.quota_used = res.quota_used; }
            applyFilter();
            showToast('Quota updated');
        } catch (e) { alert(e); }
    });
}

function applyFilter(): void {
    const q = ($('#filter-input').val() as string).toLowerCase().trim();
    const role = $('#role-filter').val() as string;
    const filtered = allUsers.filter(u => {
        const matchesRole = !role || u.roles.includes(role);
        const matchesQuery = !q || u.username.toLowerCase().includes(q) || (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
        return matchesRole && matchesQuery;
    });
    $('#filtered-count').text(`Total: ${filtered.length} users`);
    renderTable(filtered);
}
$(async () => {
    const token = getToken();
    const username = getUsername();
    if (!token || !username) { window.location.href = 'index.html'; return; }
    try {
        const user = await getMe();
        adminName = user.name || user.username;
        renderRoleSwitcher(user.roles);
        if (!user.roles.includes('admin')) { accessDenied(user.roles, 'admin'); return; }
        $('#admin-info').text(`${user.username} (Admin)`);
        allUsers = await getAdminUsers();
        applyFilter();
    } catch { window.location.href = 'index.html'; }

    $('#filter-input').on('input', applyFilter);
    $('#role-filter').on('change', applyFilter);
});
