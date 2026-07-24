import $ from 'jquery';

// ---------- Types ----------

export interface Notification {
    created: string;
    type: string;
    status: 'unread' | 'viewed' | 'emailed';
    content: string;
}

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
    notification_consent: boolean;
    notifications: Notification[];
    review_langs?: string[];
}

export interface TranslationEntry {
    model: string;
    translation: string;
    verified: boolean[] | null;
}

export interface Comment {
    author: string;
    author_name?: string;
    text: string;
    created_at: string;
}

export interface Rule {
    value: string;
}

export interface Submission {
    id: number;
    user_id: number;
    username: string;
    name?: string;
    source_text: string;
    source_media?: string;
    source_instructions?: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: TranslationEntry[];
    status: 'pending' | 'accept' | 'return';
    created_at: string;
    comments?: Comment[];
}

export interface PublicDashboardRow {
    name: string;
    affiliation: string;
    accepted_submissions: number;
}

export interface AffiliationMapAuthor {
    name: string;
    accepted: number;
}

export interface AffiliationMapAffiliation {
    name: string;
    search_terms: string[];
    logo_domain: string;
    accepted: number;
    authors: AffiliationMapAuthor[];
}

export interface AffiliationMapPlace {
    lat: number;
    lng: number;
    city: string;
    country: string;
    precision: 'exact' | 'city' | 'country';
    accepted: number;
    affiliations: AffiliationMapAffiliation[];
}

export interface AffiliationMapMeta {
    mapped_authors: number;
    mapped_accepted: number;
    omitted: Array<{
        affiliation: string;
        author: string;
        accepted: number;
    }>;
}

export interface PublicDashboardData {
    rows: PublicDashboardRow[];
    total_submissions: number;
    total_authors: number;
    languages: [string, number][];
    affiliation_places: AffiliationMapPlace[];
    affiliation_map_meta: AffiliationMapMeta;
    data_source?: 'live_public_dashboard';
}

// ---------- Cookie helpers ----------

function setCookie(name: string, value: string): void {
    const maxAge = 10 * 365 * 24 * 60 * 60; // 10 years (effectively infinite)
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

function apiCall<T>(method: string, url: string, data?: object, signal?: AbortSignal): Promise<T> {
    return new Promise<T>((resolve, reject) => {
        const settings: JQuery.AjaxSettings = {
            url,
            method,
            contentType: 'application/json',
            dataType: 'json',
            success: (x: T) => resolve(x),
            error: (xhr: JQuery.jqXHR, textStatus) => {
                if (textStatus === 'abort') {
                    reject('abort');
                    return;
                }
                let detail = (xhr.responseJSON as any)?.detail;
                if (detail !== undefined && typeof detail !== 'string') {
                    detail = JSON.stringify(detail);
                }
                reject(detail ?? 'Request failed');
            },
        };
        if (data !== undefined) settings.data = JSON.stringify(data);
        const jqXHR = $.ajax(settings);
        if (signal) {
            signal.addEventListener('abort', () => jqXHR.abort());
        }
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
    return apiCall<{ results: boolean[][]; detail: string; quota: number; quota_used: number }>(
        'POST', 'api/verify-submission', { source_text, translations, verification_rules, source_media }
    );
}

export function getSubmissions(
    mode: 'contributor' | 'reviewer' = 'contributor',
    filters?: {
        status?: 'pending' | 'accepted_or_returned' | 'accepted' | 'returned' | 'all';
        source_langs?: string[];
        target_langs?: string[];
        username?: string;
    },
    signal?: AbortSignal
) {
    const query = new URLSearchParams({ mode });
    const status = filters?.status;
    const sourceLangs = filters?.source_langs;
    const targetLangs = filters?.target_langs;
    const username = filters?.username;
    if (status && status.trim() !== '') query.set('status', status);
    if (sourceLangs && sourceLangs.length > 0) sourceLangs.forEach(l => query.append('source_langs', l));
    if (targetLangs && targetLangs.length > 0) targetLangs.forEach(l => query.append('target_langs', l));
    if (username && username.trim() !== '') query.set('username', username);
    return apiCall<Submission[]>('GET', `api/submissions?${query.toString()}`, undefined, signal);
}

export function getPublicDashboard() {
    return apiCall<PublicDashboardData>('GET', 'api/public-dashboard');
}

export function createSubmission(data: {
    source_text: string;
    source_media?: string;
    source_instructions?: string;
    source_lang: string;
    target_lang: string;
    verification_rules: Rule[];
    translations: Array<{ model: string; translation: string; verified: boolean[] | null }>;
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
    translations: Array<{ model: string; translation: string; verified: boolean[] | null }>;
}) {
    return apiCall<{ ok: boolean }>('PUT', `api/submissions/${id}`, data);
}

export function deleteSubmission(id: number) {
    return apiCall<{ ok: boolean }>('DELETE', `api/submissions/${id}`);
}


export function scoreSubmission(id: number, action: 'return' | 'accept' | 'pending') {
    return apiCall<{ ok: boolean }>('POST', `api/submissions/${id}/score`, { action });
}

export function updateProfile(data: {
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
    notification_consent: boolean;
}) {
    return apiCall<{ ok: boolean }>('PUT', 'api/profile', data);
}

export function registerUser(data: {
    name: string;
    affiliation: string;
    email: string;
    credit_consent: boolean;
    notification_consent: boolean;
}) {
    return apiCall<{ ok: boolean }>('POST', 'api/register', data);
}

export function recoverLink(email: string) {
    return apiCall<{ ok: boolean }>('POST', 'api/recover-link', { email });
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
    last_active: string;
    review_suggestions: ReviewSuggestion[];
}

export interface ReviewSuggestion {
    id: number;
    source_lang: string;
    target_lang: string;
    username: string;
    name?: string;
}

export interface AdminOverview {
    users: AdminUser[];
    submissions_without_reviewer: ReviewSuggestion[];
    submissions_total: Record<string, number>;
    pending_languages: Record<string, number>;
}

export function getAdminOverview() {
    return apiCall<AdminOverview>('GET', 'api/admin');
}

export function deleteAdminUser(uid: number) {
    return apiCall<{ ok: boolean }>('DELETE', `api/admin/users/${uid}`);
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

export function addComment(id: number, comment: string) {
    return apiCall<{ ok: boolean }>('POST', `api/submissions/${id}/comment`, { comment });
}

export function handleNotifications(action: 'view' | 'clear') {
    return apiCall<{ ok: boolean }>('POST', 'api/notifications', { action });
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

    const dashboardBtn = document.createElement('a');
    dashboardBtn.textContent = 'Dashboard';
    dashboardBtn.className = 'btn-underlined';
    dashboardBtn.style.fontSize = '0.85em';
    dashboardBtn.href = 'dashboard';
    container.appendChild(dashboardBtn);

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
