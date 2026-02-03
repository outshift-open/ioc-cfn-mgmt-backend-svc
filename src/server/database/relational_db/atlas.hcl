// Atlas configuration for SQLAlchemy models

data "external_schema" "sqlalchemy" {
    program = [
        "poetry", "run", "atlas-provider-sqlalchemy",
        "--path", "./models",
        "--dialect", "postgresql"
    ]
}

locals {
  postgres_user = getenv("POSTGRES_USER") != "" ? getenv("POSTGRES_USER") : "postgresUser"
  postgres_password = getenv("POSTGRES_PASSWORD") != "" ? getenv("POSTGRES_PASSWORD") : "postgresPW"
  postgres_host = getenv("POSTGRES_HOST") != "" ? getenv("POSTGRES_HOST") : "localhost"
  postgres_port = getenv("POSTGRES_PORT") != "" ? getenv("POSTGRES_PORT") : "5432"
  postgres_db = getenv("POSTGRES_DB") != "" ? getenv("POSTGRES_DB") : "tkf"
}

env "local" {
  src = data.external_schema.sqlalchemy.url
  # Database connection using environment variables with defaults
  url = "postgresql://${local.postgres_user}:${local.postgres_password}@${local.postgres_host}:${local.postgres_port}/${local.postgres_db}?sslmode=disable"
  # Dev database for schema diffing
  dev = "docker://postgres/17/dev?search_path=public"
  migration {
    dir = "file://migrations"
  }
  format {
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }
}

// Lint configuration
lint {
  // Enable destructive change detection
  destructive {
    error = true
  }
  
  // Data dependent changes
  data_depend {
    error = true
  }
  
  // Naming conventions
  naming {
    error   = true
    match   = "^[a-z]+(_[a-z]+)*$"
    message = "must be in snake_case"
  }
}
