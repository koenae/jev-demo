# Blog post

`jev-vs-llm/` is a Hugo page bundle: `index.md` plus the figures it references.

Copy it into the blog as a folder:

```bash
cp -r blog/jev-vs-llm  ../my-blog/content/posts/jev-vs-llm
```

Regenerate the figures from the recordings after new `--record` runs:

```bash
uv sync --all-groups
uv run python scripts/blog_figures.py
```

The SVGs contain a `prefers-color-scheme` stylesheet, so they follow the blog's dark mode.
The PNGs are previews only.
