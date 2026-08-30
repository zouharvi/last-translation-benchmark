import './assets/style.css';
import $ from 'jquery';
import {
    getMe, getCookie, getAdminOverview, deleteAdminUser,
    adjustAdminQuota, updateAdminRoles, updateAdminReviewScope, sendAdminReviewReminder, prepareAdminReviewReminder, renderRoleSwitcher, AdminUser, AdminOverview,
    getLeaderboard, updateLeaderboard, deleteLeaderboard, updateLeaderboardInfo, LeaderboardEntry
} from './api';

import { esc, showToast, accessDenied, renderHeaderStatus, formatLargeNumber } from './utils';

let allUsers: AdminUser[] = [];
let allLeaderboard: LeaderboardEntry[] = [];
let adminOverview: AdminOverview | null = null;

function renderOverview(data: AdminOverview) {
    const statusCounts = Object.entries(data.submissions_total)
        .map(([status, count]) => `<strong>${count}</strong> ${esc(status)}`)
        .join(', ');
    
    let html = `<p style="margin-top:0;"><strong>Total Submissions:</strong> ${statusCounts}. `;
    
    if (data.submissions_without_reviewer.length > 0) {
        html += `<p style="font-weight: bold; margin-bottom: 4px;">Pending submissions with no eligible reviewers (${data.submissions_without_reviewer.length}):</p>`;
        html += `<ul style="margin-top: 0; margin-bottom: 12px;">`;
        const grouped: Record<string, number[]> = {};
        for (const sub of data.submissions_without_reviewer) {
            const key = `${esc(sub.source_lang)} &rarr; ${esc(sub.target_lang)} by ${esc(sub.name || sub.username)}`;
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
        let highestRole = '';
        if (u.roles.includes('admin')) highestRole = 'admin';
        else if (u.roles.includes('reviewer')) highestRole = 'reviewer';
        else if (u.roles.includes('contributor')) highestRole = 'contributor';
        else if (u.roles.includes('api')) highestRole = 'API';

        const rolesHtml = `
            <select class="role-select admin-input" data-uid="${u.id}" style="width: 100%; padding: 2px 4px; font-size: 0.9em;">
                <option value="" ${highestRole === '' ? 'selected' : ''}>none</option>
                <option value="contributor" ${highestRole === 'contributor' ? 'selected' : ''}>contributor</option>
                <option value="reviewer" ${highestRole === 'reviewer' ? 'selected' : ''}>reviewer</option>
                <option value="admin" ${highestRole === 'admin' ? 'selected' : ''}>admin</option>
                <option value="API" ${highestRole === 'API' ? 'selected' : ''}>API</option>
            </select>
        `;

        const sugg = u.review_suggestions || [];
        let suggHtml = sugg.length === 0 ? '<span class="muted" style="font-size: 0.8em;">none</span>' : `<span class="sugg-toggle" style="cursor:pointer;" data-uid="${u.id}">${sugg.length} possible</span>`;
        if (sugg.length > 0 && !u.roles.includes('reviewer')) {
             suggHtml += `<br><span style="font-size: 0.8em;">not a reviewer</span>`;
        }

        let suggListHtml = '';
        if (sugg.length > 0) {
            const groupedSugg: Record<string, number[]> = {};
            for (const s of sugg) {
                const key = `${esc(s.source_lang)} &rarr; ${esc(s.target_lang)} by ${esc(s.name || s.username)}`;
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
            <td class="uname-cell" title="${esc(u.username)}"><a href="${link}" class="uname" target="_blank">${esc(u.username)}</a></td>
            <td class="name-cell" title="${esc(u.name)}">${esc(u.name)}</td>
            <td style="width:90px;white-space:nowrap">${rolesHtml}</td>
            <td class="scope-cell" data-uid="${u.id}" title="Click to edit language scope">${u.review_langs && u.review_langs.length ? esc(u.review_langs.join(',')) : '<span class="muted">all</span>'}</td>
            <td class="sugg-cell">${suggHtml}</td>
            <td class="affil-cell" title="${esc(u.affiliation)}">${u.affiliation ? esc(u.affiliation) : '<span class="muted">—</span>'}</td>
            <td class="email-cell" title="${esc(u.email)}"><a href="mailto:${esc(u.email)}">${esc(u.email)}</a></td>
            <td class="quota-cell" style="text-align:right;white-space:nowrap">${u.roles.includes('api') ? formatLargeNumber(u.quota_used) : u.quota_used}&nbsp;/&nbsp;<button class="act-btn act-quota" data-uid="${u.id}" title="Adjust quota">${u.roles.includes('api') ? formatLargeNumber(u.quota) : u.quota}</button></td>
            <td class="total-cell" style="text-align:right">${u.total_accepted}&nbsp;/&nbsp;${u.total_submitted}</td>
            <td>
              <div class="action-btns">
                <button class="act-btn act-mail" data-uid="${u.id}" title="Send email">E</button>
                <button class="act-btn act-delete" data-uid="${u.id}" title="Remove user">✕</button>
              </div>
            </td>
        </tr>${suggListHtml}`;
    }).join('');

    $('#user-table').html(`<table>
        <thead><tr><th class="uname-cell">Username</th><th>Name</th><th style="width:90px;white-space:nowrap">Roles</th><th class="scope-cell">Reviewer<br>scope</th><th class="sugg-cell">Reviewer<br>suggestions</th><th class="affil-cell">Affiliation</th><th class="email-cell">Email</th><th style="text-align:right">Used&nbsp;/<br>Quota</th><th style="text-align:right">Accepted&nbsp;/<br>Submitted</th><th>Actions</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>`);

    $('.sugg-toggle').on('click', function () {
        const uid = $(this).data('uid');
        $(`.sugg-row-${uid}`).toggle();
    });

    $('.role-select').on('change', async function () {
        const uid = $(this).data('uid');
        const role = $(this).val() as string;
        const u = allUsers.find(u => u.id === uid);
        if (!u) return;

        let newRoles: string[] = [];
        if (role === 'admin') newRoles = ['admin', 'reviewer', 'contributor'];
        else if (role === 'reviewer') newRoles = ['reviewer', 'contributor'];
        else if (role === 'contributor') newRoles = ['contributor'];
        else if (role === 'API') newRoles = ['api'];

        try {
            const res = await updateAdminRoles(uid, newRoles);
            u.roles = res.roles;
            showToast('Roles updated');
        } catch (e) {
            alert(e);
            // Revert UI change
            applyFilter();
        }
    });

    $('.act-delete').on('click', async function () {
        const uid = $(this).data('uid');
        if (!confirm(`Delete user ${uid}?`)) return;
        try {
            await deleteAdminUser(uid);
            allUsers = allUsers.filter(u => u.id !== uid);
            $(this).closest('tr').remove();
            $(`.sugg-row-${uid}`).remove();
            showToast('User deleted');
        } catch (e) { alert(e); }
    });

    $('.act-quota').on('click', async function () {
        const uid = $(this).data('uid');
        const u = allUsers.find(u => u.id === uid);
        const raw = prompt(`Adjust quota (current: ${u?.quota}, used: ${Math.ceil(u?.quota_used || 0)}).\nUse + or - to adjust (e.g. +50 or -10):`);
        if (raw === null) return;
        if (!/^[+-]\d+$/.test(raw.trim())) { alert('Invalid input. Must start with + or - followed by a number.'); return; }
        const delta = parseInt(raw.trim(), 10);
        try {
            const res = await adjustAdminQuota(uid, delta);
            if (u) { u.quota = res.quota; u.quota_used = res.quota_used; }
            const parent = $(this).parent();
            const usedStr = u?.roles.includes('api') ? u!.quota_used.toFixed(1) : u!.quota_used.toString();
            parent[0].firstChild!.nodeValue = `${usedStr}\u00A0/\u00A0`;
            $(this).text(res.quota);
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
            $(this).html(res.review_langs && res.review_langs.length ? esc(res.review_langs.join(',')) : '<span class="muted">all</span>');
            showToast('Language scope updated');
        } catch (e) { alert(e); }
    });

    $('.act-mail').on('click', async function () {
        const uid = $(this).data('uid');
        const u = allUsers.find(u => u.id === uid);
        if (!u) return;
        if (!u.notification_consent) {
            alert('Cannot send: user has notifications disabled');
            return;
        }

        try {
            const prep = await prepareAdminReviewReminder(uid);
            let lastSent = 'Never';
            if (prep.last_review_reminder) {
                const date = prep.last_review_reminder.split("T")[0];
                const daysAgo = Math.floor((Date.now() - new Date(prep.last_review_reminder).getTime()) / (1000 * 3600 * 24));
                lastSent = `${daysAgo} days ago (${date})`;
            }

            const modalHtml = `
                <div id="email-modal" style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); display:flex; justify-content:center; align-items:center; z-index:9999;">
                    <div style="background:white; padding:20px; border-radius:2px; width:80%; max-width:600px; display:flex; flex-direction:column; gap:10px;">
                        <textarea id="email-body" style="width:100%; height:300px; padding:10px; font-family:monospace; background-color: #eee;">${esc(prep.email_body)}</textarea>
                        <div style="display:flex; gap:10px;">
                            <span style="margin:0; width: 400px; padding-top: 5px; display: inline-block; float: left;">Last reminder sent: ${lastSent}</span>
                            <button id="email-cancel" class="btn btn-success">Cancel</button>
                            <button id="email-send" class="btn btn-success">Send Email</button>
                        </div>
                    </div>
                </div>
            `;
            $('body').append(modalHtml);

            $('#email-cancel').on('click', () => $('#email-modal').remove());
            $('#email-send').on('click', async () => {
                const customBody = $('#email-body').val() as string;
                $('#email-modal').remove();
                try {
                    await sendAdminReviewReminder(uid, customBody);
                    showToast('Review reminder sent');
                } catch (e) { alert(e); }
            });

        } catch (e) { alert(e); }
    });
}

function applyFilter(): void {
    const q = ($('#filter-input').val() as string).toLowerCase().trim();
    const role = $('#role-filter').val() as string;
    const submittedStr = $('#submitted-filter').val() as string;
    const acceptedStr = $('#accepted-filter').val() as string;
    const submitted = submittedStr ? parseInt(submittedStr, 10) : -1;
    const accepted = acceptedStr ? parseInt(acceptedStr, 10) : -1;

    const filtered = allUsers.filter(u => {
        let highestRole = '';
        if (u.roles.includes('admin')) highestRole = 'admin';
        else if (u.roles.includes('reviewer')) highestRole = 'reviewer';
        else if (u.roles.includes('contributor')) highestRole = 'contributor';
        else if (u.roles.includes('api')) highestRole = 'api';

        const matchesRole = !role || highestRole === role;
        const matchesQuery = !q || u.username.toLowerCase().includes(q) || (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
        const matchesNonzero = (u.total_submitted || 0) >= submitted;
        const matchesAccepted = (u.total_accepted || 0) >= accepted;
        return matchesRole && matchesQuery && matchesNonzero && matchesAccepted;
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
        
        allLeaderboard = await getLeaderboard();
        renderLeaderboardTable(allLeaderboard);
    } catch { window.location.href = 'index.html'; }

    $('#filter-input').on('input', applyFilter);
    $('#role-filter').on('change', applyFilter);
    $('#submitted-filter').on('input', applyFilter);
    $('#accepted-filter').on('input', applyFilter);
});

function renderLeaderboardTable(entries: LeaderboardEntry[]): void {
    if (!entries.length) {
        $('#leaderboard-table').html('<div class="empty">No leaderboard submissions found</div>');
        return;
    }
    const rows = entries.map(e => {
        const info = e.info || {} as any;
        
        let actions = '';
        if (e.status === 'pending') {
            actions = `<button class="btn-underlined lb-score" data-uid="${e.id}">Score</button>`;
        } else if (e.status === 'scored') {
            if (e.visibility === 'hidden') {
                actions = `<button class="btn-underlined lb-show" data-uid="${e.id}">Publish</button>`;
            } else {
                actions = `<button class="btn-underlined lb-hide" data-uid="${e.id}">Unpublish</button>`;
            }
        }

        let editBtn = `<button class="btn-underlined lb-edit" data-uid="${e.id}">Edit</button>`;
        let delBtn = `<button class="btn-underlined lb-delete" data-uid="${e.id}">Delete</button>`;
        
        if (e.status === 'scoring') {
            editBtn = '';
        }

        let scoreStr = 'N/A';
        if (e.status === 'scored' && typeof info.score === 'number') {
            scoreStr = Math.round(info.score * 100).toString();
        }
        const statusDisplay = `${esc(e.visibility)}, ${esc(e.status)}, ${scoreStr}%`;

        let instDisplay = esc(info.institution || '—');
        if (info.submitter_email) {
            instDisplay = `<a style="color: black;" href="mailto:${esc(info.submitter_email)}">${instDisplay}</a>`;
        }

        return `<tr>
            <td>#${e.id}</td>
            <td title="${esc(info.submitter_email || info.institution)}">${instDisplay}</td>
            <td title="${esc(info.model_name)}">${esc(info.model_name || '—')}</td>
            <td>${esc(info.mode || '—')}</td>
            <td>${e.submissions?.length || 0} items</td>
            <td>${statusDisplay}</td>
            <td style='display: inline-flex; gap: 10px;'>${actions}${editBtn}${delBtn}</td>
        </tr>`;
    }).join('');

    $('#leaderboard-table').html(`<table style="table-layout: fixed; width: 100%;">
        <colgroup>
            <col style="width: 30px;">
            <col style="width: 120px;">
            <col style="width: 200px;">
            <col style="width: 50px;">
            <col style="width: 80px;">
            <col style="width: 120px;">
            <col style="width: 130px;">
        </colgroup>
        <thead><tr><th>ID</th><th>Institution</th><th>Model Name</th><th>Mode</th><th>Items</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>`);

    $('.lb-edit').on('click', function() {
        const uid = $(this).data('uid');
        const entry = allLeaderboard.find(x => x.id === uid);
        if (!entry) return;

        const infoStr = JSON.stringify(entry.info, null, 2);

        const modalHtml = `
            <div id="info-modal" style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); display:flex; justify-content:center; align-items:center; z-index:9999;">
                <div style="background:white; padding:20px; border-radius:2px; width:80%; max-width:600px; display:flex; flex-direction:column; gap:10px;">
                    <h3 style="margin-top:0">Edit leaderboard submission info</h3>
                    <textarea id="info-body" style="width:100%; height:300px; padding:10px; font-family:monospace; background-color: #eee;">${esc(infoStr)}</textarea>
                    <div style="display:flex; gap:10px; justify-content:flex-end;">
                        <button id="info-cancel" class="btn btn-secondary">Cancel</button>
                        <button id="info-save" class="btn btn-success">Save Info</button>
                    </div>
                </div>
            </div>
        `;
        $('body').append(modalHtml);

        $('#info-cancel').on('click', () => $('#info-modal').remove());
        $('#info-save').on('click', async () => {
            const rawBody = $('#info-body').val() as string;
            let parsedInfo;
            try {
                parsedInfo = JSON.parse(rawBody);
            } catch (e) {
                alert("Invalid JSON: " + e);
                return;
            }
            
            $('#info-modal').remove();
            try {
                await updateLeaderboardInfo(uid, parsedInfo);
                entry.info = parsedInfo;
                showToast('Info updated');
                renderLeaderboardTable(allLeaderboard);
            } catch (e) { alert(e); }
        });
    });

    $('.lb-score').on('click', async function () {
        const uid = $(this).data('uid');
        const entry = allLeaderboard.find(x => x.id === uid);
        if (!entry) return;
        try {
            await updateLeaderboard(uid, 'scoring', entry.visibility);
            entry.status = 'scoring';
            showToast('Leaderboard entry scoring in background');
            renderLeaderboardTable(allLeaderboard);
        } catch (e) { alert(e); }
    });

    $('.lb-show').on('click', async function () {
        const uid = $(this).data('uid');
        const entry = allLeaderboard.find(x => x.id === uid);
        if (!entry) return;
        try {
            await updateLeaderboard(uid, entry.status, 'visible');
            entry.visibility = 'visible';
            showToast('Leaderboard entry is now visible');
            renderLeaderboardTable(allLeaderboard);
        } catch (e) { alert(e); }
    });

    $('.lb-hide').on('click', async function () {
        const uid = $(this).data('uid');
        const entry = allLeaderboard.find(x => x.id === uid);
        if (!entry) return;
        try {
            await updateLeaderboard(uid, entry.status, 'hidden');
            entry.visibility = 'hidden';
            showToast('Leaderboard entry is now hidden');
            renderLeaderboardTable(allLeaderboard);
        } catch (e) { alert(e); }
    });

    $('.lb-delete').on('click', async function () {
        const uid = $(this).data('uid');
        if (!confirm('Are you sure you want to delete this leaderboard entry?')) return;
        try {
            await deleteLeaderboard(uid);
            allLeaderboard = allLeaderboard.filter(x => x.id !== uid);
            showToast('Leaderboard entry deleted');
            renderLeaderboardTable(allLeaderboard);
        } catch (e) { alert(e); }
    });
}
