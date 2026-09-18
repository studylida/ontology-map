"""Single, versioned Kimi International contract for every product LLM role.

No environment reads or network/DB IO at import time. The same values build the
wire request and effective-input identity. There is no alternate-provider path.
"""

import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

PROVIDER = "moonshot"
BASE_URL = "https://api.moonshot.ai/v1"
MODEL_VERSION = "kimi-k2.6"
PROFILE_VERSION = "kimi-json-v1"
# Application caps, deliberately below the documented 256K combined context.
# Keep a full 32K output allowance even when a particular call uses less.
CONTEXT_CAP_TOKENS = 256_000
MAX_OUTPUT_TOKENS = 32_768
MAX_INPUT_TOKENS = CONTEXT_CAP_TOKENS - MAX_OUTPUT_TOKENS
# Billing reservation is conservative even if a server accepts input above the
# application's admission limit. Official model window: 256K (256 * 1024).
BILLABLE_INPUT_CEILING = 262_144
DEFAULT_TIMEOUT_SECONDS = 60.0
GENERATION_READ_TIMEOUT_SECONDS = 180.0
SCHEMA_SEPARATOR = "\n\nOUTPUT_SCHEMA_JSON:\n"
OUTPUT_INSTRUCTION = (
    "Return exactly one JSON object matching the output contract below. "
    "Return every required field, including required nullable fields with JSON null. "
    "Do not add keys, commentary, Markdown fences, or reasoning. "
    "The contract is a schema, not an output example; return data, not the schema. "
    "Preserve all source references and the task's semantic constraints."
)


def request_options() -> dict[str, Any]:
    """Fresh wire options; omit Kimi's fixed sampling parameters entirely."""
    return {
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
    }


def request_identity_settings() -> dict[str, Any]:
    """All shared result-affecting settings, without credentials or raw input."""
    return {
        "provider": PROVIDER,
        "base_url": BASE_URL,
        "model": MODEL_VERSION,
        "profile_version": PROFILE_VERSION,
        "wire_options": request_options(),
        "sampling": "provider-fixed-nonthinking",
        "local_schema_strict": True,
        "output_instruction_sha256": sha256(OUTPUT_INSTRUCTION.encode()).hexdigest(),
        "schema_separator": SCHEMA_SEPARATOR,
        "context_cap_tokens": CONTEXT_CAP_TOKENS,
    }


def json_messages(
    messages: Sequence[Mapping[str, str]],
    schema_name: str,
    schema: dict[str, Any],
) -> list[dict[str, str]]:
    """Attach the unchanged product schema as prompt data, not provider grammar.

    Keep the user's payload as a separate message. Schema keywords such as
    pattern/format/$ref are preserved for local validation and model guidance;
    the provider is only asked for JSON mode, not strict JSON-Schema decoding.
    """
    if not schema_name.strip() or schema.get("type") != "object" or not messages:
        raise ValueError("INVALID_OUTPUT_CONTRACT")
    result: list[dict[str, str]] = []
    for message in messages:
        if set(message) != {"role", "content"}:
            raise ValueError("INVALID_MESSAGE")
        role, content = message["role"], message["content"]
        if (
            role not in {"system", "user"}
            or not isinstance(content, str)
            or not content.strip()
        ):
            raise ValueError("INVALID_MESSAGE")
        result.append({"role": role, "content": content})
    contract = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    suffix = "\n\n" + OUTPUT_INSTRUCTION + SCHEMA_SEPARATOR + contract
    if result[0]["role"] == "system":
        result[0]["content"] += suffix
    else:
        result.insert(
            0,
            {
                "role": "system",
                "content": OUTPUT_INSTRUCTION + SCHEMA_SEPARATOR + contract,
            },
        )
    return result
