import asyncio
from typing import Any, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import Message


class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: Union[int, float] = 0.1, admin_ids: list=None):
        # Initialize latency and album_data dictionary
        self.latency = latency
        self.album_data = {}
        self.admin_ids = admin_ids if admin_ids else []
#
    def collect_album_messages(self, event: Message):
        """
        Collect messages of the same media group.
        """
#         # Check if media_group_id exists in album_data
        if event.media_group_id not in self.album_data:
#             # Create a new entry for the media group
            self.album_data[event.media_group_id] = {"messages": []}
#
#         # Append the new message to the media group
        self.album_data[event.media_group_id]["messages"].append(event)
#
#         # Return the total number of messages in the current media group
        return len(self.album_data[event.media_group_id]["messages"])
#
    async def __call__(self, handler, event: Message, data: Dict[str, Any]) -> Any:
        """
        Main middlewares logic.
        """
#         # If the event has no media_group_id, pass it to the handler immediately
        if not event.media_group_id:
            return await handler(event, data)
#
#         # Collect messages of the same media group
        total_before = self.collect_album_messages(event)
#
#         # Wait for a specified latency period
        await asyncio.sleep(self.latency)
#
#         # Check the total number of messages after the latency
        total_after = len(self.album_data[event.media_group_id]["messages"])
#
#         # If new messages were added during the latency, exit
        if total_before != total_after:
            return
#
#         # Sort the album messages by message_id and add to data
        album_messages = self.album_data[event.media_group_id]["messages"]
        album_messages.sort(key=lambda x: x.message_id)
        data["album"] = album_messages

        
        return await handler(event, data)
#