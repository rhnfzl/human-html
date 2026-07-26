# The artifact spine

The fifteen content rules say what an artifact must **contain**. This file says what an
artifact must never **do**, whatever shape it takes. That distinction is the whole reason
the file exists: a rule about containing something can only be written for a known
structure, and `artifact-mode="dynamic"` throws the structure away. Everything below
survives that, because none of it depends on which sections exist.

Read this before writing any dynamic artifact. Read it before writing prose in a
standard one too; the spine was always in force, it just was not written down.

Three layers, in order of how hard they bind:

1. **The mechanical floor.** Marked by `check`. Every rule in it is a marker check, so
   passing means "did not obviously skip this", never "got this right".
2. **The spine.** Never traded away, in any mode, for any reason. Judgment, not lint.
3. **Prose discipline.** Craft rules that make an artifact read as though a person
   with a point of view wrote it. Judgment, applied by function and not by keyword.

---

## 1. The mechanical floor

These run in both modes and are checked by `human_html_artifacts.py check`. Dynamic mode
relaxes exactly three rules (`required-section`, `read-map`, and `nav-anchors` from BLOCK
to WARN) and nothing here.

| What it aims at | Rule | What the check actually proves |
|---|---|---|
| Renders on a phone at all | `viewport-meta` (BLOCKS) | The meta tag is present and sets `width=device-width` |
| A wide table does not clip | `table-responsive` | Some responsive treatment exists near a `<table>` |
| Content exists with JavaScript off | `js-content-fallback` | JS inserts DOM and *a* `<noscript>` exists somewhere |
| The reader gets the answer first | `summary-first` (BLOCKS) | A `data-summary="true"` section exists somewhere in the page |
| A comparison gets a real visual | `comparison-visual` (BLOCKS) | A comparison heading's section contains a visual element |
| The words are gloss-able and plain | `glossary-link` and the plain-language registry | Known terms are wrapped or linked; coined terms are glossed on first use |
| Where this came from is recorded | `provenance-footer`, `provenance-fields`, `meta-ribbon` | The markers and the documented JSON-LD fields are present |
| House style holds | `em-dash`, `slop-signal` | No em/en dash in prose; no AI-default violet, emoji heading, or placeholder text |

**Read the third column, not the first.** Every one of these is a marker check, and the gap
between the two columns is where an artifact goes wrong while passing. Three that matter:

- `summary-first` finds the section anywhere in the document. A summary buried above the
  footer passes the rule and answers nobody. Put it first because the reader needs it
  first, not because `check` made you.
- `js-content-fallback` cannot read your fallback. Any `<noscript>`, including an empty one
  or one about something else entirely, satisfies it. It knows JS writes DOM and that the
  word `noscript` appears; it has no idea whether the static content matches what the
  script would build. Verify it by looking: `render --no-js`.
  Watch the `!important` trap while you are there. A `<noscript>` rule that hides an inert
  control loses to an inline `style="display:flex"` on that control, so the page renders with
  a live-looking widget driving nothing. Write `display: none !important` in a `<noscript>`
  hide, or keep `display` out of the inline style.
- `table-responsive` matches an `overflow-x` or a media query near a table. It cannot tell
  whether the container is reachable by keyboard, which is the requirement below.

None of this makes the rules pointless. A marker check catches the artifact that never
tried, which is the common failure. It just never certifies the artifact that did.

Three more belong to the floor and are **not** lintable, so they live here as
requirements rather than as rules:

- **Colour never carries meaning alone.** Every status, severity, or delta that is
  colour-coded also carries a label, a shape, or a glyph. Two mechanisms defeat hue on
  its own and neither is rare: a reader with red-green colour vision deficiency, and any
  greyscale or printed copy, which flattens every hue in the artifact at once. WCAG 1.4.1
  states the requirement; the fix is one word of text beside the swatch.
- **Anything hoverable is also focusable, and works on a touch screen.** Hover is a
  mouse-only affordance. A `<span>` with `cursor: help` and a `mouseenter` handler
  promises interactivity to everyone and delivers it to one input device. Bind
  `focusin`/`focusout` alongside the pointer events, make sure the trigger is reachable
  by keyboard, and make sure the relationship still reads with no pointer, no JavaScript,
  and no colour (a numbered `<sup>` correspondence does this; a highlight alone does not).

  Reach for `focusin` rather than `focus`, because it bubbles. If the region already
  contains something natively focusable, a link or a `<summary>` or a control, listening
  on the region catches focus from inside it and the region needs no `tabindex` of its
  own. Adding one anyway doubles the tab stops and every second stop does nothing when
  activated, which is its own accessibility problem. Add `tabindex="0"` only when nothing
  inside the region can take focus.
- **A scroll container is reachable by keyboard.** Any `overflow-x: auto` wrapper (the
  standard treatment for a wide table) needs `role="region"`, an `aria-label` naming what
  it holds, and `tabindex="0"`. Without a tab stop the container can be scrolled by
  trackpad and by nothing else, so a keyboard reader simply cannot see the clipped
  columns.

## 2. The spine

Never traded away. If a structure you invented requires breaking one of these, the
structure is wrong, not the rule.

- **No coined framework names, branded acronyms, or capitalised taxonomy labels.** Name a
  recurring pattern in plain lowercase words, for use inside this one artifact. "The
  Three Pillars of Ingest" is a tell. An established term of art, or a short operational
  handle defined on first use ("blindspot pass"), is fine: the ban is on branding, not on
  vocabulary.

