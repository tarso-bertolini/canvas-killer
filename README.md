# canvas-killer

A Claude Code plugin for students who don't have time to babysit Canvas.

It signs in to your school's Canvas (any school on Instructure Canvas), pulls every open
assignment from every course, ranks what needs you first, and works through the tasks it can
do: it reads the instructions, downloads the materials, and produces the deliverable for you
to review. Anything that needs a human (quizzes, exams, presentations, external tools) is
flagged with the reason, never faked.

> **You stay in charge.** You log in yourself, you choose the tasks, and nothing is submitted
> without your explicit yes for that one submission. Check your institution's academic
> integrity policy: you are responsible for what you hand in.

## Install

In Claude Code:

```
/plugin marketplace add tarso-bertolini/canvas-killer
/plugin install canvas-killer@canvas-killer
```

When the plugin is enabled, Claude Code asks for your **Canvas address**: the name before
`.instructure.com` (for `https://pucpr.instructure.com`, type `pucpr`), or the full address
if your school uses its own domain (`https://canvas.school.edu`).

Requirements: Python 3.9+. A browser for the login window: an installed Chrome or Edge, or
Playwright's Chromium (`ck install-browser` downloads it).

## Use

Just ask Claude: *"what's due on Canvas?"*, *"rank my Canvas tasks"*, *"do task 3"*.
Under the hood it runs the `ck` command line:

| Command | What it does |
|---|---|
| `ck setup --url pucpr` | Save your Canvas address (checks it really is Canvas) and optional profile: `--name`, `--group`, `--naming "{group}_FORMATIVA{n}"`, `--workspace` |
| `ck login` | Opens a browser window; you sign in there (SSO and two-factor work). The session is saved locally |
| `ck sync` | Pulls open assignments from all active courses and prints the ranking |
| `ck rank [--json] [--all]` | Shows the last ranking |
| `ck show 3` | Details and instructions of task #3 |
| `ck fetch 3` | Saves task #3's instructions, its attached files, the lecture material posted with it in the course module, and the course syllabus |
| `ck setup --ignore "Course name"` | Leaves a course out of the ranking (matches your nickname or the official name) |
| `ck status` / `ck logout` | Who is signed in / forget the session |

Each task is labelled:

- `auto?`: file or text submission, likely doable once the instructions are read
- `draft`: discussion post, drafted for you to post
- `you`: needs you (quiz or exam, external tool, offline work), with the reason
- `locked`: Canvas won't accept it yet

The ranking puts overdue work first, then by how soon it's due, weighted by points.

## Privacy and security

- **No passwords.** You sign in inside a real browser window; canvas-killer only keeps the
  resulting Canvas session cookies, in `~/.canvas-killer/` (readable only by you).
- It talks only to your Canvas address, through the official Canvas REST API. Credentials are
  never sent to any other host, including the storage hosts files download from.
- Everything stays on your machine. Deliverables go to `~/Documents/canvas-killer/` by default.
- A personal access token works too: set `CANVAS_TOKEN` in your environment. Some schools
  disable student tokens, which is why browser login is the default.
- `ck logout` deletes the session and the browser profile.

## Development

```
python3 -m unittest discover -s tests
claude plugin validate .
```

The plugin is the repository root: `.claude-plugin/plugin.json`, the marketplace entry in
`.claude-plugin/marketplace.json`, and the skill in `skills/canvas-killer/` (`SKILL.md`,
`references/`, and the `ck` command in `scripts/`). See [ROADMAP.md](ROADMAP.md).
