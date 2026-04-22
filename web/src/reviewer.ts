import './style.css';
import $ from 'jquery';
import {
    getToken, clearToken, getMe, logout,
    getSubmissions, scoreSubmission,
    Submission,
} from './api';

let allSugs: Submission[] = [];
let curFilter = 'pending';

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    try {
        const user = await getMe();
        if (user.role !== 'reviewer') { window.location.href = '/contributor.html'; return; }
        $('#sen-info').text(`${user.username} · Reviewer Reviewer`);
    } catch {
        clearToken();
        window.location.href = '/';
        return;
    }

    await loadSubmissions();

    // Filter tabs
    $('.tab[data-filter]').on('click', function () {
        curFilter = String($(this).data('filter'));
        $('.tab[data-filter]').removeClass('active');
        $(this).addClass('active');
        renderList();
    });

    // Language / user filter selects
    $('#filter-lang, #filter-user').on('change', renderList);

    // Refresh
    $('#refresh-btn').on('click', loadSubmissions);

    // Score buttons (event delegation — list re-renders on each load)
    $('#sen-list').on('click', '.score-btn', async function () {
        const id = parseInt(String($(this).data('id')));
        const points = parseInt(String($(this).data('points')));
        try {
            await scoreSubmission(id, points);
            const sug = allSugs.find(s => s.id === id);
            if (sug) sug.points = points;
            const $item = $(`#sug-${id}`);
            $item.find('.score-btn').removeClass('active');
            $(this).addClass('active');
            $item.find('.sug-meta .badge').replaceWith(scoreBadge(points));
            if (curFilter === 'pending') {
                setTimeout(() => {
                    $item.fadeOut(250, function () {
                        $(this).remove();
                        if (!$('#sen-list .sug-item').length) {
                            $('#sen-list').html('<div class="empty">No pending submissions</div>');
                        }
                    });
                }, 400);
            }
        } catch { alert('Failed to save score'); }
    });

    // Logout
    $('#logout-btn').on('click', async () => {
        try { await logout(); } finally { clearToken(); window.location.href = '/'; }
    });
});

async function loadSubmissions(): Promise<void> {
    $('#sen-list').html('<div class="empty">Loading…</div>');
    try {
        allSugs = await getSubmissions();
        populateFilters();
        renderList();
    } catch {
        $('#sen-list').html('<div class="empty">Failed to load submissions</div>');
    }
}

function populateFilters(): void {
    const langVal = String($('#filter-lang').val() ?? '');
    const userVal = String($('#filter-user').val() ?? '');
    const langs = [...new Set(allSugs.map(s => `${s.source_lang}→${s.target_lang}`))];
    const users = [...new Set(allSugs.map(s => s.username))];
    $('#filter-lang').html('<option value="">All Languages</option>' +
        langs.map(l => `<option value="${l}"${l === langVal ? ' selected' : ''}>${escHtml(l)}</option>`).join(''));
    $('#filter-user').html('<option value="">All Users</option>' +
        users.map(u => `<option value="${u}"${u === userVal ? ' selected' : ''}>${escHtml(u)}</option>`).join(''));
}

function renderList(): void {
    let list = allSugs;
    if (curFilter === 'pending') list = list.filter(s => s.points < 0);
    else if (curFilter === 'scored') list = list.filter(s => s.points >= 0);

    const langFilter = String($('#filter-lang').val() ?? '');
    const userFilter = String($('#filter-user').val() ?? '');
    if (langFilter) list = list.filter(s => `${s.source_lang}→${s.target_lang}` === langFilter);
    if (userFilter) list = list.filter(s => s.username === userFilter);

    const $el = $('#sen-list');
    if (!list.length) { $el.html('<div class="empty">No submissions here</div>'); return; }
    $el.html(list.map(renderSug).join(''));
}

function renderSug(s: Submission): string {
    const btnColors = ['#ef4444', '#f59e0b', '#22c55e'];
    const btns = ([0, 1, 2] as const).map(p => {
        const act = s.points === p ? ' active' : '';
        return `<button class="score-btn${act}" style="background:${btnColors[p]};color:#fff" data-id="${s.id}" data-points="${p}">${p}</button>`;
    }).join('');

    const trRows = s.translations.map(t => {
        const badge = t.verified === true
            ? '<span class="vpill vpill-pass">✓</span>'
            : t.verified === false
                ? '<span class="vpill vpill-fail">✗</span>'
                : '';
        return `<div class="api-result-row">
          <span class="api-name">${escHtml(t.api)}</span>
          <div class="tr-display">${escHtml(t.translation)}</div>
          ${badge}
        </div>`;
    }).join('');

    return `<div class="sug-item" id="sug-${s.id}">
        <div class="sug-meta">#${s.id} &middot; <b>${escHtml(s.username)}</b> &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.points)}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">SOURCE</div>${escHtml(s.source_text)}</div>
        <div style="margin-bottom:8px">${trRows}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">VERIFICATION RULE</div>${escHtml(s.verification_rule)}</div>
        <div class="sug-scoring"><span class="score-label">Score:</span>${btns}</div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number): string {
    if (p < 0) return '<span class="badge badge-pending">Pending</span>';
    const labels = ['0 · Rejected', '1 · Good', '2 · Excellent'];
    return `<span class="badge badge-score-${p}">${labels[p]}</span>`;
}
