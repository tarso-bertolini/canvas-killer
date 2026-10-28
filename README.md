# canvas-killer

A Claude Code plugin for students who don't have time to babysit Canvas.

It signs in to your school's Canvas (any school on Instructure Canvas), pulls every open
assignment from every course, ranks what needs you first, and works through the tasks it can
do: it reads the instructions, gathers the lecture material and the syllabus, produces the
deliverable for you to review, and submits it once you say yes. Anything that needs a human
(quizzes, exams, presentations, external tools) is flagged with the reason, never faked.

> **You stay in charge.** You log in yourself, you choose the tasks, and nothing is submitted
> without your explicit yes for that one submission. Quizzes and exams are always yours.
> Your school's rules on AI use apply to you: canvas-killer reads the syllabus and tells you when
> a declaration of AI use or your instructor's permission is required, and adds the declaration
> according to your setting (see [AI-use disclosure](#ai-use-disclosure)). You are responsible
> for what you hand in.

## Install

In Claude Code:

```
/plugin marketplace add tarso-bertolini/canvas-killer
/plugin install canvas-killer@canvas-killer
```

Claude Code then asks for your **Canvas address**: the name before `.instructure.com` (for
`https://pucpr.instructure.com`, type `pucpr`), or the full address if your school uses its own
domain (`https://canvas.school.edu`).

**Requirements:** Python 3.9 or newer, on macOS, Linux or Windows. The first command sets up a
private Python environment in `~/.canvas-killer/` (about a minute). The login window needs a
browser: an installed Chrome or Edge works, otherwise `ck install-browser` downloads one.

## First run

Ask Claude *"what's due on Canvas?"*. The first time, it will:

1. save your Canvas address (and optionally your name, group code and file-naming pattern);
2. open a browser window where **you** sign in, with your school's SSO and two-factor as usual;
3. pull your open assignments and show them ranked.

After that, just talk to it: *"rank my Canvas tasks"*, *"what's task 3 about?"*,
*"do task 3"*, *"submit it"*. Later logins reuse your saved session, usually without a window.

## What it runs

Claude drives the `ck` command line. You can run it yourself too
(`skills/canvas-killer/scripts/ck` inside the plugin):

| Command | What it does |
|---|---|
| `ck setup --url pucpr` | Saves your Canvas address, checking that it really is Canvas. Optional: `--name`, `--group`, `--naming "{group}_FORMATIVA{n}"`, `--workspace` |
| `ck setup --ignore "Course name"` | Leaves a course out of the ranking (matches your course nickname or the official name) |
| `ck setup --ai-disclosure never` | Whether deliverables declare AI use: `auto` (default), `always` or `never`; `--ai-disclosure-text` sets your own wording |
| `ck login` / `ck logout` | Sign in through a browser window / forget the session and browser profile |
| `ck sync` | Pulls open assignments from all active courses and prints the ranking |
| `ck rank [--json] [--all]` | Shows the last ranking (`--all` includes tasks Canvas has locked) |
| `ck show 3` | Details and instructions of task #3 |
| `ck fetch 3` | Saves task #3's instructions, its attached files, the lecture material posted with it in its course module, and the course syllabus |
| `ck submit 3 file.zip` | Previews the submission against the live assignment; nothing is sent |
| `ck submit 3 file.zip --confirm` | Submits it (only after you approved that preview) and reads the result back from Canvas |
| `ck status` | Your setup and who is signed in |

Tasks can also be given as `course_id:assignment_id`, which reaches work that already left the
ranking (for example to resubmit).

### How tasks are ranked

Work Canvas accepts now comes first: overdue, then by how soon it's due, weighted by its points
compared with the rest of its course. Undated work follows, then locked work. Each task gets a
label:

- `auto?`: file or text submission, likely doable once the material is read
- `draft`: discussion post, drafted for you to post
- `you`: needs you, with the reason (quiz or exam, external tool, offline work)
- `locked`: Canvas won't accept it yet

### AI-use disclosure

Some schools require a declaration of AI use inside the work itself, often with a fixed text;
many don't. You choose what canvas-killer does:

| Setting | Deliverables carry a declaration of AI use |
|---|---|
| `auto` (default) | only when your syllabus or school requires one, in their exact wording |
| `always` | always: your school's wording if there is one, otherwise your own text or a short neutral one |
| `never` | never; if your syllabus requires one, the task's `NOTES.md` says so in one line |

```
ck setup --ai-disclosure never
ck setup --ai-disclosure always --ai-disclosure-text "Prepared with the help of Claude (Anthropic)."
```

Whatever the setting, when a syllabus says AI use needs your instructor's permission, you are told
once before you submit.

## What it won't do

- Take quizzes or exams, or submit to them.
- Submit anything without your explicit yes for that submission.
- Handle your password: you sign in in the browser window, canvas-killer only keeps the session.
- Post to discussions for you: it drafts, you post.

## Privacy and security

- Everything stays on your machine. Settings, the session and the browser profile live in
  `~/.canvas-killer/` (readable only by you on macOS and Linux); deliverables go to
  `~/Documents/canvas-killer/` by default.
- It talks only to your Canvas address, through the official Canvas REST API. Your session is
  never sent to any other host, including the storage hosts files upload to and download from.
- A personal access token works too: set `CANVAS_TOKEN` in your environment. Many schools
  disable student tokens, which is why browser login is the default.
- `ck logout` deletes the session and the browser profile.

## Troubleshooting

| Problem | Fix |
|---|---|
| "no usable browser found" | `ck install-browser`, or install Chrome |
| The browser download times out | `ck install-browser` already allows slow links; run it again |
| Exit code 2, "session expired" | `ck login` |
| "could not confirm it is Canvas" during setup | The server didn't answer normally; the address is saved anyway, check it in your browser |
| A course you don't care about clutters the ranking | `ck setup --ignore "part of its name"` |

## Development

```
python3 -m unittest discover -s tests
claude plugin validate .
```

The repository is the plugin: `.claude-plugin/plugin.json`, the marketplace entry in
`.claude-plugin/marketplace.json`, and the skill in `skills/canvas-killer/` (`SKILL.md`,
`references/recipes.md`, and the `ck` command in `scripts/`). CI runs the tests on macOS, Linux
and Windows. See [ROADMAP.md](ROADMAP.md).

## License

[MIT](LICENSE). canvas-killer is an independent project, not affiliated with Instructure or any school.
