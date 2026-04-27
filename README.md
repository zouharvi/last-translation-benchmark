# Last Translation Benchmark (WIP 🚧)

Effort to collecting verifiable difficult-to-translate texts.
Heavily work in progress, do not use.

There are three user roles:
- **Contributor** suggests source texts (planned video, images, and speech), auto-translate them, defines a verification method (an LLM prompt), and submits.
- **Reviewer** browses pending submissions and rejects, accepts, or comments.
- **Admin** with the ability to create and modify users.

## Development

```bash
# requires python >=3.12, node >= 20
npm install --prefix web
npm run build --prefix web/
pip install -e ".[dev]" && pre-commit install  # dev: includes linting hooks
# pip install -e .  # alternatively, if not developing
# prints login URLs
python3 server
```

The `server/` contains source code for the server.
The `web/` is the frontend code (TypeScript) which, when built, goes to `server/static/` to be served by the server.

### Default accounts

Each account is associated with a magic link that can be used to login from anywhere.

| Username | Role        |
|----------|-------------|
| `r1`     | Reviewer    |
| `c1`     | Contributor |
| `c2`     | Contributor |
| `a1`     | Admin       |

### Environment variables

Create `config.toml` based on `config.template.toml`
- `OPENROUTER_API_KEY`: enables real LLM translation and verification