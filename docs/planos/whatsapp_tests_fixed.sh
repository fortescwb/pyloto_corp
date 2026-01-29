#!/bin/bash

# Carregar credenciais do arquivo .env.clean
ENV_FILE="/home/fortes/Repositórios/pyloto_corp/.env.clean"

# Extrair variáveis
WHATSAPP_PHONE_NUMBER_ID=$(grep "^WHATSAPP_PHONE_NUMBER_ID=" "$ENV_FILE" | cut -d'=' -f2)
WHATSAPP_ACCESS_TOKEN=$(grep "^WHATSAPP_ACCESS_TOKEN=" "$ENV_FILE" | cut -d'=' -f2)

# Validar credenciais
if [[ -z "$WHATSAPP_PHONE_NUMBER_ID" || -z "$WHATSAPP_ACCESS_TOKEN" ]]; then
  echo "❌ Erro: Credenciais não encontradas em $ENV_FILE"
  echo "WHATSAPP_PHONE_NUMBER_ID: $WHATSAPP_PHONE_NUMBER_ID"
  echo "WHATSAPP_ACCESS_TOKEN: ${WHATSAPP_ACCESS_TOKEN:0:20}..."
  exit 1
fi

# Configuração
API_VERSION="v24.0"
RECIPIENT="+5541988991078"
BASE_URL="https://graph.facebook.com/${API_VERSION}/${WHATSAPP_PHONE_NUMBER_ID}/messages"
LOG_FILE="/tmp/whatsapp_tests_results_fixed.log"

echo "Credenciais carregadas com sucesso:" >&2
echo "  Phone ID: $WHATSAPP_PHONE_NUMBER_ID" >&2
echo "  Token: ${WHATSAPP_ACCESS_TOKEN:0:20}..." >&2
echo "  Endpoint: $BASE_URL" >&2
echo "" >&2

# Limpar log anterior
> "$LOG_FILE"

echo "============================================" | tee -a "$LOG_FILE"
echo "Testes de Envio WhatsApp API v24.0 (CORRIGIDO)" | tee -a "$LOG_FILE"
echo "Recipient: $RECIPIENT" | tee -a "$LOG_FILE"
echo "Endpoint: $BASE_URL" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Função auxiliar para testar
test_message() {
  local type="$1"
  local payload="$2"
  local description="$3"
  
  echo "[TEST] $type: $description" | tee -a "$LOG_FILE"
  
  response=$(curl -s -X POST "$BASE_URL" \
    -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    -w "\n%{http_code}")
  
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)
  
  if [ "$http_code" = "200" ]; then
    echo "  ✅ Sucesso (HTTP $http_code)" | tee -a "$LOG_FILE"
    message_id=$(echo "$body" | grep -o '"message_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$message_id" ]; then
      echo "  Message ID: $message_id" | tee -a "$LOG_FILE"
    fi
  else
    echo "  ❌ Erro (HTTP $http_code)" | tee -a "$LOG_FILE"
    echo "  Response: $body" | tee -a "$LOG_FILE"
  fi
  echo "" | tee -a "$LOG_FILE"
}

echo "Iniciando testes..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# ==================================================
# 1. TEXT MESSAGE
# ==================================================
test_message "TEXT" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "text",
  "text": {
    "body": "Olá! Teste de mensagem de texto via API WhatsApp v24.0 - pyloto_corp"
  }
}' "Envio de texto simples"

sleep 1

# ==================================================
# 2. IMAGE MESSAGE
# ==================================================
test_message "IMAGE" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "image",
  "image": {
    "link": "https://www.gstatic.com/webp/gallery/1.png"
  }
}' "Envio de imagem via URL"

sleep 1

# ==================================================
# 3. DOCUMENT MESSAGE
# ==================================================
test_message "DOCUMENT" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "document",
  "document": {
    "link": "https://filesamples.com/samples/document/pdf/sample1.pdf",
    "caption": "Documento de teste"
  }
}' "Envio de documento PDF"

sleep 1

# ==================================================
# 4. AUDIO MESSAGE
# ==================================================
test_message "AUDIO" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "audio",
  "audio": {
    "link": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
  }
}' "Envio de áudio MP3"

