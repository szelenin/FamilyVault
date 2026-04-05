# Playbook: Update Documentation After Feature Implementation

**Trigger**: Run this after a feature spec has been implemented and committed.
**Command to invoke**: "Update the documentation for the latest feature"

---

## Step 1: Identify What Was Implemented

**Find the active feature branch and its spec:**
```bash
git branch --show-current           # e.g. 002-immich-setup
FEATURE=$(git branch --show-current | sed 's/^[0-9]*-//')
SPEC="specs/$(git branch --show-current)/spec.md"
```

**Read the feature spec to extract:**
- Feature name and description (from spec header)
- New tools/dependencies added (from Technical Context in plan.md)
- New scripts created (from `git diff main...HEAD --name-only | grep setup/`)
- New phases or steps introduced (from User Stories in spec.md)
- Changed folder structure (from data-model.md)
- New environment variables or config (from .env.example changes)

```bash
# See all files changed by this feature
git diff main...HEAD --name-only

# Read the feature spec
cat specs/$(git branch --show-current)/spec.md

# Read the implementation plan for tech stack details
cat specs/$(git branch --show-current)/plan.md
```

---

## Step 2: Update README.md

README.md is human-oriented. Update only these sections:

### Tools table
Add any new tool introduced by this feature. Format:
```markdown
| [Tool name](url) | One-line purpose description |
```
Check: `specs/NNN-feature/research.md` for tool decisions and rationale.
Do NOT add tools that are internal implementation details (e.g. Python libraries used only in scripts).

### Scripts table
Add any new user-facing script. Format:
```markdown
| `setup/component/script.sh` | One-line purpose |
```
Only include scripts the user might run directly, not internal helpers.

### Phases table
If the feature adds a new phase or significantly changes an existing one, update the row. Format:
```markdown
| N | Brief description of what happens |
```

### Storage Budget table
If the feature changes storage requirements (e.g. new cache directory), update the relevant row.

---

## Step 3: Update INSTALL.md

INSTALL.md is agent-executable. This is the most important document to update.

### Determine which phase this feature belongs to:
- Phase 0: Hardware, initial setup, folder structure
- Phase 1: iCloud / Photos.app / osxphotos
- Phase 2: Google Takeout / rclone
- Phase 3: Ongoing sync / cron
- Phase 4: Immich / Docker
- Phase 5: Verification

### If adding steps to an existing phase:

Add new steps following this exact template:
```markdown
### Step N.M — [Step Name]

**Skip if**: [command that returns success if already done]

**[AGENT]** or **[USER]** or **[AGENT + USER]**
```bash
[exact command]
```
**Verify**:
```bash
[verification command]
```
**Expected**: [exact output or description]

**On failure**: [diagnostic command or instruction]
```

Rules:
- Steps that run SSH commands are `[AGENT]`
- Steps requiring user to interact with GUI/browser are `[USER]`
- Steps that run a command then ask the user to confirm are `[AGENT + USER]`
- Every step MUST have a `**Verify**` block
- Every `[USER]` step has exact quoted text for the agent to say to the user
- Commands must be copy-paste ready — no placeholders like `<your-value>`

### If adding a new phase:

Add a new `## Phase N: Name` section following the structure of existing phases. Include:
- `**Skip if**` condition at the top
- `**Exit condition**` at the top
- All steps in order

### Update Phase 5 verification:

Add any new verification checks that confirm the new feature is working correctly.

---

## Step 4: Update component README (if applicable)

If the feature added or changed files in `setup/component/`, update `setup/component/README.md`:

- **Files table**: add new scripts with purpose
- **Troubleshooting section**: add any failure modes discovered during implementation
- **Prerequisites**: add any new prerequisites

---

## Step 5: Update CLAUDE.md (Agent Context)

CLAUDE.md is loaded automatically into every Claude Code session. Update only:
- `## Active Technologies` — add new language/framework/tool if introduced
- `## Recent Changes` — add one line: `- NNN-feature-name: What was added`

Do NOT rewrite CLAUDE.md sections — it is maintained by speckit tools.

---

## Step 6: Verify Completeness

Run this checklist before committing:

```bash
# Every tool in spec's plan.md Technical Context appears somewhere in README.md
grep -h "Primary Dependencies\|Language" specs/*/plan.md

# Every new script is in INSTALL.md
git diff main...HEAD --name-only | grep '\.sh$' | while read f; do
  basename "$f" | xargs -I{} grep -l "{}" INSTALL.md || echo "MISSING IN INSTALL.md: $f"
done

# No placeholder text left in INSTALL.md
grep -n '<your\|TODO\|FIXME\|placeholder' INSTALL.md && echo "PLACEHOLDERS FOUND" || echo "clean"

# INSTALL.md verify blocks exist for all steps
grep -c "^\*\*Verify\*\*" INSTALL.md
```

---

## Step 7: Commit

```bash
git add README.md INSTALL.md docs/ setup/*/README.md CLAUDE.md
git commit -m "docs: update documentation for [feature-name]

- Updated README tools/scripts/phases tables
- Added Phase N steps to INSTALL.md
- Updated [component] README
"
```
