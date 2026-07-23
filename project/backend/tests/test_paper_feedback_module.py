import importlib.util


def test_paper_feedback_logic_has_a_papers_module_boundary():
    assert importlib.util.find_spec("app.modules.papers.feedback") is not None

    from app.modules.papers import feedback

    assert callable(feedback.process_grading_feedback)
    assert callable(feedback.get_paper_grading_stats)
