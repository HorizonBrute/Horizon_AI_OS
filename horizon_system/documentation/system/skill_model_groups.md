# Horizon AIOS — Skill Model Groups

Every AIOS skill declares which model-preference **group** its work should run on,
as a one-line callout in the skill body. This lets the in-context model-preference
layer (see `model_preferences.md`) give each skill a sensible default model without
the user naming one each time — documentation-style skills lean cheap, security-
critical ones lean capable.

This doc covers how that labeling works and how to maintain it. It is *separate*
from the `/skill-creation` skill, which only enforces the convention at creation
time.

---

## The callout

A skill body carries this line immediately after its `# Skill:` heading:

```
**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).
```

1.1 It is **documentation the acting model reads**, not enforcement. When the skill
    runs, the model sees the line and directs work to that group per the BYO layer.
1.2 It MUST live in the **body**. Frontmatter is stripped before the model sees a
    skill, so a `model_group:` frontmatter field would never be read. (The native
    `model:` frontmatter field does harness-level selection but takes a concrete
    model, not a group, and is also invisible to the model.)
1.3 A prompt directive ("use #X") always overrides the callout.

---

## Choosing a group

Match the dominant nature of the skill's work:

1.1 `#highcap` — security-sensitive, privileged, or destructive changes; deep
    judgment where a mistake is costly.
1.2 `#investigate` — research, live fetching, cross-source analysis.
1.3 `#midcost` — structured authoring/summarization with moderate judgment.
1.4 `#lowcost` — mechanical, read-only, or report-only work.
1.5 `#fast` — trivial single actions where latency matters.
1.6 `#debug` — step-by-step debugging / coding tasks.

When two fit, prefer the cheaper unless a mistake would be costly. **When unsure,
default to `#midcost`** and flag it for later review.

---

## At skill creation

`/skill-creation` adds the callout as part of scaffolding a new skill (Step 2.4):
it picks a group from the heuristics above, defaults to `#midcost` when it cannot
decide, and fills the matching "Model group" column in the tier's `index.md`. No
separate action is needed for new skills — the convention is enforced inline.

---

## Auditing and changing assignments

Use `/model-prefs-assign` to maintain the labels across existing skills:

1.1 **Audit** — report which skills have a callout, which are missing one, and
    which are malformed (wrong format or placed in frontmatter).
1.2 **Assign** — add a callout to skills that lack one, choosing a group from the
    heuristics (or `#midcost` default), after confirming with the user.
1.3 **Modify** — change a skill's group when its behavior should differ.
1.4 **Sync** — keep both `skills_bin/index.md` and `skills_sbin/index.md`
    "Model group" columns matching the callouts.

Run it after a batch of new skills, after an upstream sync, or any time you want to
rebalance which models do which skill work.

---

## Related

- `model_preferences.md` — the model-preference layer (groups, slots, routing).
- `$HORIZON_ETC/horizon_aios_model_prefs.md` — authoritative spec for the layer.
- `/model-prefs` — configure the groups themselves (the extend file).
- `/model-catalog-refresh` — get current models to populate groups.
- `/model-prefs-test` — verify a group resolves to the model you expect.
