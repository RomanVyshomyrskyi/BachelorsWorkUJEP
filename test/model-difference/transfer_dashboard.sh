#!/bin/bash

# Ujistěte se, že proměnná WEBUI_TOKEN je nastavena
if [ -z "$WEBUI_TOKEN" ]; then
    echo "Chyba: WEBUI_TOKEN není nastaven."
    exit 1
fi

curl -s -X POST http://127.0.0.1:3000/api/v1/chat/completions \
  -H "Authorization: Bearer $WEBUI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat/completions.qwen3.5",
    "messages": [
      {
        "role": "system",
        "content": "Jsi expert na administraci Apache Superset. Tvým úkolem je migrovat dashboardy mezi servery. Odpovídej POUZE ve formátu JSON, abys spustil funkci. Použij tento formát: {\"function_name\": \"transfer_dashboard\", \"parameters\": {\"source_server_id\": \"...\", \"target_server_id\": \"...\", \"dashboard_id\": 15}}"
      },
      {
        "role": "user",
        "content": "Přenese dashboard s ID 15 ze serveru '\''superset_main'\'' na server '\''superset_backup'\''. Nejdříve si ale vypiš dostupné servery pomocí funkce list_superset_servers."
      }
    ],
    "stream": false
  }'