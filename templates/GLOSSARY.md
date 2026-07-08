# Glossary

This file is the workspace's shared definition lane for terms that appear in `docs/human-html/` artifacts. Add your domain jargon here so artifacts can link to canonical definitions instead of redefining terms each time.

## How artifacts reference these terms

Two acceptable ways:

- Inline tooltip: `<abbr title="Model Context Protocol">MCP</abbr>`
- Link to the definition: `<a href="GLOSSARY.md#mcp">MCP</a>`

The `human_html_artifacts.py check` command WARNs (does not block) when a term defined here appears in an artifact body without one of these treatments.

## Adding a term

Use a `## Term Name` heading exactly. The script extracts `## ` headings as the term list. Body text underneath can be free-form Markdown.

## Universal patterns

### Term Name

A short, clear definition. One to three sentences. Link out to authoritative documentation if relevant.

### Another Term

Same shape. Keep definitions to the point; long context belongs in the artifact, not the glossary.

---

<!--
Workspace owners: add your domain terms below this line.
Sort alphabetically within sections. Group related terms under sub-headings if useful.

Suggested first-pass terms (replace with your own domain jargon):
  ## MCP - Model Context Protocol (a boundary protocol an agent service can use to call tools)
  ## Gateway Service - example name for a front-door service that authenticates and proxies requests
  ## Agent Service - example name for a service that runs LLM agent loops
  ## SSE - Server-Sent Events, a one-way streaming transport for incremental responses
  ## Skill - a multi-turn agentic flow defined by a SKILL.md plus runtime hooks
  ## PROJ - example Jira project key; replace with your own project keys
-->
