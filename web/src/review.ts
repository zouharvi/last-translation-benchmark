import './style.css';
import $ from 'jquery';
import {
    getMe, getCookie,
    getSubmissions, scoreSubmission, addComment, renderRoleSwitcher,
    Submission,
} from './api';

import { esc as escHtml, fmtDate, scoreBadge, accessDenied, renderCommentThread, setupInstructions } from './utils';

let allSugs: Submission[] = [];
let curFilter = 'pending';

$(async () => {
    setupInstructions('all');
    if (!getCookie('ltb_token')) { window.location.href = 'index.html'; return; }

    try {
        const user = await getMe();
        renderRoleSwitcher(user.roles);
        if (!user.roles.includes('reviewer')) {
            accessDenied(user.roles, 'reviewer');
            return;
        }
        $('#sen-info').text(user.username);
    } catch {
        window.location.href = 'index.html';
        return;
    }

    await loadSubmissions();

    // Status filter dropdown
    $('#filter-status').on('change', function () {
        curFilter = String($(this).val());
        renderList();
    });

    // Language / user filter selects
    $('#filter-source-lang, #filter-target-lang, #filter-user').on('change', renderList);

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
            $(`#comment-thread-${id}`).html(renderCommentThreadWrap(sug?.comments ?? []));
        } catch { alert('Failed to save'); }
        $(this).prop('disabled', false).text('Send');
    });
});

async function loadSubmissions(): Promise<void> {
    $('#sen-list').html('<div class="empty">Loading…</div>');
    try {
        allSugs = await getSubmissions('reviewer');
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
    let list = allSugs;
    if (curFilter === 'pending') list = list.filter(s => s.points < 0);
    else if (curFilter === 'scored') list = list.filter(s => s.points >= 0);

    const sourceLangFilter = String($('#filter-source-lang').val() ?? '');
    const targetLangFilter = String($('#filter-target-lang').val() ?? '');
    const userFilter = String($('#filter-user').val() ?? '');
    if (sourceLangFilter) list = list.filter(s => s.source_lang === sourceLangFilter);
    if (targetLangFilter) list = list.filter(s => s.target_lang === targetLangFilter);
    if (userFilter) list = list.filter(s => s.username === userFilter);

    const $el = $('#sen-list');
    if (!list.length) { $el.html('<div class="empty">No submissions here</div>'); return; }
    $el.html(list.map(renderSug).join(''));
}

function renderCommentThreadWrap(comments: Submission['comments']): string {
    return renderCommentThread(comments, 'reviewer');
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

    const ruleRows = s.verification_rules.map(r => {
        let label = "LLM-VERIFICATION";

        return `<div class="sug-box" style="margin-bottom:4px; font-size: 0.9em;">
            <div class="lbl" style="font-size: 0.7em;">RULE: ${label}</div>
            ${escHtml(r.value)}
        </div>`;
    }).join('');

    return `<div class="sug-item" id="sug-${s.id}">
        <div class="sug-meta">#${s.id} &middot; <b>${escHtml(s.username)}</b> &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.points, s.reviewer_comment)}</div>
        <div class="sug-box" style="margin-bottom:8px"><div class="lbl">SOURCE</div>${renderSource(s)}</div>
        <div style="margin-bottom:8px">${trRows}</div>
        <div style="margin-bottom:8px">${ruleRows}</div>
        <div id="comment-thread-${s.id}">${renderCommentThreadWrap(s.comments)}</div>
        <div id="comment-box-${s.id}" style="display:none;margin-top:8px;flex-direction:row;align-items:flex-start;gap:6px">
            <textarea class="comment-input" placeholder="Write a comment for the contributor…" rows="2" style="flex:1;margin-bottom:0"></textarea>
            <button class="comment-send-btn score-btn" style="background:#64748b;color:#fff;align-self:stretch" data-id="${s.id}">Send</button>
        </div>
        <div class="sug-scoring">${btns}</div>
    </div>`;
}
