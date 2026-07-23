import importlib.util


def test_legacy_paper_renderer_reexports_module_implementation():
    assert importlib.util.find_spec("app.modules.paper_generation.renderer") is not None

    from app.modules.paper_generation import renderer
    from app.services import paper_template_renderer

    assert paper_template_renderer.render_exam_paper is renderer.render_exam_paper
