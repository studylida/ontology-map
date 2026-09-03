from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ontology_map.db.session import open_read_session
from ontology_map.exploration import (
    ExplorationNotFoundError,
    PublicationNotReadyError,
    TimeWindow,
    get_exploration,
)

router = APIRouter(prefix="/api/v1")

_MAX_BIGINT = 9_223_372_036_854_775_807


class ErrorBody(BaseModel):
    code: str
    retryable: bool


class ErrorResponse(BaseModel):
    error: ErrorBody


class NodeTypeResponse(BaseModel):
    code: str
    display_name: str


class GraphNodeResponse(BaseModel):
    node_id: str
    name: str
    node_type: NodeTypeResponse
    tier: Literal["CENTER", "DIRECT", "TWO_HOP"]
    activity_evidence_group_count: int = Field(ge=0)


class GraphRelationResponse(BaseModel):
    relation_id: str
    source_node_id: str
    target_node_id: str
    relation_type_display_name: str
    supporting_evidence_group_count: int = Field(ge=1)
    has_conflict: bool


class GraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    relations: list[GraphRelationResponse]


class RecommendationNodeResponse(BaseModel):
    node_id: str
    name: str
    node_type: NodeTypeResponse


class RecommendationResponse(BaseModel):
    target_node: RecommendationNodeResponse
    reason_code: Literal["DIRECT", "TWO_HOP", "AMBIENT"]
    via_node_id: str | None
    supporting_evidence_group_count: int | None = Field(default=None, ge=1)


class FollowupQuestionResponse(BaseModel):
    slot: Literal[1, 2]
    question_text: str
    target_node_id: str


class ExplorationResponse(BaseModel):
    center_node_id: str
    context_text: str
    graph: GraphResponse
    recommendations: list[RecommendationResponse]
    followup_questions: list[FollowupQuestionResponse]


class APIError(Exception):
    def __init__(self, status_code: int, code: str, *, retryable: bool) -> None:
        self.status_code = status_code
        self.code = code
        self.retryable = retryable


async def api_error_handler(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, APIError):
        raise error
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "retryable": error.retryable}},
    )


async def validation_error_handler(
    _request: Request, _error: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_REQUEST", "retryable": False}},
    )


def _node_id(value: str) -> int:
    node_id = int(value)
    if node_id > _MAX_BIGINT:
        raise APIError(422, "INVALID_REQUEST", retryable=False)
    return node_id


@router.get(
    "/exploration/{center_node_id}",
    response_model=ExplorationResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def read_exploration(
    center_node_id: Annotated[
        str,
        Path(pattern=r"^[1-9][0-9]{0,18}$"),
    ],
    time_window: Annotated[TimeWindow, Query()],
    session: Annotated[Session, Depends(open_read_session)],
) -> ExplorationResponse:
    try:
        result = get_exploration(
            session,
            _node_id(center_node_id),
            time_window,
        )
    except ExplorationNotFoundError as error:
        raise APIError(404, "NODE_NOT_FOUND", retryable=False) from error
    except PublicationNotReadyError as error:
        raise APIError(503, "PUBLICATION_NOT_READY", retryable=True) from error

    return ExplorationResponse(
        center_node_id=str(result.center_node_id),
        context_text=result.context_text,
        graph=GraphResponse(
            nodes=[
                GraphNodeResponse(
                    node_id=str(node.node_id),
                    name=node.name,
                    node_type=NodeTypeResponse(
                        code=node.node_type.code,
                        display_name=node.node_type.display_name,
                    ),
                    tier=node.tier,
                    activity_evidence_group_count=node.activity_evidence_group_count,
                )
                for node in result.graph.nodes
            ],
            relations=[
                GraphRelationResponse(
                    relation_id=str(relation.relation_id),
                    source_node_id=str(relation.source_node_id),
                    target_node_id=str(relation.target_node_id),
                    relation_type_display_name=relation.relation_type_display_name,
                    supporting_evidence_group_count=(
                        relation.supporting_evidence_group_count
                    ),
                    has_conflict=relation.has_conflict,
                )
                for relation in result.graph.relations
            ],
        ),
        recommendations=[
            RecommendationResponse(
                target_node=RecommendationNodeResponse(
                    node_id=str(recommendation.target_node.node_id),
                    name=recommendation.target_node.name,
                    node_type=NodeTypeResponse(
                        code=recommendation.target_node.node_type.code,
                        display_name=recommendation.target_node.node_type.display_name,
                    ),
                ),
                reason_code=recommendation.reason_code,
                via_node_id=(
                    str(recommendation.via_node_id)
                    if recommendation.via_node_id is not None
                    else None
                ),
                supporting_evidence_group_count=(
                    recommendation.supporting_evidence_group_count
                ),
            )
            for recommendation in result.recommendations
        ],
        followup_questions=[
            FollowupQuestionResponse(
                slot=question.slot,
                question_text=question.question_text,
                target_node_id=str(question.target_node_id),
            )
            for question in result.followup_questions
        ],
    )
