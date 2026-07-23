import re
from collections.abc import Mapping

from sqlalchemy import select

from app.models.prompt_template import PromptTemplate


def load_active_template(db, subject: str, exam_type: str) -> str | None:
    """Return the newest active prompt template, preserving legacy fallback behavior."""
    if db is None:
        return None
    try:
        template = db.scalars(
            select(PromptTemplate)
            .where(PromptTemplate.subject == subject)
            .where(PromptTemplate.exam_type == exam_type)
            .where(PromptTemplate.is_active == True)
            .order_by(PromptTemplate.updated_at.desc())
            .limit(1)
        ).first()
    except Exception:
        return None
    return template.template if template else None


def render_prompt(
    template_text: str,
    variables: Mapping[str, str],
    *,
    example_json: str | None = None,
) -> str:
    """Render a configured prompt with safe placeholder and example substitution."""
    prompt = template_text
    for variable_name, variable_value in variables.items():
        prompt = prompt.replace("{" + variable_name + "}", variable_value)

    prompt = prompt.replace('""', '"')
    prompt = prompt.replace("{{", "{").replace("}}", "}")
    if not example_json:
        return prompt

    default_example_pattern = (
        r'\{\s*"index"\s*:\s*1,.*?"analysis"\s*:\s*"[^"]*"\s*\}\s*,?\s*'
        r'\{\s*"index"\s*:\s*2,.*?"analysis"\s*:\s*"[^"]*"\s*\}\s*,?\s*'
        r'\{\s*"index"\s*:\s*3,.*?"analysis"\s*:\s*"[^"]*"\s*\}'
    )
    return re.sub(default_example_pattern, example_json, prompt, count=1, flags=re.DOTALL)
