#!/usr/bin/env python3
"""
Async Discord Gateway Example with Compression Support
Run with: python async_example.py
"""

import asyncio
import json
from async_gateway import AsyncDiscordGateway

async def main():
    # Replace with your token from config.json
    with open('config.json', 'r') as f:
        config = json.load(f)
        token = config.get('token')

    if not token or token == "token here":
        print("❌ Please set your token in config.json")
        return

    print("🚀 Starting Async Discord Gateway...")

    # Create gateway client with compression enabled (recommended)
    # Set compress=False if you want uncompressed connection
    gateway = AsyncDiscordGateway(token, client_type="web", compress=True)

    # Set up event handlers
    def on_ready(data):
        user = data.get('user', {})
        print(f"✅ Connected as {user.get('username')}#{user.get('discriminator', '0')}")
        print("🗜️ Using zlib-stream compression for better performance")

    def on_message(data):
        content = data.get('content', '')
        if content:  # Only print messages with content
            author = data.get('author', {}).get('username', 'Unknown')
            channel_id = data.get('channel_id', 'Unknown')
            print(f"📨 #{channel_id} | {author}: {content}")

    gateway.on_ready = on_ready
    gateway.on_message = on_message

    # Connect and run
    try:
        await gateway.connect()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
