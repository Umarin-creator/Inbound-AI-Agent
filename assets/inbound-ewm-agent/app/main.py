import logging
import os
import pathlib

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.responses import FileResponse

from agent_executor import AgentExecutor

_JOULE_RUNTIME = os.environ.get("JOULE_RUNTIME") == "1"

if _JOULE_RUNTIME:
    from sap_cloud_sdk.aicore import set_aicore_config
    set_aicore_config()
    from starlette.middleware.base import BaseHTTPMiddleware
    from mcp_providers.agw import set_user_token, reset_user_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))


def _build_app():
    skill = AgentSkill(
        id="inbound-ewm-agent",
        name="inbound-ewm-agent",
        description="An AI agent that guides warehouse operators step by step through the complete SAP EWM inbound warehouse process using natural language, barcode scanning, and human approvals via SAP Joule",
        tags=["inbound", "ewm", "warehouse", "sap", "agent"],
        examples=["Process inbound delivery 1800012345", "What is the status of TU 12345?"],
    )
    agent_card = AgentCard(
        name="inbound-ewm-agent",
        description="An AI agent that guides warehouse operators step by step through the complete SAP EWM inbound warehouse process using natural language, barcode scanning, and human approvals via SAP Joule",
        url=os.environ.get("AGENT_PUBLIC_URL", f"http://{HOST}:{PORT}/"),
        version="1.0.0",
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[skill],
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=DefaultRequestHandler(
            agent_executor=AgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    )
    app = server.build()

    if not _JOULE_RUNTIME:
        from starlette.middleware.cors import CORSMiddleware
        _origins = os.environ.get("CORS_ALLOW_ORIGINS", "*").split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
            max_age=3600,
        )

        _ui_file = pathlib.Path(__file__).parent.parent / "test-client" / "index.html"
        _ui_outbound_file = pathlib.Path(__file__).parent.parent / "test-client" / "outbound.html"

        async def _ui_handler(request):
            return FileResponse(str(_ui_file), media_type="text/html")

        async def _ui_outbound_handler(request):
            return FileResponse(str(_ui_outbound_file), media_type="text/html")

        app.add_route("/ui", _ui_handler, methods=["GET"])
        app.add_route("/ui-outbound", _ui_outbound_handler, methods=["GET"])

    if _JOULE_RUNTIME:
        class JWTContextMiddleware(BaseHTTPMiddleware):
            """Extracts JWT token from Authorization header and sets it in context."""

            async def dispatch(self, request, call_next):
                auth_header = request.headers.get("authorization", "")
                token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
                token_ctx = set_user_token(token)
                try:
                    return await call_next(request)
                finally:
                    reset_user_token(token_ctx)

        app.add_middleware(JWTContextMiddleware)

    return app


# ASGI application object — imported by gunicorn on CF
application = _build_app()

if __name__ == "__main__":
    logger.info(f"Starting A2A server at http://{HOST}:{PORT}")
    uvicorn.run(application, host=HOST, port=PORT)
