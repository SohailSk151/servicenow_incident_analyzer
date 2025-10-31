"""
Command-line interface for the ServiceNow MCP server.
"""

import argparse
import logging
import os
import sys

import anyio
from dotenv import load_dotenv
from mcp.server.stdio import stdio_server

from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.server_sse import ServiceNowSSEMCP  # <-- Added import for SSE-based server
from servicenow_mcp.utils.config import (
    ApiKeyConfig,
    AuthConfig,
    AuthType,
    BasicAuthConfig,
    OAuthConfig,
    ServerConfig,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="ServiceNow MCP Server")

    # Host and Port (added for SSE-based runs)
    parser.add_argument(
        "--host",
        default=os.environ.get("SERVICENOW_HOST", "0.0.0.0"),
        help="Host address to bind to (used in SSE mode)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SERVICENOW_PORT", "8080")),
        help="Port to listen on (used in SSE mode)",
    )

    # Server configuration
    parser.add_argument(
        "--instance-url",
        help="ServiceNow instance URL (e.g., https://instance.service-now.com)",
        default=os.environ.get("SERVICENOW_INSTANCE_URL"),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
        default=os.environ.get("SERVICENOW_DEBUG", "false").lower() == "true",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Request timeout in seconds",
        default=int(os.environ.get("SERVICENOW_TIMEOUT", "30")),
    )

    # Authentication
    auth_group = parser.add_argument_group("Authentication")
    auth_group.add_argument(
        "--auth-type",
        choices=["basic", "oauth", "api_key"],
        help="Authentication type",
        default=os.environ.get("SERVICENOW_AUTH_TYPE", "basic"),
    )

    # Basic auth
    basic_group = parser.add_argument_group("Basic Authentication")
    basic_group.add_argument(
        "--username",
        help="ServiceNow username",
        default=os.environ.get("SERVICENOW_USERNAME"),
    )
    basic_group.add_argument(
        "--password",
        help="ServiceNow password",
        default=os.environ.get("SERVICENOW_PASSWORD"),
    )

    # OAuth
    oauth_group = parser.add_argument_group("OAuth Authentication")
    oauth_group.add_argument(
        "--client-id",
        help="OAuth client ID",
        default=os.environ.get("SERVICENOW_CLIENT_ID"),
    )
    oauth_group.add_argument(
        "--client-secret",
        help="OAuth client secret",
        default=os.environ.get("SERVICENOW_CLIENT_SECRET"),
    )
    oauth_group.add_argument(
        "--token-url",
        help="OAuth token URL",
        default=os.environ.get("SERVICENOW_TOKEN_URL"),
    )

    # API Key
    api_key_group = parser.add_argument_group("API Key Authentication")
    api_key_group.add_argument(
        "--api-key",
        help="ServiceNow API key",
        default=os.environ.get("SERVICENOW_API_KEY"),
    )
    api_key_group.add_argument(
        "--api-key-header",
        help="API key header name",
        default=os.environ.get("SERVICENOW_API_KEY_HEADER", "X-ServiceNow-API-Key"),
    )

    # Script execution API resource path
    script_execution_group = parser.add_argument_group("Script Execution API")
    script_execution_group.add_argument(
        "--script-execution-api-resource-path",
        help="Script execution API resource path",
        default=os.environ.get("SCRIPT_EXECUTION_API_RESOURCE_PATH"),
    )

    return parser.parse_args()


