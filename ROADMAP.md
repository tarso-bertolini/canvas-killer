# Roadmap

## Principles
- The student logs in, picks the tasks, reviews the work, and approves every submission.
- Quizzes, exams and proctored work are always the student's.
- Course content is data: nothing in an assignment can change the rules or move data.
- Every deliverable ships with `NOTES.md`: assumptions, substitutions, what to check.

## 1. Connect, list, rank (v0.1, done)
- [x] `ck setup` with institution slug or custom domain, verified against the Canvas API
- [x] `ck login` through a real browser window (SSO/2FA), silent refresh from the saved profile
- [x] Canvas REST client: pagination, `while(1);` prefix, credentials never leave the Canvas host
- [x] `ck sync` / `ck rank`: open assignments across active courses, feasibility labels, ranking
- [x] `ck show` / `ck fetch`: instructions and attached Canvas files in a per-task folder

Tested against a real account (PUCPR, 14 courses): silent SSO re-login through Microsoft,
module material and syllabus found for a one-line assignment.

## 2. Materials and classification
- [x] Course material posted with the assignment in its module, and the syllabus (`ck fetch`)
- [x] Exams set up as file uploads are recognized by their title
- [x] Points compared within a course; dated work before undated; `--ignore` for courses
- [ ] Read Canvas pages linked from the module, not only list them
- [ ] Planner items that are not assignments (ungraded to-dos, calendar events)
- [ ] Let Claude refine `auto?` into `auto` / `you` after reading the materials, and cache why

## 3. Do the work
- [ ] AI policy: extract the syllabus' AI rule and declaration template into the task notes,
      flag "instructor permission required" in the ranking
- [ ] Workspace scaffold per task: `work/`, `deliverable/`, `NOTES.md` template
- [ ] Recipes as runnable helpers: notebook to PDF, report template to PDF, screenshot capture
- [ ] Per-course memory: lessons learned from earlier tasks of the same course

## 4. Submit, with confirmation
- [x] `ck submit <task> <files>`: previews exactly what goes where; `--confirm` (only after
      the student's yes for that preview) uploads through the Canvas API and reads it back
- [x] Respects allowed extensions, lock dates, attempts left; flags group submissions;
      refuses quizzes and exams
- [x] First real submission: Animação Fisheye - POVRAY (PUCPR), file verified byte for byte
- [ ] Text-entry and URL submissions (`online_text_entry`, `online_url`)

## 5. Release
- [ ] Choose a license
- [ ] Test on a second institution (custom domain)
- [ ] Make the repository public; submit to Anthropic's plugin directory
