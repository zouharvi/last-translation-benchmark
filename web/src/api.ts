import $ from 'jquery';

// ---------- Types ----------

export interface User {
    username: string;
    roles: string[];
    quota_used: number;
    quota: number;
    total_accepted: number;
    total_submitted: number;
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
}

export interface TranslationEntry {
    model: string;
    translation: string;
    verified: boolean | null;
}

export interface Comment {
    author: string;
    text: string;
    timestamp: string;
}

export interface Rule {
    value: string;
}

export interface Submission {
    id: number;
    user_id: number;
    username: string;
    source_text: string;
    source_media?: string;
    source_instructions?: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: TranslationEntry[];
    status: 'pending' | 'accept' | 'reject';
    created_at: string;
    comments?: Comment[];
}

export interface PublicDashboardRow {
    name: string;
    affiliation: string;
    accepted_submissions: number;
}

// ---------- Cookie helpers ----------

function setCookie(name: string, value: string): void {
    const maxAge = 30 * 24 * 60 * 60; // 30 days
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${name}=${encodeURIComponent(value)}; max-age=${maxAge}; path=/; SameSite=Strict${secure}`;
}

export function getCookie(name: string): string | null {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
}

export function checkUrlAndSetCookies(): void {
    const params = new URLSearchParams(window.location.search);
    const urlUser = params.get('user');
    const urlToken = params.get('token');

    if (urlUser && urlToken) {
        setCookie('ltb_user', urlUser);
        setCookie('ltb_token', urlToken);
        
        const url = new URL(window.location.href);
        url.searchParams.delete('user');
        url.searchParams.delete('token');
        window.history.replaceState({}, document.title, url.toString());
    }
}

// Run immediately on import
checkUrlAndSetCookies();

export function logout(): void {
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `ltb_token=; max-age=0; path=/; SameSite=Strict${secure}`;
    document.cookie = `ltb_user=; max-age=0; path=/; SameSite=Strict${secure}`;
    window.location.href = '/';
}

// ---------- Generic fetch ----------

function apiCall<T>(method: string, url: string, data?: object): Promise<T> {
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
        if (data !== undefined) settings.data = JSON.stringify(data);
        $.ajax(settings);
    });
}

// ---------- API calls ----------

export function getMe() {
    return apiCall<User>('GET', 'api/me');
}

export function translate(text: string, source_lang: string, target_lang: string, source_media?: string, source_instructions?: string) {
    return apiCall<{
        results: Array<{ model: string; translation: string | null; error: string | null }>;
        quota_used: number;
        quota: number;
    }>('POST', 'api/translate-submission', { text, source_lang, target_lang, source_media, source_instructions });
}



export function verify(
    source_text: string,
    translations: string[],
    verification_rules: Rule[],
    source_media?: string,
) {
    return apiCall<{ results: boolean[]; detail: string }>(
        'POST', 'api/verify-submission', { source_text, translations, verification_rules, source_media }
    );
}

export function getSubmissions(
    mode: 'contributor' | 'reviewer' = 'contributor',
    filters?: {
        status?: 'pending' | 'accepted_or_rejected' | 'accepted' | 'rejected' | 'all';
        source_lang?: string;
        target_lang?: string;
        username?: string;
    },
) {
    const query = new URLSearchParams({ mode });
    const status = filters?.status;
    const sourceLang = filters?.source_lang;
    const targetLang = filters?.target_lang;
    const username = filters?.username;
    if (status && status.trim() !== '') query.set('status', status);
    if (sourceLang && sourceLang.trim() !== '') query.set('source_lang', sourceLang);
    if (targetLang && targetLang.trim() !== '') query.set('target_lang', targetLang);
    if (username && username.trim() !== '') query.set('username', username);
    return apiCall<Submission[]>('GET', `api/submissions?${query.toString()}`);
}

export function getPublicDashboard() {
    return apiCall<PublicDashboardRow[]>('GET', 'api/public-dashboard');
}

export function createSubmission(data: {
    source_text: string;
    source_media?: string;
    source_instructions?: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: Array<{ model: string; translation: string; verified: boolean | null }>;
}) {
    return apiCall<{ ok: boolean }>('POST', 'api/submissions', data);
}

export function updateSubmission(id: number, data: {
    source_text: string;
    source_media?: string;
    source_instructions?: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: Array<{ model: string; translation: string; verified: boolean | null }>;
}) {
    return apiCall<{ ok: boolean }>('PUT', `api/submissions/${id}`, data);
}

export function deleteSubmission(id: number) {
    return apiCall<{ ok: boolean }>('DELETE', `api/submissions/${id}`);
}


export function scoreSubmission(id: number, action: 'reject' | 'accept' | 'comment' | 'pending', comment?: string) {
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
    total_accepted: number;
    total_submitted: number;
    review_langs: string[];
    invite_sent: string;
    last_active: string;
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

export function updateAdminReviewScope(uid: number, review_langs: string[]) {
    return apiCall<AdminUser>('POST', `api/admin/users/${uid}/review-scope`, { review_langs });
}

export function markInviteSent(uid: number) {
    return apiCall<{ invite_sent: string }>('POST', `api/admin/users/${uid}/mark-invite-sent`);
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

    if (roles.includes('contributor')) {
        const btn = document.createElement('a');
        btn.textContent = 'Contribute';
        btn.className = 'btn-underlined';
        btn.style.fontSize = '0.85em';
        btn.href = 'contribute';
        container.appendChild(btn);
    }
    if (roles.includes('reviewer')) {
        const btn = document.createElement('a');
        btn.textContent = 'Review';
        btn.className = 'btn-underlined';
        btn.style.fontSize = '0.85em';
        btn.href = 'review';
        container.appendChild(btn);
    }
    if (roles.includes('admin')) {
        const btn = document.createElement('a');
        btn.textContent = 'Admin';
        btn.className = 'btn-underlined';
        btn.style.fontSize = '0.85em';
        btn.href = 'admin';
        container.appendChild(btn);
    }
    const profileBtn = document.createElement('a');
    profileBtn.textContent = 'Profile';
    profileBtn.className = 'btn-underlined';
    profileBtn.style.fontSize = '0.85em';
    profileBtn.href = 'profile';
    container.appendChild(profileBtn);

    const logoutBtn = document.createElement('button');
    logoutBtn.textContent = 'Logout';
    logoutBtn.className = 'btn-underlined';
    logoutBtn.style.fontSize = '0.85em';
    logoutBtn.addEventListener('click', logout);
    container.appendChild(logoutBtn);

    const headerActions = document.querySelector('header > div');
    if (headerActions) {
        headerActions.appendChild(container);
    }
}
