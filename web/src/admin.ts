import './assets/style.css';
import $ from 'jquery';
import {
    getMe, getCookie, getAdminOverview, deleteAdminUser,
    adjustAdminQuota, updateAdminRoles, updateAdminReviewScope, renderRoleSwitcher, AdminUser, AdminOverview
} from './api';

import { esc, showToast, accessDenied, renderHeaderStatus } from './utils';

let allUsers: AdminUser[] = [];
let adminOverview: AdminOverview | null = null;

function renderOverview(data: AdminOverview) {
    const statusCounts = Object.entries(data.submissions_total)
        .map(([status, count]) => `<strong>${count}</strong> ${esc(status)}`)
        .join(', ');
    
    let html = `<p style="margin-top:0;"><strong>Total Submissions:</strong> ${statusCounts}. `;
    
    if (data.submissions_without_reviewer.length > 0) {
        html += `<p style="font-weight: bold; margin-bottom: 4px;">Pending submissions with no elligible reviewers (${data.submissions_without_reviewer.length}):</p>`;
        html += `<ul style="margin-top: 0; margin-bottom: 12px;">`;
        const grouped: Record<string, number[]> = {};
        for (const sub of data.submissions_without_reviewer) {
            const key = `${esc(sub.source_lang)} &rarr; ${esc(sub.target_lang)} by ${esc(sub.user_name || sub.username)}`;
            (grouped[key] ||= []).push(sub.id);
        }
        for (const [key, ids] of Object.entries(grouped)) {
            html += `<li>${key} (${ids.map(id => `#${id}`).join(', ')})</li>`;
        }
        html += `</ul>`;
    }

    const pendingLangsCount = Object.keys(data.pending_languages || {}).length;
    if (pendingLangsCount > 0) {
        const sortedLangs = Object.entries(data.pending_languages)
            .sort((a: [string, number], b: [string, number]) => b[1] - a[1])
            .map(([lang, count]: [string, number]) => `<strong>${count}</strong> ${esc(lang)}`)
            .join(', ');
        html += `<p style="margin-top: 0; margin-bottom: 12px;"><strong>Pending by language:</strong> ${sortedLangs}</p>`;
    }

    html += `</p>`
    
    $('#overview-content').html(html);
}

