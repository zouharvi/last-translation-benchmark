import './assets/style.css';
import $ from 'jquery';
import {
    getMe, getCookie,
    getSubmissions, scoreSubmission, User, renderRoleSwitcher,
    Submission, deleteSubmission, addComment,
} from './api';

import { esc as escHtml, fmtDate, scoreBadge, accessDenied, renderCommentThread, renderHeaderStatus, renderSource, sortSubmissions } from './utils';
import instructionsHtml from './assets/instructions.html';

let allSugs: Submission[] = [];
let curFilter = 'pending';
let curSort = 'last_updated';
let currentUser: User | null = null;

$(async () => {
    $('#instructions-box').html(instructionsHtml);
    if (!getCookie('ltb_token')) { window.location.href = 'index.html'; return; }

    try {
        currentUser = await getMe();
        renderHeaderStatus(currentUser);
        renderRoleSwitcher(currentUser.roles);
        if (!currentUser.roles.includes('reviewer')) {
            accessDenied(currentUser.roles, 'reviewer');
            return;
        }
        $('#sen-info').text(currentUser.username);
    } catch {
        window.location.href = 'index.html';
        return;
    }

    await loadSubmissions();

    // Status filter dropdown
    $('#filter-status').on('change', function () {
        curFilter = String($(this).val());
        loadSubmissions();
    });

    // Sort filter dropdown
    $('#filter-sort').on('change', function () {
        curSort = String($(this).val());
        renderList();
    });

    // Language / user filter selects
    $('#filter-source-lang, #filter-target-lang, #filter-user').on('change', loadSubmissions);

    $('#sen-list').on('click', '.score-btn:not(.comment-send-btn)', async function () {
        if ($(this).prop('disabled')) return;
        const id = parseInt(String($(this).data('id')));
        const action = String($(this).data('action')) as 'return' | 'accept' | 'comment';
        if (!['return', 'accept', 'comment'].includes(action)) return;
        if (action === 'comment') {
            // Toggle inline comment box instead of using prompt()
            const $box = $(`#comment-box-${id}`);
            const visible = $box.css('display') !== 'none';
            $box.css('display', visible ? 'none' : 'flex');
            if (!visible) {
                $box.find('.comment-input').trigger('focus');
                $(this).hide();
                $(`#sug-${id} .comment-send-btn`).css('display', 'inline-block');
            }
            return;
        }

        const isActive = $(this).hasClass('active');
        const targetAction = isActive ? 'pending' : action;

        try {
            await scoreSubmission(id, targetAction);
            const status = targetAction === 'accept' ? 'accept' : (targetAction === 'return' ? 'return' : 'pending');
            const sug = allSugs.find(s => s.id === id);
            if (sug) { sug.status = status; }
            const $item = $(`#sug-${id}`);
            $item.find('.score-btn').removeClass('active');
            if (targetAction !== 'pending') {
                $(this).addClass('active');
            }
            $item.find('.sug-meta .badge').replaceWith(scoreBadge(status, (sug?.comments?.length ?? 0) > 0));
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
            await addComment(id, text);
            const sug = allSugs.find(s => s.id === id);
            if (sug) {
                if (!sug.comments) sug.comments = [];
                sug.comments.push({ author: currentUser!.username, author_name: currentUser!.name, text, created_at: new Date().toISOString().slice(0, 16).replace('T', ' ') });
            }
            $input.val('');
            if (sug) {
                $(`#sug-${id} .sug-meta .badge`).replaceWith(scoreBadge(sug.status, true));
                $(`#comment-thread-${id}`).html(renderCommentThreadWrap(sug.comments));
            }
        } catch { alert('Failed to save'); }
        $(this).prop('disabled', false).text('Send');
    });

    // Delete submission (admin only)
    $('#sen-list').on('click', '.delete-btn', async function () {
        const id = parseInt(String($(this).data('id')));
        if (!confirm(`Are you sure you want to delete submission #${id}? In most cases you should return with a reason for return so that the contributor can fix their submission.`)) return;

        try {
            await deleteSubmission(id);
            allSugs = allSugs.filter(s => s.id !== id);
            $(`#sug-${id}`).fadeOut(250, function () {
                $(this).remove();
                if (!$('#sen-list .sug-item').length) {
                    $('#sen-list').html('<div class="empty">No submissions here</div>');
                }
            });
        } catch (err) {
            alert('Failed to delete: ' + err);
        }
    });
});

async function loadSubmissions(): Promise<void> {
    $('#sen-list').html('<div class="empty">Loading…</div>');
    const sourceLangVal = String($('#filter-source-lang').val() ?? '');
    const targetLangVal = String($('#filter-target-lang').val() ?? '');
    const userFilter = String($('#filter-user').val() ?? '');
    
    let source_langs = sourceLangVal === 'my_langs' ? [...(currentUser?.review_langs || []), 'English'] : (sourceLangVal ? [sourceLangVal] : []);
    let target_langs = targetLangVal === 'my_langs' ? [...(currentUser?.review_langs || []), 'English'] : (targetLangVal ? [targetLangVal] : []);

    try {
        allSugs = await getSubmissions('reviewer', {
            status: curFilter as 'pending' | 'accepted_or_returned' | 'accepted' | 'returned' | 'all',
            source_langs: source_langs,
            target_langs: target_langs,
            username: userFilter,
        });
        populateFilters();
        renderList();
    } catch {
        $('#sen-list').html('<div class="empty">Failed to load submissions</div>');
    }
}