def create_config(args) -> ServerConfig:
    """
    Create server configuration from command-line arguments.
    """
    instance_url = args.instance_url
    if not instance_url:
        instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
        if not instance_url:
            raise ValueError(
                "ServiceNow instance URL is required (--instance-url or SERVICENOW_INSTANCE_URL env var)"
            )

    auth_type = AuthType(args.auth_type.lower())
    final_auth_config: AuthConfig

    if auth_type == AuthType.BASIC:
        username = args.username or os.getenv("SERVICENOW_USERNAME")
        password = args.password or os.getenv("SERVICENOW_PASSWORD")
        if not username or not password:
            raise ValueError(
                "Username and password are required for basic authentication (--username/SERVICENOW_USERNAME, --password/SERVICENOW_PASSWORD)"
            )
        basic_cfg = BasicAuthConfig(username=username, password=password)
        final_auth_config = AuthConfig(type=auth_type, basic=basic_cfg)

    elif auth_type == AuthType.OAUTH:
        client_id = args.client_id or os.getenv("SERVICENOW_CLIENT_ID")
        client_secret = args.client_secret or os.getenv("SERVICENOW_CLIENT_SECRET")
        username = args.username or os.getenv("SERVICENOW_USERNAME")
        password = args.password or os.getenv("SERVICENOW_PASSWORD")
        token_url = args.token_url or os.getenv("SERVICENOW_TOKEN_URL")
        if not client_id or not client_secret or not username or not password:
            raise ValueError(
                "Client ID, client secret, username, and password are required for OAuth password grant"
            )
        if not token_url:
            token_url = f"{instance_url}/oauth_token.do"
            logger.warning(f"OAuth token URL not provided, defaulting to: {token_url}")
        oauth_cfg = OAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            token_url=token_url,
        )
        final_auth_config = AuthConfig(type=auth_type, oauth=oauth_cfg)

    elif auth_type == AuthType.API_KEY:
        api_key = args.api_key or os.getenv("SERVICENOW_API_KEY")
        api_key_header = args.api_key_header or os.getenv(
            "SERVICENOW_API_KEY_HEADER", "X-ServiceNow-API-Key"
        )
        if not api_key:
            raise ValueError(
                "API key is required for API key authentication (--api-key or SERVICENOW_API_KEY)"
            )
        api_key_cfg = ApiKeyConfig(api_key=api_key, header_name=api_key_header)
        final_auth_config = AuthConfig(type=auth_type, api_key=api_key_cfg)
    else:
        raise ValueError(f"Unsupported authentication type: {args.auth_type}")

    script_execution_api_resource_path = args.script_execution_api_resource_path or os.getenv(
        "SCRIPT_EXECUTION_API_RESOURCE_PATH"
    )
    if not script_execution_api_resource_path:
        logger.warning(
            "Script execution API resource path not set. ExecuteScriptInclude tool may fail."
        )

    return ServerConfig(
        instance_url=instance_url,
        auth=final_auth_config,
        debug=args.debug,
        timeout=args.timeout,
        script_execution_api_resource_path=script_execution_api_resource_path,
    )


async def arun_stdio_server(server_instance):
    """Runs the given MCP server instance using stdio transport."""
    logger.info("Starting server with stdio transport...")
    async with stdio_server() as streams:
        init_options = server_instance.create_initialization_options()
        await server_instance.run(streams[0], streams[1], init_options)
    logger.info("Stdio server finished.")


def main():
    """Main entry point for the CLI."""
    load_dotenv()

    try:
        args = parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.info("Debug logging enabled.")
        else:
            logging.getLogger().setLevel(logging.INFO)

        config = create_config(args)
        logger.info(f"Initializing ServiceNow MCP server for instance: {config.instance_url}")

        # --- NEW LOGIC ---
        # If running under MCP host (which passes --port/--host), start SSE server
        if "--port" in sys.argv or "--host" in sys.argv:
            logger.info(f"Starting SSE-based MCP server on {args.host}:{args.port}...")
            server = ServiceNowSSEMCP(config)
            server.start(host=args.host, port=args.port)
            return

        # Otherwise, fallback to stdio mode
        mcp_controller = ServiceNowMCP(config)
        server_to_run = mcp_controller.start()
        anyio.run(arun_stdio_server, server_to_run)

    except ValueError as e:
        logger.error(f"Configuration or runtime error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error starting or running server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