function renderTable(users: AdminUser[]): void {
    if (!users.length) {
        $('#user-table').html('<div class="empty">No users found</div>');
        return;
    }
    // Slightly complicated way to get the hosting root. We could use host but that doesn't work if this is hosted from a directory.
    let root = window.location.origin + window.location.pathname.split("/").slice(0, -1).join("/");
    const rows = users.map(u => {
        const link = root + '/?user=' + encodeURIComponent(u.username) + '&token=' + encodeURIComponent(u.magic_token);
        const allRoles = ['admin', 'reviewer', 'contributor'];
        const rolesHtml = allRoles.map(r => {
            const active = u.roles.includes(r);
            return `<span class="role-tag role-${r} ${active ? '' : 'role-inactive'}" data-role="${r}">${esc(r)}</span>`;
        }).join('');

        const sugg = u.review_suggestions || [];
        let suggHtml = sugg.length === 0 ? '<span class="muted" style="font-size: 0.8em;">none</span>' : `<span class="sugg-toggle" style="cursor:pointer;" data-uid="${u.id}">${sugg.length} possible</span>`;
        if (sugg.length > 0 && !u.roles.includes('reviewer')) {
             suggHtml += `<br><span style="font-size: 0.8em;">not a reviewer</span>`;
        }

        let suggListHtml = '';
        if (sugg.length > 0) {
            const groupedSugg: Record<string, number[]> = {};
            for (const s of sugg) {
                const key = `${esc(s.source_lang)} &rarr; ${esc(s.target_lang)} by ${esc(s.user_name || s.username)}`;
                (groupedSugg[key] ||= []).push(s.id);
            }
            suggListHtml = `<tr class="sugg-row-${u.id}" style="display:none;">
                <td colspan="10" style="padding: 10px 20px; border-bottom: 1px solid #e2e8f0;">
                    <ul style="margin: 0; padding-left: 20px; font-size: 0.9em;">
                        ${Object.entries(groupedSugg).map(([k, ids]) => `<li>${k} (${ids.map(id => `#${id}`).join(', ')})</li>`).join('')}
                    </ul>
                </td>
            </tr>`;
        }

        return `<tr data-uid="${u.id}">
            <td><a href="${link}" class="uname" target="_blank">${esc(u.username)}</a></td>
            <td>${u.name ? esc(u.name) : '<span class="muted">—</span>'}</td>
            <td style="width:1%;white-space:nowrap">${rolesHtml}</td>
            <td class="scope-cell" data-uid="${u.id}" title="Click to edit language scope">${u.review_langs && u.review_langs.length ? esc(u.review_langs.join(',')) : '<span class="muted">all</span>'}</td>
            <td class="sugg-cell">${suggHtml}</td>
            <td class="affil-cell" title="${esc(u.affiliation)}">${u.affiliation ? esc(u.affiliation) : '<span class="muted">—</span>'}</td>
            <td class="email-cell" title="${esc(u.email)}"><a href="mailto:${esc(u.email)}">${esc(u.email)}</a></td>
            <td style="text-align:right;white-space:nowrap">${u.quota_used}&nbsp;/&nbsp;<button class="act-btn act-quota" data-uid="${u.id}" title="Adjust quota">${u.quota}</button></td>
            <td style="text-align:right">${u.total_accepted}&nbsp;/&nbsp;${u.total_submitted}</td>
            <td>
              <div class="action-btns">
                <button class="act-btn act-delete" data-uid="${u.id}" title="Remove user">✕</button>
              </div>
            </td>
        </tr>${suggListHtml}`;
    }).join('');

    $('#user-table').html(`<table>
        <thead><tr><th>Username</th><th>Name</th><th style="width:1%;white-space:nowrap">Roles</th><th class="scope-cell">Reviewer<br>scope</th><th class="sugg-cell">Reviewer<br>suggestions</th><th class="affil-cell">Affiliation</th><th class="email-cell">Email</th><th style="text-align:right">Used&nbsp;/<br>Quota</th><th style="text-align:right">Accepted&nbsp;/<br>Submitted</th><th>Actions</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>`);

    $('.sugg-toggle').on('click', function () {
        const uid = $(this).data('uid');
        $(`.sugg-row-${uid}`).toggle();
    });

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

    $('.act-delete').on('click', async function () {
        const uid = $(this).data('uid');
        if (!confirm(`Delete user ${uid}?`)) return;
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

    $('.scope-cell').on('click', async function () {
        const uid = $(this).data('uid');
        const u = allUsers.find(u => u.id === uid);
        if (!u) return;
        const current = (u.review_langs && u.review_langs.length) ? u.review_langs.join(',') : '';
        const input = prompt('Language scope (comma-separated, empty = all, e.g. English,Czech,German).\nIf you wish to prevent someone from reviewing, then remove the review role.', current);
        if (input === null) return;
        if (input.includes(', ')) { alert('Use commas without spaces (e.g. English,Czech,German).'); return; }
        const langs = input.trim() ? input.split(',').filter(Boolean) : [];
        try {
            const res = await updateAdminReviewScope(uid, langs);
            u.review_langs = res.review_langs;
            applyFilter();
            showToast('Language scope updated');
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
    if (!getCookie('ltb_token')) { window.location.href = 'index.html'; return; }
    try {
        const user = await getMe();
        renderHeaderStatus(user);
        renderRoleSwitcher(user.roles);
        if (!user.roles.includes('admin')) { accessDenied(user.roles, 'admin'); return; }
        adminOverview = await getAdminOverview();
        allUsers = adminOverview.users;
        renderOverview(adminOverview);
        applyFilter();
    } catch { window.location.href = 'index.html'; }

    $('#filter-input').on('input', applyFilter);
    $('#role-filter').on('change', applyFilter);
});
