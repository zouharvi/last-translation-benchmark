import './assets/style.css';
import $ from 'jquery';
import {
    getMe, getCookie,
    translate, verify, createSubmission, updateSubmission, getSubmissions, addComment, renderRoleSwitcher,
    User, Submission, Rule,
} from './api';

import { esc as escHtml, fmtDate, scoreBadge, accessDenied, renderCommentThread, renderHeaderStatus, renderSource, sortSubmissions } from './utils';
import instructionsHtml from './assets/instructions.html';

let currentUser: User | null = null;

// Last set of API translation results
type ApiResult = { model: string; translation: string | null; error: string | null; verified?: boolean[] | null };
let lastResults: ApiResult[] = [];
let ownVerified: boolean[] | null = null;
let editingSubmissionId: number | null = null;
let allMySubmissions: Submission[] = [];
let lastMediaData: string | null = null;
let rules: Rule[] = [{ value: '' }];
let inputCorrespondsToTranslations = true;
let curSort = 'last_updated';




$(async () => {
    $('#instructions-box').html(instructionsHtml);
    if (!getCookie('ltb_token')) { window.location.href = 'index.html'; return; }

    let LANGUAGES: string[] = [];
    try {
        LANGUAGES = await (await fetch('languages.json')).json();
    } catch (e) {
        console.error('Failed to load languages', e);
    }

    const langOptions = LANGUAGES.map(name => `<option value="${name}">${name}</option>`).join('');
    $('#src-langs').html(langOptions);
    $('#tgt-langs').html(langOptions);

    try {
        currentUser = await getMe();
        renderHeaderStatus(currentUser);
        renderRoleSwitcher(currentUser.roles);
        if (!currentUser.roles.includes('contributor')) {
            accessDenied(currentUser.roles, 'contributor');
            return;
        }
    } catch {
        window.location.href = 'index.html';
        return;
    }


    loadMySubmissions();
    $('#filter-pending, #filter-returned, #filter-accepted').on('change', () => {
        renderFilteredSubmissions();
    });
    $('#filter-sort').on('change', function () {
        curSort = String($(this).val());
        renderFilteredSubmissions();
    });
    renderRules();
    updateButtonStates();

    // Input type toggle
    $('#add-media-btn').on('click', () => {
        const file = ($('#src-file')[0] as HTMLInputElement).files?.[0];
        if (file || lastMediaData) {
            ($('#src-file')[0] as HTMLInputElement).value = '';
            lastMediaData = null;
            $('#media-preview').empty();
            $('#add-media-btn').text('Add image/audio/video');
            inputCorrespondsToTranslations = false;
            invalidateVerification();
            updateButtonStates();
        } else {
            $('#src-file').trigger("click");
        }
    });

    $('#add-context-btn').on('click', () => {
        const isHidden = $('#src-instructions').is(':hidden');
        if (isHidden) {
            $('#src-instructions').show().trigger('focus');
            $('#add-context-btn').text('Remove instructions/context');
        } else {
            $('#src-instructions').hide().val('');
            $('#add-context-btn').text('Add instructions/context');
            inputCorrespondsToTranslations = false;
            invalidateVerification();
            updateButtonStates();
        }
    });

    $('#src-file').on('change', function () {
        const file = (this as HTMLInputElement).files?.[0];
        if (!file) return;
        $('#media-preview').empty();

        const isAudio = /\.(mp3|wav)$/i.test(file.name);
        const isVideo = /\.(mp4|webm|mpeg|mov)$/i.test(file.name);
        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = String(e.target?.result ?? '');
            lastMediaData = dataUrl;
            let mediaTag = `<img class="context_image" src="${dataUrl}">`;
            if (isAudio) mediaTag = `<audio class="context_audio" controls src="${dataUrl}"></audio>`;
            else if (isVideo) mediaTag = `<video class="context_video" controls src="${dataUrl}" style="max-width:100%; max-height:150px;"></video>`;

            $('#media-preview').html(mediaTag);
            $('#add-media-btn').text('Remove media');
            inputCorrespondsToTranslations = false;
            invalidateVerification();
            updateButtonStates();
        };
        reader.readAsDataURL(file);
    });



    $('#add-rule-btn').on('click', () => {
        if (rules.length >= 10) return;
        rules.push({ value: '' });
        renderRules();
        invalidateVerification();
        updateButtonStates();
    });


    $('#rules-container').on('input', '.rule-value', function () {
        const index = $(this).closest('.rule-row').data('index');
        rules[index].value = $(this).val() as string;
        invalidateVerification();
        updateButtonStates();
    });

    $('#rules-container').on('click', '.rule-remove', function () {
        const index = $(this).closest('.rule-row').data('index');
        rules.splice(index, 1);
        renderRules();
        invalidateVerification();
        updateButtonStates();
    });

    $('#own-translation').on('input', () => {
        ownVerified = null;
        $('#own-verify-badge').empty();
        $('#pass-count').empty();
        updateButtonStates();
    });

    $('#src-text, #src-instructions, #src-lang, #tgt-lang').on('input change', () => {
        inputCorrespondsToTranslations = false;
        invalidateVerification();
        updateButtonStates();
    });


    // Translate by server
    $('#tr-btn').on('click', async () => {
        const srcLang = String($('#src-lang').val());
        const tgtLang = String($('#tgt-lang').val());
        $('#tr-btn').prop('disabled', true);
        $('#tr-status').text('Translating…');
        try {
            const text = String($('#src-text').val() ?? '').trim();
            const instVal = $('#src-instructions').is(':visible') ? String($('#src-instructions').val() ?? '').trim() : '';
            const data = await translate(text, srcLang, tgtLang, lastMediaData ?? undefined, instVal || undefined);

            lastResults = data.results;
            currentUser!.quota_used = data.quota_used;
            currentUser!.quota = data.quota;
            renderHeaderStatus(currentUser!);
            renderApiResults();
            lastResults.forEach(r => r.verified = null);
            ownVerified = null;
            inputCorrespondsToTranslations = true;
            $('#pass-count').text('');
            $('#verify-result').text('');
            $('#tr-status').text('');
        } catch (err) {
            console.error('translate error:', err);
            $('#tr-status').html(`<span class="msg-err">✗ ${escHtml(err instanceof Error ? err.message : JSON.stringify(err))}</span>`);
        } finally {
            $('#tr-btn').prop('disabled', false);
            updateButtonStates();
        }
    });


    // Test verification (on all translations)
    $('#verify-btn').on('click', async () => {
        // clear previous status
        $('#submit-status').text('');
        const mtTranslations = lastResults.map(r => r.translation).filter(t => t !== null) as string[];
        const ownTranslation = String($('#own-translation').val() ?? '').trim();
        const translations = [...mtTranslations];
        if (ownTranslation) translations.push(ownTranslation);

        if (translations.length === 0) { $('#verify-result').html('<span class="msg-err">No translations available</span>'); return; }
        if (rules.length === 0) { $('#verify-result').html('<span class="msg-err">No verification rules</span>'); return; }
        if (rules.some(r => !r.value.trim())) { $('#verify-result').html('<span class="msg-err">All rules must have content</span>'); return; }

        $('#verify-btn').prop('disabled', true);
        $('#submit-btn').prop('disabled', true);
        $('#verify-result').html('<span style="color:#64748b;font-size:0.9em">Verifying...</span>');
        try {
            const source_text = String($('#src-text').val() ?? '').trim();
            const data = await verify(source_text, translations, rules, lastMediaData ?? undefined);

            currentUser!.quota_used = data.quota_used;
            currentUser!.quota = data.quota;
            renderHeaderStatus(currentUser!);

            let resultIdx = 0;
            let pass = 0;
            lastResults.forEach((r, i) => {
                if (r.translation !== null) {
                    const verified: boolean[] = data.results[resultIdx++];
                    r.verified = verified;
                    const badge = verified.map(v => v ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>').join('');
                    $(`[data-idx="${i}"]`).html(badge);
                    if (verified.every(v => v)) pass++;
                } else {
                    $(`[data-idx="${i}"]`).html('');
                }
            });

            if (ownTranslation) {
                const verified: boolean[] = data.results[resultIdx++];
                ownVerified = verified;
                const badge = verified.map(v => v ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>').join('');
                $('#own-verify-badge').html(badge);
                if (verified.every(v => v)) pass++;
            } else {
                ownVerified = null;
                $('#own-verify-badge').html('');
            }

            const cls = pass === 0 ? 'count-fail' : (pass === translations.length ? 'count-pass' : 'count-partial');
            $('#verify-result').html("");
            $('#pass-count').html(`<span class="${cls}">${pass}/${translations.length} pass verification</span>`);
        } catch (err) {
            $('#verify-result').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        } finally {
            updateButtonStates();
        }
    });

    // Submit or Update submission
    $('#submit-btn').on('click', async () => {
        const source_text = String($('#src-text').val() ?? '').trim();
        const ownTranslation = String($('#own-translation').val() ?? '').trim();

        const translations: Array<{ model: string; translation: string; verified: boolean[] | null }> = [];
        lastResults.forEach(r => {
            if (r.translation !== null) {
                translations.push({ model: r.model, translation: r.translation, verified: r.verified ?? null });
            }
        });
        if (ownTranslation) {
            translations.push({ model: 'human', translation: ownTranslation, verified: ownVerified ?? null });
        }

        const source_lang = String($('#src-lang').val());
        const target_lang = String($('#tgt-lang').val());

        if (translations.length === 0 || rules.length === 0) {
            $('#submit-status').html('<span class="msg-err">Please fill all required fields, translate and verify translations first</span>');
            return;
        }
        if (rules.some(r => !r.value.trim())) {
            $('#submit-status').html('<span class="msg-err">All rules must have content</span>');
            return;
        }

        if (!ownTranslation) {
            $('#submit-status').html('<span class="msg-err">A human translation is required</span>');
            return;
        }
        if (ownVerified === null) {
            $('#submit-status').html('<span class="msg-err">Please verify translations before submitting</span>');
            return;
        }
        if (ownVerified !== null && !ownVerified.every(v => v)) {
            $('#submit-status').html('<span class="msg-err">Human translation must pass verification</span>');
            return;
        }

        const mtPassCount = lastResults.filter(r => r.verified != null && r.verified.every(v => v)).length;
        if (mtPassCount > 2) {
            $('#submit-status').html('<span class="msg-err">At most two MT translations can pass verification</span>');
            return;
        }

        $('#verify-btn').prop('disabled', true);
        $('#submit-btn').prop('disabled', true);
        try {
            const source_media = lastMediaData ?? undefined;
            const source_instructions = $('#src-instructions').is(':visible') ? String($('#src-instructions').val() ?? '').trim() : undefined;
            if (editingSubmissionId !== null) {
                await updateSubmission(editingSubmissionId, { source_text, source_media, source_instructions, source_lang, target_lang, verification_rules: rules, translations });
                $('#submit-status').html('<span class="msg-ok">✓ Updated!</span>');
            } else {
                await createSubmission({ source_text, source_media, source_instructions, source_lang, target_lang, verification_rules: rules, translations });
                $('#submit-status').html('<span class="msg-ok">✓ Submitted!</span>');
            }
            lastMediaData = null;
            clearForm();
        } catch (err) {
            $('#submit-status').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        } finally {
            updateButtonStates();
        }
    });

    // Send a contributor reply from the sidebar
    $('#my-submissions').on('click', '.contrib-send-btn', async function () {
        const id = parseInt(String($(this).data('id')));
        const $input = $(`#contrib-reply-${id}`);
        const text = String($input.val() ?? '').trim();
        if (!text) return;
        $(this).prop('disabled', true).text('Sending…');
        try {
            await addComment(id, text);
            $input.val('');
            // Refresh sidebar to show new comment
            loadMySubmissions();
        } catch (err) {
            alert('Failed to send: ' + String(err));
        }
        $(this).prop('disabled', false).text('Reply');
    });

    // Edit a submission from the sidebar
    $('#my-submissions').on('click', '.edit-btn', function () {
        const id = parseInt(String($(this).data('id')));
        const sub = allMySubmissions.find(s => s.id === id);
        if (!sub) return;

        editingSubmissionId = id;
        if (sub.source_media) {
            lastMediaData = sub.source_media;
            const isAudio = /^data:audio/.test(sub.source_media);
            const isVideo = /^data:video/.test(sub.source_media);
            let mediaTag = `<img class="context_image" src="${sub.source_media}">`;
            if (isAudio) mediaTag = `<audio class="context_audio" controls src="${sub.source_media}"></audio>`;
            else if (isVideo) mediaTag = `<video class="context_video" controls src="${sub.source_media}" style="max-width:100%; max-height:150px;"></video>`;
            $('#media-preview').html(mediaTag);
            $('#add-media-btn').text('Remove media');
        } else {
            lastMediaData = null;
            $('#media-preview').empty();
            $('#add-media-btn').text('Add image/audio/video');
        }

        if (sub.source_instructions) {
            $('#src-instructions').val(sub.source_instructions).show();
            $('#add-context-btn').text('Remove instructions');
        } else {
            $('#src-instructions').val('').hide();
            $('#add-context-btn').text('Add instructions/context');
        }

        $('#src-text').val(sub.source_text);
        $('#src-lang').val(sub.source_lang);
        $('#tgt-lang').val(sub.target_lang);
        rules = sub.verification_rules.length > 0 ? JSON.parse(JSON.stringify(sub.verification_rules)) : [{ value: '' }];
        renderRules();

        // Clear previous MT results and own translation
        lastResults = [];
        ownVerified = null;
        $('#api-results-body').hide();
        $('#own-verify-badge').html('');
        $('#own-translation').val('');
        $('#pass-count').text('');
        $('#verify-result').text('');

        // Find own translation if any
        const ownTr = sub.translations.find(t => t.model === 'human');
        if (ownTr) {
            $('#own-translation').val(ownTr.translation);
            ownVerified = ownTr.verified;
            if (ownVerified !== null) {
                const badge = ownVerified.map(v => v ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>').join('');
                $('#own-verify-badge').html(badge);
            }
        }

        // Fill MT results
        lastResults = sub.translations.filter(t => t.model !== 'human').map(t => ({
            model: t.model,
            translation: t.translation,
            error: null,
            verified: t.verified
        }));
        inputCorrespondsToTranslations = true;
        if (lastResults.length > 0) {
            renderApiResults();
            // Show verification badges
            lastResults.forEach((r, i) => {
                if (r.verified != null) {
                    const badge = r.verified.map(v => v ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>').join('');
                    $(`[data-idx="${i}"]`).html(badge);
                }
            });
        }

        $('#submit-btn').text('Update Submission');
        $('#cancel-edit-btn').show();
        updateButtonStates();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    $('#cancel-edit-btn').on('click', () => {
        clearForm();
    });

    function clearForm() {
        editingSubmissionId = null;
        lastMediaData = null;
        $('#media-preview').empty();
        $('#src-text, #own-translation').val('');
        ($('#src-file')[0] as HTMLInputElement).value = '';
        $('#media-status').text('');
        $('#verify-result, #own-verify-badge').html('');
        lastResults = [];
        ownVerified = null;
        inputCorrespondsToTranslations = true;
        rules = [{ value: '' }];
        renderRules();
        $('#api-results-body').hide();
        $('#submit-btn').text('Submit Input, Translations & Rule');
        $('#cancel-edit-btn').hide();
        $('#pass-count').text('');
        loadMySubmissions();
        setTimeout(() => $('#submit-status').html(''), 3000);

        $('#media-preview').empty();
        $('#add-media-btn').text('Add image/audio/video');
        $('#src-instructions').val('').hide();
        $('#add-context-btn').text('Add instructions/context');
        updateButtonStates();
    }


});

// ---- Stats bar ----


function renderRules() {
    const $container = $('#rules-container');
    $container.empty();
    const disabled = rules.length == 1 ? 'disabled' : '';
    rules.forEach((rule, index) => {
        const placeholder = "Describe what the LLM should check (e.g. 'Should be sarcastic.').";

        const $row = $(`
            <div class="rule-row" data-index="${index}" style="display: flex; gap: 12px; align-items: flex-start; margin-bottom: 8px;">
                <button class="rule-remove btn-underlined" style="font-size: 0.85em; align-self: center;" ${disabled}>- Remove</button>
                <textarea class="rule-value" placeholder="${escHtml(placeholder)}" style="flex: 1; height: 40px; padding: 7px 10px; border: none; min-height: 60px; font-size: 0.85em; resize: vertical;">${escHtml(rule.value)}</textarea>
            </div>
        `);
        $container.append($row);
    });

    $('#add-rule-btn').prop('disabled', rules.length >= 10);
}

// ---- API results table ----

function renderApiResults(): void {
    const $body = $('#api-results-body');
    $body.html(lastResults.map((r, i) => {
        const trText = r.translation ?? `<em class="tr-error">${escHtml(r.error ?? 'Error')}</em>`;
        const verifyBadge = '';
        return `<div class="translation-result-row">
          <span class="api-name">${escHtml(r.model)}</span>
          <div class="tr-display">${trText}</div>
          <div data-idx="${i}" style="display: flex; gap: 4px; flex-wrap: wrap;">${verifyBadge}</div>
        </div>`;
    }).join(''));
    $body.show();
}


// ---- Sidebar: my submissions ----

async function loadMySubmissions(): Promise<void> {
    try {
        const sugs = await getSubmissions('contributor');
        allMySubmissions = sugs;
        renderFilteredSubmissions();
    } catch { /* ignore */ }
}

function renderFilteredSubmissions(): void {
    const showPending = $('#filter-pending').prop('checked');
    const showReturned = $('#filter-returned').prop('checked');
    const showAccepted = $('#filter-accepted').prop('checked');

    const filtered = allMySubmissions.filter(s => {
        if (s.status === 'pending' && showPending) return true;
        if (s.status === 'return' && showReturned) return true;
        if (s.status === 'accept' && showAccepted) return true;
        return false;
    });

    const $el = $('#my-submissions');
    if (filtered.length == 0) {
        $el.html('<div class="empty">No submissions yet</div>');
        return;
    }
    sortSubmissions(filtered, curSort, currentUser!.username);
    $el.html(filtered.map(renderMySug).join(''));
}

function renderMySug(s: Submission): string {
    const humanTr = s.translations.find(t => t.model === 'human')?.translation ?? s.translations[0]?.translation ?? '';

    const rulesHtml = s.verification_rules.map((r, i) =>
        `<div class="sug-box" style="margin-bottom: 4px; font-size: 0.9em; background: transparent; padding: 0;"><span class="lbl">VERIFICATION: </span>${escHtml(r.value)}</div>`
    ).join('');

    const comments = s.comments ?? [];
    const threadHtml = renderCommentThread(comments, currentUser!.username);

    const replyHtml = `<div class="comment-reply-row" style="display: flex; gap: 8px; align-items: center;">
            <textarea id="contrib-reply-${s.id}" class="comment-input" placeholder="Add comment…" style="height: 30px; min-height: 30px; flex: 1;"></textarea>
            <button class="contrib-send-btn score-btn" style="background:#64748b;color:#fff;margin:0" data-id="${s.id}">Reply</button>
           </div>`;

    return `<div class="sug-mini">
        <div class="sug-mini-meta" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <span>#${s.id} &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.status, (s.comments?.length ?? 0) > 0)}</span>
            ${s.status === 'accept' ? '' : `<button class="score-btn edit-btn" data-id="${s.id}">Edit submission</button>`}
        </div>
        
        <div class="sug-box" style="margin-bottom: 8px; color: #1e293b; font-weight: 500; word-break: break-word; background: transparent; padding: 0;">
            <span class="lbl">INPUT: </span>${renderSource(s)}
        </div>
        
        <div class="sug-box" style="margin-bottom: 8px; color: #475569; word-break: break-word; white-space: pre-wrap; background: transparent; padding: 0;"><span class="lbl">HUMAN: </span>${escHtml(humanTr)}</div>
        
        <div style="margin-bottom: 8px; word-break: break-word;">
            ${rulesHtml || '<div style="color: #94a3b8; font-style: italic;">No rules</div>'}
        </div>

        ${threadHtml}
        ${replyHtml}
    </div>`;
}

function invalidateVerification(): void {
    ownVerified = null;
    $('#own-verify-badge').empty();
    lastResults.forEach(r => r.verified = null);
    $('[data-idx]').html('');
    $('#pass-count').empty();
    $('#verify-result').empty();
}

function updateButtonStates(): void {
    const ownTranslation = String($('#own-translation').val() ?? '').trim();
    const hasOwnTranslation = ownTranslation !== '';
    const hasMtTranslation = lastResults.some(r => r.translation !== null);

    // Verify button: enabled if translations exist AND they correspond to the current input
    const canVerify = (hasOwnTranslation || hasMtTranslation) && inputCorrespondsToTranslations;
    $('#verify-btn').prop('disabled', !canVerify);

    const rulesNotEmpty = rules.length > 0 && rules.every(r => r.value.trim() !== '');
    const humanExistsAndPasses = hasOwnTranslation && ownVerified !== null && ownVerified.every(v => v);
    const mtPassCount = lastResults.filter(r => r.verified != null && r.verified.every(v => v)).length;
    const mtPassValid = mtPassCount <= 2;

    // Submit button: enabled only if all requirements pass AND translations correspond to current input
    const allPassed = rulesNotEmpty && humanExistsAndPasses && mtPassValid && inputCorrespondsToTranslations;
    $('#submit-btn').prop('disabled', !allPassed);

    if (allPassed) {
        $('#submit-reason').text('');
    } else {
        let reason = '';
        if (lastResults.length === 0 || !inputCorrespondsToTranslations) reason = 'Run translations first';
        else if (!rulesNotEmpty) reason = 'All rules must have content';
        else if (!hasOwnTranslation) reason = 'Human translation is required';
        else if (ownVerified === null) reason = 'Run verification first';
        else if (!humanExistsAndPasses) reason = 'Human translation must pass verification';
        else if (!mtPassValid) reason = 'Only 2 MTs can pass';
        else reason = 'Run verification first';
        
        $('#submit-reason').text(`(${reason})`);
    }
}