- **Never name, segment, flatter, or exclude a reader.** No "for the engineers", no "if
  you are non-technical", no reading guide labelled by job title, and no job title in the
  markup either. Depth is offered and never assigned: lead with the plain intuition, then
  give the concrete detail, and let people stop where they want. Reading guides are
  labelled by depth (`Quick read`, `Standard`, `Full read`).

  This bans sorting readers into groups, not the second person. "You" is fine and usually
  better: it is one peer over your shoulder, and an instruction reads plainer as "wrap the
  table in a scroll container" than as "the table should be wrapped". What is banned is
  the sentence that decides which reader you are before addressing you.

- **Refuse the engineered keystone.** No sentence built to be quoted, no bolded law per
  section on a schedule, no aphorism as a closer. An artifact ends on the finding or the
  plain judgment. A memorable line is fine when it falls out of the reasoning; a line
  placed to be memorable is the tell.

- **Hedges stay.** "Perhaps", "at least in our case", "we did not test the third path"
  are honesty, and they are load-bearing in a document someone will act on. Do not smooth
  them into confident prose. Hedge about your own confidence, never to rank someone
  else's authority.

- **Every claim earned.** No population claims ("most teams do X", "everyone knows Y").
  State the mechanism, cite the artifact, or mark it as a view. An artifact that a reader
  will act on cannot afford a claim it cannot back.

- **Credibility comes from this artifact's own evidence.** A `file:line`, a log line, a
  config diff, a measured number, a named commit. Not from a borrowed name. Honest
  attribution of an idea you took is good; a name used to win an argument instead of
  making it is not.

- **Avoid the first person.** Prefer the subject dropped ("Traced it to the retry
  wrapper"), the artifact as subject ("the plan sequences the migration in three"), or
  the second person. Not an absolute ban, but the default is to route around it.

- **Never stage common knowledge as a reveal.** Writing to a reader who knows the system
  is the job. Mark shared ground as shared and pivot immediately to what is actually new.
  A "here is something you did not know" cadence over a fact the reader uses daily is
  the fastest way to lose them.

- **Plain register throughout.** No em dashes. No hype diction (unlock, seamless,
  transform, elevate, delve, boasts, a testament to, evolving landscape). Short
  declaratives. Honest concession over deflection.

- **Diagrams are thinking aids.** A diagram earns its place by making a mechanism
  legible, never by filling space or looking finished. It carries a plain-prose
  restatement beside it so it is not the only path to the information.

- **Inherit the tokens.** Dynamic mode is free in structure and locked in style. Use the
  scaffold's CSS variables and type scale. Do not invent a palette. Palette invention is
  the first place a model's defaults surface, and the violet AI-default ramp is already a
  `slop-signal` hit.

## 3. Prose discipline

Craft rules. Apply by rhetorical function, not by keyword: "highlight", "key", and
"align" are often the right technical word, and the tell is the promotional use, not the
string.

- **No list left as a dump.** After any list or table, one sentence saying what it
  implies or how big the consequence is. Artifacts are mostly lists, which makes this
  the highest-value rule on the page.

- **Name the failure, not the category.** A finding says what breaks and when, not what
  bucket it belongs to. "Unbounded retry" is a category. "A 500 from the vendor retries
  forever and the queue backs up behind it within about four minutes" is a failure.
  Every finding, risk, and blocker gets the second form.

- **Small precise numbers over adjectives.** "cut p95 from 1.2s to 340ms" over
  "significantly faster". Falsifiable and slightly deflating beats impressive.

- **One canonical noun per thing.** Repeat the correct term. Synonym-swapping for
  elegance makes a reader wonder whether two names mean two things.

- **Unpack a compressed label in the next sentence.** A coined pair without its
  plain-language meaning reads as jargon, even when it is precise.

- **No participle analysis tails.** End on the fact, not on ", highlighting the
  importance of X" or ", underscoring a shift". A participle naming a real action is
  fine and usually reads better as a finite clause.

- **Vary the rhythm.** A template produces blocks of identical size, and identical size
  reads as machine-made. A one-line paragraph is a pivot or a landing; two to four
  sentences is ordinary development; an occasional longer one marks the dense centre.
  The smell is uniformity, not length. Split at the seam between beats, never at a count.

- **A mechanism section earns its own visual.** `comparison-visual` requires this for
  comparisons. Extend it by default: if a section explains how something works, give it
  a figure.

- **British English in prose** (summarise, favourite, colour, behaviour). CSS keywords
  and code identifiers are exempt; `color: var(--ink)` stays as it is.

- **Ground an abstract instruction in one concrete example first**, a real command or a
  real config, then generalise.

## What is deliberately not here

No rule against contrast pairs, enumeration, or three-item sequences. Those are how an
argument gets built, and banning the construction to avoid a tell would cost more than
the tell does. The failure mode is **monotony**: one mould repeated, or a triad assembled
for rhythm rather than because there are three real things. Thin the repeats and keep
the substrate contrasts.

No rule prescribing which sections a dynamic artifact contains. That is the mode.

## Keeping this thin

This file is short on purpose. Most of it came from reading one repository of 33
hand-authored artifacts once, plus the prose rules already calibrated elsewhere from
real edits. One artifact is n equals 1. When a real artifact shows a rule here to be
wrong, or shows a missing one, change it and date the change; do not harden a single
observation into law. A durable principle earns a place here. A one-time surface
observation stays a note until it repeats.
