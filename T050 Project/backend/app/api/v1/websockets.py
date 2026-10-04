"""
WebSocket Real-Time Event Hub.

Provides real-time bi-directional communication channels for live contract collaboration,
approval workflow state changes, instant comments, and SLA alerts.
"""
import asyncio
import json
import logging
from typing import Dict, List, Set, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websockets"])


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by global channels and contract-specific rooms.
    """

    def __init__(self):
        # Global notification subscribers: connection -> user_id
        self.active_global_connections: Dict[WebSocket, str] = {}
        # Contract room subscribers: contract_id -> Set[WebSocket]
        self.contract_rooms: Dict[str, Set[WebSocket]] = {}

    async def connect_global(self, websocket: WebSocket, user_id: str = "anonymous"):
        await websocket.accept()
        self.active_global_connections[websocket] = user_id
        logger.info(f"WebSocket client connected (user: {user_id}). Total global: {len(self.active_global_connections)}")

    def disconnect_global(self, websocket: WebSocket):
        if websocket in self.active_global_connections:
            del self.active_global_connections[websocket]
            logger.info("WebSocket global client disconnected.")

    async def connect_room(self, websocket: WebSocket, contract_id: str):
        await websocket.accept()
        if contract_id not in self.contract_rooms:
            self.contract_rooms[contract_id] = set()
        self.contract_rooms[contract_id].add(websocket)
        logger.info(f"WebSocket client joined contract room '{contract_id}'. Total in room: {len(self.contract_rooms[contract_id])}")

    def disconnect_room(self, websocket: WebSocket, contract_id: str):
        if contract_id in self.contract_rooms and websocket in self.contract_rooms[contract_id]:
            self.contract_rooms[contract_id].remove(websocket)
            if not self.contract_rooms[contract_id]:
                del self.contract_rooms[contract_id]
            logger.info(f"WebSocket client left contract room '{contract_id}'.")

    async def broadcast_global(self, message: Dict[str, Any]):
        """Broadcast event message to all connected global clients."""
        payload = json.dumps(message)
        dead_connections = []
        for ws in list(self.active_global_connections.keys()):
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)
        for ws in dead_connections:
            self.disconnect_global(ws)

    async def broadcast_room(self, contract_id: str, message: Dict[str, Any]):
        """Broadcast event message to all clients in a specific contract room."""
        if contract_id not in self.contract_rooms:
            return
        payload = json.dumps(message)
        dead_connections = []
        for ws in list(self.contract_rooms[contract_id]):
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)
        for ws in dead_connections:
            self.disconnect_room(ws, contract_id)


manager = ConnectionManager()

_main_loop = None

def set_main_loop(loop):
    global _main_loop
    _main_loop = loop


def dispatch_global_event(event_data: Dict[str, Any]):
    """Safely dispatches a real-time event to all connected WebSocket clients from any thread or handler."""
    global _main_loop
    try:
        # 1. Thread-safe execution onto uvicorn main loop if called from sync worker thread
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast_global(event_data), _main_loop)
            return

        # 2. Check if current thread has an active loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            _main_loop = loop
            loop.create_task(manager.broadcast_global(event_data))
        else:
            logger.warning("No running main event loop found for dispatch_global_event")
    except Exception as e:
        logger.warning(f"Failed to dispatch real-time global event: {e}")


@router.websocket("/contracts")
async def websocket_contracts_endpoint(websocket: WebSocket, token: str = Query(None)):
    """
    Contracts Real-Time WebSocket endpoint.
    Clients receive instant updates on contract INSERT, UPDATE, DELETE, and approval progression.
    """
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    user_id = "contracts_client"
    await manager.connect_global(websocket, user_id=user_id)
    try:
        await websocket.send_text(json.dumps({
            "event": "connected",
            "channel": "contracts",
            "message": "Real-time contracts stream active.",
        }))
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect_global(websocket)


@router.websocket("/notifications")
async def websocket_notifications_endpoint(websocket: WebSocket, token: str = Query(None)):
    """
    Global notification WebSocket endpoint.
    Clients receive real-time alerts for approvals, contract status updates, and risk detections.
    """
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    user_id = "user_demo"
    await manager.connect_global(websocket, user_id=user_id)
    try:
        # Send initial connection status message
        await websocket.send_text(json.dumps({
            "event": "connected",
            "message": "Real-time notification socket active.",
            "user_id": user_id
        }))
        while True:
            # Keep connection alive and process ping/pong or client messages
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect_global(websocket)


@router.websocket("/contracts/{contract_id}")
async def websocket_contract_room_endpoint(websocket: WebSocket, contract_id: str):
    """
    Contract Room WebSocket endpoint.
    Clients viewing a specific contract receive instant updates for comments, redlines, and stage transitions.
    """
    await manager.connect_room(websocket, contract_id)
    try:
        await websocket.send_text(json.dumps({
            "event": "room_joined",
            "contract_id": contract_id,
            "message": f"Connected to live updates for contract {contract_id}"
        }))
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                action = payload.get("action")
                if action == "typing":
                    await manager.broadcast_room(contract_id, {
                        "event": "user_typing",
                        "contract_id": contract_id,
                        "user_name": payload.get("user_name", "Team Member")
                    })
                elif action == "comment":
                    await manager.broadcast_room(contract_id, {
                        "event": "new_comment",
                        "contract_id": contract_id,
                        "author": payload.get("author", "Reviewer"),
                        "comment": payload.get("comment", "")
                    })
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect_room(websocket, contract_id)
