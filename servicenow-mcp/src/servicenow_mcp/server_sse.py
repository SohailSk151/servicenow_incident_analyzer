"""
ServiceNow MCP Server

This module provides the main implementation of the ServiceNow MCP server.
"""

import argparse
import os
import logging
from typing import Dict, Union, Optional

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
        - limit: Number of incidents to return (default: 100
        )
        - sysparm_query: ServiceNow query string (optional)
        - priority: Filter by priority (e.g., priority=1 for P1)
        """
        try:
            logger.info("Received request to GET /incidents")
            
            limit = request.query_params.get('limit', '100')
            sysparm_query = request.query_params.get('sysparm_query', '')
            priority = request.query_params.get('priority', '')
            
            
            # Add priority filter if specified
            if priority:
                if sysparm_query:
                    sysparm_query += f"^priority={priority}"
                else:
                    sysparm_query = f"priority={priority}"
            
            incidents = servicenow_mcp.fetch_incidents(
                limit=int(limit),
                sysparm_query=sysparm_query
            )
            
            logger.info(f"Successfully fetched {len(incidents)} incidents")
            return JSONResponse(incidents)
            
        except Exception as e:
            logger.error(f"Error fetching incidents: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to fetch incidents"},
                status_code=500
            )

    async def get_incident_by_id(request: Request) -> JSONResponse:
        """Get a specific incident by sys_id or number"""
        try:
            incident_id = request.path_params['incident_id']
            logger.info(f"Fetching incident: {incident_id}")
            
            incident = servicenow_mcp.get_incident(incident_id)
            
            if incident:
                return JSONResponse(incident)
            else:
                return JSONResponse(
                    {"error": "Incident not found"},
                    status_code=404
                )
            
        except Exception as e:
            logger.error(f"Error fetching incident: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to fetch incident"},
                status_code=500
            )

    async def create_incident(request: Request) -> JSONResponse:
        """Create a new incident"""
        try:
            logger.info("Received request to CREATE incident")
            
            body = await request.json()
            logger.info(f"Request body: {body}")
            
            incident = servicenow_mcp.create_incident(body)
            
            logger.info(f"Successfully created incident: {incident.get('number')}")
            return JSONResponse(incident, status_code=201)
            
        except Exception as e:
            logger.error(f"Error creating incident: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to create incident"},
                status_code=500
            )

    async def update_incident(request: Request) -> JSONResponse:
        """Update an existing incident"""
        try:
            incident_id = request.path_params['incident_id']
            logger.info(f"Received request to UPDATE incident: {incident_id}")
            
            body = await request.json()
            logger.info(f"Update data: {body}")
            
            incident = servicenow_mcp.update_incident(incident_id, body)
            
            logger.info(f"Successfully updated incident: {incident_id}")
            return JSONResponse(incident)
            
        except Exception as e:
            logger.error(f"Error updating incident: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to update incident"},
                status_code=500
            )

    async def delete_incident(request: Request) -> JSONResponse:
        """Delete an incident"""
        try:
            incident_id = request.path_params['incident_id']
            logger.info(f"Received request to DELETE incident: {incident_id}")
            
            servicenow_mcp.delete_incident(incident_id)
            
            logger.info(f"Successfully deleted incident: {incident_id}")
            return JSONResponse({"message": f"Incident {incident_id} deleted successfully"})
            
        except Exception as e:
            logger.error(f"Error deleting incident: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to delete incident"},
                status_code=500
            )

    async def assign_incident(request: Request) -> JSONResponse:
        """Assign an incident to a user"""
        try:
            incident_id = request.path_params['incident_id']
            body = await request.json()
            user_id = body.get('assigned_to')
            
            logger.info(f"Assigning incident {incident_id} to user {user_id}")
            
            incident = servicenow_mcp.assign_incident(incident_id, user_id)
            
            return JSONResponse(incident)
            
        except Exception as e:
            logger.error(f"Error assigning incident: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to assign incident"},
                status_code=500
            )

    async def resolve_incident(request: Request) -> JSONResponse:
        """Resolve an incident"""
        try:
            incident_id = request.path_params['incident_id']
            body = await request.json()
            resolution_notes = body.get('close_notes', '')
            
            logger.info(f"Resolving incident: {incident_id}")
            
            incident = servicenow_mcp.resolve_incident(incident_id, resolution_notes)
            
            return JSONResponse(incident)
            
        except Exception as e:
            logger.error(f"Error resolving incident: {str(e)}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "message": "Failed to resolve incident"},
                status_code=500
            )

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint"""
        return JSONResponse({"status": "healthy", "service": "ServiceNow MCP Server"})

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=health_check, methods=["GET"]),
            
            # Incident CRUD operations
            Route("/incidents", endpoint=get_incidents, methods=["GET"]),
            Route("/incidents", endpoint=create_incident, methods=["POST"]),
            Route("/incidents/{incident_id:path}", endpoint=get_incident_by_id, methods=["GET"]),
            Route("/incidents/{incident_id:path}", endpoint=update_incident, methods=["PUT", "PATCH"]),
            Route("/incidents/{incident_id:path}", endpoint=delete_incident, methods=["DELETE"]),
            
            # Additional operations
            Route("/incidents/{incident_id:path}/assign", endpoint=assign_incident, methods=["POST"]),
            Route("/incidents/{incident_id:path}/resolve", endpoint=resolve_incident, methods=["POST"]),
            
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


