"""
ServiceNow MCP Server

This module provides the main implementation of the ServiceNow MCP server.
"""

import argparse
import os
import logging
from typing import Dict, Union

import uvicorn
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import requests
from requests.auth import HTTPBasicAuth

from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_starlette_app(mcp_server: Server, servicenow_mcp: 'ServiceNowSSEMCP', *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    async def get_incidents(request: Request) -> JSONResponse:
        """
        Fetch incidents from ServiceNow.
        
        Query parameters:
        - limit: Number of incidents to return (default: 100)
        - sysparm_query: ServiceNow query string (optional)
        """
        try:
            logger.info("Received request to /incidents endpoint")
            
            # Get query parameters
            limit = request.query_params.get('limit', '100')
            sysparm_query = request.query_params.get('sysparm_query', '')
            
            logger.info(f"Fetching incidents with limit={limit}, query={sysparm_query}")
            
            # Fetch incidents from ServiceNow
            incidents = servicenow_mcp.fetch_incidents(
                limit=int(limit),
                sysparm_query=sysparm_query
            )
            
            logger.info(f"Successfully fetched {len(incidents)} incidents")
            return JSONResponse(incidents)
            
        except Exception as e:
            logger.error(f"Error fetching incidents: {str(e)}", exc_info=True)
            return JSONResponse(
                {
                    "error": str(e), 
                    "message": "Failed to fetch incidents from ServiceNow",
                    "type": type(e).__name__
                },
                status_code=500
            )

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint"""
        return JSONResponse({"status": "healthy", "service": "ServiceNow MCP Server"})

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/incidents", endpoint=get_incidents, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


class ServiceNowSSEMCP(ServiceNowMCP):
    """
    ServiceNow MCP Server implementation.

    This class provides a Model Context Protocol (MCP) server for ServiceNow,
    allowing LLMs to interact with ServiceNow data and functionality.
    """

    def __init__(self, config: Union[Dict, ServerConfig]):
        """
        Initialize the ServiceNow MCP server.

        Args:
            config: Server configuration, either as a dictionary or ServerConfig object.
        """
        super().__init__(config)
        self.config = config if isinstance(config, ServerConfig) else ServerConfig(**config)
        logger.info(f"Initialized ServiceNow MCP with instance: {self.config.instance_url}")

    def fetch_incidents(self, limit: int = 100, sysparm_query: str = "") -> list:
        """
        Fetch incidents from ServiceNow using the Table API (synchronous).

        Args:
            limit: Maximum number of incidents to return
            sysparm_query: ServiceNow query string for filtering

        Returns:
            List of incident records
        """
        instance_url = self.config.instance_url
        username = self.config.auth.basic.username
        password = self.config.auth.basic.password

        logger.info(f"Connecting to ServiceNow instance: {instance_url}")

        # Build the API URL
        url = f"{instance_url}/api/now/table/incident"
        
        params = {
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        
        if sysparm_query:
            params["sysparm_query"] = sysparm_query

        try:
            logger.info(f"Making request to: {url}")
            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(username, password),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                incidents = data.get('result', [])
                logger.info(f"Successfully fetched {len(incidents)} incidents")
                return incidents
            else:
                error_text = response.text
                logger.error(f"ServiceNow API error {response.status_code}: {error_text}")
                raise Exception(f"ServiceNow API returned {response.status_code}: {error_text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {str(e)}")
            raise Exception(f"Failed to connect to ServiceNow: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

    def start(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Start the MCP server with SSE transport using Starlette and Uvicorn.

        Args:
            host: Host address to bind to
            port: Port to listen on
        """
        # Create Starlette app with SSE transport and REST endpoints
        starlette_app = create_starlette_app(self.mcp_server, self, debug=True)

        print(f"🚀 Starting ServiceNow MCP Server on http://{host}:{port}")
        print(f"📍 SSE endpoint: http://{host}:{port}/sse")
        print(f"📍 Incidents API: http://{host}:{port}/incidents")
        print(f"📍 Health check: http://{host}:{port}/health")
        print(f"🔗 ServiceNow Instance: {self.config.instance_url}")

        # Run using uvicorn
        uvicorn.run(starlette_app, host=host, port=port, log_level="info")


def create_servicenow_mcp(instance_url: str, username: str, password: str):
    """
    Create a ServiceNow MCP server with minimal configuration.

    This is a simplified factory function that creates a pre-configured
    ServiceNow MCP server with basic authentication.

    Args:
        instance_url: ServiceNow instance URL
        username: ServiceNow username
        password: ServiceNow password

    Returns:
        A configured ServiceNowMCP instance ready to use

    Example:
        ```python
        from servicenow_mcp.server import create_servicenow_mcp

        # Create an MCP server for ServiceNow
        mcp = create_servicenow_mcp(
            instance_url="https://instance.service-now.com",
            username="admin",
            password="password"
        )

        # Start the server
        mcp.start()
        ```
    """

    # Create basic auth config
    auth_config = AuthConfig(
        type=AuthType.BASIC, basic=BasicAuthConfig(username=username, password=password)
    )

    # Create server config
    config = ServerConfig(instance_url=instance_url, auth=auth_config)

    # Create and return server
    return ServiceNowSSEMCP(config)


def main():
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run ServiceNow MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    # Validate environment variables
    instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
    username = os.getenv("SERVICENOW_USERNAME")
    password = os.getenv("SERVICENOW_PASSWORD")

    if not all([instance_url, username, password]):
        logger.error("Missing required environment variables!")
        logger.error("Please set: SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD")
        return

    server = create_servicenow_mcp(
        instance_url=instance_url,
        username=username,
        password=password,
    )
    server.start(host=args.host, port=args.port)


if __name__ == "__main__":
    main()