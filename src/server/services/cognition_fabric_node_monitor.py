# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Fabric Node Monitor - Background service for monitoring node heartbeats"""

import asyncio
import logging

from server.services.cognition_fabric_node import cognition_fabric_node_service

logger = logging.getLogger(__name__)


class CognitionFabricNodeMonitor:
    """Background monitor for Cognition Fabric Node status"""

    def __init__(self, check_interval_seconds: int = 60, offline_threshold_minutes: int = 2):
        """
        Initialize Cognition Fabric Node Monitor

        Args:
            check_interval_seconds: How often to check for stale nodes (default: 60s)
            offline_threshold_minutes: Minutes since last heartbeat to mark offline (default: 2min)
        """
        self.check_interval = check_interval_seconds
        self.offline_threshold = offline_threshold_minutes
        self.running = False
        logger.info(
            f"Cognition Fabric Node Monitor initialized (check_interval={self.check_interval}s, "
            f"offline_threshold={self.offline_threshold}min)"
        )

    async def start(self):
        """Start the background monitoring loop"""
        self.running = True
        logger.info("Starting Cognition Fabric Node monitor")

        while self.running:
            try:
                count = cognition_fabric_node_service.mark_stale_nodes_offline(self.offline_threshold)
                if count > 0:
                    logger.info(f"Marked {count} Cognition Fabric Node(s) as offline")
            except Exception as e:
                logger.error(f"Error in Cognition Fabric Node monitor: {e}", exc_info=True)

            # Wait for next check interval
            await asyncio.sleep(self.check_interval)

        logger.info("Cognition Fabric Node monitor stopped")

    def stop(self):
        """Stop the background monitoring loop"""
        self.running = False
        logger.info("Stopping Cognition Fabric Node monitor")


# Global instance
cognition_fabric_node_monitor = CognitionFabricNodeMonitor(check_interval_seconds=60, offline_threshold_minutes=2)
