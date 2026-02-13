# Cognitive Fabric Node (CFN) Management API

**Implementation Date**: January 30, 2026
**Last Updated**: February 11, 2026
**Status**: ✅ Complete and Production Ready

## Overview

Cognitive Fabric Nodes (CFNs) are data path services that communicate with the management backend via HTTP REST APIs. This document describes the complete lifecycle management API for CFNs.

**Short Form**: CFN
**Communication Contract**: HTTP REST (ioc-mgmt-svc ↔ ioc-cfn)

---

## Table of Contents

1. [API Endpoints](#api-endpoints)
2. [Lifecycle Management](#lifecycle-management)
3. [Complete Flows](#complete-flows)
4. [Database Schema](#database-schema)
5. [RBAC Permissions](#rbac-permissions)
6. [Background Monitoring](#background-monitoring)
7. [Testing](#testing)

---

## API Endpoints

### 1. Create CFN

**POST** `/api/workspaces/{workspace_id}/cognitive-fabric-node`

Creates a new CFN node or refreshes an active one.

**Request Body:**
```json
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1",
  "cfn_config": {
    "memory": "8GB",
    "max_connections": 500
  }
}
```

**Response (201 Created):**
```json
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1",
  "status": "offline",
  "cloud_config": {
    "workspace_id": "ws-abc-123",
    "log_level": "INFO",
    "features": [],
    "updated_at": "2026-02-11T10:00:00Z"
  }
}
```

**Behavior by CFN State:**

| CFN State                  | Behavior                            | Response      |
| -------------------------- | ----------------------------------- | ------------- |
| **New CFN**                | Creates new entry                   | 201 Created   |
| **Deleted CFN** (ID reuse) | Reuses ID to create new CFN         | 201 Created   |
| **Active CFN** (reboot)    | Refreshes config, resets to offline | 201 Created   |
| **Disabled CFN**           | Rejects creation, ID is locked      | 403 Forbidden |

**Authorization:** Requires `create_cognitive_fabric_node` permission (Admin)

---

### 2. Enable CFN

**PATCH** `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/enable`

Manually re-enables a disabled CFN node.

**Response (200 OK):**
```json
{
  "cfn_id": "cfn-node-001",
  "workspace_id": "ws-abc-123",
  "cfn_name": "production-cfn-1",
  "enabled": true,
  "status": "offline",
  "last_seen": "2026-02-11T10:00:00Z",
  ...
}
```

**Authorization:** Requires `enable_cognitive_fabric_node` permission (Admin)

---

### 3. Disable CFN

**PATCH** `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable`

Disables a CFN node (soft disable). Stops heartbeats and prepares for deletion.

**Effects:**
- Sets `enabled=false`
- CFN hidden from list
- CFN ID is **LOCKED** (cannot be reused while disabled)
- "Delete" button appears in UI
- Heartbeats rejected with 403 Forbidden

**Response (200 OK):**
```json
{
  "cfn_id": "cfn-node-001",
  "workspace_id": "ws-abc-123",
  "cfn_name": "production-cfn-1",
  "enabled": false,
  "status": "offline",
  ...
}
```

**Authorization:** Requires `disable_cognitive_fabric_node` permission (Admin)

---

### 4. Delete CFN

**DELETE** `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}`

Deletes a CFN node (hard delete). **CFN must be disabled first.**

**Effects:**
- Sets `deleted_at` timestamp
- CFN ID **CAN BE REUSED** to create a new CFN
- Completely removes from UI workspace list

**Response:** 204 No Content

**Authorization:** Requires `delete_cognitive_fabric_node` permission (Admin)

**Important:** Returns 400 Bad Request if CFN is not disabled first.

---

### 5. Heartbeat

**PUT** `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat`

Updates CFN heartbeat timestamp and status.

**Response (200 OK):**
```json
{
  "status": "online",
  "last_seen": "2026-02-11T10:00:00Z"
}
```

**Behavior:**
- Updates `last_seen` timestamp
- Changes status from `offline` → `online`
- Disabled CFNs: Returns 403 Forbidden
- Deleted CFNs: Returns 403 Forbidden

**Frequency:** CFN should send heartbeat every 30 seconds
**Offline Threshold:** CFN marked offline after 2 minutes without heartbeat

**Authorization:** Requires `heartbeat_cognitive_fabric_node` permission (Admin)

---

### 6. Update CFN

**PUT** `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}`

Updates CFN name or configuration.

**Request Body:**
```json
{
  "cfn_name": "production-cfn-1-updated",
  "cfn_config": {
    "memory": "16GB",
    "max_connections": 1000
  }
}
```

**Response (200 OK):** Full CFN details

**Authorization:** Requires `update_cognitive_fabric_node` permission (Admin)

---

### 7. List CFNs

**GET** `/api/workspaces/{workspace_id}/cognitive-fabric-node`

Lists all **enabled** CFNs in workspace. Disabled CFNs are hidden.

**Query Parameters:**
- `status` (optional): Filter by status (`online`, `offline`)

**Response (200 OK):**
```json
{
  "nodes": [
    {
      "cfn_id": "cfn-node-001",
      "workspace_id": "ws-abc-123",
      "cfn_name": "production-cfn-1",
      "status": "online",
      "last_seen": "2026-02-11T10:00:00Z",
      "enabled": true,
      "created_at": "2026-02-11T09:00:00Z"
    }
  ],
  "total": 1
}
```

**Authorization:** Requires `list_cognitive_fabric_node` permission (Admin, Viewer)

---

### 8. Get CFN Details

**GET** `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}`

Gets detailed CFN information.

**Response (200 OK):**
```json
{
  "cfn_id": "cfn-node-001",
  "workspace_id": "ws-abc-123",
  "cfn_name": "production-cfn-1",
  "cfn_config": { "memory": "8GB" },
  "cloud_config": { "workspace_id": "ws-abc-123", ... },
  "status": "online",
  "last_seen": "2026-02-11T10:00:00Z",
  "enabled": true,
  "created_at": "2026-02-11T09:00:00Z",
  "updated_at": "2026-02-11T10:00:00Z",
  "created_by": "user-123",
  "updated_by": "user-123"
}
```

**Authorization:** Requires `get_cognitive_fabric_node` permission (Admin, Viewer)

---

## Lifecycle Management

### CFN States

```
┌─────────────────────────────────────────────────────────────┐
│                     CFN State Machine                       │
└─────────────────────────────────────────────────────────────┘

   CREATE
     ↓
  ┌──────────────────┐
  │ OFFLINE (Active) │  enabled=true, status=offline
  │                  │  (just created, waiting for heartbeat)
  └────────┬─────────┘
           │ heartbeat
           ↓
  ┌──────────────────┐
  │ ONLINE (Active)  │  enabled=true, status=online
  │                  │  (heartbeat received within 2min)
  └────────┬─────────┘
           │ no heartbeat for 2min
           ↓
  ┌──────────────────┐
  │ OFFLINE (Stale)  │  enabled=true, status=offline
  │                  │  (heartbeat exceeded threshold)
  └────────┬─────────┘
           │ user clicks "Disable"
           ↓
  ┌──────────────────┐
  │ DISABLED         │  enabled=false, deleted_at=null
  │                  │  (soft disabled, ID LOCKED)
  │                  │  (hidden from list, no heartbeat)
  └────────┬─────────┘
           │ user clicks "Delete"
           ↓
  ┌──────────────────┐
  │ DELETED          │  enabled=false, deleted_at=timestamp
  │                  │  (hard deleted, ID CAN BE REUSED)
  └──────────────────┘
```

### Status Transitions

| From State           | Action              | To State         | Notes                        |
| -------------------- | ------------------- | ---------------- | ---------------------------- |
| **N/A**              | Create              | Offline (Active) | New CFN created              |
| **Offline (Active)** | Heartbeat           | Online           | First heartbeat received     |
| **Online**           | Heartbeat           | Online           | Regular heartbeat            |
| **Online**           | No heartbeat (2min) | Offline (Stale)  | Background job marks offline |
| **Offline (Stale)**  | Heartbeat           | Online           | CFN recovers                 |
| **Online/Offline**   | Disable             | Disabled         | User action                  |
| **Disabled**         | Enable              | Offline (Active) | Admin re-enables             |
| **Disabled**         | Delete              | Deleted          | User action (after disable)  |
| **Deleted**          | Create (same ID)    | Offline (Active) | ID reused for new CFN        |

---

## Complete Flows

### 1. Normal Operations Flow

```bash
# 1. CFN calls create endpoint
POST /api/workspaces/{workspace_id}/cognitive-fabric-node
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1",
  "cfn_config": {"memory": "8GB"}
}
→ Response: 201 Created, status=offline

# 2. CFN sends heartbeat (every 30 seconds)
PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/heartbeat
→ Response: 200 OK, status=online

# 3. CFN continues sending heartbeat
PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/heartbeat
→ Response: 200 OK, status=online

# 4. Background job monitors (every 60 seconds)
# If no heartbeat for 2 minutes → status=offline
```

### 2. CFN Reboot/Reconnection Flow

```bash
# CFN reboots or loses connection
# CFN calls create endpoint again with same ID

POST /api/workspaces/{workspace_id}/cognitive-fabric-node
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1-rebooted",
  "cfn_config": {"memory": "16GB"}
}
→ Response: 201 Created, status=offline
→ Config refreshed, name updated

# CFN resumes heartbeat
PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/heartbeat
→ Response: 200 OK, status=online
```

### 3. Disable → Enable → Reconnect Flow

```bash
# 1. User disables CFN in UI
PATCH /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/disable
→ Response: 200 OK, enabled=false

# 2. CFN tries to send heartbeat (fails)
PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/heartbeat
→ Response: 403 Forbidden "CFN node is disabled"

# 3. CFN tries to reconnect (fails)
POST /api/workspaces/{workspace_id}/cognitive-fabric-node
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1"
}
→ Response: 403 Forbidden "CFN node has been disabled"

# 4. Admin re-enables CFN in UI
PATCH /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/enable
→ Response: 200 OK, enabled=true

# 5. CFN reconnects
POST /api/workspaces/{workspace_id}/cognitive-fabric-node
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1"
}
→ Response: 201 Created, status=offline

# 6. CFN resumes heartbeat
PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/heartbeat
→ Response: 200 OK, status=online
```

### 4. Disable → Delete → ID Reuse Flow

```bash
# 1. User disables CFN in UI
PATCH /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/disable
→ Response: 200 OK, enabled=false

# 2. User deletes CFN in UI
DELETE /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001
→ Response: 204 No Content

# 3. New CFN created with same ID (ID reuse)
POST /api/workspaces/{workspace_id}/cognitive-fabric-node
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1-v2",
  "cfn_config": {"memory": "32GB"}
}
→ Response: 201 Created, status=offline
→ New CFN created with same ID, clean slate

# 4. New CFN sends heartbeat
PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-node-001/heartbeat
→ Response: 200 OK, status=online
```

### CFN Config JSON

The `cloud_config` is returned by the management service to the CFN node during creation/reconnection. The CFN node reconciles against this configuration and applies it to its data path operations.

**Structure Overview:**
- **metadata**: Workspace context and audit trail
- **network**: Management endpoints and connectivity settings
- **memory_provider**: Internal graph database configuration
- **multi_agent_system**: Agent definitions and capabilities
- **resource_limits**: CPU, memory, storage quotas
- **features**: Enabled workspace features and toggles
- **logging**: Log levels and destinations
- **security**: Authentication, encryption, and access control
- **integrations**: External service endpoints
- **workspace_settings**: Workspace-specific configuration

**Complete Example:**

```json
{
  "version": "1.0",
  "config_id": "cfg-20260211-100000-abc123",
  "generated_at": "2026-02-11T10:00:00Z",

  "metadata": {
    "workspace_id": "ws-abc-123",
    "workspace_name": "Production Workspace",
    "cfn_id": "cfn-node-001",
    "cfn_name": "production-cfn-1",
    "created_by": "user-123",
    "created_at": "2026-02-11T09:00:00Z",
    "updated_by": "user-123",
    "updated_at": "2026-02-11T10:00:00Z",
    "environment": "production"
  },

  "network": {
    "management_endpoint": "https://mgmt.example.com:8000",
    "heartbeat_interval_seconds": 30,
    "heartbeat_timeout_seconds": 120,
    "reconnect_backoff_max_seconds": 300,
    "tls": {
      "enabled": true,
      "verify_certificates": true,
      "ca_bundle_path": "/etc/ssl/certs/ca-bundle.crt"
    },
    "proxy": {
      "enabled": false,
      "http_proxy": null,
      "https_proxy": null,
      "no_proxy": []
    }
  },

  "memory_provider": {
    "type": "internal",
    "provider": "neo4j",
    "config": {
      "host": "localhost",
      "port": 7687,
      "protocol": "bolt",
      "database": "neo4j",
      "max_connection_pool_size": 50,
      "connection_timeout_seconds": 30,
      "max_transaction_retry_time_seconds": 30,
      "encryption": true,
      "trust": "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES"
    },
    "backup": {
      "enabled": true,
      "interval_hours": 24,
      "retention_days": 7,
      "destination": "s3://backups/workspace-ws-abc-123/"
    }
  },

  "multi_agent_system": {
    "enabled": true,
    "orchestration_mode": "distributed",
    "agents": [
      {
        "agent_id": "agent-001",
        "agent_name": "Data Processor",
        "role": "data-processor",
        "version": "2.1.0",
        "enabled": true,
        "capabilities": [
          "process_data",
          "generate_report",
          "validate_schema",
          "transform_data"
        ],
        "config": {
          "memory_limit": "4GB",
          "cpu_limit": "2",
          "max_concurrent_tasks": 10,
          "task_timeout_seconds": 300,
          "retry_policy": {
            "max_retries": 3,
            "backoff_multiplier": 2
          }
        },
        "dependencies": []
      },
      {
        "agent_id": "agent-002",
        "agent_name": "Model Trainer",
        "role": "model-trainer",
        "version": "1.5.0",
        "enabled": true,
        "capabilities": [
          "train_model",
          "evaluate_model",
          "hyperparameter_tuning",
          "model_versioning"
        ],
        "config": {
          "memory_limit": "16GB",
          "cpu_limit": "8",
          "gpu_enabled": true,
          "gpu_count": 2,
          "gpu_memory_limit": "24GB",
          "max_training_time_hours": 24,
          "checkpoint_interval_minutes": 30
        },
        "dependencies": ["agent-001"]
      },
      {
        "agent_id": "agent-003",
        "agent_name": "Query Executor",
        "role": "query-executor",
        "version": "3.0.0",
        "enabled": true,
        "capabilities": [
          "execute_query",
          "optimize_query",
          "cache_results",
          "stream_results"
        ],
        "config": {
          "memory_limit": "8GB",
          "cpu_limit": "4",
          "query_timeout_seconds": 600,
          "max_result_size_mb": 500,
          "cache_ttl_seconds": 3600
        },
        "dependencies": []
      }
    ],
    "communication": {
      "protocol": "grpc",
      "port_range": "9000-9100",
      "timeout_seconds": 60,
      "retry_policy": {
        "max_retries": 3,
        "initial_backoff_ms": 100,
        "max_backoff_ms": 5000,
        "backoff_multiplier": 2
      }
    },
    "coordination": {
      "leader_election": {
        "enabled": true,
        "lease_duration_seconds": 15,
        "renew_deadline_seconds": 10,
        "retry_period_seconds": 2
      },
      "task_distribution": {
        "strategy": "least-loaded",
        "rebalance_interval_seconds": 300
      }
    }
  },

  "resource_limits": {
    "cpu": {
      "total_cores": 16,
      "reserved_cores": 2,
      "throttle_threshold_percent": 85
    },
    "memory": {
      "total_gb": 64,
      "reserved_gb": 8,
      "oom_threshold_percent": 90,
      "swap_enabled": false
    },
    "storage": {
      "total_gb": 1000,
      "reserved_gb": 100,
      "data_path": "/data/cfn",
      "temp_path": "/tmp/cfn",
      "max_file_size_mb": 5000,
      "disk_usage_warning_percent": 80,
      "disk_usage_critical_percent": 90
    },
    "network": {
      "max_connections": 5000,
      "max_bandwidth_mbps": 10000,
      "connection_timeout_seconds": 30,
      "idle_timeout_seconds": 600
    }
  },

  "features": {
    "data_encryption_at_rest": true,
    "data_encryption_in_transit": true,
    "audit_logging": true,
    "metrics_collection": true,
    "distributed_tracing": true,
    "auto_scaling": false,
    "real_time_analytics": true,
    "batch_processing": true,
    "streaming_ingestion": true,
    "model_serving": true,
    "feature_store": true,
    "data_versioning": true,
    "schema_registry": true,
    "query_optimization": true,
    "result_caching": true,
    "experimental_features": {
      "quantum_safe_crypto": false,
      "federated_learning": false,
      "edge_computing": false
    }
  },

  "logging": {
    "level": "INFO",
    "format": "json",
    "output": ["stdout", "file"],
    "file": {
      "path": "/var/log/cfn/cfn-node-001.log",
      "max_size_mb": 100,
      "max_backups": 10,
      "max_age_days": 30,
      "compress": true
    },
    "remote": {
      "enabled": true,
      "endpoint": "https://logs.example.com:9200",
      "protocol": "elasticsearch",
      "batch_size": 100,
      "flush_interval_seconds": 10
    },
    "components": {
      "core": "INFO",
      "agents": "INFO",
      "network": "WARN",
      "database": "WARN",
      "security": "INFO"
    },
    "structured_logging": true,
    "include_caller": true,
    "include_stack_trace": true
  },

  "security": {
    "authentication": {
      "method": "mutual-tls",
      "certificate_path": "/etc/cfn/certs/client.crt",
      "private_key_path": "/etc/cfn/certs/client.key",
      "ca_certificate_path": "/etc/cfn/certs/ca.crt",
      "certificate_rotation_days": 90
    },
    "authorization": {
      "rbac_enabled": true,
      "policy_endpoint": "https://authz.example.com/v1/policies",
      "policy_refresh_interval_seconds": 300,
      "default_deny": true
    },
    "encryption": {
      "algorithm": "AES-256-GCM",
      "key_rotation_days": 90,
      "kms_provider": "aws-kms",
      "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/abc-def-ghi"
    },
    "secrets_management": {
      "provider": "vault",
      "vault_address": "https://vault.example.com:8200",
      "vault_namespace": "cfn",
      "vault_mount_path": "secret/cfn-node-001",
      "token_renewal_interval_seconds": 3600
    },
    "network_policies": {
      "ingress_allowed_cidrs": ["10.0.0.0/8", "172.16.0.0/12"],
      "egress_allowed_destinations": ["*"],
      "rate_limiting": {
        "enabled": true,
        "requests_per_second": 1000,
        "burst_size": 2000
      }
    }
  },

  "integrations": {
    "object_storage": {
      "provider": "s3",
      "endpoint": "https://s3.amazonaws.com",
      "region": "us-east-1",
      "bucket": "workspace-ws-abc-123-data",
      "access_key_id": "AKIA...",
      "secret_access_key_path": "/etc/cfn/secrets/s3-secret",
      "encryption": "AES256"
    },
    "message_queue": {
      "provider": "kafka",
      "brokers": ["kafka-1.example.com:9092", "kafka-2.example.com:9092"],
      "topic_prefix": "ws-abc-123",
      "consumer_group": "cfn-node-001",
      "security_protocol": "SASL_SSL",
      "sasl_mechanism": "PLAIN"
    },
    "metrics": {
      "provider": "prometheus",
      "endpoint": "https://prometheus.example.com:9090",
      "push_interval_seconds": 15,
      "metrics_path": "/metrics",
      "labels": {
        "workspace_id": "ws-abc-123",
        "cfn_id": "cfn-node-001",
        "environment": "production"
      }
    },
    "tracing": {
      "provider": "jaeger",
      "endpoint": "https://jaeger.example.com:14268/api/traces",
      "sampling_rate": 0.1,
      "service_name": "cfn-node-001"
    },
    "model_registry": {
      "provider": "mlflow",
      "endpoint": "https://mlflow.example.com",
      "tracking_uri": "https://mlflow.example.com",
      "artifact_location": "s3://workspace-ws-abc-123-models/"
    }
  },

  "workspace_settings": {
    "timezone": "UTC",
    "locale": "en_US",
    "data_retention_days": 365,
    "backup_enabled": true,
    "disaster_recovery_enabled": true,
    "high_availability_enabled": false,
    "compliance": {
      "gdpr_enabled": true,
      "hipaa_enabled": false,
      "sox_enabled": false,
      "data_residency": "us-east-1"
    },
    "quotas": {
      "max_agents": 10,
      "max_concurrent_queries": 100,
      "max_storage_tb": 10,
      "max_bandwidth_gbps": 10
    },
    "notification": {
      "channels": ["email", "slack"],
      "email_recipients": ["ops@example.com"],
      "slack_webhook": "https://hooks.slack.com/services/T00/B00/XXX",
      "alert_on_errors": true,
      "alert_on_resource_limits": true
    },
    "custom": {
      "business_unit": "Data Science",
      "cost_center": "DS-001",
      "project_code": "ML-2026-Q1",
      "owner": "user-123"
    }
  },

  "health_checks": {
    "enabled": true,
    "interval_seconds": 30,
    "timeout_seconds": 10,
    "failure_threshold": 3,
    "success_threshold": 1,
    "endpoints": [
      {
        "name": "liveness",
        "path": "/health/liveness",
        "port": 8080
      },
      {
        "name": "readiness",
        "path": "/health/readiness",
        "port": 8080
      }
    ]
  },

  "maintenance": {
    "auto_update": {
      "enabled": false,
      "check_interval_hours": 24,
      "update_window_start": "02:00",
      "update_window_end": "04:00",
      "allowed_days": ["saturday", "sunday"]
    },
    "garbage_collection": {
      "enabled": true,
      "interval_hours": 6,
      "aggressive_mode": false
    },
    "log_rotation": {
      "enabled": true,
      "interval_hours": 24
    }
  }
}
```

**Key Sections Explained:**

1. **metadata**: Workspace context, CFN identity, audit trail
2. **network**: Management connectivity, heartbeat settings, TLS/proxy config
3. **memory_provider**: Internal graph database (Neo4j) configuration
4. **multi_agent_system**: Agent definitions with capabilities, resources, dependencies
5. **resource_limits**: CPU, memory, storage, network quotas and thresholds
6. **features**: Feature flags for workspace capabilities
7. **logging**: Log levels, formats, outputs, remote logging
8. **security**: Authentication, authorization, encryption, secrets management
9. **integrations**: External services (S3, Kafka, Prometheus, Jaeger, MLflow)
10. **workspace_settings**: Workspace-specific settings, compliance, quotas
11. **health_checks**: Liveness and readiness probe configuration
12. **maintenance**: Auto-update, garbage collection, log rotation settings

**CFN Reconciliation Flow:**

1. CFN receives `cloud_config` from management service
2. CFN validates config schema and version
3. CFN compares received config with current state
4. CFN applies changes incrementally:
   - Update agent configurations
   - Adjust resource limits
   - Enable/disable features
   - Update logging levels
   - Reconfigure integrations
5. CFN reports reconciliation status in next heartbeat
6. CFN enters steady state until next config update

---

## Database Schema

### Table: `cognitive_fabric_node`

| Column         | Type         | Nullable | Description                             |
| -------------- | ------------ | -------- | --------------------------------------- |
| `cfn_id`       | VARCHAR(255) | NOT NULL | Primary key, CFN identifier (immutable) |
| `workspace_id` | VARCHAR(36)  | NOT NULL | Foreign key to workspace                |
| `cfn_name`     | VARCHAR(255) | NOT NULL | Human-readable name (can be updated)    |
| `mgmt_host_ip` | VARCHAR(255) | NULL     | Management backend IP (optional)        |
| `mgmt_port`    | INTEGER      | NULL     | Management backend port (optional)      |
| `cfn_config`   | JSONB        | NULL     | CFN's reported configuration            |
| `cloud_config` | JSONB        | NULL     | Management's desired configuration      |
| `status`       | VARCHAR(50)  | NOT NULL | `online`, `offline`                     |
| `last_seen`    | TIMESTAMP    | NOT NULL | Last heartbeat timestamp                |
| `enabled`      | BOOLEAN      | NOT NULL | Whether node is enabled (default: true) |
| `created_at`   | TIMESTAMP    | NOT NULL | Creation timestamp                      |
| `updated_at`   | TIMESTAMP    | NULL     | Last update timestamp                   |
| `created_by`   | VARCHAR(36)  | NOT NULL | User who created CFN                    |
| `updated_by`   | VARCHAR(36)  | NULL     | User who last updated CFN               |
| `deleted_at`   | TIMESTAMP    | NULL     | Soft delete timestamp                   |

**Indexes:**
- Primary Key: `cfn_id`
- Foreign Key: `workspace_id` → `workspace.id`
- Unique: `(workspace_id, cfn_name)` for active CFNs (deleted_at IS NULL)

**Note:** `deleted_at` is used for hard delete marker. When set, the CFN ID can be reused.

---

## RBAC Permissions

### Admin Operations (Full Access)

| Permission                        | Description            |
| --------------------------------- | ---------------------- |
| `create_cognitive_fabric_node`    | Create or refresh CFN  |
| `update_cognitive_fabric_node`    | Update CFN name/config |
| `enable_cognitive_fabric_node`    | Re-enable disabled CFN |
| `disable_cognitive_fabric_node`   | Disable CFN (soft)     |
| `delete_cognitive_fabric_node`    | Delete CFN (hard)      |
| `heartbeat_cognitive_fabric_node` | Send heartbeat         |
| `get_cognitive_fabric_node`       | Get CFN details        |
| `list_cognitive_fabric_node`      | List CFNs              |

### Viewer Operations (Read-Only)

| Permission                   | Description     |
| ---------------------------- | --------------- |
| `get_cognitive_fabric_node`  | Get CFN details |
| `list_cognitive_fabric_node` | List CFNs       |

### Guest Operations

No access to any CFN operations.

---

## Background Monitoring

### CFN Monitor Service

**Service:** `CFNMonitor` (singleton: `cfn_monitor`)

**Configuration:**
- **Check Interval:** 60 seconds
- **Offline Threshold:** 2 minutes (4 missed heartbeats)
- **Heartbeat Frequency:** CFN should send heartbeat every 30 seconds

**Behavior:**
- Runs as async background task
- Starts on application startup
- Stops gracefully on shutdown
- Marks online nodes as offline if `last_seen` > 2 minutes

**Implementation:**
```python
# Background job runs every 60 seconds
for cfn in online_cfns:
    if cfn.last_seen < (now - 2 minutes):
        cfn.status = "offline"
```

---

## Testing

### Test Coverage

**Total Tests:** 35 tests, all passing ✅

**Test Categories:**
- CFN Create (5 tests)
- CFN Heartbeat (3 tests)
- CFN List (4 tests)
- CFN Get (3 tests)
- CFN Update (4 tests)
- CFN Disable (3 tests)
- CFN Delete (4 tests)
- CFN Enable/Disable Cycle (8 tests)
- CFN Background Monitoring (1 test)

### Run Tests

```bash
# All CFN tests
poetry run pytest tests/test_cognitive_fabric_node.py -v

# Specific test category
poetry run pytest tests/test_cognitive_fabric_node.py::TestCognitiveFabricNodeCreate -v

# Single test
poetry run pytest tests/test_cognitive_fabric_node.py::TestCognitiveFabricNodeCreate::test_create_cfn_success -v
```

### Example Test Scenarios

```python
# Test 1: Create CFN successfully
cfn_data = {"cfn_id": "cfn-001", "cfn_name": "test-node"}
response = client.post(f"/api/workspaces/{ws_id}/cognitive-fabric-node", json=cfn_data)
assert response.status_code == 201
assert response.json()["status"] == "offline"

# Test 2: Heartbeat changes status to online
response = client.put(f"/api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/heartbeat")
assert response.status_code == 200
assert response.json()["status"] == "online"

# Test 3: Disable prevents heartbeat
client.patch(f"/api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/disable")
response = client.put(f"/api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/heartbeat")
assert response.status_code == 403

# Test 4: Delete allows ID reuse
client.patch(f"/api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/disable")
client.delete(f"/api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001")
response = client.post(f"/api/workspaces/{ws_id}/cognitive-fabric-node", json=cfn_data)
assert response.status_code == 201  # ID reused successfully
```

---

## Key Design Decisions

### 1. Workspace Scoping

CFNs are workspace-scoped resources (not global). Each CFN belongs to exactly one workspace.

**Why?**
- Tenant isolation (critical for compliance)
- Clear resource attribution and billing
- Consistent with other workspace resources

### 2. Create Endpoint for Everything

CFN nodes always call the same `POST /cognitive-fabric-node` endpoint, regardless of state.

**Why?**
- IoT-style: Like IoT devices that don't know their state
- Simple for CFN implementation: one endpoint to remember
- Backend handles all state transitions automatically

### 3. Disable Before Delete

CFNs must be disabled before they can be deleted (two-step process).

**Why?**
- Safety: Prevents accidental deletion
- Clear UI flow: Disable → "Delete" button appears
- Time to reconsider: Grace period before permanent action

### 4. ID Reuse After Delete

Deleted CFN IDs can be reused to create new CFNs.

**Why?**
- Flexibility: Allows redeployment with same identifier
- Clean slate: New CFN has no connection to old CFN
- IoT-style: Physical device can be reconfigured

### 5. Disabled IDs are Locked

Disabled CFN IDs **cannot** be reused (must delete first).

**Why?**
- Safety: Disabled state is temporary, not permanent
- Clear intent: Disable = pause, Delete = remove
- Prevents confusion: No ambiguity about CFN state

---

## Migration Guide

### From Register/Deregister to Create/Delete

If you have existing code using the old naming convention:

**API Endpoints:**
```diff
- POST /cognitive-fabric-node/register
+ POST /cognitive-fabric-node

- DELETE /cognitive-fabric-node/{id}  (called "deregister")
+ DELETE /cognitive-fabric-node/{id}  (called "delete")
```

**RBAC Permissions:**
```diff
- register_cognitive_fabric_node
+ create_cognitive_fabric_node

- deregister_cognitive_fabric_node
+ delete_cognitive_fabric_node
```

**Service Methods:**
```diff
- cognitive_fabric_node_service.register(...)
+ cognitive_fabric_node_service.create(...)

- cognitive_fabric_node_service.deregister(...)
+ cognitive_fabric_node_service.delete(...)
```

---

## Troubleshooting

### CFN Shows as Offline

**Possible Causes:**
1. CFN is not sending heartbeat
2. Heartbeat exceeded 2-minute threshold
3. CFN just created (hasn't sent first heartbeat)

**Solution:**
- Check CFN logs for heartbeat errors
- Verify network connectivity
- Ensure CFN is calling heartbeat endpoint every 30 seconds

### CFN Cannot Send Heartbeat (403 Forbidden)

**Possible Causes:**
1. CFN is disabled
2. CFN is deleted

**Solution:**
- Check CFN status via GET endpoint
- If disabled, admin must enable via PATCH /enable
- If deleted, CFN must create again

### CFN Cannot Reconnect After Reboot (403 Forbidden)

**Possible Causes:**
1. CFN was disabled before reboot

**Solution:**
- Admin must enable CFN via PATCH /enable endpoint
- Then CFN can call create endpoint to reconnect

### CFN ID Cannot Be Reused (403 Forbidden)

**Possible Causes:**
1. CFN is only disabled, not deleted

**Solution:**
- Delete the CFN first: DELETE /cognitive-fabric-node/{id}
- Then create new CFN with same ID

---

## References

- [CLAUDE.md](./CLAUDE.md) - Full project documentation
- [RBAC-IMPLEMENTATION.md](./RBAC-IMPLEMENTATION.md) - RBAC details
- Database Migration: `20260130185900_add_cognitive_fabric_node_table.sql`
- Service Implementation: `src/server/services/cognitive_fabric_node.py`
- API Endpoints: `src/server/api/endpoints/cognitive_fabric_node.py`
- Tests: `tests/test_cognitive_fabric_node.py`

---

**Document Version:** 2.0
**Last Updated:** February 11, 2026
**Breaking Changes:** Renamed "register/deregister" to "create/delete" for clarity
