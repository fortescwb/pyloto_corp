#!/usr/bin/env python
"""Script de diagnóstico do fluxo inbound.

Testa:
1. Extração de mensagens do webhook payload
2. Processamento via AIOrchestrator
3. Construção do outbound_job
4. Validação de recipient formatação

Uso:
    python scripts/test_inbound_flow.py
"""

import json
import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.ai.orchestrator import AIOrchestrator


def test_extract_messages():
    """Testa extração de mensagens do payload."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "test_msg_123",
                                    "from": "5511999999999",
                                    "text": {"body": "oi"},
                                    "timestamp": "1738272000",
                                    "type": "text",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_messages(payload)
    print(f"✅ Mensagens extraídas: {len(messages)}")
    
    if not messages:
        print("❌ ERRO: Nenhuma mensagem extraída do payload")
        return None
    
    msg = messages[0]
    print(f"  - ID: {msg.message_id}")
    print(f"  - From: {msg.from_number}")
    print(f"  - Text: {msg.text}")
    
    return msg


def test_orchestrator(msg):
    """Testa processamento via orquestrador."""
    print("\n🤖 Testando AIOrchestrator...")
    orchestrator = AIOrchestrator()
    
    response = orchestrator.process_message(message=msg)
    
    print(f"  - Intent: {response.intent}")
    print(f"  - Outcome: {response.outcome}")
    print(f"  - Confidence: {response.confidence}")
    print(f"  - Reply: {response.reply_text}")
    
    if not response.reply_text:
        print("⚠️  ATENÇÃO: Orquestrador não gerou reply_text")
        return None
    
    print("✅ Orquestrador gerou resposta")
    return response


def test_outbound_job_construction(msg, response):
    """Testa construção do outbound_job."""
    print("\n📤 Testando construção do outbound_job...")
    
    recipient = msg.from_number
    if recipient and not recipient.startswith("+"):
        recipient = f"+{recipient}"
    
    outbound_job = {
        "to": recipient,
        "message_type": "text",
        "text": response.reply_text,
        "idempotency_key": msg.message_id,
        "correlation_id": "test_correlation_123",
        "inbound_event_id": "test_event_456",
    }
    
    print(f"  - To: {outbound_job['to']}")
    print(f"  - Message type: {outbound_job['message_type']}")
    print(f"  - Text: {outbound_job['text'][:50]}...")
    print(f"  - Idempotency key: {outbound_job['idempotency_key']}")
    
    # Validações
    issues = []
    if not outbound_job["to"]:
        issues.append("❌ Campo 'to' está vazio")
    if not outbound_job["to"].startswith("+"):
        issues.append(f"⚠️  Número não tem '+': {outbound_job['to']}")
    if not outbound_job["text"]:
        issues.append("❌ Campo 'text' está vazio")
    if not outbound_job["idempotency_key"]:
        issues.append("❌ Campo 'idempotency_key' está vazio")
    
    if issues:
        print("\n⚠️  PROBLEMAS DETECTADOS:")
        for issue in issues:
            print(f"  {issue}")
        return None
    
    print("✅ outbound_job construído corretamente")
    return outbound_job


def main():
    """Executa bateria de testes diagnósticos."""
    print("🔍 DIAGNÓSTICO DO FLUXO INBOUND\n")
    print("=" * 60)
    
    # Teste 1: Extração de mensagens
    print("\n1️⃣  Testando extração de mensagens...")
    msg = test_extract_messages()
    if not msg:
        print("\n❌ FALHA CRÍTICA: Não foi possível extrair mensagens")
        return 1
    
    # Teste 2: Orquestrador
    print("\n2️⃣  Testando orquestrador LLM...")
    response = test_orchestrator(msg)
    if not response:
        print("\n❌ FALHA CRÍTICA: Orquestrador não gerou resposta")
        return 1
    
    # Teste 3: Construção outbound_job
    print("\n3️⃣  Testando construção de outbound_job...")
    outbound_job = test_outbound_job_construction(msg, response)
    if not outbound_job:
        print("\n❌ FALHA CRÍTICA: outbound_job inválido")
        return 1
    
    # Resultado final
    print("\n" + "=" * 60)
    print("\n✅ TODOS OS TESTES PASSARAM")
    print("\n📋 Payload final que seria enfileirado:")
    print(json.dumps(outbound_job, indent=2, ensure_ascii=False))
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
