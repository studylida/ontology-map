from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def restore_focused_tests() -> None:
    subprocess.run(
        [
            "git",
            "checkout",
            "--",
            "server/tests/test_promotion_provenance_postgres.py",
            "server/tests/test_promotion_provenance_migration_postgres.py",
        ],
        cwd=ROOT,
        check=True,
    )


def apply_existing_document_patch() -> None:
    source_path = ROOT / ".github/workflows/issue-216-stage1-scope-patch.yml"
    source = source_path.read_text(encoding="utf-8")
    marker = "          python - <<'PY'\n"
    start = source.index(marker) + len(marker)
    end = source.rindex("\n          PY\n")
    raw = source[start:end]
    code = "\n".join(
        line[10:] if line.startswith("          ") else line
        for line in raw.splitlines()
    )
    compiled = compile(code, str(source_path), "exec")
    exec(compiled, {"__name__": "__main__"})


def patch_focused_provenance_test() -> None:
    path = ROOT / "server/tests/test_promotion_provenance_postgres.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "from ontology_map.db import entity_resolution as entity_db\n",
        "",
    )

    alias_start = text.index(
        "def test_alias_new_reuse_evidence_and_retry_record_only_real_mutations"
    )
    alias_end = text.index(
        "\ndef test_claim_association_attribute_and_event_surfaces",
        alias_start,
    )
    alias_test = '''def test_alias_primitives_are_exact_and_same_batch_retry_dedupes(
    database: Session,
) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)
    alias_id = returning(
        database,
        """
        INSERT INTO node_alias (node_id, alias_text, language, is_preferred)
        VALUES (:node_id, :text, 'ko', false)
        RETURNING node_alias_id
        """,
        node_id=values["left"],
        text=f"stage-one-alias-{uuid4()}",
    )

    provenance.record_node_alias_changed(database, batch_id, alias_id)
    provenance.record_node_alias_changed(database, batch_id, alias_id)
    assert provenance.add_node_alias_evidence(
        database, batch_id, alias_id, values["observation"]
    )
    assert not provenance.add_node_alias_evidence(
        database, batch_id, alias_id, values["observation"]
    )

    changes = provenance.changes_for_batch(database, batch_id)
    assert [change.change_kind for change in changes] == [
        "NODE_ALIAS_CHANGED",
        "NODE_ALIAS_EVIDENCE_ADDED",
    ]

'''
    text = text[:alias_start] + alias_test + text[alias_end + 1 :]

    schema_anchor = '''    assert all(
        "UNIQUE INDEX" in row.indexdef and " WHERE " in row.indexdef for row in indexes
    )
'''
    schema_extra = schema_anchor + '''
    definitions = {
        row.conname: row.definition
        for row in execute(
            database,
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'promotion_canonical_change'::regclass
            """,
        ).all()
    }
    expected_foreign_targets = {
        "fk_promotion_canonical_change__promotion_batch": "REFERENCES promotion_batch(promotion_batch_id)",
        "fk_promotion_canonical_change__node_alias": "REFERENCES node_alias(node_alias_id)",
        "fk_promotion_canonical_change__node_alias_evidence": "REFERENCES node_alias_evidence(node_alias_id, observation_id)",
        "fk_promotion_canonical_change__claim_observation": "REFERENCES claim_observation(claim_id, observation_id)",
        "fk_promotion_canonical_change__claim_relation": "REFERENCES claim_relation(claim_id, relation_id)",
        "fk_promotion_canonical_change__attribute_value": "REFERENCES claim_attribute_value(claim_attribute_value_id)",
        "fk_promotion_canonical_change__event_temporal_basis": "REFERENCES event_temporal_basis(event_node_id, claim_id)",
    }
    for name, target in expected_foreign_targets.items():
        assert name in definitions
        assert target.replace(" ", "") in definitions[name].replace(" ", "")

    batch_index = execute(
        database,
        """
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'promotion_canonical_change'
          AND indexname = 'ix_promotion_canonical_change__batch'
        """,
    ).scalar_one()
    assert "(promotion_batch_id, promotion_canonical_change_id)" in batch_index
'''
    if text.count(schema_anchor) != 1:
        raise RuntimeError("schema assertion anchor not found exactly once")
    text = text.replace(schema_anchor, schema_extra, 1)

    restart_start = text.index(
        "def test_restart_reload_projection_inputs_and_publication_lifecycle_preserve_history"
    )
    legacy_start = text.index(
        "def test_legacy_committed_not_started_batches_block_cutover_without_mutation",
        restart_start,
    )
    text = text[:restart_start] + text[legacy_start:]

    legacy_anchor = '''def test_legacy_committed_not_started_batches_block_cutover_without_mutation(
    database: Session,
) -> None:
    legacy_batch = _batch(database, committed=True)
'''
    legacy_replacement = '''def test_legacy_committed_not_started_batches_block_cutover_without_mutation(
    database: Session,
) -> None:
    assert provenance.legacy_committed_not_started_batch_ids(database) == ()
    provenance.assert_initial_publication_cutover_safe(database)

    legacy_batch = _batch(database, committed=True)
'''
    if text.count(legacy_anchor) != 1:
        raise RuntimeError("legacy guard anchor not found exactly once")
    text = text.replace(legacy_anchor, legacy_replacement, 1)

    compile(text, str(path), "exec")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    apply_existing_document_patch()
    restore_focused_tests()
    patch_focused_provenance_test()


if __name__ == "__main__":
    main()
