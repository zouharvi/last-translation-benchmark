import './assets/style.css';
import $ from 'jquery';
import {
    getMe, getCookie,
    getSubmissions, scoreSubmission, User, renderRoleSwitcher,
    Submission, deleteSubmission,
} from './api';

import { esc as escHtml, fmtDate, scoreBadge, accessDenied, renderCommentThread, setupInstructions } from './utils';

let allSugs: Submission[] = [];
let curFilter = 'pending';
let currentUser: User | null = null;

$(async () => {
    setupInstructions('all');
    if (!getCookie('ltb_token')) { window.location.href = 'index.html'; return; }

    try {
        currentUser = await getMe();
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

    // Language / user filter selects
    $('#filter-source-lang, #filter-target-lang, #filter-user').on('change', loadSubmissions);

    // Refresh
    $('#refresh-btn').on('click', loadSubmissions);

    // Action buttons (event delegation — list re-renders on each load)
    $('#sen-list').on('click', '.score-btn:not(.comment-send-btn)', async function () {
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
                $(this).hide();
                $(`#sug-${id} .comment-send-btn`).css('display', 'inline-block');
            }
            return;
        }

        const isActive = $(this).hasClass('active');
        const targetAction = isActive ? 'pending' : action;

        try {
            await scoreSubmission(id, targetAction);
            const status = targetAction === 'accept' ? 'accept' : (targetAction === 'reject' ? 'reject' : 'pending');
            const sug = allSugs.find(s => s.id === id);
            if (sug) { sug.status = status; }
            const $item = $(`#sug-${id}`);
            $item.find('.score-btn').removeClass('active');
            if (targetAction !== 'pending') {
                $(this).addClass('active');
            }
            $item.find('.sug-meta .badge').replaceWith(scoreBadge(status, (sug?.comments?.length ?? 0) > 0));

            let matchesFilter = true;
            if (curFilter === 'pending') {
                matchesFilter = status === 'pending';
            } else if (curFilter === 'accepted_or_rejected') {
                matchesFilter = status === 'accept' || status === 'reject';
            } else if (curFilter === 'accepted') {
                matchesFilter = status === 'accept';
            } else if (curFilter === 'rejected') {
                matchesFilter = status === 'reject';
            }

            if (!matchesFilter) {
                setTimeout(() => {
                    $item.fadeOut(250, function () {
                        $(this).remove();
                        if (!$('#sen-list .sug-item').length) {
                            $('#sen-list').html('<div class="empty">No submissions here</div>');
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
                sug.status = 'pending';
                if (!sug.comments) sug.comments = [];
                sug.comments.push({ author: currentUser!.username, text, timestamp: new Date().toISOString().slice(0, 16).replace('T', ' ') });
            }
            $input.val('');
            $(`#sug-${id} .sug-meta .badge`).replaceWith(scoreBadge('pending', true));
            $(`#comment-thread-${id}`).html(renderCommentThreadWrap(sug?.comments ?? []));
        } catch { alert('Failed to save'); }
        $(this).prop('disabled', false).text('Send');
    });

    // Delete submission (admin only)
    $('#sen-list').on('click', '.delete-btn', async function () {
        const id = parseInt(String($(this).data('id')));
        if (!confirm(`Are you sure you want to delete submission #${id}? In most cases you should reject with a reason for rejection so that the contributor can fix their submission.`)) return;

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
    const sourceLangFilter = String($('#filter-source-lang').val() ?? '');
    const targetLangFilter = String($('#filter-target-lang').val() ?? '');
    const userFilter = String($('#filter-user').val() ?? '');
    try {
        allSugs = await getSubmissions('reviewer', {
            status: curFilter as 'pending' | 'accepted_or_rejected' | 'accepted' | 'rejected' | 'all',
            source_lang: sourceLangFilter,
            target_lang: targetLangFilter,
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
    const sourceLangs = [...new Set(allSugs.map(s => s.source_lang))];
    const targetLangs = [...new Set(allSugs.map(s => s.target_lang))];
    const users = [...new Set(allSugs.map(s => s.username))];
    $('#filter-source-lang').html('<option value="">All Source Languages</option>' +
        sourceLangs.map(l => `<option value="${l}"${l === sourceLangVal ? ' selected' : ''}>${escHtml(l)}</option>`).join(''));
    $('#filter-target-lang').html('<option value="">All Target Languages</option>' +
        targetLangs.map(l => `<option value="${l}"${l === targetLangVal ? ' selected' : ''}>${escHtml(l)}</option>`).join(''));
    $('#filter-user').html('<option value="">All Users</option>' +
        users.map(u => `<option value="${u}"${u === userVal ? ' selected' : ''}>${escHtml(u)}</option>`).join(''));
}

function renderList(): void {
    const $el = $('#sen-list');
    if (!allSugs.length) { $el.html('<div class="empty">No submissions here</div>'); return; }
    $el.html(allSugs.map(renderSug).join(''));
}

function renderCommentThreadWrap(comments: Submission['comments']): string {
    return renderCommentThread(comments, currentUser!.username);
}

function renderSource(s: Submission): string {
    const isAudio = s.source_media && /^data:audio/.test(s.source_media);
    let out = '';
    if (s.source_media) {
        out += isAudio
            ? `<audio controls src="${s.source_media}" class="context_audio"></audio>`
            : `<img src="${s.source_media}" class="context_image">`;
    }
    if (s.source_text) out += escHtml(s.source_text);
    return out;
}

function renderSug(s: Submission): string {
    const scoreActions: Array<['reject' | 'accept', string, string]> = [
        ['reject', '#ef4444', 'Reject submission'],
        ['accept', '#22c55e', 'Accept submission'],
    ];
    const scoreBtns = scoreActions.map(([action, color, label]) => {
        const act = (action === 'accept' && s.status === 'accept') || (action === 'reject' && s.status === 'reject') ? ' active' : '';
        return `<button class="score-btn${act}" style="background:${color};color:#fff" data-id="${s.id}" data-action="${action}">${label}</button>`;
    }).join('');
    const deleteBtn = currentUser?.roles.includes('admin')
        ? `<button class="delete-btn btn-underlined" style="margin-left:8px;font-size:0.8em" data-id="${s.id}">Delete submission</button>`
        : '';
    const commentBtn = `<button class="score-btn" style="background:#64748b;color:#fff;margin-left:auto" data-id="${s.id}" data-action="comment">Comment submission</button>`;
    const sendBtn = `<button class="score-btn comment-send-btn" style="background:#64748b;color:#fff;display:none;margin-left:auto" data-id="${s.id}">Send comment</button>`;
    const btns = scoreBtns + deleteBtn + commentBtn + sendBtn;


    const trRows = s.translations.map(t => {
        const badge = t.verified === true
            ? '<span class="vpill vpill-pass">✓</span>'
            : t.verified === false
                ? '<span class="vpill vpill-fail">✗</span>'
                : '';
        return `<div class="api-result-row">
          <span class="api-name">${escHtml(t.model)}</span>
          <div class="tr-display">${escHtml(t.translation)}</div>
          ${badge}
        </div>`;
    }).join('');

    const ruleRows = s.verification_rules.map(r => {
        let label = "LLM-VERIFICATION";

        return `<div class="sug-box" style="margin-bottom:4px; font-size: 0.9em;">
            <div class="lbl" style="font-size: 0.7em;">RULE: ${label}</div>
            ${escHtml(r.value)}
        </div>`;
    }).join('');

    return `<div class="sug-item" id="sug-${s.id}">
        <div class="sug-meta">#${s.id} &middot; <b>${escHtml(s.username)}</b> &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.status, (s.comments?.length ?? 0) > 0)}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">SOURCE</div>${renderSource(s)}</div>
        <div style="margin-bottom:8px">${trRows}</div>
        <div style="margin-bottom:8px">${ruleRows}</div>
        <div id="comment-thread-${s.id}">${renderCommentThreadWrap(s.comments)}</div>
        <div id="comment-box-${s.id}" style="display:none;margin-top:8px;flex-direction:row;align-items:flex-start;gap:6px">
            <textarea class="comment-input" placeholder="Write a comment for the contributor…" rows="2" style="flex:1;margin-bottom:0"></textarea>
        </div>
        <div class="sug-scoring">${btns}</div>
    </div>`;
}
