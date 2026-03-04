#!/bin/bash

# 1. Kontrola, zda je nastavený token
if [ -z "$WEBUI_TOKEN" ]; then
    echo "Chyba: WEBUI_TOKEN není nastaven."
    exit 1
fi

echo "Posílám požadavek na model Qwen3.5 (Open WebUI)..."

# 2. Samotný curl požadavek uložíme do proměnné
RESPONSE=$(curl -s -X POST http://127.0.0.1:3000/api/v1/chat/completions \
  -H "Authorization: Bearer $WEBUI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat/completions.qwen3.5",
    "messages": [
      {
        "role": "system",
        "content": "Jsi BI inženýr expert na Apache Superset. Tvým úkolem je navrhnout postup pro vytvoření dashboardu z existujícího datasetu. Odpovídej POUZE platným polem ve formátu JSON. Žádný text okolo. K dispozici máš tyto funkce: superset_create_chart(server_id, slice_name, viz_type, datasource_id, datasource_type, params), superset_generate_robust_dashboard_layout(server_id, chart_ids), superset_create_dashboard(server_id, dashboard_title, position_json), superset_bulk_link_charts_to_dashboard(server_id, dashboard_id, chart_ids)."
      },
      {
        "role": "user",
        "content": "Na serveru \"superset_main\" už máme existující dataset z tabulky \"orders\" (předpokládejme datasource_id: 10, datasource_type: \"table\"). Vytvoř 2 grafy (jednu tabulku a jeden koláčový graf). Následně vygeneruj layout, vytvoř dashboard s názvem \"Daily Sales Status\" a grafy do něj propoj."
      }
    ],
    "stream": false
  }')

# 3. Zpracování a výpis odpovědi
# Zkontrolujeme, zda se dotaz vůbec povedl (jestli neobsahuje dřívější error)
if echo "$RESPONSE" | grep -q '"error"'; then
    echo -e "\nServer vrátil chybu:"
    echo "$RESPONSE"
    exit 1
fi

echo -e "\nÚspěch! Zde je plán akcí navržený modelem:\n"

# Zkusíme použít jq pro hezké naformátování textu, který model vrátil
if command -v jq &> /dev/null; then
    # Vytáhneme pouze samotný obsah (content) odpovědi
    echo "$RESPONSE" | jq -r '.choices[0].message.content'
else
    echo "(Doporučuji nainstalovat 'jq' pomocí 'sudo apt install jq' pro lepší čitelnost)"
    echo "$RESPONSE" | grep -o '"content":"[^"]*"' | sed 's/"content":"//' | sed 's/"$//'
fi