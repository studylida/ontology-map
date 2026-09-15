from pathlib import Path
import subprocess


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    if old not in text:
        raise RuntimeError(f"expected text not found in {path}")
    target.write_text(text.replace(old, new, 1))


activation_path = "server/src/ontology_map/db/ontology_reference_data.py"
old_node_types = '''def _ensure_node_types(session: Session) -> dict[str, int]:
    result: dict[str, int] = {}
    for code, display_name in NODE_TYPE_DEFINITIONS:
        row = (
            session.execute(
                sa.select(
                    node_type.c.node_type_id,
                    node_type.c.display_name,
                    node_type.c.is_active,
                ).where(node_type.c.node_type_code == code)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            node_type_id = int(
                session.execute(
                    node_type.insert()
                    .values(
                        node_type_code=code,
                        display_name=display_name,
                        creation_rule=_NODE_CREATION_RULE,
                        is_active=True,
                    )
                    .returning(node_type.c.node_type_id)
                ).scalar_one()
            )
        else:
            if str(row["display_name"]) != display_name:
                raise RuntimeError(
                    f"node_type {code} has a conflicting display name: "
                    f"{row['display_name']!r}"
                )
            node_type_id = int(row["node_type_id"])
            if not bool(row["is_active"]):
                session.execute(
                    node_type.update()
                    .where(node_type.c.node_type_id == node_type_id)
                    .values(is_active=True)
                )
        result[code] = node_type_id
    return result
'''
new_node_types = '''def _ensure_node_types(session: Session) -> dict[str, int]:
    result: dict[str, int] = {}
    for code, display_name in NODE_TYPE_DEFINITIONS:
        row = (
            session.execute(
                sa.select(
                    node_type.c.node_type_id,
                    node_type.c.display_name,
                    node_type.c.creation_rule,
                    node_type.c.is_active,
                ).where(node_type.c.node_type_code == code)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            node_type_id = int(
                session.execute(
                    node_type.insert()
                    .values(
                        node_type_code=code,
                        display_name=display_name,
                        creation_rule=_NODE_CREATION_RULE,
                        is_active=True,
                    )
                    .returning(node_type.c.node_type_id)
                ).scalar_one()
            )
        else:
            if (
                str(row["display_name"]) != display_name
                or str(row["creation_rule"]) != _NODE_CREATION_RULE
            ):
                raise RuntimeError(
                    f"node_type {code} conflicts with the frozen prerequisite contract"
                )
            if not bool(row["is_active"]):
                raise RuntimeError(
                    f"node_type {code} is inactive; #201 activation will not reactivate it"
                )
            node_type_id = int(row["node_type_id"])
        result[code] = node_type_id
    return result
'''
replace_once(activation_path, old_node_types, new_node_types)

fixture_path = "server/src/ontology_map/db/fixture.py"
fixture_marker = '''def _seed_reference_data(
    connection: Connection,
) -> tuple[dict[str, int], int, dict[str, int], int]:
    node_type_ids: dict[str, int] = {}
    for code, display_name in (
        ("PERSON", "사람"),
        ("COMPANY", "회사"),
        ("TECHNOLOGY", "기술"),
        ("TOPIC", "주제"),
        ("EVENT", "사건"),
    ):
        node_type_ids[code] = int(
            connection.execute(
                node_type.insert()
                .values(
                    node_type_code=code,
                    display_name=display_name,
                    creation_rule="공개 원문 근거와 대표 alias가 필요하다.",
                    is_active=True,
                )
                .returning(node_type.c.node_type_id)
            ).scalar_one()
        )
'''
fixture_replacement = '''_FIXTURE_NODE_TYPES = (
    ("PERSON", "사람"),
    ("COMPANY", "회사"),
    ("TECHNOLOGY", "기술"),
    ("TOPIC", "주제"),
    ("EVENT", "사건"),
)
_FIXTURE_NODE_CREATION_RULE = "공개 원문 근거와 대표 alias가 필요하다."


def _fixture_node_types(connection: Connection) -> dict[str, int]:
    node_type_ids: dict[str, int] = {}
    for code, display_name in _FIXTURE_NODE_TYPES:
        row = (
            connection.execute(
                sa.select(
                    node_type.c.node_type_id,
                    node_type.c.display_name,
                    node_type.c.creation_rule,
                    node_type.c.is_active,
                ).where(node_type.c.node_type_code == code)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            node_type_id = int(
                connection.execute(
                    node_type.insert()
                    .values(
                        node_type_code=code,
                        display_name=display_name,
                        creation_rule=_FIXTURE_NODE_CREATION_RULE,
                        is_active=True,
                    )
                    .returning(node_type.c.node_type_id)
                ).scalar_one()
            )
        else:
            if (
                str(row["display_name"]) != display_name
                or str(row["creation_rule"]) != _FIXTURE_NODE_CREATION_RULE
                or not bool(row["is_active"])
            ):
                raise RuntimeError(
                    f"기존 node_type {code}가 HBF fixture prerequisite와 호환되지 않습니다."
                )
            node_type_id = int(row["node_type_id"])
        node_type_ids[code] = node_type_id
    return node_type_ids


def _seed_reference_data(
    connection: Connection,
) -> tuple[dict[str, int], int, dict[str, int], int]:
    node_type_ids = _fixture_node_types(connection)
'''
replace_once(fixture_path, fixture_marker, fixture_replacement)

