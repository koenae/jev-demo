# Blog post

`jev-vs-llm/index.md` is the post. The figures next to it are referenced with absolute
paths (`/fig-1-head-to-head.svg`), so in the Hugo repo they go into `static/`, not into
the post's folder.

Copy the post and the figures:

```bash
mkdir -p ../my-blog/content/posts/jev-vs-llm
cp blog/jev-vs-llm/index.md  ../my-blog/content/posts/jev-vs-llm/
cp blog/jev-vs-llm/fig-*.svg ../my-blog/static/
```

Regenerate the figures from the recordings after new `--record` runs:

```bash
uv sync --all-groups
uv run python scripts/blog_figures.py
```

The SVGs are self-contained light cards with fixed colors, so they look the same in light
and dark mode.
