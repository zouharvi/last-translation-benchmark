import $ from 'jquery';
import { Comment } from './api';

export const esc = (s: string) => $('<div>').text(s).html();
export const fmtDate = (d: string) => (d || '').replace('T', ' ').slice(0, 16);

export function showToast(msg: string): void {
    const t = $('#toast').text(msg).addClass('show');
    setTimeout(() => t.removeClass('show'), 2000);
}

export function scoreBadge(status: 'pending' | 'accept' | 'reject', hasComments?: boolean): string {
    if (status === 'pending') return '<span class="badge badge-pending">Pending</span>';
    if (status === 'accept') return '<span class="badge badge-score-3">✓ Accepted</span>';
    return '<span class="badge badge-score-0">✗ Rejected</span>';
}

function getUsernameColor(username: string): string {
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = hash % 360;
    return `hsl(${h}, 70%, 90%)`;
}


export function renderCommentThread(comments: Comment[] | undefined, currentUsername: string): string {
    if (!comments?.length) return '';
    return `<div class="comment-thread">${comments.map(c => {
        const isOwn = c.author === currentUsername;
        const align = isOwn ? 'flex-end' : 'flex-start';
        const bg = getUsernameColor(c.author);
        return `<div class="comment-msg" style="align-self: ${align}; background: ${bg};">
            <span class="comment-author" title="${esc(c.timestamp)}" style="cursor: help;">${esc(c.author)}</span>
            <div class="comment-body">${esc(c.text)}</div>
        </div>`;
    }).join('')}</div>`;
}

export function accessDenied(roles: string[], target: string): void {
    document.body.innerHTML = `<div style="padding: 2rem; text-align: center;">
        <h2>Access Denied</h2>
        <p>You have roles: ${roles.map(x => `<em>${esc(x)}</em>`).join(', ')}.<br>Need: <em>${esc(target)}</em>.</p>
    </div>`;
}

export async function setupInstructions(mode: 'all' | 'contributor' | 'reviewer', loadImmediately = false) {
    const btn = $('#show-instructions-btn');
    const box = $('#instructions-box');
    if (!box.length) return;

    const loadContent = async () => {
        if (!box.data('loaded')) {
            const html = await fetch('assets/instructions.html').then(r => r.text());
            const bodyMatch = html.match(/<body>([\s\S]*?)<\/body>/);
            const body = bodyMatch ? bodyMatch[1] : html;

            let filtered = body;
            const splitKey = '<h2>Instructions for Reviewers</h2>';
            if (mode === 'contributor') {
                filtered = body.split(splitKey)[0];
            } else if (mode === 'reviewer') {
                filtered = splitKey + body.split(splitKey)[1];
            }

            box.html(filtered).data('loaded', true);
        }
    };

    if (loadImmediately) {
        await loadContent();
        box.show();
    }

    if (btn.length) {
        btn.on('click', async () => {
            if (box.is(':visible')) {
                box.slideUp();
                return;
            }

            await loadContent();
            box.slideDown();
        });
    }
}
