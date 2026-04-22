import './style.css';
import $ from 'jquery';
import {
    getToken, clearToken, getMe, logout,
    translate, verify, createSubmission, getSubmissions,
    User, Submission,
} from './api';

let currentUser: User | null = null;

// Last set of API translation results
type ApiResult = { api: string; translation: string | null; error: string | null; verified?: boolean | null };
let lastResults: ApiResult[] = [];
let ownVerified: boolean | null = null;

const LANGUAGES = [
    { name: 'Afrikaans', code: 'af' },
    { name: 'Albanian', code: 'sq' },
    { name: 'Amharic', code: 'am' },
    { name: 'Arabic', code: 'ar' },
    { name: 'Armenian', code: 'hy' },
    { name: 'Assamese', code: 'as' },
    { name: 'Aymara', code: 'ay' },
    { name: 'Azerbaijani', code: 'az' },
    { name: 'Bambara', code: 'bm' },
    { name: 'Basque', code: 'eu' },
    { name: 'Belarusian', code: 'be' },
    { name: 'Bengali', code: 'bn' },
    { name: 'Bhojpuri', code: 'bho' },
    { name: 'Bosnian', code: 'bs' },
    { name: 'Bulgarian', code: 'bg' },
    { name: 'Catalan', code: 'ca' },
    { name: 'Cebuano', code: 'ceb' },
    { name: 'Chichewa', code: 'ny' },
    { name: 'Chinese (Simplified)', code: 'zh-CN' },
    { name: 'Chinese (Traditional)', code: 'zh-TW' },
    { name: 'Corsican', code: 'co' },
    { name: 'Croatian', code: 'hr' },
    { name: 'Czech', code: 'cs' },
    { name: 'Danish', code: 'da' },
    { name: 'Dhivehi', code: 'dv' },
    { name: 'Dogri', code: 'doi' },
    { name: 'Dutch', code: 'nl' },
    { name: 'English', code: 'en' },
    { name: 'Esperanto', code: 'eo' },
    { name: 'Estonian', code: 'et' },
    { name: 'Ewe', code: 'ee' },
    { name: 'Filipino', code: 'tl' },
    { name: 'Finnish', code: 'fi' },
    { name: 'French', code: 'fr' },
    { name: 'Frisian', code: 'fy' },
    { name: 'Galician', code: 'gl' },
    { name: 'Georgian', code: 'ka' },
    { name: 'German', code: 'de' },
    { name: 'Greek', code: 'el' },
    { name: 'Guarani', code: 'gn' },
    { name: 'Gujarati', code: 'gu' },
    { name: 'Haitian Creole', code: 'ht' },
    { name: 'Hausa', code: 'ha' },
    { name: 'Hawaiian', code: 'haw' },
    { name: 'Hebrew', code: 'iw' },
    { name: 'Hindi', code: 'hi' },
    { name: 'Hmong', code: 'hmn' },
    { name: 'Hungarian', code: 'hu' },
    { name: 'Icelandic', code: 'is' },
    { name: 'Igbo', code: 'ig' },
    { name: 'Ilocano', code: 'ilo' },
    { name: 'Indonesian', code: 'id' },
    { name: 'Irish', code: 'ga' },
    { name: 'Italian', code: 'it' },
    { name: 'Japanese', code: 'ja' },
    { name: 'Javanese', code: 'jw' },
    { name: 'Kannada', code: 'kn' },
    { name: 'Kazakh', code: 'kk' },
    { name: 'Khmer', code: 'km' },
    { name: 'Kinyarwanda', code: 'rw' },
    { name: 'Konkani', code: 'gom' },
    { name: 'Korean', code: 'ko' },
    { name: 'Krio', code: 'kri' },
    { name: 'Kurdish (Kurmanji)', code: 'ku' },
    { name: 'Kurdish (Sorani)', code: 'ckb' },
    { name: 'Kyrgyz', code: 'ky' },
    { name: 'Lao', code: 'lo' },
    { name: 'Latin', code: 'la' },
    { name: 'Latvian', code: 'lv' },
    { name: 'Lingala', code: 'ln' },
    { name: 'Lithuanian', code: 'lt' },
    { name: 'Luganda', code: 'lg' },
    { name: 'Luxembourgish', code: 'lb' },
    { name: 'Macedonian', code: 'mk' },
    { name: 'Maithili', code: 'mai' },
    { name: 'Malagasy', code: 'mg' },
    { name: 'Malay', code: 'ms' },
    { name: 'Malayalam', code: 'ml' },
    { name: 'Maltese', code: 'mt' },
    { name: 'Maori', code: 'mi' },
    { name: 'Marathi', code: 'mr' },
    { name: 'Meiteilon (Manipuri)', code: 'mni-Mtei' },
    { name: 'Mizo', code: 'lus' },
    { name: 'Mongolian', code: 'mn' },
    { name: 'Myanmar', code: 'my' },
    { name: 'Nepali', code: 'ne' },
    { name: 'Norwegian', code: 'no' },
    { name: 'Odia (Oriya)', code: 'or' },
    { name: 'Oromo', code: 'om' },
    { name: 'Pashto', code: 'ps' },
    { name: 'Persian', code: 'fa' },
    { name: 'Polish', code: 'pl' },
    { name: 'Portuguese', code: 'pt' },
    { name: 'Punjabi', code: 'pa' },
    { name: 'Quechua', code: 'qu' },
    { name: 'Romanian', code: 'ro' },
    { name: 'Russian', code: 'ru' },
    { name: 'Samoan', code: 'sm' },
    { name: 'Sanskrit', code: 'sa' },
    { name: 'Scots Gaelic', code: 'gd' },
    { name: 'Sepedi', code: 'nso' },
    { name: 'Serbian', code: 'sr' },
    { name: 'Sesotho', code: 'st' },
    { name: 'Shona', code: 'sn' },
    { name: 'Sindhi', code: 'sd' },
    { name: 'Sinhala', code: 'si' },
    { name: 'Slovak', code: 'sk' },
    { name: 'Slovenian', code: 'sl' },
    { name: 'Somali', code: 'so' },
    { name: 'Spanish', code: 'es' },
    { name: 'Sundanese', code: 'su' },
    { name: 'Swahili', code: 'sw' },
    { name: 'Swedish', code: 'sv' },
    { name: 'Tajik', code: 'tg' },
    { name: 'Tamil', code: 'ta' },
    { name: 'Tatar', code: 'tt' },
    { name: 'Telugu', code: 'te' },
    { name: 'Thai', code: 'th' },
    { name: 'Tigrinya', code: 'ti' },
    { name: 'Tsonga', code: 'ts' },
    { name: 'Turkish', code: 'tr' },
    { name: 'Turkmen', code: 'tk' },
    { name: 'Twi', code: 'ak' },
    { name: 'Ukrainian', code: 'uk' },
    { name: 'Urdu', code: 'ur' },
    { name: 'Uyghur', code: 'ug' },
    { name: 'Uzbek', code: 'uz' },
    { name: 'Vietnamese', code: 'vi' },
    { name: 'Welsh', code: 'cy' },
    { name: 'Xhosa', code: 'xh' },
    { name: 'Yiddish', code: 'yi' },
    { name: 'Yoruba', code: 'yo' },
    { name: 'Zulu', code: 'zu' }
];

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    const langOptions = LANGUAGES.map(l => `<option value="${l.code}">${l.name}</option>`).join('');
    $('#src-langs').html(langOptions);
    $('#tgt-langs').html(langOptions);

    try {
        currentUser = await getMe();
        if (currentUser.role !== 'contributor') {
            window.location.href = '/reviewer.html';
            return;
        }
    } catch {
        clearToken();
        window.location.href = '/';
        return;
    }

    $('#ann-info').text(`${currentUser.username} · Contributor`);
    renderStats(currentUser.quota_remaining, currentUser.daily_quota, currentUser.total_points);
    loadMySubmissions();


    // Auto-translate
    $('#tr-btn').on('click', async () => {
        const text = String($('#src-text').val() ?? '').trim();
        if (!text) { alert('Enter source text first.'); return; }
        $('#tr-btn').prop('disabled', true);
        $('#tr-status').text('Translating…');
        try {
            const data = await translate(
                text,
                String($('#src-lang').val()),
                String($('#tgt-lang').val()),
            );
            lastResults = data.results;
            currentUser!.quota_remaining = data.quota_remaining;
            renderStats(data.quota_remaining, currentUser!.daily_quota, currentUser!.total_points);
            renderApiResults();
            lastResults.forEach(r => r.verified = null);
            ownVerified = null;
            $('#pass-count').text('');
            $('#verify-result').text('');
            $('#tr-status').text('✓ Done');
        } catch (err) {
            $('#tr-status').text(`✗ ${err}`);
        } finally {
            $('#tr-btn').prop('disabled', false);
        }
    });


    // Test verification (on all translations)
    $('#verify-btn').on('click', async () => {
        const mtTranslations = lastResults.map(r => r.translation).filter(t => t !== null) as string[];
        const ownTranslation = String($('#own-translation').val() ?? '').trim();
        const translations = [...mtTranslations];
        if (ownTranslation) translations.push(ownTranslation);

        const vcontent = String($('#vc-content').val() ?? '').trim();
        if (translations.length === 0) { $('#verify-result').html('<span class="msg-err">No translations available</span>'); return; }
        if (!vcontent) { $('#verify-result').html('<span class="msg-err">No verification content</span>'); return; }

        $('#verify-result').html('<span style="color:#64748b;font-size:0.9em">Verifying...</span>');
        try {
            const data = await verify(translations, vcontent);

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

    // Submit submission
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
            translations.push({ api: 'perfect', translation: ownTranslation, verified: ownVerified ?? null });
        }

        const source_lang = String($('#src-lang').val());
        const target_lang = String($('#tgt-lang').val());
        const verification_rule = String($('#vc-content').val() ?? '').trim();

        if (!source_text || translations.length === 0 || !verification_rule) {
            $('#submit-status').html('<span class="msg-err">Please fill all required fields, translate and verify translations first</span>');
            return;
        }
        try {
            await createSubmission({ source_text, source_lang, target_lang, verification_rule, translations });
            $('#submit-status').html('<span class="msg-ok">✓ Submitted!</span>');
            $('#src-text, #vc-content, #own-translation').val('');
            $('#verify-result, #own-verify-badge').html('');
            lastResults = [];
            ownVerified = null;
            $('#api-results-body').hide();
            loadMySubmissions();
            setTimeout(() => $('#submit-status').html(''), 3000);
        } catch (err) {
            $('#submit-status').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        }
    });

    // Logout
    $('#logout-btn').on('click', async () => {
        try { await logout(); } finally { clearToken(); window.location.href = '/'; }
    });
});

