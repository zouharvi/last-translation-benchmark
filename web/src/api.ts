import $ from 'jquery';

// ---------- Types ----------

export interface User {
    username: string;
    role: 'contributor' | 'reviewer';
    quota_used: number;
    quota_remaining: number;
    contributor_quota: number;
    total_points: number;
}

export interface TranslationEntry {
    api: string;
    translation: string;
    verified: boolean | null;
}

export interface Submission {
    id: number;
    user_id: number;
    username: string;
    source_text: string;
    source_lang: string;
    target_lang: string;
    verification_rule: string;
    translations: TranslationEntry[];
    points: number;
    reviewer_comment: string;
    created_at: string;
}

// ---------- Token helpers ----------

export function getToken(): string | null {
    const params = new URLSearchParams(window.location.search);
    return params.get('token');
}

// ---------- Generic fetch ----------

function apiCall<T>(method: string, url: string, data?: object): Promise<T> {
    const token = getToken();
    return new Promise<T>((resolve, reject) => {
        const settings: JQuery.AjaxSettings = {
            url,
            method,
            contentType: 'application/json',
            dataType: 'json',
            success: (x: T) => resolve(x),
            error: (xhr: JQuery.jqXHR) => {
                const detail = (xhr.responseJSON as { detail?: string })?.detail ?? 'Request failed';
                reject(detail);
            },
        };
        if (token) settings.headers = { Authorization: `Bearer ${token}` };
        if (data !== undefined) settings.data = JSON.stringify(data);
        $.ajax(settings);
    });
}

// ---------- API calls ----------

export function getMe() {
    return apiCall<User>('GET', '/api/me');
}

export function translate(text: string, source_lang: string, target_lang: string) {
    return apiCall<{
        results: Array<{ api: string; translation: string | null; error: string | null }>;
        quota_remaining: number;
    }>('POST', '/api/translate-submission', { text, source_lang, target_lang });
}

export function verify(
    translations: string[],
    verification_rule: string,
) {
    return apiCall<{ results: boolean[]; detail: string }>(
        'POST', '/api/verify-submission', { translations, verification_rule }
    );
}

export function getSubmissions() {
    return apiCall<Submission[]>('GET', '/api/submissions');
}

export function createSubmission(data: {
    source_text: string;
    source_lang: string;
    target_lang: string;
    verification_rule: string;
    translations: Array<{ api: string; translation: string; verified: boolean | null }>;
}) {
    return apiCall<{ ok: boolean }>('POST', '/api/submissions', data);
}

export function scoreSubmission(id: number, action: 'reject' | 'accept' | 'comment', comment?: string) {
    return apiCall<{ ok: boolean }>('POST', `/api/submissions/${id}/score`, { action, comment });
}
