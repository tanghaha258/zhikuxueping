import importlib.util


def test_legacy_paper_generator_reexports_generation_module():
    assert importlib.util.find_spec("app.modules.paper_generation.generation") is not None

    from app.modules.paper_generation import generation
    from app.services import paper_generator

    assert paper_generator.generate_paper is generation.generate_paper
    assert paper_generator.smart_compose_paper is generation.smart_compose_paper
    assert paper_generator._call_ai_generate_stream is generation._call_ai_generate_stream
