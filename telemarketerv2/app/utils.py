import logging
from typing import Dict, Any
from jinja2 import Environment, BaseLoader, TemplateNotFound

logger = logging.getLogger(__name__)

# --- Jinja2 Environment for Dialogue Templating ---
# This setup assumes templates are simple strings passed directly.
# If loading from files is needed later, the loader can be changed.
class DictLoader(BaseLoader):
    def __init__(self, templates):
        self.templates = templates

    def get_source(self, environment, template):
        if template not in self.templates:
            raise TemplateNotFound(template)
        source = self.templates[template]
        # source, filename, is_uptodate function
        return source, None, lambda: True

# Initialize environment - can be reused
jinja_env = Environment(loader=DictLoader({}), enable_async=False)

# Helper to render dialogue using Jinja
def render_dialogue(template_string: str, context: Dict[str, Any]) -> str:
    """Renders a dialogue template string using Jinja2."""
    if not template_string:
        return ""
    if '{{' not in template_string and '}}' not in template_string:
        return template_string # Return as is if no Jinja syntax detected
    
    try:
        # --- Debug Logging Added ---
        logger.debug(f"Attempting to render Jinja template:")
        logger.debug(f"Template String: '{template_string}'")
        # Log context keys and types for diagnosis
        context_repr = {k: type(v).__name__ for k, v in context.items()}
        logger.debug(f"Context Provided (Keys/Types): {context_repr}") 
        # Be careful logging full context values if they contain sensitive data
        # logger.debug(f"Full Context: {context}") 
        # --- End Debug Logging ---
        
        template = jinja_env.from_string(template_string)
        rendered = template.render(context)
        # logger.debug(f"Rendered template '{template_string[:30]}...' with context keys {list(context.keys())} -> '{rendered[:50]}...'")
        return rendered
    except TemplateNotFound:
        logger.error(f"Jinja TemplateNotFound error (should not happen with from_string): {template_string}")
        return template_string # Fallback
    except Exception as e:
        # Log the specific error and the template that caused it
        logger.error(f"Error rendering dialogue template '{template_string[:50]}...': {e}", exc_info=False) # Log exception type
        # Log the specific traceback for syntax errors if needed, but can be verbose
        # logger.exception(f"Full traceback for Jinja rendering error:") 
        return template_string # Fallback to the original string 