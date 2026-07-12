# Security

`human-html` generates **self-contained, static HTML** review artifacts. A generated artifact runs no server, ships no telemetry, and transmits nothing on its own - open it in a browser and it renders from its own inline CSS/JS. The skill writes files under `docs/human-html/` and never uploads or sends anything by itself.

Two touch-points reach outside the local machine. Both are **optional, off by default, and intentional**; this file records why they are safe so an audit (human or automated) has the rationale in-repo.

## 1. S3 publish helper - `skills/human-html/scripts/publish-s3.sh`

An **opt-in** convenience for sharing an artifact as a link. It does nothing unless you run it *and* set `HUMAN_HTML_S3_BUCKET` (no default), and it refuses to run without an authenticated AWS session and an existing, reachable bucket **you own**. It **uploads** the local artifact to that bucket and prints an open URL (derived from the AWS CLI's own presigner). The flow is upload-then-display: it never downloads or executes remote content, and no S3 endpoint is hardcoded in the script.

## 2. Mermaid diagrams - optional client-side CDN import

Artifacts that contain a *live* Mermaid diagram load a **version-pinned** Mermaid build (`mermaid@10.9.1`) from the jsdelivr CDN via a browser `import()`. Safeguards:

- **Browser-only.** The import runs in the *reader's* browser when they open the HTML - never on the agent host or during generation. It cannot reach your machine, files, or credentials.
- **Pinned, not floating.** The version is pinned (`@10.9.1`), not `latest`, so the fetched code cannot change under you.
- **Self-gating.** The loader fetches the CDN **only** when a `.mermaid` element is present; a diagram-free artifact makes no network request at all.
- **Degrades safely.** With JavaScript off (or the CDN unreachable) the diagram shows its legible Mermaid source instead of breaking - the `.mermaid:not([data-processed])` fallback.
- **Preferred shipped state is offline.** The documented best practice (`skills/human-html/references/diagram-types.md`) is to render diagrams to **inline SVG** for the shipped artifact, dropping both the CDN and the JS dependency. The live CDN path is for drafting and iteration only.

## Reporting

Found something? Open an issue at https://github.com/rhnfzl/human-html/issues (or use the repository's private vulnerability reporting, if enabled).
