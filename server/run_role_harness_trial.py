"""The finite #139 development comparison, using the product extraction functions.

No DB, raw provider responses, reasoning, resume, or automatic retry. Parsed
candidates are private, temporary review material, never application artifacts.
"""

import argparse
import json
import os
import stat
import subprocess
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr

from ontology_map.extraction import (
    BODY_PROMPT,
    CLAIM_PROMPT,
    GENERATION_PROMPT,
    MEANING_PROMPT,
    BodySelectionError,
    ExtractionLimits,
    extract_body,
    generate_knowledge,
    judge_proposals,
)
from ontology_map.extraction_contracts import (
    AttributeRule,
    BodySelection,
    ClaimSupport,
    KnowledgeProposals,
    MeaningSupport,
    Ontology,
    RelationRule,
    SourceDocument,
    SourceSpan,
    digest,
)
from ontology_map.model_studio import (
    FLASH,
    PLUS,
    RATES,
    Budget,
    CallFailed,
    CallLimits,
    ModelStudio,
    validate_base_url,
)

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = Path("/home/studylida/.config/ontology-map/model-studio.env")
# The one prior paid execution; #139 comments 5612600497 and 5612890817.
# This finite runner does not discover/resume executions or reset their allowance.
PRIOR_EXECUTION = {
    "sha256": "c5eb5e62b287f44d5ed8964cb6df749c01d263368371a2e0808ea4780a83ca98",
    "calls": 1,
    "calls_by_role": {
        "body": 1,
        "generation": 0,
        "claim_support": 0,
        "meaning_support": 0,
    },
    "charged_upper_usd": Decimal("0.0005054"),
}
LIMITS = ExtractionLimits(
    body=CallLimits(32768, 2048, 131072),
    generation=CallLimits(32768, 12288, 131072),
    judgment=CallLimits(32768, 256, 131072),
    max_candidates=24,
)


def approved_ontology():
    # #126 comment 5612152332: runtime definitions, not fabricated DB revisions.
    actors, technology = ("COMPANY", "PERSON"), ("TECHNOLOGY",)
    descriptions = (
        ("AFFILIATED_WITH", "인물의 회사 소속", ("PERSON",), ("COMPANY",)),
        ("DEVELOPS", "기술·제품 개발", actors, technology),
        ("COLLABORATES_WITH", "두 회사의 공동 행위", ("COMPANY",), ("COMPANY",)),
        ("ANNOUNCES", "기술·제품·사건 발표", actors, ("TECHNOLOGY", "EVENT")),
        ("INVESTS_IN", "회사·기술·제품 투자", ("COMPANY",), ("COMPANY", "TECHNOLOGY")),
        ("ADOPTS", "기술·제품 도입", ("COMPANY",), technology),
        ("TESTS", "기술·제품 시험·검증", ("COMPANY",), technology),
        ("SUPPLIES", "기술·제품 공급", ("COMPANY",), technology),
        ("SUPPLIES_TO", "회사 간 공급", ("COMPANY",), ("COMPANY",)),
        ("INCLUDES", "기술·제품 구성 포함", technology, technology),
        ("PARTICIPATES_IN", "구체적 사건 참여", actors, ("EVENT",)),
        (
            "MENTIONS",
            "실제 발언의 대상. 이름의 동시 등장만으로 연결하지 않는다.",
            actors,
            ("COMPANY", "PERSON", "TECHNOLOGY", "EVENT"),
        ),
        (
            "HAS_TOPIC",
            "원문 표현이 자기 근거에서 지원하는 승인 Topic 의미 연결",
            ("COMPANY", "PERSON", "TECHNOLOGY", "EVENT"),
            ("TOPIC",),
        ),
    )
    attributes = (
        ("ROLE_TITLE", "원문 직책", "PERSON", "STRING", ()),
        ("TECHNOLOGY_VERSION", "원문 기술·제품 버전", "TECHNOLOGY", "STRING", ()),
        (
            "COMMERCIALIZATION_STATUS",
            "원문의 상용화 단계·계획·검토·완료 구분",
            "TECHNOLOGY",
            "STRING",
            (),
        ),
        (
            "COMMERCIALIZATION_SCHEDULE",
            "원문 일정 문자열. 상대 시점을 임의 날짜로 바꾸지 않는다.",
            "TECHNOLOGY",
            "STRING",
            (),
        ),
        (
            "CORE_COUNT",
            "정확한 코어 수만 사용. 상한·범위·조건을 지워 단일 값으로 바꾸지 않는다.",
            "TECHNOLOGY",
            "NUMBER",
            ("COUNT",),
        ),
        (
            "MAX_MEMORY_BANDWIDTH",
            "최대 메모리 대역폭. 최대라는 의미와 원문 단위를 보존하고 환산하지 않는다.",
            "TECHNOLOGY",
            "NUMBER",
            ("GB_PER_S", "TB_PER_S"),
        ),
    )
    return Ontology(
        node_types=("COMPANY", "PERSON", "TECHNOLOGY", "EVENT", "TOPIC"),
        relations=tuple(
            RelationRule(
                code=code,
                version_no=1,
                revision_id=None,
                description=description
                + " 계획·부정·시점·수량·귀속은 Claim에서 보존한다.",
                direction="SYMMETRIC" if code == "COLLABORATES_WITH" else "DIRECTED",
                endpoints=tuple((s, t) for s in sources for t in targets),
            )
            for code, description, sources, targets in descriptions
        ),
        attributes=tuple(
            AttributeRule(
                code=code,
                version_no=1,
                revision_id=None,
                description=description,
                node_type=node_type,
                value_kind=kind,
                units=units,
            )
            for code, description, node_type, kind, units in attributes
        ),
        topics=(
            "반도체",
            "메모리 반도체",
            "첨단 패키징",
            "인공지능",
            "데이터센터",
            "제조 공정",
            "투자",
            "상용화",
            "규제·정책",
        ),
    )


