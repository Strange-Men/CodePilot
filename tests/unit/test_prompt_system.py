from backend.models.context import RepositoryContext
from backend.prompts import (
    PromptRenderer,
    PromptSection,
    PromptTemplate,
    PromptVersion,
    TokenBudgeter,
)


def test_prompt_template_renders_versioned_sections_in_order() -> None:
    template = PromptTemplate(
        version=PromptVersion.V2_6,
        sections=(
            PromptSection(name="first", lines=("one", "two")),
            PromptSection(name="second", lines=("three",)),
        ),
    )

    assert template.render() == "one\ntwo\nthree"
    assert template.version == "2.6"


def test_prompt_renderer_exposes_independent_section_model(sample_context) -> None:
    template = PromptRenderer(5000).build_template(sample_context)

    assert [section.name for section in template.sections[:5]] == [
        "instructions",
        "repository_summary",
        "repository_insights",
        "architecture_summary",
        "architecture_graph",
    ]
    assert "Repository URL: https://github.com/example/project" in template.render()
    assert template.render().endswith("Configuration:\n- None detected.")


def test_prompt_renderer_accepts_nested_review_context(sample_context) -> None:
    renderer = PromptRenderer(5000)

    legacy_prompt = renderer.render(sample_context)
    nested_prompt = renderer.render(sample_context.to_review_context())

    assert nested_prompt == legacy_prompt


def test_token_budgeter_preserves_complete_lines() -> None:
    budgeter = TokenBudgeter(budget=3)

    fitted = budgeter.fit("one\ntwo\nthree")

    assert fitted in {"one", "one\ntwo"}
    assert budgeter.count(fitted) <= 3


def test_repository_context_import_remains_available() -> None:
    assert RepositoryContext.__name__ == "RepositoryContext"
