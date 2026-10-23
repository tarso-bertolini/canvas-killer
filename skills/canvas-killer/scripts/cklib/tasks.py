"""Turn Canvas assignments into ranked tasks.

A task is a plain dict so it can be cached as JSON and handed to Claude with
``ck rank --json``. Feasibility here is a first pass from Canvas metadata only;
reading the instructions and materials can still move a task to "you".
"""

import html
import re
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser

# Feasibility labels, in the order they are explained to the user
AUTO = "auto?"      # file or text submission: automatable once the instructions are read
DRAFT = "draft"     # Claude drafts it, the student posts it themselves
HUMAN = "you"       # needs the student: quiz/exam, external tool, offline work
LOCKED = "locked"   # Canvas will not accept a submission right now

DONE_STATES = {"submitted", "graded", "pending_review", "complete"}

# Exams are often set up as plain file uploads; the title gives them away.
# Matched on accent-stripped lowercase text, so "Avaliação" matches "avaliacao".
EXAM_TITLE = re.compile(r"\b(exams?|exame\w*|provas?|quiz+e?s?|tests?|midterm|final exam|somativa\w*|"
                        r"avaliacao\w*|presencial)\b")


def plain(text):
    """Lowercase without accents, for keyword matching across languages."""
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()


def short_course(name):
    """'Mundos Virtuais (Turma 8º B) - Ciência da Computação' -> 'Mundos Virtuais'."""
    short = re.split(r"\s+\(|\s+-\s+", name or "", maxsplit=1)[0].strip()
    return short[:40] or name


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classify(a):
    """Return (label, reason) for one Canvas assignment."""
    types = set(a.get("submission_types") or [])
    if a.get("locked_for_user"):
        reason = a.get("lock_explanation") or "Canvas has it locked"
        return LOCKED, re.sub(r"<[^>]+>", "", reason).strip()
    if a.get("is_quiz_assignment") or a.get("quiz_id") or "online_quiz" in types:
        return HUMAN, "quiz or exam: always yours"
    if "external_tool" in types:
        return HUMAN, "runs in an external tool Canvas can't hand over"
    if EXAM_TITLE.search(plain(a.get("name"))):
        return HUMAN, "the title says exam or assessment: yours"
    if "discussion_topic" in types:
        return DRAFT, "discussion post: drafted for you, you post it"
    if types & {"online_upload", "online_text_entry", "online_url"}:
        return AUTO, "file or text submission"
    if types & {"on_paper", "none", "not_graded"} or not types:
        return HUMAN, "offline or in-person work"
    return HUMAN, "unsupported submission type: %s" % ", ".join(sorted(types))


def is_open(a, now):
    """True when the assignment still needs a submission and can receive one."""
    sub = a.get("submission") or {}
    if sub.get("excused") or sub.get("workflow_state") in DONE_STATES:
        return False
    if not a.get("published", True):
        return False
    lock_at = parse_time(a.get("lock_at"))
    return not (lock_at and lock_at < now)


def normalize(course, a, now):
    sub = a.get("submission") or {}
    label, reason = classify(a)
    unlock_at = parse_time(a.get("unlock_at"))
    if label != LOCKED and unlock_at and unlock_at > now:
        label, reason = LOCKED, "opens %s" % unlock_at.astimezone().strftime("%Y-%m-%d %H:%M")
    return {
        "key": "%s:%s" % (course["id"], a["id"]),
        "course_id": course["id"],
        "assignment_id": a["id"],
        "course": short_course(course.get("name") or course.get("course_code") or str(course["id"])),
        "course_name": course.get("original_name") or course.get("name") or "",
        "title": a.get("name") or "(untitled)",
        "due_at": a.get("due_at"),
        "lock_at": a.get("lock_at"),
        "points": a.get("points_possible") or 0,
        "submission_types": a.get("submission_types") or [],
        "allowed_extensions": a.get("allowed_extensions") or [],
        "group_work": bool(a.get("group_category_id")),
        "missing": bool(sub.get("missing")),
        "attempts_left": (a.get("allowed_attempts") - (sub.get("attempt") or 0))
                         if (a.get("allowed_attempts") or -1) > 0 else None,
        "feasibility": label,
        "reason": reason,
        "url": a.get("html_url") or "",
    }