def documents(path):
    rows = json.loads(path.read_text())
    if [row["id"] for row in rows] != ["C01", "C02", "C03", "C04"]:
        raise ValueError("SOURCE_SET_CHANGED")
    return [
        SourceDocument(
            document_id=row["id"],
            body=row["source"],
            body_hash=row["sha256"],
            sources=tuple(
                SourceSpan(
                    source_id=s["block_id"],
                    start=s["start_char"],
                    end=s["end_char"],
                    quote=s["text"],
                    quote_hash=digest(s["text"]),
                    paragraph_id=s["paragraph_id"],
                )
                for s in row["sentences"]
            ),
        )
        for row in rows
    ]


def json_default(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("UNSUPPORTED_REVIEW_VALUE")


def encoded(value):
    return json.dumps(value, default=json_default, ensure_ascii=False, sort_keys=True)


def write_private(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(encoded(value) + "\n")


def manifest(args, docs, ontology, base_url):
    tracked = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    )
    if tracked:
        raise ValueError("TRACKED_WORKTREE_NOT_CLEAN")
    gold = json.loads(args.gold.read_text())
    if [a["article_id"] for a in gold["articles"]] != [d.document_id for d in docs]:
        raise ValueError("GOLD_SOURCE_SET")
    if [len(a["facts"]) for a in gold["articles"]] != [6, 6, 6, 6]:
        raise ValueError("GOLD_FACT_SET")
    return {
        "trial": "139-role-harness-paragraph-v1-body-diagnostics",
        "scope": "development-regression",
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "code_sha256": {
            str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                ROOT / "server/pyproject.toml",
                ROOT / "server/uv.lock",
                *sorted((ROOT / "server/src/ontology_map").glob("*.py")),
            ]
        },
        "sources_sha256": sha256(args.sources.read_bytes()).hexdigest(),
        "gold_sha256": sha256(args.gold.read_bytes()).hexdigest(),
        "documents": {d.document_id: d.body_hash for d in docs},
        "spans": {d.document_id: len(d.sources) for d in docs},
        "ontology": ontology,
        "ontology_sha256": digest(ontology.model_dump_json()),
        "prompt_sha256": {
            role: digest(prompt)
            for role, prompt in (
                ("body", BODY_PROMPT),
                ("generation", GENERATION_PROMPT),
                ("claim_support", CLAIM_PROMPT),
                ("meaning_support", MEANING_PROMPT),
            )
        },
        "schema_sha256": {
            t.__name__: digest(encoded(t.model_json_schema()))
            for t in (BodySelection, KnowledgeProposals, ClaimSupport, MeaningSupport)
        },
        "endpoint_kind": "Singapore workspace-dedicated",
        "endpoint_sha256": digest(base_url),
        "models": [FLASH, PLUS],
        "rates_per_million": RATES,
        "limits": asdict(LIMITS),
        "max_calls_by_role": {
            "body": 5,
            "generation": 8,
            "claim_support": 192,
            "meaning_support": 192,
        },
        "max_calls": 396,
        "max_usd": "3.00",
        "prior_execution": PRIOR_EXECUTION,
        "reservation_input_tokens": 1_000_000,
        "temperature": 0,
        "thinking": False,
        "streaming": False,
        "retries": 0,
        "conditions": {"A": "paragraph_id=null", "B": "normalized paragraph_id"},
        "order": {
            "C01": ["A", "B"],
            "C02": ["B", "A"],
            "C03": ["A", "B"],
            "C04": ["B", "A"],
        },
        "body_selection": "one Flash selection shared by both conditions per document",
        "selection_approval": "139#5612152480",
        "catalog_approval": "126#5612152332",
        "budget_approval": "139#5611799845",
        "body_limit_approval": "139#5612890817",
        "selection_criterion": {
            "final_required_retention": "strictly higher",
            "final_critical_rate": (
                "not worse; all final nonduplicate claims denominator"
            ),
            "claim_support_false_accept_rate": (
                "not worse; unsupported judged claims denominator"
            ),
            "new_critical_fact_family": False,
            "requires": (
                "complete comparison; both nonempty; nonzero metric denominators"
            ),
            "independent_gate": "not evaluated by these four development articles",
        },
    }