// ---- Stats bar ----

function renderStats(remaining: number, total: number, points: number): void {
    const pct = total > 0 ? (remaining / total * 100) : 0;
    $('#quota-fill').css('width', `${pct}%`);
    $('#quota-text').text(`${remaining} / ${total} remaining`);
    $('#total-points').text(String(points));
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
        const sugs = await getSubmissions();
        const $el = $('#my-submissions');
        if (sugs.length == 0) {
            $el.html('<div class="empty">No submissions yet</div>');
            return;
        }
        console.log("X", sugs.map(renderMySug));
        $el.html(sugs.map(renderMySug).join(''));
    } catch { /* ignore */ }
}

function renderMySug(s: Submission): string {
    const srcPreview = s.source_text.length > 60 ? s.source_text.slice(0, 60) + '…' : s.source_text;
    const firstTr = s.translations[0]?.translation ?? '';
    const trPreview = firstTr.length > 60 ? firstTr.slice(0, 60) + '…' : firstTr;
    return `<div class="sug-mini">
        <div class="sug-mini-meta">#${s.id} &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)}</div>
        <div class="sug-mini-text">${escHtml(srcPreview)}</div>
        <div class="sug-mini-tr">${escHtml(trPreview)}${s.translations.length > 1 ? ` <em>(+${s.translations.length - 1} more)</em>` : ''}</div>
        <div class="sug-mini-footer">
          <code class="sug-mini-vc">${escHtml(s.verification_rule)}</code>
          ${scoreBadge(s.points)}
        </div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number): string {
    if (p < 0) return '<span class="badge badge-pending">Pending</span>';
    const labels = ['0 · Rejected', '1 · Good', '2 · Excellent'];
    return `<span class="badge badge-score-${p}">${labels[p]}</span>`;
}
