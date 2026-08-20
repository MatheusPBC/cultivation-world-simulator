"""提示词处理"""

from pathlib import Path
from src.utils.strings import intentify_prompt_infos


def build_prompt(template: str, infos: dict) -> str:
    """
    根据模板构建提示词
    
    Args:
        template: 提示词模板
        infos: 要填充的信息字典
        
    Returns:
        str: 构建好的提示词
    """
    processed = intentify_prompt_infos(infos)
    return template.format(**processed)


def load_template(path: Path | str) -> str:
    """
    加载模板文件
    
    Args:
        path: 模板文件路径
        
    Returns:
        str: 模板内容
    """
    path = Path(path)
    return path.read_text(encoding="utf-8")


def append_output_locale_instruction(prompt: str) -> str:
    """Append the active game's localized output-language contract."""
    from src.i18n.template_resolver import resolve_locale_template_path

    instruction_path = resolve_locale_template_path("llm_output_language.txt")
    instruction = load_template(instruction_path).strip()
    if not instruction:
        return prompt
    return f"{prompt.rstrip()}\n\n---\n{instruction}"
