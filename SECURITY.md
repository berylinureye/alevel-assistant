# Security Policy

## Reporting Security Issues

If you find a security issue, please do not open a public issue with exploit details.

Instead, contact the maintainer privately through GitHub, or open a minimal issue that says you have a security concern and need a private channel.

## Supported Scope

This is an open-source portfolio and research project. The public repository is intended for review, demos, and local experimentation.

Security-sensitive production deployments should review and harden:

- API key handling.
- Debug endpoints.
- CORS configuration.
- File upload limits.
- Public feedback/admin endpoints.
- Logging of model inputs and outputs.
- Raw paper corpus storage.

## Secrets

Never commit real values for:

- `ANTHROPIC_API_KEY`
- `DASHSCOPE_API_KEY`
- `DEEPSEEK_API_KEY`
- `GLM_API_KEY`
- `ADMIN_TOKEN`
- database passwords
- private URLs or credentials

Use `.env` locally. The repository intentionally tracks only `.env.example`.

## Public Repository Notes

- `data/papers/` is ignored and should remain outside normal Git history.
- Raw third-party exam PDFs should only be redistributed if you have the rights to do so.
- Demo databases and metadata should not contain student personal information.
- Student uploads should be treated as sensitive data in any hosted deployment.
