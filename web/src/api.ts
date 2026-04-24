import $ from 'jquery';

// ---------- Types ----------

export interface User {
    username: string;
    roles: string[];
    quota_used: number;
    quota_remaining: number;
    contributor_quota: number;
    total_points: number;
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
}

export interface TranslationEntry {
    api: string;
    translation: string;
    verified: boolean | null;
}

export interface Comment {
    author: string;
    role: 'reviewer' | 'contributor';
    text: string;
    timestamp: string;
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
    comments?: Comment[];
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

export function updateProfile(data: {
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
}) {
    return apiCall<{ ok: boolean }>('PUT', '/api/profile', data);
}

export interface AdminUser {
    id: number;
    username: string;
    roles: string[];
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
}

export function getAdminUsers() {
    return apiCall<AdminUser[]>('GET', '/api/admin/users');
}

export function addComment(id: number, comment: string) {
    return apiCall<{ ok: boolean }>('POST', `/api/submissions/${id}/comment`, { comment });
}

// ---------- UI helpers ----------

export function renderRoleSwitcher(roles: string[]): void {
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.gap = '8px';
    container.style.marginLeft = '16px';

    const search = window.location.search;

    if (roles.includes('admin')) {
        const btn = document.createElement('button');
        btn.textContent = 'Admin';
        btn.className = 'btn btn-secondary';
        btn.style.padding = '3px 8px';
        btn.style.fontSize = '0.8em';
        btn.onclick = () => window.location.href = '/admin.html' + search;
        container.appendChild(btn);
    }
    if (roles.includes('contributor')) {
        const btn = document.createElement('button');
        btn.textContent = 'Contribute';
        btn.className = 'btn btn-secondary';
        btn.style.padding = '3px 8px';
        btn.style.fontSize = '0.8em';
        btn.onclick = () => window.location.href = '/contributor.html' + search;
        container.appendChild(btn);
    }
    if (roles.includes('reviewer')) {
        const btn = document.createElement('button');
        btn.textContent = 'Review';
        btn.className = 'btn btn-secondary';
        btn.style.padding = '3px 8px';
        btn.style.fontSize = '0.8em';
        btn.onclick = () => window.location.href = '/reviewer.html' + search;
        container.appendChild(btn);
    }

    const profileBtn = document.createElement('button');
    profileBtn.textContent = 'Profile';
    profileBtn.className = 'btn btn-secondary';
    profileBtn.style.padding = '3px 8px';
    profileBtn.style.fontSize = '0.8em';
    profileBtn.onclick = () => window.location.href = '/profile.html' + search;
    container.appendChild(profileBtn);

    const headerActions = document.querySelector('header > div');
    if (headerActions) {
        headerActions.appendChild(container);
    }
}
