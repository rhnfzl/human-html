# Workflow integrations

> On-demand reference for the human-html skill.

Two recurring downstream workflows for HTML artifacts produced by this skill: handing the artifact to a coding agent to implement the decisions inside, and overlaying meeting Q&A onto the artifact after presenting it. Each gets a dedicated optional block that lives inside the artifact as embedded JSON-LD plus a human-readable rendering.

### Decisions-captured block (coding-agent handoff)

After running an adversarial plan-review session against the artifact, you typically end with a small set of decisions you want a coding agent (Claude Code, Cursor, Aider, Codex) to act on. Capture them in a dedicated block inside the artifact so you can hand the same HTML file to any agent and have it implement the resolutions.

Recommended block shape: a visible "Decisions" section with a human-readable summary per decision, followed by an embedded JSON-LD array machine-readable by any of the named agents.

```html
<section id="decisions" class="section" data-decisions="true">
  <h2>Decisions captured</h2>
  <ol>
    <li>
      <p><strong>DR-001 - Use OAuth2 client credentials for service-to-service auth.</strong>
      <em>Rationale:</em> simpler token-refresh story than mTLS; aligned with the current auth service.
      <em>Implementation note:</em> add issuer config, migrate <code>service_clients</code> table, update CI tests.</p>
    </li>
    <li>
      <p><strong>DR-002 - Keep cookie-based sessions for one sprint as the rollback path.</strong>
      <em>Rationale:</em> minimises blast radius if JWT rollout regresses; cookie middleware stays in code, gated by feature flag.</p>
    </li>
  </ol>
  <script type="application/ld+json" id="decisions-data">
  [
    {
      "@context": "https://schema.org/",
      "@type": "Decision",
      "id": "urn:decision:DR-001",
      "summary": "Use OAuth2 client credentials for service-to-service auth",
      "task": "Add OAuth2 issuer endpoint to the auth service; migrate service_clients table; update CI to assert token issuance under 200ms.",
      "constraints": ["preserve existing API surface", "no major version bump"],
      "languages": ["Python"],
      "priority": "high",
      "acceptanceCriteria": ["pytest auth/test_oauth_client.py passes", "smoke test issues a token in &lt; 200ms"],
      "targets": [
        {"path": "auth/issuer.py", "purpose": "new endpoint"},
        {"path": "migrations/2026_07_add_service_clients.sql", "purpose": "table"}
      ],
      "patchPreferences": { "format": "unified-diff", "perHunk": true },
      "status": "accepted",
      "confidence": "high",
      "author": "Jordan Ellis",
      "dateCreated": "2026-05-25"
    }
  ]
  </script>
</section>
```

Field shape (camelCase, derived from ADR + agent-handoff research):

- Required: `@context`, `@type` (`Decision` or `PatchDecision`), `id`, `summary`, `status` (one of `proposed`, `accepted`, `rejected`, `deferred`), `confidence` (`high`/`medium`/`low`, per the confidence tiers below).
- Recommended: `task` (the imperative instruction), `constraints`, `acceptanceCriteria`, `targets[]` (`{path, purpose, hunkId?}`), `priority` (`low`/`medium`/`high`), `dateCreated`, `author`.
- Optional: `patchPreferences`, `tests[]`, `assignees`, `links` (related ADRs, tickets).

#### Per-agent handoff (no adapter code in the skill, but documented placement)

| Agent | How it reads the block |
|---|---|
| Claude Code | Place the artifact at `docs/human-html/...html` and add a short pointer in `CLAUDE.md` / `.claude/CLAUDE.md` (`See docs/human-html/<file>.html for the decisions to implement.`). Claude walks up the tree and concatenates `CLAUDE.md`. |
| Cursor | Drop a `.cursor/rules/decisions.mdc` file that says `Implement the decisions captured in docs/human-html/<file>.html. Apply each Decision in order. Respect constraints and acceptanceCriteria.` |
| Aider | Add the artifact to `.aider.conf.yml` under `file:`, then run `/ask` against it and switch to `/code` to apply. |
| Codex CLI | Symlink or copy the artifact into `specs/decisions/<file>.html` or reference it from `codex.md`. Use `--output-schema` if you want the agent to return a structured patch. |

The skill itself does not write these adapter files; documenting where they go is enough so the same artifact serves all four agents.

### Meeting Q&A overlay (footnote-style)

After presenting an HTML artifact in a meeting, you typically end with a list of audience questions: ones you answered, ones you deferred, and ones nobody asked but might have inferred from the discussion. The Q&A overlay pattern captures them back into the artifact as a single footnote-style block at the bottom, with each question anchored back to the section that prompted it.

Footnote-style annotations beat marginalia / sticky notes / threaded comments for single-file HTML. They scale to many questions, export cleanly to PDF, are accessible by default, and survive copy-paste.

