import './style.css';
import $ from 'jquery';
import {
    getToken, getMe,
    getSubmissions, scoreSubmission, addComment, renderRoleSwitcher,
    Submission,
} from './api';

let allSugs: Submission[] = [];
let curFilter = 'pending';

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    try {
        const user = await getMe();
        renderRoleSwitcher(user.roles);
        if (!user.roles.includes('reviewer')) {
            document.body.innerHTML = `<div style="padding: 2rem; text-align: center; font-family: sans-serif;">
                <h2>Access Denied</h2>
                <p>You have the following roles: ${user.roles.join(', ')}, which does not match "reviewer" which you're trying to access.</p>
            </div>`;
            return;
        }
        $('#sen-info').text(`${user.username} · Reviewer`);
    } catch {
        window.location.href = '/';
        return;
    }

    await loadSubmissions();

    // Status filter dropdown
    $('#filter-status').on('change', function () {
        curFilter = String($(this).val());
        renderList();
    });

    // Language / user filter selects
    $('#filter-lang, #filter-user').on('change', renderList);

    // Refresh
    $('#refresh-btn').on('click', loadSubmissions);

    // Action buttons (event delegation — list re-renders on each load)
    $('#sen-list').on('click', '.score-btn', async function () {
        const id = parseInt(String($(this).data('id')));
        const action = String($(this).data('action')) as 'reject' | 'accept' | 'comment';
        if (!['reject', 'accept', 'comment'].includes(action)) return;
        if (action === 'comment') {
            // Toggle inline comment box instead of using prompt()
            const $box = $(`#comment-box-${id}`);
            const visible = $box.css('display') !== 'none';
            $box.css('display', visible ? 'none' : 'flex');
            if (!visible) {
                $box.find('.comment-input').trigger('focus');
            }
            return;
        }

        try {
            await scoreSubmission(id, action);
            const points = action === 'accept' ? 1 : 0;
            const sug = allSugs.find(s => s.id === id);
            if (sug) { sug.points = points; sug.reviewer_comment = ''; }
            const $item = $(`#sug-${id}`);
            $item.find('.score-btn').removeClass('active');
            $(this).addClass('active');
            $item.find('.sug-meta .badge').replaceWith(scoreBadge(points, ''));
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
        } catch { alert('Failed to save'); }
    });

    // Send comment from inline box
    $('#sen-list').on('click', '.comment-send-btn', async function () {
        const id = parseInt(String($(this).data('id')));
        const $input = $(`#comment-box-${id} .comment-input`);
        const text = String($input.val() ?? '').trim();
        if (!text) return;

        $(this).prop('disabled', true).text('Sending…');
        try {
            await scoreSubmission(id, 'comment', text);
            const sug = allSugs.find(s => s.id === id);
            if (sug) {
                sug.points = -1;
                sug.reviewer_comment = text;
                if (!sug.comments) sug.comments = [];
                sug.comments.push({ author: 'You', role: 'reviewer', text, timestamp: new Date().toISOString().slice(0, 16).replace('T', ' ') });
            }
            $input.val('');
            $(`#comment-box-${id}`).hide();
            $(`#sug-${id} .sug-meta .badge`).replaceWith(scoreBadge(-1, text));
            $(`#comment-thread-${id}`).html(renderCommentThread(sug?.comments ?? []));
        } catch { alert('Failed to save'); }
        $(this).prop('disabled', false).text('Send');
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

function renderCommentThread(comments: Submission['comments']): string {
    if (!comments || !comments.length) return '';
    // On the reviewer screen, reviewer = "own" → right; contributor = "foreign" → left
    const classFor = (role: string) =>
        role === 'reviewer' ? 'comment-msg-contributor' : 'comment-msg-reviewer';
    return `<div class="comment-thread">${comments.map(c => `
        <div class="comment-msg ${classFor(c.role)}">
            <span class="comment-author">${escHtml(c.author)}</span>
            <span class="comment-ts">${escHtml(c.timestamp)}</span>
            <div class="comment-body">${escHtml(c.text)}</div>
        </div>`).join('')}</div>`;
}

function renderSug(s: Submission): string {
    const scoreActions: Array<['reject' | 'accept', string, string]> = [
        ['reject', '#ef4444', 'Reject'],
        ['accept', '#22c55e', 'Accept'],
    ];
    const scoreBtns = scoreActions.map(([action, color, label]) => {
        const act = (action === 'accept' && s.points === 1) || (action === 'reject' && s.points === 0) ? ' active' : '';
        return `<button class="score-btn${act}" style="background:${color};color:#fff" data-id="${s.id}" data-action="${action}">${label}</button>`;
    }).join('');
    const commentBtn = `<button class="score-btn" style="background:#64748b;color:#fff" data-id="${s.id}" data-action="comment">Comment</button>`;
    const btns = scoreBtns + commentBtn;

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

    const threadHtml = renderCommentThread(s.comments);

    return `<div class="sug-item" id="sug-${s.id}">
        <div class="sug-meta">#${s.id} &middot; <b>${escHtml(s.username)}</b> &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.points, s.reviewer_comment)}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">SOURCE</div>${escHtml(s.source_text)}</div>
        <div style="margin-bottom:8px">${trRows}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">VERIFICATION RULE</div>${escHtml(s.verification_rule)}</div>
        <div id="comment-thread-${s.id}">${threadHtml}</div>
        <div id="comment-box-${s.id}" style="display:none;margin-top:8px;flex-direction:row;align-items:flex-start;gap:6px">
            <textarea class="comment-input" placeholder="Write a comment for the contributor…" rows="2" style="flex:1;margin-bottom:0"></textarea>
            <button class="comment-send-btn score-btn" style="background:#64748b;color:#fff;align-self:stretch" data-id="${s.id}">Send</button>
        </div>
        <div class="sug-scoring">${btns}</div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number, comment?: string): string {
    if (p < 0) {
        if (comment) return '<span class="badge badge-score-1">💬 Commented</span>';
        return '<span class="badge badge-pending">Pending</span>';
    }
    const labels = ['✗ Rejected', '✓ Accepted'];
    return `<span class="badge badge-score-${p === 1 ? 3 : 0}">${labels[p] ?? String(p)}</span>`;
}
