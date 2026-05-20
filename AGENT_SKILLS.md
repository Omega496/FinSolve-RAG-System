# AGENT_SKILLS.md — Skill Manifest

---

## Available Skills

### 1. Caveman Mode (Ultra-Compressed Communication)
**Trigger:** `/caveman` or "be brief" or "less tokens"
**What:** Cuts token usage ~75%. Drop filler, articles, pleasantries. Fragments OK.
**Levels:** `/caveman lite` | `/caveman full` (default) | `/caveman ultra`
**Stop:** "stop caveman" or "normal mode"

### 2. Cavecrew (Subagent Delegation)
**Trigger:** "use cavecrew", "delegate to subagent", "spawn investigator/builder/reviewer"
**What:** Caveman-compressed subagents. Save ~60% context tokens.
**Agents:**
- `cavecrew-investigator` — locate code, find symbols
- `cavecrew-builder` — surgical edit, ≤2 files
- `cavecrew-reviewer` — diff review, one-line comments

### 3. Caveman-Commit (Commit Messages)
**Trigger:** `/commit` or "write a commit" or staging changes
**What:** Terse commit messages. Conventional Commits. ≤50 char subject.
**Example:** `feat(api): add GET /users/:id/profile`

### 4. Caveman-Review (Code Review)
**Trigger:** `/review` or "code review" or "review the diff"
**What:** One-line PR comments. Location, problem, fix.
**Example:** `L42: 🔴 bug: user null. Add guard.`

### 5. Caveman-Compress (Memory File Compression)
**Trigger:** `/caveman:compress <filepath>` or "compress memory file"
**What:** Compress .md/.txt files to caveman prose. Saves ~46% input tokens.
**Backup:** Original saved as `FILE.original.md`

### 6. Caveman-Stats (Token Usage)
**Trigger:** `/caveman-stats`
**What:** Show real token usage and savings for current session.

### 7. Caveman-Help (Quick Reference)
**Trigger:** `/caveman-help`
**What:** Display all caveman commands and modes.

### 8. Graphify (Knowledge Graph)
**Trigger:** `/graphify` or `/graphify <path>`
**What:** Build navigable knowledge graph from codebase.
**Outputs:** `graphify-out/graph.html` (interactive), `GRAPH_REPORT.md` (audit), `graph.json` (GraphRAG-ready)
**Commands:**
- `/graphify .` — build graph of current directory
- `/graphify query "question"` — BFS traversal
- `/graphify path "A" "B"` — shortest path between concepts
- `/graphify explain "X"` — plain-language explanation of node

### 9. Find-Skills (Skill Discovery)
**Trigger:** "find skill for X" or "is there a skill for X"
**What:** Search skills.sh for new skills to install.
**Install:** `npx skills add <owner/repo@skill> -g -y`

---

## Session Start Checklist

1. `/caveman` — activate compressed mode
2. `/graphify .` — map the codebase (if not already done)
3. Before commits: `/commit`
4. Before reviews: `/review`
5. Context tight: "use cavecrew"
6. Check usage: `/caveman-stats`

---

## Skill Paths (for reference)

All skills stored in: `~/.agents/skills/`

| Skill | Path |
|-------|------|
| caveman | `~/.agents/skills/caveman/SKILL.md` |
| cavecrew | `~/.agents/skills/cavecrew/SKILL.md` |
| caveman-commit | `~/.agents/skills/caveman-commit/SKILL.md` |
| caveman-review | `~/.agents/skills/caveman-review/SKILL.md` |
| caveman-compress | `~/.agents/skills/caveman-compress/SKILL.md` |
| caveman-stats | `~/.agents/skills/caveman-stats/SKILL.md` |
| caveman-help | `~/.agents/skills/caveman-help/SKILL.md` |
| graphify | `~/.agents/skills/graphify/SKILL.md` |
| find-skills | `~/.agents/skills/find-skills/SKILL.md` |
| compress | `~/.agents/skills/compress/SKILL.md` |

---

## Auto-Trigger Rules

These skills activate automatically (no manual trigger needed):

- **caveman** — when user says "less tokens", "be brief", "save tokens"
- **caveman-commit** — when staging changes detected
- **caveman-review** — when reviewing PRs/diffs

---

## Quick Commands

```
/caveman                    # Activate caveman mode
/caveman ultra              # Maximum compression
/commit                     # Generate commit message
/review                     # Code review comments
/caveman:compress FILE.md   # Compress memory file
/caveman-stats              # Show token usage
/caveman-help               # Show all commands
/graphify .                 # Build knowledge graph
/graphify query "question"  # Query the graph
use cavecrew                # Delegate to subagents
find skill for X            # Discover new skills
```

---

## Notes

- Skills are tools. Pick up when needed. Don't need all at once.
- Caveman mode persists until "stop caveman" or session end.
- Graphify outputs survive across sessions (`graphify-out/`).
- Compressed files backed up as `FILE.original.md`.
- Subagent output is caveman-compressed (~60% smaller).