old_loader = '''def load_hbf_fixture() -> tuple[bool, dict[str, int]]:
    if get_settings().environment != "development":
        raise RuntimeError("HBF fixture는 development 환경에서만 실행할 수 있습니다.")

    with get_engine().begin() as connection:
        marker_exists = connection.scalar(
            sa.select(source_document.c.source_document_id).where(
                source_document.c.source_key == FIXTURE_MARKER
            )
        )
        if marker_exists is not None:
            return False, _current_fixture_nodes(connection)

        node_type_ids, relation_revision_id, contract_ids, batch_id = (
            _seed_reference_data(connection)
        )
        observation_ids = _seed_evidence(connection)
        node_ids, node_names = _seed_nodes(
            connection,
            node_type_ids,
            observation_ids,
            batch_id,
        )
        relation_ids, claim_ids = _seed_relations(
            connection,
            node_ids,
            node_names,
            observation_ids,
            relation_revision_id,
            batch_id,
        )
        _seed_node_artifacts(
            connection,
            node_ids,
            node_names,
            relation_ids,
            claim_ids,
            contract_ids,
            batch_id,
        )
        return True, node_ids
'''
new_loader = '''def _load_hbf_fixture(connection: Connection) -> tuple[bool, dict[str, int]]:
    marker_exists = connection.scalar(
        sa.select(source_document.c.source_document_id).where(
            source_document.c.source_key == FIXTURE_MARKER
        )
    )
    if marker_exists is not None:
        return False, _current_fixture_nodes(connection)

    node_type_ids, relation_revision_id, contract_ids, batch_id = _seed_reference_data(
        connection
    )
    observation_ids = _seed_evidence(connection)
    node_ids, node_names = _seed_nodes(
        connection,
        node_type_ids,
        observation_ids,
        batch_id,
    )
    relation_ids, claim_ids = _seed_relations(
        connection,
        node_ids,
        node_names,
        observation_ids,
        relation_revision_id,
        batch_id,
    )
    _seed_node_artifacts(
        connection,
        node_ids,
        node_names,
        relation_ids,
        claim_ids,
        contract_ids,
        batch_id,
    )
    return True, node_ids


def load_hbf_fixture() -> tuple[bool, dict[str, int]]:
    if get_settings().environment != "development":
        raise RuntimeError("HBF fixture는 development 환경에서만 실행할 수 있습니다.")

    with get_engine().begin() as connection:
        return _load_hbf_fixture(connection)
'''
replace_once(fixture_path, old_loader, new_loader)