class ServiceNowSSEMCP(ServiceNowMCP):
    """ServiceNow MCP Server implementation with full CRUD support."""

    def __init__(self, config: Union[Dict, ServerConfig]):
        super().__init__(config)
        self.config = config if isinstance(config, ServerConfig) else ServerConfig(**config)
        logger.info(f"Initialized ServiceNow MCP with instance: {self.config.instance_url}")

    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None):
        """Helper method to make requests to ServiceNow"""
        instance_url = self.config.instance_url
        username = self.config.auth.basic.username
        password = self.config.auth.basic.password

        url = f"{instance_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                params=params,
                auth=HTTPBasicAuth(username, password),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            logger.info(f"{method} {url} - Status: {response.status_code}")
            
            if response.status_code in [200, 201, 204]:
                return response.json() if response.content else {}
            else:
                error_text = response.text
                logger.error(f"ServiceNow API error {response.status_code}: {error_text}")
                raise Exception(f"ServiceNow API returned {response.status_code}: {error_text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {str(e)}")
            raise Exception(f"Failed to connect to ServiceNow: {str(e)}")

    def fetch_incidents(self, limit: int = 100, sysparm_query: str = "") -> list:
        """Fetch incidents from ServiceNow"""
        params = {
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        
        if sysparm_query:
            params["sysparm_query"] = sysparm_query

        result = self._make_request("GET", "/api/now/table/incident", params=params)
        return result.get('result', [])

    def get_incident(self, incident_id: str) -> Optional[dict]:
        """Get a specific incident by sys_id or number"""
        # Try by sys_id first
        try:
            result = self._make_request("GET", f"/api/now/table/incident/{incident_id}")
            return result.get('result')
        except:
            # If fails, try searching by number
            params = {"sysparm_query": f"number={incident_id}", "sysparm_limit": 1}
            result = self._make_request("GET", "/api/now/table/incident", params=params)
            incidents = result.get('result', [])
            return incidents[0] if incidents else None

    def create_incident(self, data: dict) -> dict:
        """Create a new incident"""
        result = self._make_request("POST", "/api/now/table/incident", data=data)
        return result.get('result', {})

    def update_incident(self, incident_id: str, data: dict) -> dict:
        """Update an existing incident"""
        # Get the sys_id if number is provided
        incident = self.get_incident(incident_id)
        if not incident:
            raise Exception(f"Incident {incident_id} not found")
        
        sys_id = incident.get('sys_id')
        result = self._make_request("PATCH", f"/api/now/table/incident/{sys_id}", data=data)
        return result.get('result', {})

    def delete_incident(self, incident_id: str):
        """Delete an incident"""
        # Get the sys_id if number is provided
        incident = self.get_incident(incident_id)
        if not incident:
            raise Exception(f"Incident {incident_id} not found")
        
        sys_id = incident.get('sys_id')
        self._make_request("DELETE", f"/api/now/table/incident/{sys_id}")

    def assign_incident(self, incident_id: str, user_id: str) -> dict:
        """Assign an incident to a user"""
        return self.update_incident(incident_id, {"assigned_to": user_id})

    def resolve_incident(self, incident_id: str, resolution_notes: str = "") -> dict:
        """Resolve an incident"""
        data = {
            "state": "6",  # Resolved state
            "close_notes": resolution_notes
        }
        return self.update_incident(incident_id, data)

    def start(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the MCP server"""
        starlette_app = create_starlette_app(self.mcp_server, self, debug=True)

        print(f"🚀 Starting ServiceNow MCP Server on http://{host}:{port}")
        print(f"📍 Health check: http://{host}:{port}/health")
        print(f"\n📋 Available Endpoints:")
        print(f"   GET    /incidents - List incidents")
        print(f"   POST   /incidents - Create incident")
        print(f"   GET    /incidents/{{id}} - Get specific incident")
        print(f"   PATCH  /incidents/{{id}} - Update incident")
        print(f"   DELETE /incidents/{{id}} - Delete incident")
        print(f"   POST   /incidents/{{id}}/assign - Assign incident")
        print(f"   POST   /incidents/{{id}}/resolve - Resolve incident")
        print(f"\n🔗 ServiceNow Instance: {self.config.instance_url}\n")

        uvicorn.run(starlette_app, host=host, port=port, log_level="info")


def create_servicenow_mcp(instance_url: str, username: str, password: str):
    """Create a ServiceNow MCP server with minimal configuration."""
    auth_config = AuthConfig(
        type=AuthType.BASIC, basic=BasicAuthConfig(username=username, password=password)
    )
    config = ServerConfig(instance_url=instance_url, auth=auth_config)
    return ServiceNowSSEMCP(config)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run ServiceNow MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

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