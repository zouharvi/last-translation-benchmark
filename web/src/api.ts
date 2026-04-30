import $ from 'jquery';

// ---------- Types ----------

export interface User {
    username: string;
    roles: string[];
    quota_used: number;
    quota: number;
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

export interface Rule {
    type: 'llm' | 'contains' | 'not_contains' | '';
    value: string;
}

export interface Submission {
    id: number;
    user_id: number;
    username: string;
    source_text: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
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

export function getUsername(): string | null {
    const params = new URLSearchParams(window.location.search);
    return params.get('user');
}

// ---------- Generic fetch ----------

function apiCall<T>(method: string, url: string, data?: object): Promise<T> {
    const token = getToken();
    const username = getUsername();
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
        if (token && username) {
            settings.headers = {
                'Authorization': `Bearer ${token}`,
                'X-User-ID': username
            };
        }
        if (data !== undefined) settings.data = JSON.stringify(data);
        $.ajax(settings);
    });
}

// ---------- API calls ----------

export function getMe() {
    return apiCall<User>('GET', 'api/me');
}

export function translate(text: string, source_lang: string, target_lang: string) {
    return apiCall<{
        results: Array<{ api: string; translation: string | null; error: string | null }>;
        quota_used: number;
        quota: number;
    }>('POST', 'api/translate-submission', { text, source_lang, target_lang });
}

export function verify(
    source_text: string,
    translations: string[],
    verification_rules: Rule[],
) {
    return apiCall<{ results: boolean[]; detail: string }>(
        'POST', 'api/verify-submission', { source_text, translations, verification_rules }
    );
}

export function getSubmissions(mode: 'contributor' | 'reviewer' = 'contributor') {
    return apiCall<Submission[]>('GET', `api/submissions?mode=${mode}`);
}

export function createSubmission(data: {
    source_text: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: Array<{ api: string; translation: string; verified: boolean | null }>;
}) {
    return apiCall<{ ok: boolean }>('POST', 'api/submissions', data);
}

export function updateSubmission(id: number, data: {
    source_text: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: Array<{ api: string; translation: string; verified: boolean | null }>;
}) {
    return apiCall<{ ok: boolean }>('PUT', `api/submissions/${id}`, data);
}

export function scoreSubmission(id: number, action: 'reject' | 'accept' | 'comment', comment?: string) {
    return apiCall<{ ok: boolean }>('POST', `api/submissions/${id}/score`, { action, comment });
}

export function updateProfile(data: {
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
}) {
    return apiCall<{ ok: boolean }>('PUT', 'api/profile', data);
}

export function registerUser(data: {
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
}) {
    return apiCall<{ ok: boolean }>('POST', 'api/register', data);
}

export interface AdminUser {
    id: number;
    username: string;
    roles: string[];
    magic_token: string;
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
    quota: number;
    quota_used: number;
}

export function getAdminUsers() {
    return apiCall<AdminUser[]>('GET', 'api/admin/users');
}

export function deleteAdminUser(uid: number) {
    return apiCall<{ ok: boolean }>('DELETE', `api/admin/users/${uid}`);
}

export function rotateAdminToken(uid: number) {
    return apiCall<{ magic_token: string }>('POST', `api/admin/users/${uid}/rotate-token`);
}

export function adjustAdminQuota(uid: number, delta: number) {
    return apiCall<{ quota: number, quota_used: number }>('POST', `api/admin/users/${uid}/adjust-quota`, { delta });
}

export function updateAdminRoles(uid: number, roles: string[]) {
    return apiCall<AdminUser>('POST', `api/admin/users/${uid}/roles`, { roles });
}

export function addComment(id: number, comment: string) {
    return apiCall<{ ok: boolean }>('POST', `api/submissions/${id}/comment`, { comment });
}

// ---------- UI helpers ----------

export function renderRoleSwitcher(roles: string[]): void {
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.gap = '8px';
    container.style.marginLeft = '16px';

    const search = window.location.search;

    if (roles.includes('contributor')) {
        const btn = document.createElement('a');
        btn.textContent = 'Contribute';
        btn.className = 'btn btn-secondary';
        btn.style.padding = '3px 8px';
        btn.style.fontSize = '0.8em';
        btn.style.textDecoration = 'none';
        btn.href = 'contributor.html' + search;
        container.appendChild(btn);
    }
    if (roles.includes('reviewer')) {
        const btn = document.createElement('a');
        btn.textContent = 'Review';
        btn.className = 'btn btn-secondary';
        btn.style.padding = '3px 8px';
        btn.style.fontSize = '0.8em';
        btn.style.textDecoration = 'none';
        btn.href = 'reviewer.html' + search;
        container.appendChild(btn);
    }
    if (roles.includes('admin')) {
        const btn = document.createElement('a');
        btn.textContent = 'Admin';
        btn.className = 'btn btn-secondary';
        btn.style.padding = '3px 8px';
        btn.style.fontSize = '0.8em';
        btn.style.textDecoration = 'none';
        btn.href = 'admin.html' + search;
        container.appendChild(btn);
    }
    const profileBtn = document.createElement('a');
    profileBtn.textContent = 'Profile';
    profileBtn.className = 'btn btn-secondary';
    profileBtn.style.padding = '3px 8px';
    profileBtn.style.fontSize = '0.8em';
    profileBtn.style.textDecoration = 'none';
    profileBtn.href = 'profile.html' + search;
    container.appendChild(profileBtn);

    const headerActions = document.querySelector('header > div');
    if (headerActions) {
        headerActions.appendChild(container);
    }
}
