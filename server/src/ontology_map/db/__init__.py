"""PostgreSQL 연결과 schema 정의."""

# Importing this module registers #203's additive metadata on the shared
# ``schema.metadata`` object before callers import individual schema tables.
from ontology_map.db import topic_reference_schema as topic_reference_schema
