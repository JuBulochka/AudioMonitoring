"""WebSocket consumer — pushes real-time alerts to authenticated operators."""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("apps.alerts")


class AlertConsumer(AsyncWebsocketConsumer):
    """
    Each authenticated user gets their own group: user_<id>_alerts.
    The alert service calls channel_layer.group_send() when new alerts arrive.
    Frontend subscribes on page load.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_{user.id}_alerts"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("WS connected: user=%s group=%s", user.id, self.group_name)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def alert_new(self, event):
        """Receive alert from channel layer and forward to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "alert",
            "alert_id": event.get("alert_id"),
            "alert_type": event.get("alert_type"),
            "severity": event.get("severity"),
            "title": event.get("title"),
            "message": event.get("message"),
            "device_id": event.get("device_id"),
            "created_at": event.get("created_at"),
        }))
