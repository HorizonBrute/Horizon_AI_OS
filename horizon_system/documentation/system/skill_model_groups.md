# Horizon AIOS — Skill Model Groups

Every AIOS skill declares which model-preference group its work should run on, via a one-line callout in the skill body. This lets the model-preference layer give each skill a sensible default without the user naming one each time.

**Full specification (group semantics, task-class routing, member grammar):**
→ https://github.com/HorizonBrute/Standardized_AI_Looping_Language-SAILL

---

## The callout

Placed immediately after the `# Skill:` heading in the skill body:

```
**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).
```

- **Body only** — frontmatter is stripped before the model sees a skill; this line must be in the body.
- **Documentation the acting model reads**, not enforcement. The model directs work to the group per the BYO layer.
- A prompt directive (`"use #X"`) always overrides the callout.
- Directs work the skill **delegates to agents** — it does not change the session model running the skill itself.

---

## Choosing a group

| Group | Use when… |
|-------|-----------|
| `#lowcost` | Mechanical, low-stakes, high-volume delegated work |
| `#midcost` | Default for most skills — balanced capability |
| `#highcap` | Security-critical, complex reasoning, or highest-accuracy tasks |
| `#investigate` | Open-ended research and exploration |

---

## Skills

| Skill | What it does |
|-------|--------------|
| `/skill-creation` | Scaffolds new skills; populates the callout (defaults to `#midcost`) |
| `/model-prefs-assign` | Audits all skills for missing/stale callouts and refreshes assignments |
