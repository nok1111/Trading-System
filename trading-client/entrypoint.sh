#!/bin/bash
set -e

# Validate that AUTH_SERVER_URL is configured
if [ -z "$AUTH_SERVER_URL" ]; then
  echo "ERROR: AUTH_SERVER_URL no configurado. Edita tu archivo .env"
  exit 1
fi

# Check Auth Server is reachable
echo "Validating connection to Auth Server at $AUTH_SERVER_URL..."
for i in $(seq 1 5); do
  if curl -s -o /dev/null -w "%{http_code}" "$AUTH_SERVER_URL/health" | grep -q "200"; then
    echo "Auth Server is reachable."
    break
  fi
  echo "Attempt $i: Auth Server not reachable, retrying in 3s..."
  sleep 3
  if [ $i -eq 5 ]; then
    echo "WARNING: Auth Server not reachable at $AUTH_SERVER_URL"
    echo "The Trading Client will start but API calls will be blocked until the Auth Server is available."
  fi
done

# Start the server
exec uvicorn app.api.app:app --host 0.0.0.0 --port 8080
