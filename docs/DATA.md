# Data Strategy

This project uses two kinds of data:

1. Lightweight structured data that belongs in Git.
2. Large raw source assets that should live outside normal Git history.

## Included In This Repository

- `data/questions.db`
  - SQLite question bank.
  - Current snapshot contains 5536 parsed questions.
  - Useful for demos, local practice mode, and API development.

- `data/papers_catalog.csv`
  - Catalog metadata for available CAIE 9709 papers.
  - Small enough to review and version with source code.

## Not Included In Normal Git

- `data/papers/`
  - Raw question paper and mark scheme PDFs.
  - Local corpus currently contains 936 PDF files.
  - This folder is ignored by `.gitignore`.

Reasons:

- GitHub blocks regular Git files larger than 100 MiB and warns above 50 MiB.
- Large binary histories make clones and diffs slow.
- Public redistribution of third-party exam PDFs can have licensing or copyright constraints.
- The PDF corpus changes independently from source code.

## Recommended Packaging Options

For private project use:

- Keep `data/papers/` local and restore it from a private backup.
- Use a private cloud bucket or drive folder and document the restore path.
- Use GitHub Releases or Git LFS only if you are comfortable with storage/bandwidth quota and rights to redistribute the files.

For public portfolio/demo use:

- Commit only the code, metadata, and lightweight SQLite sample.
- Keep raw PDFs out of the public repository.
- Add a short note explaining that the full paper corpus is excluded.

## Restore Layout

When restoring the raw corpus locally, use:

```text
data/papers/
  9709/
    2016/
    2022/
    ...
```

The app and question-bank tools expect paper paths to remain under `data/papers/`.