sleep 1

# ==================================================
# 5. VIDEO MESSAGE
# ==================================================
test_message "VIDEO" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "video",
  "video": {
    "link": "https://www.commondatastorage.googleapis.com/gtv-videos-library/sample/BigBuckBunny.mp4",
    "caption": "Vídeo de teste"
  }
}' "Envio de vídeo MP4"

sleep 1

# ==================================================
# 6. LOCATION MESSAGE
# ==================================================
test_message "LOCATION" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "location",
  "location": {
    "latitude": "-25.4267",
    "longitude": "-49.2733",
    "name": "Curitiba - Pyloto HQ",
    "address": "Rua Exemplo, 123 - Curitiba, PR"
  }
}' "Envio de localização (GPS)"

sleep 1

# ==================================================
# 7. CONTACTS MESSAGE
# ==================================================
test_message "CONTACTS" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "contacts",
  "contacts": [
    {
      "addresses": [
        {
          "city": "Curitiba",
          "country": "Brasil",
          "country_code": "BR",
          "state": "PR",
          "street": "Rua Teste, 123",
          "type": "WORK",
          "zip": "80000-000"
        }
      ],
      "emails": [
        {
          "email": "contato@pyloto.com.br",
          "type": "WORK"
        }
      ],
      "name": {
        "first_name": "Pyloto",
        "last_name": "Teste",
        "formatted_name": "Pyloto Teste"
      },
      "org": {
        "company": "Pyloto Soluções"
      },
      "phones": [
        {
          "phone": "+5541988991078",
          "type": "WORK"
        }
      ]
    }
  ]
}' "Envio de contato vCard"

sleep 1

# ==================================================
# 8. INTERACTIVE MESSAGE (Buttons)
# ==================================================
test_message "INTERACTIVE_BUTTONS" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {
      "text": "Qual é sua escolha?"
    },
    "footer": {
      "text": "Pyloto - Teste de Botões"
    },
    "action": {
      "buttons": [
        {
          "type": "reply",
          "reply": {
            "id": "btn_1",
            "title": "Opção 1"
          }
        },
        {
          "type": "reply",
          "reply": {
            "id": "btn_2",
            "title": "Opção 2"
          }
        }
      ]
    }
  }
}' "Envio de botões interativos"

sleep 1

# ==================================================
# 9. INTERACTIVE MESSAGE (List)
# ==================================================
test_message "INTERACTIVE_LIST" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "interactive",
  "interactive": {
    "type": "list",
    "body": {
      "text": "Selecione uma opção da lista"
    },
    "footer": {
      "text": "Pyloto - Menu de Opções"
    },
    "action": {
      "button": "Ver Opções",
      "sections": [
        {
          "title": "Seção 1",
          "rows": [
            {
              "id": "row_1",
              "title": "Item 1",
              "description": "Descrição do item 1"
            },
            {
              "id": "row_2",
              "title": "Item 2",
              "description": "Descrição do item 2"
            }
          ]
        }
      ]
    }
  }
}' "Envio de menu com lista"

sleep 1

# ==================================================
# 10. TEMPLATE MESSAGE
# ==================================================
test_message "TEMPLATE" '{
  "messaging_product": "whatsapp",
  "to": "'$RECIPIENT'",
  "type": "template",
  "template": {
    "name": "hello_world",
    "language": {
      "code": "en_US"
    }
  }
}' "Envio de template pré-aprovado (hello_world)"

sleep 1

# ==================================================
# 11. REACTION MESSAGE (requer message_id válido)
# ==================================================
test_message "REACTION" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "reaction",
  "reaction": {
    "message_id": "wamid.test123456",
    "emoji": "👍"
  }
}' "Envio de reação emoji"

sleep 1

# ==================================================
# 12. STICKER (se houver suporte via URL)
# ==================================================
test_message "STICKER" '{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "'$RECIPIENT'",
  "type": "sticker",
  "sticker": {
    "link": "https://www.gstatic.com/webp/gallery/1.webp"
  }
}' "Envio de adesivo WEBP"

echo "" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "Testes Finalizados em: $(date)" | tee -a "$LOG_FILE"
echo "Log salvo em: $LOG_FILE" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"

