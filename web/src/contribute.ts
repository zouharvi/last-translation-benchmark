import './style.css';
import $ from 'jquery';
import {
    getMe, getCookie,
    translate, verify, createSubmission, updateSubmission, getSubmissions, addComment, renderRoleSwitcher,
    User, Submission, Rule,
} from './api';

import { esc as escHtml, fmtDate, scoreBadge, accessDenied, renderCommentThread, setupInstructions } from './utils';

let currentUser: User | null = null;

// Last set of API translation results
type ApiResult = { api: string; translation: string | null; error: string | null; verified?: boolean | null };
let lastResults: ApiResult[] = [];
let ownVerified: boolean | null = null;
let editingSubmissionId: number | null = null;
let allMySubmissions: Submission[] = [];
let lastMediaData: string | null = null;
let rules: Rule[] = [{ value: '' }];




$(async () => {
    setupInstructions('contributor');
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
        renderRoleSwitcher(currentUser.roles);
        if (!currentUser.roles.includes('contributor')) {
            accessDenied(currentUser.roles, 'contributor');
            return;
        }
    } catch {
        window.location.href = 'index.html';
        return;
    }

    $('#ann-info').text(currentUser.username);
    renderStats(currentUser.quota_used, currentUser.quota, currentUser.total_accepted);
    loadMySubmissions();
    renderRules();

    // Input type toggle
    $('#add-media-btn').on('click', () => {
        const file = ($('#src-file')[0] as HTMLInputElement).files?.[0];
        if (file || lastMediaData) {
            ($('#src-file')[0] as HTMLInputElement).value = '';
            lastMediaData = null;
            $('#media-preview').empty();
            $('#add-media-btn').text('Add image/audio context');
        } else {
            $('#src-file').trigger("click");
        }
    });

    $('#src-file').on('change', function () {
        const file = (this as HTMLInputElement).files?.[0];
        if (!file) return;
        $('#media-preview').empty();

        const isAudio = /\.(mp3|wav)$/i.test(file.name);
        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = String(e.target?.result ?? '');
            lastMediaData = dataUrl;
            const mediaTag = isAudio ? `<audio class="context_audio" controls src="${dataUrl}"></audio>` : `<img class="context_image" src="${dataUrl}">`;

            $('#media-preview').html(mediaTag);
            $('#add-media-btn').text('Remove audio/image context');
        };
        reader.readAsDataURL(file);
    });



    $('#add-rule-btn').on('click', () => {
        if (rules.length >= 10) return;
        rules.push({ value: '' });
        renderRules();
    });


    $('#rules-container').on('input', '.rule-value', function () {
        const index = $(this).closest('.rule-row').data('index');
        rules[index].value = $(this).val() as string;
    });

    $('#rules-container').on('click', '.rule-remove', function () {
        const index = $(this).closest('.rule-row').data('index');
        rules.splice(index, 1);
        renderRules();
    });


    // Translate by server
    $('#tr-btn').on('click', async () => {
        const srcLang = String($('#src-lang').val());
        const tgtLang = String($('#tgt-lang').val());
        $('#tr-btn').prop('disabled', true);
        $('#tr-status').text('Translating…');
        try {
            const text = String($('#src-text').val() ?? '').trim();
            const data = await translate(text, srcLang, tgtLang, lastMediaData ?? undefined);

            lastResults = data.results;
            currentUser!.quota_used = data.quota_used;
            currentUser!.quota = data.quota;
            renderStats(data.quota_used, data.quota, currentUser!.total_accepted);
            renderApiResults();
            lastResults.forEach(r => r.verified = null);
            ownVerified = null;
            $('#pass-count').text('');
            $('#verify-result').text('');
            $('#tr-status').text('✓ Done');
        } catch (err) {
            console.error('translate error:', err);
            $('#tr-status').text(`✗ ${err instanceof Error ? err.message : JSON.stringify(err)}`);
        } finally {
            $('#tr-btn').prop('disabled', false);
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

        $('#verify-result').html('<span style="color:#64748b;font-size:0.9em">Verifying...</span>');
        try {
            const source_text = String($('#src-text').val() ?? '').trim();
            const data = await verify(source_text, translations, rules, lastMediaData ?? undefined);

            let resultIdx = 0;
            let pass = 0;
            lastResults.forEach((r, i) => {
                if (r.translation !== null) {
                    const verified = data.results[resultIdx++];
                    r.verified = verified;
                    const badge = verified ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>';
                    $(`[data-idx="${i}"]`).html(badge);
                    if (verified) pass++;
                } else {
                    $(`[data-idx="${i}"]`).html('');
                }
            });

            if (ownTranslation) {
                const verified = data.results[resultIdx++];
                ownVerified = verified;
                const badge = verified ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>';
                $('#own-verify-badge').html(badge);
                if (verified) pass++;
            } else {
                ownVerified = null;
                $('#own-verify-badge').html('');
            }

            const cls = pass === 0 ? 'count-fail' : (pass === translations.length ? 'count-pass' : 'count-partial');
            $('#verify-result').html("");
            $('#pass-count').html(`<span class="${cls}">${pass}/${translations.length} pass verification</span>`);
        } catch (err) {
            $('#verify-result').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        }
    });

    // Submit or Update submission
    $('#submit-btn').on('click', async () => {
        const source_text = String($('#src-text').val() ?? '').trim();
        const ownTranslation = String($('#own-translation').val() ?? '').trim();

        const translations: Array<{ api: string; translation: string; verified: boolean | null }> = [];
        lastResults.forEach(r => {
            if (r.translation !== null) {
                translations.push({ api: r.api, translation: r.translation, verified: r.verified ?? null });
            }
        });
        if (ownTranslation && !translations.some(t => t.translation === ownTranslation)) {
            translations.push({ api: 'human', translation: ownTranslation, verified: ownVerified ?? null });
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
        if (ownVerified !== true) {
            $('#submit-status').html('<span class="msg-err">Human translation must pass verification</span>');
            return;
        }

        const mtPassCount = lastResults.filter(r => r.verified === true).length;
        if (mtPassCount > 2) {
            $('#submit-status').html('<span class="msg-err">At most two MT translations can pass verification</span>');
            return;
        }

        try {
            const source_media = lastMediaData ?? undefined;
            if (editingSubmissionId !== null) {
                await updateSubmission(editingSubmissionId, { source_text, source_media, source_lang, target_lang, verification_rules: rules, translations });
                $('#submit-status').html('<span class="msg-ok">✓ Updated!</span>');
            } else {
                await createSubmission({ source_text, source_media, source_lang, target_lang, verification_rules: rules, translations });
                $('#submit-status').html('<span class="msg-ok">✓ Submitted!</span>');
            }
            lastMediaData = null;
            clearForm();
        } catch (err) {
            $('#submit-status').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
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
            const mediaTag = isAudio ? `<audio class="context_audio" controls src="${sub.source_media}"></audio>` : `<img class="context_image" src="${sub.source_media}">`;
            $('#media-preview').html(mediaTag);
            $('#add-media-btn').text('Remove image/audio');
        } else {
            lastMediaData = null;
            $('#media-preview').empty();
            $('#add-media-btn').text('Add image/audio');
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
        const ownTr = sub.translations.find(t => t.api === 'human');
        if (ownTr) {
            $('#own-translation').val(ownTr.translation);
            ownVerified = ownTr.verified;
            if (ownVerified !== null) {
                const badge = ownVerified ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>';
                $('#own-verify-badge').html(badge);
            }
        }

        // Fill MT results
        lastResults = sub.translations.filter(t => t.api !== 'human').map(t => ({
            api: t.api,
            translation: t.translation,
            error: null,
            verified: t.verified
        }));
        if (lastResults.length > 0) {
            renderApiResults();
            // Show verification badges
            lastResults.forEach((r, i) => {
                if (r.verified !== null) {
                    const badge = r.verified ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>';
                    $(`[data-idx="${i}"]`).html(badge);
                }
            });
        }

        $('#submit-btn').text('Update Submission');
        $('#cancel-edit-btn').show();
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
        rules = [{ value: '' }];
        renderRules();
        $('#api-results-body').hide();
        $('#submit-btn').text('Submit Input, Translations & Rule');
        $('#cancel-edit-btn').hide();
        $('#pass-count').text('');
        loadMySubmissions();
        setTimeout(() => $('#submit-status').html(''), 3000);

        $('#media-preview').empty();
        $('#add-media-btn').text('Add image/audio context');
    }


});

// ---- Stats bar ----

function renderStats(used: number, quota: number, accepted: number): void {
    $('#quota-text').text(`Used: ${used} / ${quota}`);
    $('#total-points').text(accepted);
}

function renderRules() {
    const $container = $('#rules-container');
    $container.empty();
    const disabled = rules.length == 1 ? 'disabled' : '';
    rules.forEach((rule, index) => {
        const placeholder = "Describe what the LLM should check (e.g. 'Should be sarcastic.')";

        const $row = $(`
            <div class="rule-row" data-index="${index}" style="display: flex; gap: 12px; align-items: flex-start; margin-bottom: 8px;">
                <button class="rule-remove btn btn-secondary" style="padding: 4px 10px; font-size: 0.85em; width: fit-content; align-self: center;" ${disabled}>- Remove</button>
                <textarea class="rule-value" placeholder="${escHtml(placeholder)}" style="flex: 1; height: 40px; padding: 7px 10px; border: 1px solid #d1d5db; min-height: 60px; border-radius: 5px; font-size: 0.85em; resize: vertical;">${escHtml(rule.value)}</textarea>
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
        return `<div class="api-result-row">
          <span class="api-name">${escHtml(r.api)}</span>
          <div class="tr-display">${trText}</div>
          <span class="verify-pill" data-idx="${i}">${verifyBadge}</span>
        </div>`;
    }).join(''));
    $body.show();
}


// ---- Sidebar: my submissions ----

async function loadMySubmissions(): Promise<void> {
    try {
        const sugs = await getSubmissions('contributor');
        allMySubmissions = sugs;
        const $el = $('#my-submissions');
        if (sugs.length == 0) {
            $el.html('<div class="empty">No submissions yet</div>');
            return;
        }
        $el.html(sugs.map(renderMySug).join(''));
    } catch { /* ignore */ }
}

function renderMySug(s: Submission): string {
    const srcPreview = s.source_text.length > 60 ? s.source_text.slice(0, 60) + '…' : s.source_text;
    const firstTr = s.translations[0]?.translation ?? '';
    const trPreview = firstTr.length > 60 ? firstTr.slice(0, 60) + '…' : firstTr;
    const isAudio = s.source_media && /^data:audio/.test(s.source_media);
    const mediaHtml = s.source_media
        ? (isAudio
            ? `<audio controls src="${s.source_media}" class="context_audio"></audio>`
            : `<img src="${s.source_media}" class="context_image">`)
        : '';

    const comments = s.comments ?? [];
    const threadHtml = renderCommentThread(comments, 'contributor');

    const replyHtml = `<div class="comment-reply-row">
            <textarea id="contrib-reply-${s.id}" class="comment-input" placeholder="Add comment…" style="height: 30px; min-height: 30px"></textarea>
            <div style="text-align:right;margin-top:4px">
                <button class="contrib-send-btn score-btn" style="background:#64748b;color:#fff" data-id="${s.id}">Reply</button>
            </div>
           </div>`;

    return `<div class="sug-mini">
        <div class="sug-mini-meta">#${s.id} &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)}</div>
        ${mediaHtml}
        <div class="sug-mini-text">${escHtml(srcPreview)}</div>
        <div class="sug-mini-tr">${escHtml(trPreview)}${s.translations.length > 1 ? ` <em>(+${s.translations.length - 1} more)</em>` : ''}</div>
        <div class="sug-mini-footer">
          <div class="sug-mini-rules">
            ${s.verification_rules.map(r => `<code class="sug-mini-vc" title="LLM Verification: ${escHtml(r.value)}">${escHtml(r.value)}</code>`).join('')}
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <button class="btn btn-secondary edit-btn" style="padding: 2px 6px; font-size: 0.75em;" data-id="${s.id}">Edit</button>
            ${scoreBadge(s.points)}
          </div>
        </div>
        ${threadHtml}
        ${replyHtml}
    </div>`;
}