def score(task, now, max_points):
    """Higher is more pressing: urgency of the deadline times the weight of the grade.

    max_points is the largest value in the task's own course: point scales differ
    between courses (one grades out of 0.5, another out of 100)."""
    due = parse_time(task["due_at"])
    if due is None:
        urgency = 0.05
    else:
        hours = (due - now).total_seconds() / 3600
        urgency = 2.0 if hours < 0 else 1.0 / (1.0 + hours / 24.0)
    weight = 0.5 + 0.5 * (task["points"] / max_points) if max_points else 0.5
    return round(urgency * weight, 4)


def rank(tasks, now=None):
    """Sort in place: dated work Canvas accepts now, then undated work, then locked work."""
    now = now or datetime.now(timezone.utc)
    course_max = {}
    for t in tasks:
        course_max[t["course_id"]] = max(course_max.get(t["course_id"], 0), t["points"])
    for t in tasks:
        t["score"] = score(t, now, course_max[t["course_id"]])
    tasks.sort(key=lambda t: (t["feasibility"] == LOCKED, t["due_at"] is None, -t["score"], t["due_at"] or ""))
    for i, t in enumerate(tasks, 1):
        t["rank"] = i
    return tasks


def humanize_due(due_at, now):
    due = parse_time(due_at)
    if due is None:
        return "no due date"
    secs = (due - now).total_seconds()
    mins = abs(int(secs // 60))
    days, hours = mins // 1440, (mins % 1440) // 60
    span = ("%dd %dh" % (days, hours)) if days else ("%dh %02dm" % (hours, mins % 60))
    return ("overdue " + span) if secs < 0 else ("in " + span)


def format_table(tasks, now=None, width=110):
    now = now or datetime.now(timezone.utc)
    rows = [("#", "Due", "Course", "Task", "Pts", "Do it", "Why")]
    for t in tasks:
        title = t["title"] + (" [group]" if t["group_work"] else "") + (" [MISSING]" if t["missing"] else "")
        rows.append((str(t["rank"]), humanize_due(t["due_at"], now), t["course"][:18], title[:46],
                     ("%g" % t["points"]), t["feasibility"], t["reason"][:40]))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip() for r in rows]
    lines.insert(1, "-" * min(width, len(lines[0])))
    return "\n".join(lines)


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")
        if tag == "a" and a.get("href"):
            self.links.append({"href": a["href"], "api": a.get("data-api-endpoint"),
                               "file_id": _file_id(a["href"]) or _file_id(a.get("data-api-endpoint") or "")})

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


SYLLABUS_TITLE = re.compile(r"plano[\s_-]*de[\s_-]*ensino|syllabus|cronograma|course[\s_-]*(outline|schedule)|"
                            r"programa[\s_-]*da[\s_-]*disciplina")
STOP_TYPES = {"Assignment", "Quiz", "Discussion"}


def module_context(modules, assignment_id):
    """Course material that belongs with an assignment, from the course modules.

    Professors often post the one-line assignment right after the lecture files
    it depends on, so the related material is the module items between the
    previous assessment and this one. Syllabus files from any module come too,
    because they hold rules such as the course's AI policy.
    Returns (related_items, syllabus_items) as module item dicts.
    """
    related, syllabus = [], []
    for m in modules:
        items = m.get("items") or []
        for i, it in enumerate(items):
            if it.get("type") == "Assignment" and str(it.get("content_id")) == str(assignment_id):
                j = i - 1
                while j >= 0 and items[j].get("type") not in STOP_TYPES:
                    if items[j].get("type") in ("File", "Page", "ExternalUrl"):
                        related.insert(0, items[j])
                    j -= 1
        for it in items:
            if it.get("type") == "File" and SYLLABUS_TITLE.search(plain(it.get("title"))):
                syllabus.append(it)
    return related, syllabus


def slug(text, limit=60):
    """File-system safe name that keeps accents readable (F14 - Scripts -> F14-Scripts)."""
    s = re.sub(r"[^\w.]+", "-", text).strip("-.")
    return (s[:limit].rstrip("-.") or "task")


def safe_filename(name):
    name = re.sub(r"[/\\:\x00-\x1f]", "_", name or "").strip(" .")
    return name or "file"


def _file_id(url):
    m = re.search(r"/files/(\d+)", url or "")
    return m.group(1) if m else None


def html_to_text(fragment):
    """Readable text plus the links (with Canvas file ids) of an assignment description."""
    p = _TextExtractor()
    p.feed(fragment or "")
    text = html.unescape("".join(p.parts))
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, p.links
