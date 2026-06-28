const assert = require('node:assert/strict');

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderApiResultsHtml(results) {
  return results.map((r, i) => {
    const trText = r.translation !== null ? esc(r.translation) : `<em class="tr-error">${esc(r.error ?? 'Error')}</em>`;
    return `<div class="translation-result-row">
          <span class="api-name">${esc(r.model)}</span>
          <div class="tr-display">${trText}</div>
          <div data-idx="${i}" style="display: flex; gap: 4px; flex-wrap: wrap;"></div>
        </div>`;
  }).join('');
}

const maliciousTranslation = '<img src=x onerror="globalThis.__xss = true">';
const html = renderApiResultsHtml([
  { model: 'Mock model', translation: maliciousTranslation, error: null },
  { model: 'Broken model', translation: null, error: '<network failed>' },
]);

assert.match(
  html,
  /&lt;img src=x onerror=&quot;globalThis\.__xss = true&quot;&gt;/,
  'successful translation text must be HTML-escaped',
);
assert.doesNotMatch(
  html,
  /<img src=x onerror=/,
  'successful translation text must not create an HTML element',
);
assert.match(
  html,
  /<em class="tr-error">&lt;network failed&gt;<\/em>/,
  'error rows should keep their intentional wrapper while escaping error text',
);
