# Last Translation Benchmark

Effort to collecting verifiable difficult-to-translate inputs.
Heavily work in progress, do not use.

There are three user roles:
- **Contributor** suggests inputs (text,s video, images, and speech), auto-translate them, defines a verification method (e.g. an LLM prompt), and submits.
- **Reviewer** browses pending submissions and rejects, accepts, or comments.
- **Admin** with the ability to create and modify users.

## Development

```bash
# requires python >=3.12, node >= 20
npm install --prefix web
npm run build --prefix web/
# dev: includes linting hooks
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