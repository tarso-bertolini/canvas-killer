# Recipes for common task types

Lessons from real coursework. Read the section that matches the task.

## Jupyter notebook to PDF
1. Copy the notebook into `work/`. Fill only the cells the assignment asks for; keep the
   professor's comments, which often state the expected results.
2. Make Colab-only cells tolerant (`google.colab` import, `drive.mount`) so the notebook runs
   locally, and print a short note instead of failing.
3. Execute: `jupyter nbconvert --to notebook --execute --inplace notebook.ipynb`
   (venv with `nbconvert ipykernel` and the libraries the notebook imports; register the
   kernel with `python -m ipykernel install --user --name python3`).
4. Check every cell's output for errors and compare with the expected values in comments.
   `display(Image(missing_path))` does not raise inside your code: test `os.path.exists`.
5. PDF: `nbconvert --to html`, add print CSS (wrap long code lines, avoid breaking cells),
   open it in Playwright Chromium, wait for MathJax, and `page.pdf(format="A4")`. This needs
   no LaTeX install.

## Report template (RTF/DOCX "paste your screenshots here")
- Reproduce the template's text faithfully (title, headings, numbered items, page
  orientation and margins from the file) and place each screenshot under its item.
- Without LibreOffice, build the page as HTML and print it to PDF with Playwright. Read the
  RTF's `\paperw`/`\paperh` and `\landscape` for the page setup.
- Screenshots must be legible: capture at device scale 2 and check them before assembling.

## Material that was never distributed
Assignments sometimes reference files that only exist in the professor's own drive (a figure,
a dataset). If the instructions or expected results let you reconstruct it exactly, do so and
say so in `NOTES.md` and in the deliverable itself. Otherwise ask the student to download it.

## Lab tasks in Docker (e.g. monitoring tools)
- Check free disk first (`df -h`); a full disk makes every shell command fail in confusing
  ways. Budget about 3 GB for a database plus a web app.
- With Colima on macOS, bind mounts only work for paths under `$HOME`; a mount from `/tmp`
  silently becomes an empty directory.
- Some official images regenerate their config file on every start, so edits inside the
  container vanish on restart. Point the process at your own config file instead.
- Verify each step through the tool's API before taking the screenshot of it in the UI.
- Clean up when done: `docker compose down -v`, `docker system prune -af --volumes`, and on
  Colima `colima delete --data -f` (without `--data` the container data disk survives).

## Playwright's browser download times out
`ck install-browser` sets `PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=600000`, which fixes the
30-second timeout on slow links. `ck login` prefers an installed Chrome or Edge anyway.
