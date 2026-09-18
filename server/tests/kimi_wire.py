"""Assertions on actual mock HTTP bytes for the Kimi JSON-mode contract."""

import json

from ontology_map.llm_config import OUTPUT_INSTRUCTION, SCHEMA_SEPARATOR


def wire_schema(payload):
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["stream"] is False
    assert not {"temperature", "top_p", "enable_thinking", "tools"} & payload.keys()
    content = payload["messages"][0]["content"]
    prefix, encoded = content.rsplit(SCHEMA_SEPARATOR, 1)
    assert prefix.endswith(OUTPUT_INSTRUCTION)
    return json.loads(encoded)


def task_prompt(payload):
    content = payload["messages"][0]["content"]
    return content.rsplit("\n\n" + OUTPUT_INSTRUCTION + SCHEMA_SEPARATOR, 1)[0]
