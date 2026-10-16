"""CF-side LLM factory using gen_ai_hub (AI Core proxy).

Only loaded when JOULE_RUNTIME is not set. On Joule, ChatLiteLLM is used instead
because sap_cloud_sdk configures litellm with AI Core credentials automatically.
"""
import logging

logger = logging.getLogger(__name__)


def create_llm(model_name: str, temperature: float = 0.0):
    """Return a LangChain LLM backed by AI Core via gen_ai_hub.

    Reads AI Core connection details from AICORE_SERVICE_KEY or VCAP_SERVICES.
    """
    from gen_ai_hub.proxy.langchain.init_models import init_llm  # type: ignore[import]

    return init_llm(model_name=model_name, temperature=temperature)
