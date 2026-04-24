# Last Translation Benchmark (WIP 🚧)

Effort to collecting verifiable difficult-to-translate texts.
Heavily work in progress, do not use.

There are three user roles:
- **Contributor** suggests source texts (planned video, images, and speech), auto-translate them, defines a verification method (an LLM prompt), and submits.
- **Reviewer** browses pending submissions and rejects, accepts, or comments.
- **Admin** with the ability to create and modify users.

## Quick start

```bash
# requires python >=3.12, node >= 20
npm install --prefix web
npm run build --prefix web/
pip install -e .
python3 server
```

<!-- TODO: print this link instead -->
Then open <http://localhost:8000>.

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