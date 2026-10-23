import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "canvas-killer" / "scripts"))

from cklib import api, config, tasks  # noqa: E402

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def iso(delta_hours):
    return (NOW + timedelta(hours=delta_hours)).isoformat().replace("+00:00", "Z")


def assignment(**kw):
    a = {"id": 1, "name": "Task", "submission_types": ["online_upload"], "points_possible": 10,
         "due_at": iso(48), "published": True, "submission": {"workflow_state": "unsubmitted"}}
    a.update(kw)
    return a


COURSE = {"id": 70826, "name": "Avaliação de Desempenho", "course_code": "ADS"}


class BaseUrl(unittest.TestCase):
    def test_slug_becomes_instructure_host(self):
        self.assertEqual(config.normalize_base_url("pucpr"), "https://pucpr.instructure.com")
        self.assertEqual(config.normalize_base_url(" PUCPR "), "https://pucpr.instructure.com")

    def test_custom_domain_and_full_url(self):
        self.assertEqual(config.normalize_base_url("canvas.school.edu"), "https://canvas.school.edu")
        self.assertEqual(config.normalize_base_url("https://pucpr.instructure.com/courses/1"),
                         "https://pucpr.instructure.com")

    def test_rejects_plain_http_and_junk(self):
        for bad in ("http://pucpr.instructure.com", "", "pu cpr", "https://bad host"):
            with self.assertRaises(config.ConfigError):
                config.normalize_base_url(bad)


class Classify(unittest.TestCase):
    def label(self, **kw):
        return tasks.classify(assignment(**kw))[0]

    def test_labels(self):
        self.assertEqual(self.label(), tasks.AUTO)
        self.assertEqual(self.label(submission_types=["online_quiz"]), tasks.HUMAN)
        self.assertEqual(self.label(is_quiz_assignment=True), tasks.HUMAN)
        self.assertEqual(self.label(submission_types=["external_tool"]), tasks.HUMAN)
        self.assertEqual(self.label(submission_types=["discussion_topic"]), tasks.DRAFT)
        self.assertEqual(self.label(submission_types=["on_paper"]), tasks.HUMAN)
        self.assertEqual(self.label(locked_for_user=True, lock_explanation="<b>Locked</b> until X"), tasks.LOCKED)

    def test_quiz_wins_over_upload(self):
        self.assertEqual(self.label(submission_types=["online_upload"], quiz_id=9), tasks.HUMAN)

    def test_exam_titles_on_upload_assignments_are_yours(self):
        for title in ("Written Exam #2: Deep Learning - TBD", "AVALIACAOEXAME", "AVALIACAOPRESENCIAL",
                      "SOMATIVA 01 - RECUPERAÇÃO", "Prova 2", "Final exam"):
            self.assertEqual(self.label(name=title), tasks.HUMAN, title)
        for title in ("F17 - Séries temporais BASELINE", "Animação Fisheye - POVRAY", "Graded Assignment #2"):
            self.assertEqual(self.label(name=title), tasks.AUTO, title)

    def test_not_yet_open_is_locked(self):
        t = tasks.normalize(COURSE, assignment(unlock_at=iso(24)), NOW)
        self.assertEqual(t["feasibility"], tasks.LOCKED)


class OpenTasks(unittest.TestCase):
    def test_submitted_graded_excused_and_closed_are_not_open(self):
        self.assertTrue(tasks.is_open(assignment(), NOW))
        self.assertFalse(tasks.is_open(assignment(submission={"workflow_state": "submitted"}), NOW))
        self.assertFalse(tasks.is_open(assignment(submission={"workflow_state": "graded"}), NOW))
        self.assertFalse(tasks.is_open(assignment(submission={"excused": True}), NOW))
        self.assertFalse(tasks.is_open(assignment(lock_at=iso(-1)), NOW))
        self.assertTrue(tasks.is_open(assignment(due_at=iso(-5), lock_at=iso(24)), NOW))


