"""Result-affecting provider limits for #215 NODE_CONTEXT durable execution."""

from ontology_map.model_studio import MAX_INPUT_TOKENS, CallLimits

NODE_CONTEXT_LIMITS = CallLimits(
    max_input_tokens=MAX_INPUT_TOKENS,
    max_output_tokens=32_768,
    max_request_bytes=8 * 1024 * 1024,
)
