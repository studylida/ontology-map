from pathlib import Path

path = Path("server/tests/test_promotion_provenance_postgres.py")
text = path.read_text(encoding="utf-8")
old = '''    expected_foreign_targets = {
        "fk_promotion_canonical_change__promotion_batch": "REFERENCES promotion_batch(promotion_batch_id)",
        "fk_promotion_canonical_change__node_alias": "REFERENCES node_alias(node_alias_id)",
        "fk_promotion_canonical_change__node_alias_evidence": "REFERENCES node_alias_evidence(node_alias_id, observation_id)",
        "fk_promotion_canonical_change__claim_observation": "REFERENCES claim_observation(claim_id, observation_id)",
        "fk_promotion_canonical_change__claim_relation": "REFERENCES claim_relation(claim_id, relation_id)",
        "fk_promotion_canonical_change__attribute_value": "REFERENCES claim_attribute_value(claim_attribute_value_id)",
        "fk_promotion_canonical_change__event_temporal_basis": "REFERENCES event_temporal_basis(event_node_id, claim_id)",
    }
'''
new = '''    expected_foreign_targets = {
        "fk_promotion_canonical_change__promotion_batch": (
            "REFERENCES promotion_batch(promotion_batch_id)"
        ),
        "fk_promotion_canonical_change__node_alias": (
            "REFERENCES node_alias(node_alias_id)"
        ),
        "fk_promotion_canonical_change__node_alias_evidence": (
            "REFERENCES node_alias_evidence(node_alias_id, observation_id)"
        ),
        "fk_promotion_canonical_change__claim_observation": (
            "REFERENCES claim_observation(claim_id, observation_id)"
        ),
        "fk_promotion_canonical_change__claim_relation": (
            "REFERENCES claim_relation(claim_id, relation_id)"
        ),
        "fk_promotion_canonical_change__attribute_value": (
            "REFERENCES claim_attribute_value(claim_attribute_value_id)"
        ),
        "fk_promotion_canonical_change__event_temporal_basis": (
            "REFERENCES event_temporal_basis(event_node_id, claim_id)"
        ),
    }
'''
if text.count(old) != 1:
    raise SystemExit("expected FK block not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
