# Last Translation Benchmark (WIP 🚧)

Effort to collecting verifiable difficult-to-translate texts.
Heavily work in progress, do not use.

There are two user roles:
- **Contributor** suggests source texts (planned video, images, and speech), auto-translate them, defines a verification method (an LLM prompt), and submits.
- **Reviewer** browses pending submissions and awards points (0, 1, or 2) per submission.

## Quick start

```bash
npm install --prefix web
npm run build --prefix web/
pip install -e .
python3 server
```

<!-- TODO: print this link instead -->
Then open <http://localhost:8000>.

### Default accounts

| Username | Password | Role        |
|----------|----------|-------------|
| `r1`     | `r1`     | Reviewer    |
| `c1`     | `c1`     | Contributor |
| `c2`     | `c2`     | Contributor |

### Environment variables

Create `config.toml` based on `config.template.toml`
- `OPENROUTER_API_KEY`: enables real LLM translation and verification
- 