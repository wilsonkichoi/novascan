"""API Lambda entry point — Lambda Powertools resolver with health check."""

from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

from api.dashboard import router as dashboard_router
from api.receipts import router as receipts_router
from api.upload import router as upload_router

logger = Logger()
tracer = Tracer()
app = APIGatewayHttpResolver()

app.include_router(upload_router)
app.include_router(receipts_router)
app.include_router(dashboard_router)


@app.get("/api/health")
@tracer.capture_method
def health() -> dict[str, str]:
    return {"status": "ok"}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
