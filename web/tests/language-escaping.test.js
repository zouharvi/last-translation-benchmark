const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

function read(relPath) {
  return fs.readFileSync(path.join(root, relPath), 'utf8');
}

function assertEscapesLanguageFields(relPath) {
  const source = read(relPath);

  assert.match(
    source,
    /escHtml\(s\.source_lang\)/,
    `${relPath} must escape source_lang before inserting it into HTML text`,
  );
  assert.match(
    source,
    /escHtml\(s\.target_lang\)/,
    `${relPath} must escape target_lang before inserting it into HTML text`,
  );
  assert.doesNotMatch(
    source,
    /\$\{s\.source_lang\}&rarr;\$\{s\.target_lang\}/,
    `${relPath} must not render raw language fields`,
  );
}

function assertBuildsFilterOptionsWithDomApi(relPath) {
  const source = read(relPath);

  assert.match(
    source,
    /appendLanguageOptions/,
    `${relPath} must build language filter options via DOM APIs`,
  );
  assert.match(
    source,
    /\.val\(lang\)/,
    `${relPath} must set option values without HTML interpolation`,
  );
  assert.match(
    source,
    /\.text\(lang\)/,
    `${relPath} must set option labels without HTML interpolation`,
  );
  assert.doesNotMatch(
    source,
    /<option value="\$\{[^}]*l[^}]*\}"/,
    `${relPath} must not interpolate language values into option attributes`,
  );
}

assertEscapesLanguageFields('src/review.ts');
assertEscapesLanguageFields('src/contribute.ts');
assertBuildsFilterOptionsWithDomApi('src/review.ts');