test_path = Path("server/tests/test_ontology_reference_data_postgres.py")
test_text = test_path.read_text()
test_text = test_text.replace(
    "from ontology_map.db.fixture import load_hbf_fixture",
    "from ontology_map.db.fixture import _load_hbf_fixture",
    1,
)
test_text = test_text.replace(
    "    ATTRIBUTE_DEFINITIONS,\n    RELATION_DEFINITIONS,",
    "    ATTRIBUTE_DEFINITIONS,\n    NODE_TYPE_DEFINITIONS,\n    RELATION_DEFINITIONS,",
    1,
)
prefix = test_text.split("\ndef test_clean_activation_is_exact_and_idempotent() -> None:", 1)[0]
new_tests = r'''

_NODE_CREATION_RULE = "공개 원문 근거와 대표 alias가 필요하다."


def _activate(connection: sa.Connection):
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        with session.begin():
            result = activate_approved_ontology_reference_data(session)
            _force_constraints(session)
        return result


def _insert_node_types(
    connection: sa.Connection,
    *,
    only: set[str] | None = None,
    inactive: set[str] | None = None,
) -> dict[str, int]:
    inactive = inactive or set()
    result: dict[str, int] = {}
    for code, display_name in NODE_TYPE_DEFINITIONS:
        if only is not None and code not in only:
            continue
        result[code] = int(
            connection.execute(
                node_type.insert()
                .values(
                    node_type_code=code,
                    display_name=display_name,
                    creation_rule=_NODE_CREATION_RULE,
                    is_active=code not in inactive,
                )
                .returning(node_type.c.node_type_id)
            ).scalar_one()
        )
    return result


def _reference_snapshot(session: Session) -> dict[str, int]:
    return {
        "node_type": _count(session, node_type),
        "relation_type": _count(session, relation_type),
        "relation_revision": _count(session, relation_type_revision),
        "relation_endpoint": _count(session, relation_endpoint_rule),
        "attribute": _count(session, attribute),
        "attribute_revision": _count(session, attribute_revision),
        "attribute_unit": _count(session, attribute_revision_allowed_unit),
        "topic_reference": _count(session, topic_reference),
        "knowledge_item": _count(session, knowledge_item),
        "node": _count(session, node),
        "relation": _count(session, relation),
        "claim": _count(session, claim),
        "source_document": _count(session, source_document),
        "observation": _count(session, observation),
        "promotion_batch": _count(session, promotion_batch),
        "node_search_document": _count(session, node_search_document),
    }


def test_clean_activation_is_exact_and_idempotent() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            first = _activate(connection)
            second = _activate(connection)
            assert first == second
            assert len(first.relation_revision_ids) == 14
            assert len(first.attribute_revision_ids) == 6
            assert len(first.topic_node_ids) == 9

            with Session(bind=connection) as session:
                relation_contract = _relation_contract(session)
                assert set(relation_contract) == {
                    definition.code for definition in RELATION_DEFINITIONS
                }
                for definition in RELATION_DEFINITIONS:
                    actual_direction, actual_pairs = relation_contract[definition.code]
                    assert actual_direction == definition.directionality
                    assert _normalized_pairs(actual_direction, actual_pairs) == (
                        _normalized_pairs(
                            definition.directionality,
                            set(definition.endpoint_pairs),
                        )
                    )

                assert relation_contract["RELATED_TO"] == (
                    "SYMMETRIC",
                    {("TECHNOLOGY", "EVENT")},
                )
                assert relation_contract["HAS_TOPIC"] == (
                    "DIRECTED",
                    {
                        ("COMPANY", "TOPIC"),
                        ("PERSON", "TOPIC"),
                        ("TECHNOLOGY", "TOPIC"),
                        ("EVENT", "TOPIC"),
                    },
                )

                attribute_contract = _attribute_contract(session)
                assert set(attribute_contract) == {
                    definition.code for definition in ATTRIBUTE_DEFINITIONS
                }
                assert attribute_contract["CORE_COUNT"] == (
                    "TECHNOLOGY",
                    "NUMBER",
                    {"COUNT"},
                )
                assert attribute_contract["MAX_MEMORY_BANDWIDTH"] == (
                    "TECHNOLOGY",
                    "NUMBER",
                    {"GB_PER_S", "TB_PER_S"},
                )

                topic_rows = session.execute(
                    sa.select(
                        topic_reference.c.node_id,
                        topic_reference.c.topic_code,
                        topic_reference.c.canonical_display_name,
                        topic_reference.c.is_active,
                        knowledge_item.c.lifecycle_kind,
                        knowledge_item.c.current_state,
                        knowledge_item.c.promotion_batch_id,
                        node_type.c.node_type_code,
                    )
                    .join(node, node.c.node_id == topic_reference.c.node_id)
                    .join(node_type, node_type.c.node_type_id == node.c.node_type_id)
                    .join(
                        knowledge_item,
                        knowledge_item.c.knowledge_item_id == topic_reference.c.node_id,
                    )
                    .order_by(topic_reference.c.topic_code)
                ).all()
                assert {
                    (str(code), str(name))
                    for _node_id, code, name, *_rest in topic_rows
                } == set(APPROVED_TOPIC_DEFINITIONS)
                assert all(bool(row.is_active) for row in topic_rows)
                assert all(
                    row.lifecycle_kind == PRODUCT_REFERENCE for row in topic_rows
                )
                assert all(row.current_state is None for row in topic_rows)
                assert all(row.promotion_batch_id is None for row in topic_rows)
                assert all(row.node_type_code == "TOPIC" for row in topic_rows)
                assert _count(session, source_document) == 0
                assert _count(session, observation) == 0
                assert _count(session, promotion_batch) == 0
                assert _count(session, claim) == 0
                assert _count(session, relation) == 0
                assert _count(session, node_alias) == 0
                assert _count(session, node_search_document) == 0
        finally:
            outer.rollback()


@pytest.mark.parametrize("first", ["fixture", "activation"])
def test_fixture_and_activation_coexist_in_both_orders(first: str) -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            if first == "fixture":
                created, fixture_node_ids = _load_hbf_fixture(connection)
                assert created
                activation = _activate(connection)
            else:
                activation = _activate(connection)
                created, fixture_node_ids = _load_hbf_fixture(connection)
                assert created

            with Session(bind=connection) as session:
                first_snapshot = _reference_snapshot(session)
                dev_revision_id = int(
                    session.scalar(
                        sa.select(
                            relation_type_revision.c.relation_type_revision_id
                        )
                        .join(
                            relation_type,
                            relation_type.c.relation_type_id
                            == relation_type_revision.c.relation_type_id,
                        )
                        .where(
                            relation_type.c.relation_code
                            == "PUBLICLY_ASSOCIATED_WITH",
                            relation_type_revision.c.is_active,
                        )
                    )
                )

            activation_again = _activate(connection)
            created_again, fixture_node_ids_again = _load_hbf_fixture(connection)
            assert activation_again == activation
            assert not created_again
            assert fixture_node_ids_again == fixture_node_ids
            assert not set(fixture_node_ids.values()) & set(
                activation.topic_node_ids.values()
            )

            with Session(bind=connection) as session:
                assert _reference_snapshot(session) == first_snapshot
                assert _count(session, topic_reference) == 9
                assert (
                    session.scalar(
                        sa.select(
                            relation_type_revision.c.relation_type_revision_id
                        )
                        .join(
                            relation_type,
                            relation_type.c.relation_type_id
                            == relation_type_revision.c.relation_type_id,
                        )
                        .where(
                            relation_type.c.relation_code
                            == "PUBLICLY_ASSOCIATED_WITH",
                            relation_type_revision.c.is_active,
                        )
                    )
                    == dev_revision_id
                )
        finally:
            outer.rollback()


def test_inactive_node_type_is_preserved_and_activation_fails_closed() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            ids = _insert_node_types(
                connection,
                only={"TOPIC"},
                inactive={"TOPIC"},
            )
            with pytest.raises(RuntimeError, match="node_type TOPIC is inactive"):
                _activate(connection)

            row = connection.execute(
                sa.select(node_type.c.node_type_id, node_type.c.is_active).where(
                    node_type.c.node_type_code == "TOPIC"
                )
            ).one()
            assert int(row.node_type_id) == ids["TOPIC"]
            assert not bool(row.is_active)
            assert int(
                connection.scalar(sa.select(sa.func.count()).select_from(node_type)) or 0
            ) == 1
            assert int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(relation_type)
                )
                or 0
            ) == 0
            assert int(
                connection.scalar(sa.select(sa.func.count()).select_from(attribute))
                or 0
            ) == 0
            assert int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(topic_reference)
                )
                or 0
            ) == 0
        finally:
            outer.rollback()


def test_conflicting_active_relation_revision_fails_closed_and_rolls_back() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            _insert_node_types(connection)
            relation_type_id = int(
                connection.execute(
                    relation_type.insert()
                    .values(relation_code="DEVELOPS")
                    .returning(relation_type.c.relation_type_id)
                ).scalar_one()
            )
            conflict_revision_id = int(
                connection.execute(
                    relation_type_revision.insert()
                    .values(
                        relation_type_id=relation_type_id,
                        version_no=1,
                        display_name="conflict",
                        directionality="SYMMETRIC",
                        is_active=True,
                    )
                    .returning(relation_type_revision.c.relation_type_revision_id)
                ).scalar_one()
            )

            with pytest.raises(RuntimeError, match="active relation revision for DEVELOPS"):
                _activate(connection)

            codes = set(connection.scalars(sa.select(relation_type.c.relation_code)))
            assert codes == {"DEVELOPS"}
            assert connection.scalar(
                sa.select(relation_type_revision.c.relation_type_revision_id).where(
                    relation_type_revision.c.is_active
                )
            ) == conflict_revision_id
            assert int(
                connection.scalar(sa.select(sa.func.count()).select_from(attribute))
                or 0
            ) == 0
            assert int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(topic_reference)
                )
                or 0
            ) == 0
        finally:
            outer.rollback()


def test_conflicting_active_attribute_revision_fails_closed_and_rolls_back() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            type_ids = _insert_node_types(connection)
            attribute_id = int(
                connection.execute(
                    attribute.insert()
                    .values(attribute_code="TECHNOLOGY_VERSION")
                    .returning(attribute.c.attribute_id)
                ).scalar_one()
            )
            conflict_revision_id = int(
                connection.execute(
                    attribute_revision.insert()
                    .values(
                        attribute_id=attribute_id,
                        version_no=1,
                        display_name="conflict",
                        target_node_type_id=type_ids["PERSON"],
                        allowed_value_kind="STRING",
                        is_active=True,
                    )
                    .returning(attribute_revision.c.attribute_revision_id)
                ).scalar_one()
            )

            with pytest.raises(
                RuntimeError,
                match="active attribute revision for TECHNOLOGY_VERSION",
            ):
                _activate(connection)

            assert set(connection.scalars(sa.select(attribute.c.attribute_code))) == {
                "TECHNOLOGY_VERSION"
            }
            assert connection.scalar(
                sa.select(attribute_revision.c.attribute_revision_id).where(
                    attribute_revision.c.is_active
                )
            ) == conflict_revision_id
            assert int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(relation_type)
                )
                or 0
            ) == 0
            assert int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(topic_reference)
                )
                or 0
            ) == 0
        finally:
            outer.rollback()


def test_exact_inactive_revisions_are_reused_by_id() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            type_ids = _insert_node_types(connection)

            relation_type_id = int(
                connection.execute(
                    relation_type.insert()
                    .values(relation_code="AFFILIATED_WITH")
                    .returning(relation_type.c.relation_type_id)
                ).scalar_one()
            )
            relation_revision_id = int(
                connection.execute(
                    relation_type_revision.insert()
                    .values(
                        relation_type_id=relation_type_id,
                        version_no=7,
                        display_name="existing exact relation",
                        directionality="DIRECTED",
                        is_active=False,
                    )
                    .returning(relation_type_revision.c.relation_type_revision_id)
                ).scalar_one()
            )
            connection.execute(
                relation_endpoint_rule.insert().values(
                    relation_type_revision_id=relation_revision_id,
                    source_node_type_id=type_ids["PERSON"],
                    target_node_type_id=type_ids["COMPANY"],
                )
            )

            attribute_id = int(
                connection.execute(
                    attribute.insert()
                    .values(attribute_code="CORE_COUNT")
                    .returning(attribute.c.attribute_id)
                ).scalar_one()
            )
            attribute_revision_id = int(
                connection.execute(
                    attribute_revision.insert()
                    .values(
                        attribute_id=attribute_id,
                        version_no=3,
                        display_name="existing exact attribute",
                        target_node_type_id=type_ids["TECHNOLOGY"],
                        allowed_value_kind="NUMBER",
                        is_active=False,
                    )
                    .returning(attribute_revision.c.attribute_revision_id)
                ).scalar_one()
            )
            connection.execute(
                attribute_revision_allowed_unit.insert().values(
                    attribute_revision_id=attribute_revision_id,
                    allowed_value_kind="NUMBER",
                    unit_code="COUNT",
                )
            )

            result = _activate(connection)
            assert result.relation_revision_ids["AFFILIATED_WITH"] == relation_revision_id
            assert result.attribute_revision_ids["CORE_COUNT"] == attribute_revision_id
            assert bool(
                connection.scalar(
                    sa.select(relation_type_revision.c.is_active).where(
                        relation_type_revision.c.relation_type_revision_id
                        == relation_revision_id
                    )
                )
            )
            assert bool(
                connection.scalar(
                    sa.select(attribute_revision.c.is_active).where(
                        attribute_revision.c.attribute_revision_id
                        == attribute_revision_id
                    )
                )
            )
        finally:
            outer.rollback()
'''
test_path.write_text(prefix + new_tests)