function populateFilters(): void {
    const sourceLangVal = String($('#filter-source-lang').val() ?? '');
    const targetLangVal = String($('#filter-target-lang').val() ?? '');
    const userVal = String($('#filter-user').val() ?? '');

    const getOptions = (id: string) => {
        return $(id).find('option').map((_, el) => $(el).attr('value')).get().filter(v => v !== '');
    };

    const existingSourceLangs = getOptions('#filter-source-lang').filter(v => v !== 'my_langs');
    const existingTargetLangs = getOptions('#filter-target-lang').filter(v => v !== 'my_langs');
    const existingUsers = getOptions('#filter-user');

    const sourceLangs = [...new Set([...existingSourceLangs, ...allSugs.map(s => s.source_lang)])].sort();
    const targetLangs = [...new Set([...existingTargetLangs, ...allSugs.map(s => s.target_lang)])].sort();
    const users = [...new Set([...existingUsers, ...allSugs.map(s => s.username)])].sort();

    let mySourceLangsOption = '';
    let myTargetLangsOption = '';
    if (currentUser?.roles.includes('admin')) {
        mySourceLangsOption = `<option value="my_langs" ${sourceLangVal === 'my_langs' ? 'selected' : ''}>My languages only</option>`;
        myTargetLangsOption = `<option value="my_langs" ${targetLangVal === 'my_langs' ? 'selected' : ''}>My languages only</option>`;
    }

    $('#filter-source-lang').html('<option value="">All Source Languages</option>' + mySourceLangsOption +
        sourceLangs.map(l => `<option value="${l}"${l === sourceLangVal ? ' selected' : ''}>${escHtml(l)}</option>`).join(''));
    $('#filter-target-lang').html('<option value="">All Target Languages</option>' + myTargetLangsOption +
        targetLangs.map(l => `<option value="${l}"${l === targetLangVal ? ' selected' : ''}>${escHtml(l)}</option>`).join(''));
    const userDisplay = (u: string) => {
        const sub = allSugs.find(s => s.username === u);
        return sub?.user_name || u;
    };
    $('#filter-user').html('<option value="">All Users</option>' +
        users.map(u => `<option value="${u}"${u === userVal ? ' selected' : ''}>${escHtml(userDisplay(u))}</option>`).join(''));
}

function renderList(): void {
    const $el = $('#sen-list');
    if (!allSugs.length) { $el.html('<div class="empty">No submissions here</div>'); return; }
    sortSubmissions(allSugs, curSort, currentUser!.username);
    $el.html(allSugs.map(renderSug).join(''));
}

function renderCommentThreadWrap(comments: Submission['comments']): string {
    return renderCommentThread(comments, currentUser!.username);
}

function renderSug(s: Submission): string {
    const scoreActions: Array<['return' | 'accept', string, string]> = [
        ['return', '#ef4444', 'Return submission'],
        ['accept', '#22c55e', 'Accept submission'],
    ];
    const isOwner = s.username === currentUser!.username;
    const isAdmin = currentUser!.roles.includes('admin');
    const canScore = !(isOwner && !isAdmin);

    const scoreBtns = scoreActions.map(([action, color, label]) => {
        const act = (action === 'accept' && s.status === 'accept') || (action === 'return' && s.status === 'return') ? ' active' : '';
        const style = canScore
            ? `style="background:${color};color:#fff"`
            : `style="background:${color};color:#fff;opacity:0.3;cursor:not-allowed"`;
        const disabled = canScore ? '' : ' disabled';
        return `<button class="score-btn${act}" ${style}${disabled} data-id="${s.id}" data-action="${action}">${label}</button>`;
    }).join('');
    const deleteBtn = currentUser?.roles.includes('admin')
        ? `<button class="delete-btn btn-underlined" style="margin-left:8px;font-size:0.8em" data-id="${s.id}">Delete submission</button>`
        : '';
    const commentBtn = `<button class="score-btn" style="background:#64748b;color:#fff;margin-left:auto" data-id="${s.id}" data-action="comment">Comment submission</button>`;
    const sendBtn = `<button class="score-btn comment-send-btn" style="background:#64748b;color:#fff;display:none;margin-left:auto" data-id="${s.id}">Send comment</button>`;
    const btns = scoreBtns + deleteBtn + commentBtn + sendBtn;


    const trRows = s.translations.map(t => {
        const badge = Array.isArray(t.verified)
            ? t.verified.map(v => v ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>').join('')
            : '';
        return `<div class="translation-result-row">
          <span class="api-name">${escHtml(t.model)}</span>
          <div class="tr-display">${escHtml(t.translation)}</div>
          <div style="display: flex; gap: 4px; flex-wrap: wrap;">${badge}</div>
        </div>`;
    }).join('');

    const ruleRows = s.verification_rules.map(r => {
        return `<div class="sug-box" style="margin-bottom:4px; font-size: 0.9em;">
            <div class="lbl"">VERIFICATION</div>
            ${escHtml(r.value)}
        </div>`;
    }).join('');

    return `<div class="sug-item" id="sug-${s.id}">
        <div class="sug-meta">#${s.id} &middot; <b>${escHtml(s.user_name || s.username)}</b> &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.status, (s.comments?.length ?? 0) > 0)}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">INPUT</div>${renderSource(s)}</div>
        <div style="margin-bottom:8px">${trRows}</div>
        <div style="margin-bottom:8px">${ruleRows}</div>
        <div id="comment-thread-${s.id}">${renderCommentThreadWrap(s.comments)}</div>
        <div id="comment-box-${s.id}" style="display:none;margin-top:8px;flex-direction:row;align-items:flex-start;gap:6px">
            <textarea class="comment-input" placeholder="Write a comment for the contributor…" rows="2" style="flex:1;margin-bottom:0"></textarea>
        </div>
        <div class="sug-scoring">${btns}</div>
    </div>`;
}