```html
<section id="meeting-qa" class="section" data-meeting-qa="true">
  <h2>Questions from the 2026-05-25 review meeting</h2>
  <p>Grouped by topic, not by speaker. Three categories: answered live, deferred / action item, and inferred (questions that did not get asked but probably should have).</p>

  <h3>Topic: rollout sequencing</h3>
  <ol class="qa-list">
    <li class="qa-item qa-answered" data-status="answered" data-anchor="#sequence">
      <p><strong>Q1.</strong> Why land Candidate 2 stage 1 before Candidate 3? <em>(asked by Marcus, 14:08)</em></p>
      <p><strong>A.</strong> Because the helpers split in Candidate 3 needs the <code>BundleCfg</code> abstraction from stage 1; doing them in reverse forces rework. Linked to <a href="#sequence">Sequence section</a>.</p>
    </li>
    <li class="qa-item qa-deferred" data-status="deferred" data-anchor="#recommendation">
      <p><strong>Q2.</strong> Should the same sequencing apply to the Agent Service mirror? <em>(asked by Sam, 14:21; deferred)</em></p>
      <p><strong>Action:</strong> Sam to draft a parallel decision artifact for the Agent Service; due 2026-06-01. <a href="#recommendation">Source section</a>.</p>
    </li>
  </ol>

  <h3>Topic: risk &amp; rollback</h3>
  <ol class="qa-list">
    <li class="qa-item qa-inferred" data-status="inferred" data-confidence="0.82">
      <p><strong>Q3 (inferred, confidence 0.82).</strong> What is the rollback plan if Candidate 1's <code>register_tool_bundle</code> regresses one of the 50 wrappers in production?
      <em>Rationale for inferring:</em> rollout sequencing was discussed but rollback was not raised; for a wide-blast-radius refactor it is the obvious next question.</p>
      <p><strong>Suggested owner:</strong> Jordan Ellis, before sign-off.</p>
    </li>
  </ol>

  <script type="application/ld+json" id="meeting-qa-data">
  {
    "@type": "MeetingQAOverlay",
    "meetingDate": "2026-05-25",
    "transcriptSource": "meetings/2026-05-25-architecture-review.docx",
    "questions": [
      {"id": "Q1", "topic": "rollout sequencing", "text": "Why land Candidate 2 stage 1 before Candidate 3?", "speaker": "Marcus", "timestamp": "14:08", "status": "answered", "answer": "Because the helpers split in Candidate 3 needs BundleCfg from stage 1.", "anchor": "#sequence"},
      {"id": "Q2", "topic": "rollout sequencing", "text": "Should the same sequencing apply to the Agent Service mirror?", "speaker": "Sam", "timestamp": "14:21", "status": "deferred", "owner": "Sam", "dueDate": "2026-06-01", "anchor": "#recommendation"},
      {"id": "Q3", "topic": "risk and rollback", "text": "What is the rollback plan if Candidate 1's register_tool_bundle regresses one of the 50 wrappers in production?", "status": "inferred", "confidence": 0.82, "rationale": "Rollback was not raised but is the obvious next question for a wide-blast-radius refactor."}
    ]
  }
  </script>
</section>
```

Categorization (research-backed thresholds):

- `answered` - question asked during the meeting and answered live. Include the answer inline.
- `deferred` / `action_item` - question asked but punted; include owner + due date.
- `inferred` - question that did not get asked but probably should have. Required: `confidence` field (0-1) and `rationale`. Surface defaults: `confidence >= 0.9` auto-show, `0.7-0.9` show with provenance label, `<0.7` hide behind an "inferred ideas" toggle. Use conservative wording ("Could a follow-up ask...") when grounding is absent.

Grouping: by topic, not by speaker. Topic grouping surfaces cross-cutting concerns; speaker grouping hides patterns and personalises follow-up.

When `data-meeting-qa="true"` is present, the meeting Q&A overlay rule validates the embedded `#meeting-qa-data` JSON-LD (that rule is defined in `SKILL.md`). The overlay itself remains optional and post-presentation; the validator only fires once you add the marker. Worked example in `examples/architecture-canonical.html`.

---


### Decision confidence tiers

Tag each captured decision with how settled it is, so a reader knows what to trust:

- `confidence: high` - sourced / verified. Render `<span class="confidence confidence-high">high</span>` (green).
- `confidence: medium` - inferred, not verified. `<span class="confidence confidence-medium">medium</span>` (blue).
- `confidence: low` - not recoverable / a guess; treat as cognitive debt. `<span class="confidence confidence-low">low</span>` (amber).

Add `confidence` to the JSON-LD `Decision` object **and** show the badge on the human-readable line.

### Re-entry context

`review` and `architecture` scaffolds ship a **Re-entry context** section: the invariants that must stay true, the non-obvious coupling, and the easy-to-miss step a returning reader (or agent) needs to resume the work. Keep it to the 3-5 things that are not recoverable by reading the code.