replace_once(
    "docs/data/ontology-reference-data.md",
    "clean migrated DB에는 ontology row가 없으므로 activation은 frozen logical schema의 초기 stable node type `PERSON`, `COMPANY`, `TECHNOLOGY`, `TOPIC`, `EVENT`도 공통 prerequisite로 보장한다. 이 다섯 type은 아래 제품 Relation·attribute·Topic payload와 HBF 개발 fixture가 공유하는 기반 코드이며, fixture의 시험 Relation을 제품 ontology로 승격시키지 않는다.",
    "clean migrated DB에는 ontology row가 없으므로 activation은 frozen logical schema의 초기 stable node type `PERSON`, `COMPANY`, `TECHNOLOGY`, `TOPIC`, `EVENT`를 공통 prerequisite로 생성할 수 있다. 이미 같은 code가 있으면 display name·creation rule이 호환되고 active인 row만 재사용한다. 기존 row가 inactive이거나 정의가 충돌하면 그 상태를 변경하지 않고 fail-closed하며, 특히 inactive `TOPIC`을 몰래 재활성화하지 않는다. HBF fixture도 같은 compatible active node type을 재사용하므로 fixture → activation과 activation → fixture 두 순서가 모두 가능하고, fixture 소유 `PUBLICLY_ASSOCIATED_WITH`는 제품 ontology와 계속 분리된다.",
)
replace_once(
    "docs/data/ontology-reference-data.md",
    "activation은 Relation type/revision/endpoint, attribute/revision/unit과 Topic reference만 다룬다. 기존 Relation·Claim·Evidence·publication과 HBF fixture를 새 제품 code로 소급 변환하지 않는다. 실제 PostgreSQL 검증에서는 activation 재실행 시 동일 revision/Topic ID가 유지되는지, HBF fixture 이후 실행해도 fixture Relation·Claim·source·Observation·promotion·검색 문서 수가 바뀌지 않는지 확인한다.",
    "activation은 Relation type/revision/endpoint, attribute/revision/unit과 Topic reference만 다룬다. 기존 Relation·Claim·Evidence·publication과 HBF fixture를 새 제품 code로 소급 변환하지 않는다. 실제 PostgreSQL 검증에서는 fixture → activation과 activation → fixture 양방향 실행 및 양쪽 재실행의 idempotency, inactive node type 보존/fail-closed, conflicting active Relation·Attribute revision의 transaction rollback, exact inactive revision ID 재사용을 함께 확인한다.",
)

subprocess.run(
    [
        "uv",
        "run",
        "--project",
        "server",
        "--frozen",
        "ruff",
        "format",
        activation_path,
        fixture_path,
        str(test_path),
    ],
    check=True,
)
