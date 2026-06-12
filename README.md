# <img src="web/src/assets/favicon.svg" height=30> Last Translation Benchmark


This platform gathers inputs (text, video, audio, images, documents) that are challenging for modern machine translation systems.
Contributors submit these inputs alongside machine translation outputs and a verification rule.
With 10 approved submissions, contributors are eligible for inclusion in the upcoming research publication.

There are three user roles:
- **Contributor** suggests inputs (text, images, and speech), auto-translate them, defines a verification method, and submits.
- **Reviewer** browses pending submissions and returns, accepts, or comments.
- **Admin** with the ability to create and modify users.
Each account is associated with a magic link that can be used to login from anywhere.

If you're interested in contributing, register at [last-translation-benchmark.vilda.net](https://last-translation-benchmark.vilda.net).
Make sure you read the instructions beforehand.

> Example from English to Czech translation: \
> **Source**: "_what's the difference between jail and prison?_" \
> **Translation (Google Translate)**: "_jaký je rozdíl mezi vězením a vězením?_" \
> **Translation (Human)**: "_jaký je rozdíl mezi vazební věznicí a vězením?_" \
> **Verification rule**: "_The words for the "jail" and "prison" shouldn't be identical."_

## Development

```bash
# requires python >=3.12, node >= 20
npm install --prefix web
npm run build --prefix web/
# use this one when developing
pip install -e ".[dev]" && pre-commit install -c .github/.pre-commit-config.yaml
# use this one when not developing
pip install -e .
# prints login URLs
python3 server
```

The `server/` contains source code for the server.
The `web/` is the frontend code (TypeScript) which, when built, goes to `server/static/` to be served by the server.

You can specify the `--host`, `--port` and `--host-public` arguments when starting the server. 
The last is used to show the login URLs.

### Environment variables

Create `config.toml` based on `config.template.toml`
- `CONTRIBUTOR_QUOTA_DEFAULT` default "credits" for new users
- `DB_PATH` path to the persistent database file (will be created automatically)
- `EMAIL_*` configuration of email sending

Some API services need API keys:
- `OPENROUTER_API_KEY`: enables real LLM translation and verification
- `LARA_API_ID` and `LARA_API_SECRET`: enables Lara API-based translation
- `GOOGLE_TRANSLATE_API_KEY`: enables API-based Google Translate


### Instructions

The instructions in [web/src/assets/instructions.html](web/src/assets/instructions.html) are based on upstream document written in Typst and should not be edited locally in this repo.

## Contributing

We welcome bugreports, hands-on, and research contributions.
AI-generated PRs are fine as long as you verify everything and take ownership of the changes.
This effort is organized by a collective of researchers from ETH Zurich, JHU, CUNI, UvA, KIT, and many others.
Reach out to [last-translation-benchmark@vilda.net](mailto:last-translation-benchmark@vilda.net) with inquiries.