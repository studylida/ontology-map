"""Complete SQLAlchemy metadata for migrations, schema tests, and generated docs."""

from ontology_map.db.promotion_provenance import promotion_canonical_change
from ontology_map.db.schema import metadata

__all__ = ("metadata", "promotion_canonical_change")