def load_credentials():
    # Reuse the earlier trial's restricted reader, without importing its executor.
    with os.fdopen(os.open(KEY_FILE, os.O_RDONLY | os.O_NOFOLLOW)) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("CREDENTIAL_FILE_OWNER")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("CREDENTIAL_FILE_PERMISSIONS")
        settings = dotenv_values(stream=handle, interpolate=False)
    base_url = validate_base_url(settings.get("MODEL_STUDIO_BASE_URL") or "")
    key = settings.get("DASHSCOPE_API_KEY") or ""
    if not key or any(c.isspace() for c in key):
        raise ValueError("KEY_NOT_CONFIGURED")
    return SecretStr(key), base_url


def execute(args, frozen, docs, ontology, key, base_url):
    # Exclusive marker prevents replaying ambiguous calls, including a crashed run.
    write_private(
        args.output_dir / "started.json", {"manifest_sha256": digest(encoded(frozen))}
    )
    budget = Budget(
        396 - PRIOR_EXECUTION["calls"],
        Decimal("3.00") - PRIOR_EXECUTION["charged_upper_usd"],
    )
    rows = []
    client = None
    status, error_code = "INCOMPLETE", None
    stage = "credentials"
    try:
        os.environ["DASHSCOPE_API_KEY"] = key.get_secret_value()
        client = ModelStudio(key, budget, base_url=base_url)
        for doc in docs:
            stage = "body"
            print(f"{doc.document_id} body START", flush=True)
            body = extract_body(doc, client, LIMITS.body)
            write_private(args.output_dir / f"{doc.document_id}-body.json", body)
            if not body:
                raise CallFailed("EMPTY_BODY", fatal=True)
            for condition in frozen["order"][doc.document_id]:
                stage = "generation"
                print(f"{doc.document_id} {condition} generation START", flush=True)
                proposals = generate_knowledge(
                    body, ontology, client, LIMITS, include_structure=condition == "B"
                )
                write_private(
                    args.output_dir / f"{doc.document_id}-{condition}-generated.json",
                    proposals,
                )
                stage = "judgment"
                print(
                    f"{doc.document_id} {condition} judgment {len(proposals.claims)}",
                    flush=True,
                )
                result = judge_proposals(proposals, body, ontology, client, LIMITS)
                write_private(
                    args.output_dir / f"{doc.document_id}-{condition}-result.json",
                    asdict(result),
                )
                rows.append(
                    {
                        "document": doc.document_id,
                        "condition": condition,
                        "status": result.status,
                        "generated": len(result.generated),
                        "verified": len(result.verified),
                        "error_code": result.error_code,
                    }
                )
                print(
                    encoded(
                        {
                            **rows[-1],
                            "calls": len(budget.records),
                            "cost_upper_usd": budget.charged_upper_usd,
                        }
                    ),
                    flush=True,
                )
                if result.status == "FAILED" or any(
                    r.status != "SUCCESS" for r in budget.records
                ):
                    raise CallFailed(
                        result.error_code or "CALL_CONTRACT_FAILURE", fatal=True
                    )
        status = "COMPLETE"
    except CallFailed as error:
        status, error_code = "STOPPED", error.code
    except BodySelectionError as error:
        status, error_code = "STOPPED", error.code
        write_private(
            args.output_dir / "body-selection-error.json",
            {"document_id": doc.document_id, **error.diagnostic},
        )
    except Exception:
        # Never print exceptions containing credentials, source data, or outputs.
        status, error_code = "STOPPED", "LOCAL_CONTRACT_ERROR"
    finally:
        os.environ.pop("DASHSCOPE_API_KEY", None)
        if client is not None:
            client.close()
        report = {
            "status": status,
            "error_code": error_code,
            "last_stage": stage,
            "rows": rows,
            "records": [asdict(r) for r in budget.records],
            "calls": len(budget.records),
            "charged_upper_usd": budget.charged_upper_usd,
            "cumulative_calls": PRIOR_EXECUTION["calls"] + len(budget.records),
            "cumulative_charged_upper_usd": (
                PRIOR_EXECUTION["charged_upper_usd"] + budget.charged_upper_usd
            ),
            "manifest_sha256": digest(encoded(frozen)),
        }
        write_private(args.output_dir / "execution.json", report)
        print(encoded({k: v for k, v in report.items() if k != "records"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    info = args.output_dir.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("PRIVATE_DIRECTORY_REQUIRED")
    docs, ontology = documents(args.sources), approved_ontology()
    key, base_url = load_credentials()
    frozen = manifest(args, docs, ontology, base_url)
    path = args.output_dir / "manifest.json"
    if not args.execute:
        write_private(path, frozen)
        print(encoded(frozen))
        return
    if path.read_text().strip() != encoded(frozen):
        raise ValueError("FROZEN_INPUT_CHANGED")
    execute(args, frozen, docs, ontology, key, base_url)


if __name__ == "__main__":
    try:
        main()
    except CallFailed as error:
        raise SystemExit(error.code) from None
    except Exception:
        raise SystemExit("TRIAL_PREFLIGHT_FAILED") from None
