# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine Monitor - Background service for monitoring engine heartbeats"""

import asyncio
import logging

from server.services.cognition_engine import cognition_engine_service

logger = logging.getLogger(__name__)


class CognitionEngineMonitor:
    """Background monitor for Cognition Engine status"""

    def __init__(self, check_interval_seconds: int = 60, offline_threshold_minutes: int = 2):
        """
        Initialize Cognition Engine Monitor

        Args:
            check_interval_seconds: How often to check for stale engines (default: 60s)
            offline_threshold_minutes: Minutes since last heartbeat to mark offline (default: 2min)
        """
        self.check_interval = check_interval_seconds
        self.offline_threshold = offline_threshold_minutes
        self.running = False
        logger.info(
            f"Cognition Engine Monitor initialized (check_interval={self.check_interval}s, "
            f"offline_threshold={self.offline_threshold}min)"
        )

    async def start(self):
        """Start the background monitoring loop"""
        self.running = True
        logger.info("Starting Cognition Engine monitor")

        while self.running:
            try:
                count = cognition_engine_service.mark_stale_engines_offline(self.offline_threshold)
                if count > 0:
                    logger.info(f"Marked {count} Cognition Engine(s) as offline")
            except Exception as e:
                logger.error(f"Error in Cognition Engine monitor: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

        logger.info("Cognition Engine monitor stopped")

    def stop(self):
        """Stop the background monitoring loop"""
        self.running = False
        logger.info("Stopping Cognition Engine monitor")


# Global instance
cognition_engine_monitor = CognitionEngineMonitor()
