import $ from 'jquery';
import { Comment } from './api';

export const esc = (s: string) => $('<div>').text(s).html();
export const fmtDate = (d: string) => (d || '').replace('T', ' ').slice(0, 16);

export function showToast(msg: string): void {
    const t = $('#toast').text(msg).addClass('show');
    setTimeout(() => t.removeClass('show'), 2000);
}

export function scoreBadge(p: number, comment?: string): string {
    if (p < 0) return comment ? '<span class="badge badge-score-1">💬 Commented</span>' : '<span class="badge badge-pending">Pending</span>';
    return `<span class="badge badge-score-${p === 1 ? 3 : 0}">${['✗ Rejected', '✓ Accepted'][p] ?? p}</span>`;
}

export function renderCommentThread(comments: Comment[] | undefined, viewerRole: 'reviewer' | 'contributor'): string {
    if (!comments?.length) return '';
    return `<div class="comment-thread">${comments.map(c => {
        const cls = c.role === viewerRole ? 'comment-msg-contributor' : 'comment-msg-reviewer';
        return `<div class="comment-msg ${cls}">
            <span class="comment-author">${esc(c.author)}</span>
            <span class="comment-ts">${esc(c.timestamp)}</span>
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

export async function setupInstructions(mode: 'all' | 'contributor' | 'reviewer') {
    const btn = $('#show-instructions-btn');
    const box = $('#instructions-box');
    if (!btn.length || !box.length) return;

    btn.on('click', async () => {
        if (box.is(':visible')) {
            box.slideUp();
            return;
        }

        if (!box.data('loaded')) {
            const html = await fetch('instructions.html').then(r => r.text());
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
        box.slideDown();
    });
}
