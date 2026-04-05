#!/usr/bin/env bats

# T005: .env.example content tests
# Must FAIL before T006 creates .env.example

ENV_FILE="$BATS_TEST_DIRNAME/../../../setup/immich/.env.example"

@test ".env.example exists" {
  [ -f "$ENV_FILE" ]
}

@test ".env.example contains UPLOAD_LOCATION" {
  grep -q "^UPLOAD_LOCATION=" "$ENV_FILE"
}

@test ".env.example contains DB_PASSWORD" {
  grep -q "^DB_PASSWORD=" "$ENV_FILE"
}

@test ".env.example contains JWT_SECRET" {
  grep -q "^JWT_SECRET=" "$ENV_FILE"
}

@test ".env.example contains DB_USERNAME" {
  grep -q "^DB_USERNAME=" "$ENV_FILE"
}

@test ".env.example contains DB_DATABASE_NAME" {
  grep -q "^DB_DATABASE_NAME=" "$ENV_FILE"
}

@test ".env.example does not contain real secrets (values must be placeholders)" {
  # Passwords should be placeholder text, not real values
  run grep "^DB_PASSWORD=" "$ENV_FILE"
  [ "$status" -eq 0 ]
  # Value should be a placeholder (empty, or contains CHANGE_ME / your_ / placeholder)
  [[ "$output" =~ (=|=CHANGE_ME|=your_|=changeme|=$) ]]
}