class Ranking(unittest.TestCase):
    def ranked(self, *assignments):
        ts = [tasks.normalize(COURSE, dict(a, id=i), NOW) for i, a in enumerate(assignments, 1)]
        return [t["assignment_id"] for t in tasks.rank(ts, NOW)]

    def test_overdue_first_then_soonest(self):
        order = self.ranked(assignment(due_at=iso(72)), assignment(due_at=iso(-2)), assignment(due_at=iso(5)))
        self.assertEqual(order, [2, 3, 1])

    def test_points_break_near_ties(self):
        order = self.ranked(assignment(due_at=iso(24), points_possible=1),
                            assignment(due_at=iso(26), points_possible=100))
        self.assertEqual(order, [2, 1])

    def test_no_due_date_and_locked_sink(self):
        order = self.ranked(assignment(due_at=None), assignment(due_at=iso(10), unlock_at=iso(5)),
                            assignment(due_at=iso(200)))
        self.assertEqual(order, [3, 1, 2])  # far-off but open, then undated, locked last

    def test_points_compare_within_a_course(self):
        big = {"id": 1, "name": "Big course"}
        ts = [tasks.normalize(big, assignment(id=1, due_at=iso(30), points_possible=100), NOW),
              tasks.normalize(big, assignment(id=2, due_at=iso(30), points_possible=100), NOW),
              tasks.normalize(COURSE, assignment(id=3, due_at=iso(24), points_possible=0.5), NOW)]
        # 0.5 is the top grade of its own course, so the sooner task wins
        self.assertEqual([t["assignment_id"] for t in tasks.rank(ts, NOW)][0], 3)

    def test_humanize(self):
        self.assertEqual(tasks.humanize_due(iso(-26), NOW), "overdue 1d 2h")
        self.assertEqual(tasks.humanize_due(iso(1.5), NOW), "in 1h 30m")
        self.assertEqual(tasks.humanize_due(None, NOW), "no due date")


class Text(unittest.TestCase):
    def test_html_to_text_keeps_structure_and_file_ids(self):
        html = ('<p>Baixar o notebook: <a href="https://x.instructure.com/courses/1/files/6375874?wrap=1" '
                'data-api-endpoint="https://x.instructure.com/api/v1/courses/1/files/6375874">CMTD</a></p>'
                '<ul><li>Executar as c&eacute;lulas</li><li>Salvar como pdf</li></ul>')
        text, links = tasks.html_to_text(html)
        self.assertIn("Baixar o notebook: CMTD", text)
        self.assertIn("- Executar as células", text)
        self.assertEqual(links[0]["file_id"], "6375874")

    def test_slug_and_filename(self):
        self.assertEqual(tasks.slug("F14 - Scripts / Zabbix"), "F14-Scripts-Zabbix")
        self.assertEqual(tasks.safe_filename("../../etc/passwd"), "_.._etc_passwd")

    def test_short_course(self):
        self.assertEqual(tasks.short_course("Mundos Virtuais e Realidade Misturada (Turma 8º B) - Ciência da Computação"),
                         "Mundos Virtuais e Realidade Misturada")
        self.assertEqual(tasks.short_course("Avaliação de Desempenho - Noite"), "Avaliação de Desempenho")

    def test_module_context_takes_material_since_previous_assessment(self):
        modules = [
            {"name": "Plano", "items": [{"type": "File", "title": "Plano_de_Ensino_v2.pdf", "content_id": 5}]},
            {"name": "Aulas", "items": [
                {"type": "File", "title": "old.pdf", "content_id": 1},
                {"type": "Assignment", "title": "Animação de Personagens", "content_id": 100},
                {"type": "File", "title": "Aula_FullDome.pdf", "content_id": 2},
                {"type": "Page", "title": "notas", "html_url": "u"},
                {"type": "File", "title": "POV-RAY-DOMO.zip", "content_id": 3},
                {"type": "Assignment", "title": "Animação Fisheye - POVRAY", "content_id": 367645},
                {"type": "File", "title": "next.pdf", "content_id": 4}]}]
        related, syllabus = tasks.module_context(modules, 367645)
        self.assertEqual([i["title"] for i in related], ["Aula_FullDome.pdf", "notas", "POV-RAY-DOMO.zip"])
        self.assertEqual([i["content_id"] for i in syllabus], [5])

    def test_next_link(self):
        link = ('<https://x/api/v1/c?page=2&per_page=100>; rel="next", '
                '<https://x/api/v1/c?page=1&per_page=100>; rel="first"')
        self.assertEqual(api._next_link(link), "https://x/api/v1/c?page=2&per_page=100")
        self.assertIsNone(api._next_link('<https://x/a>; rel="last"'))


class CredentialSafety(unittest.TestCase):
    def test_refuses_to_send_credentials_to_another_host(self):
        c = api.Canvas("https://pucpr.instructure.com", cookies=[{"name": "s", "value": "1"}])
        with self.assertRaises(api.CanvasError):
            c._open("https://evil.example.com/api/v1/users/self")

    def test_needs_some_credential(self):
        with self.assertRaises(api.SessionExpired):
            api.Canvas("https://pucpr.instructure.com")


if __name__ == "__main__":
    unittest.main()
