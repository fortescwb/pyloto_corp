# Schema do Firestore — pyloto_corp

Este documento define o schema das collections do Firestore utilizadas pelo `pyloto_corp`.

## Referências

- [Funcionamento.md](../../Funcionamento.md) — Especificações do produto
- [regras_e_padroes.md](../../regras_e_padroes.md) — Padrões de código e segurança
- [TODO_01_INFRAESTRUTURA_E_SERVICOS.md](../../TODO_01_INFRAESTRUTURA_E_SERVICOS.md) — Tarefas de infraestrutura

---

## Collections

### 1. `conversations`

Armazena sessões de conversa com usuários.

```
/conversations/{conversation_id}
├── user_id: str                    # ID derivado (HMAC do phone, não expõe PII)
├── phone_hash: str                 # Hash do telefone (para lookup)
├── status: str                     # ACTIVE | CLOSED | AWAITING_USER
├── outcome: str | null             # Outcome terminal (quando encerrada)
├── active_intent: str | null       # Intent ativa atual
├── intents_detected: list[str]     # Intenções detectadas na sessão
├── created_at: timestamp           # Criação da sessão
├── updated_at: timestamp           # Última atualização
├── closed_at: timestamp | null     # Quando foi encerrada
├── timeout_at: timestamp | null    # Quando expira (AWAITING_USER)
├── metadata: map                   # Dados adicionais estruturados
│   ├── source: str                 # Canal de origem (whatsapp)
│   ├── correlation_id: str         # ID de correlação
│   └── ...
└── messages/                       # Subcollection de mensagens
    └── {message_id}
        ├── timestamp: timestamp
        ├── direction: str          # INBOUND | OUTBOUND
        ├── type: str               # text | image | interactive | etc
        ├── content_hash: str       # Hash do conteúdo (dedupe)
        ├── outcome: str | null     # Outcome associado à mensagem
        └── metadata: map           # Dados específicos do tipo
```

**Índices necessários:**

- `user_id` + `status` (filtro de conversas ativas por usuário)
- `created_at` DESC (ordenação cronológica)
- `status` + `timeout_at` (limpeza de sessões expiradas)

---

### 2. `user_profiles`

Armazena perfis de usuários (leads).

```
/user_profiles/{user_id}
├── phone_hash: str                 # Hash do telefone (para lookup)
├── name: str | null                # Nome do usuário (quando fornecido)
├── city: str | null                # Cidade
├── is_business: bool               # Se é pessoa jurídica
├── business_name: str | null       # Nome da empresa
├── role: str | null                # Cargo/função
├── created_at: timestamp           # Primeira interação
├── updated_at: timestamp           # Última atualização
├── last_interaction_at: timestamp  # Última mensagem
├── qualification_level: str        # low | medium | high
├── total_conversations: int        # Contador de sessões
├── metadata: map                   # Dados adicionais
│   ├── source: str                 # Canal de origem
│   ├── tags: list[str]             # Tags de segmentação
│   └── ...
└── history/                        # Subcollection de histórico (opcional)
    └── {update_id}
        ├── timestamp: timestamp
        ├── field: str
        ├── old_value: any
        └── new_value: any
```

**Índices necessários:**

- `phone_hash` (lookup por telefone)
- `qualification_level` + `last_interaction_at` (segmentação)

---

### 3. `audit_logs`

Trilha de auditoria encadeada com hash.

```
/audit_logs/{log_id}
├── timestamp: timestamp            # Momento do evento
├── event_type: str                 # MESSAGE_RECEIVED | OUTCOME_ASSIGNED | etc
├── actor: str                      # SYSTEM | USER | AGENT
├── conversation_id: str | null     # Referência à conversa
├── user_id: str | null             # Referência ao usuário
├── correlation_id: str             # ID de correlação
├── prev_hash: str                  # Hash do log anterior (encadeamento)
├── data_hash: str                  # Hash dos dados deste evento
├── data: map                       # Dados do evento (sem PII)
│   ├── outcome: str | null
│   ├── intent: str | null
│   ├── action: str | null
│   └── ...
└── signature: str | null           # Assinatura externa (opcional)
```

**Regras de encadeamento:**

1. Cada log tem `prev_hash` = hash do log anterior
2. `data_hash` = SHA256(JSON serializado de `data`)
3. Primeiro log da cadeia tem `prev_hash` = "GENESIS"
4. Concurrency control via expected `prev_hash`

**Índices necessários:**

- `conversation_id` + `timestamp` (trilha por conversa)
- `event_type` + `timestamp` (filtro por tipo)

---

### 4. `templates`

Metadados de templates WhatsApp sincronizados da Meta.

```
/templates/{template_id}
├── namespace: str                  # Namespace do Meta
├── name: str                       # Nome do template
├── language: str                   # Código do idioma (pt_BR, en, etc)
├── status: str                     # APPROVED | PENDING | REJECTED
├── category: str                   # MARKETING | UTILITY | AUTHENTICATION
├── components: list[map]           # Componentes do template
│   ├── type: str                   # HEADER | BODY | FOOTER | BUTTONS
│   ├── format: str | null          # TEXT | IMAGE | VIDEO | etc
│   ├── text: str | null            # Texto com {{1}} placeholders
│   └── ...
├── synced_at: timestamp            # Última sincronização com Meta
├── created_at: timestamp           # Criação no Firestore
├── updated_at: timestamp           # Última atualização
└── metadata: map                   # Dados adicionais
    ├── example_values: list[str]   # Valores de exemplo
    └── ...
```

**Índices necessários:**

- `namespace` + `name` + `language` (lookup)
- `status` (filtro de templates aprovados)

---

### 5. `exports`

Metadados de exportações de histórico.

```
/exports/{export_id}
├── requested_by: str               # ID do solicitante
├── conversation_id: str | null     # Conversa específica (ou null = todas)
├── user_id: str | null             # Usuário específico (ou null = todos)
├── format: str                     # JSON | PDF | HTML
├── include_pii: bool               # Se inclui PII
├── status: str                     # PENDING | PROCESSING | COMPLETED | FAILED
├── gcs_path: str | null            # Caminho no GCS
├── signed_url: str | null          # URL assinada para download
├── signed_url_expires_at: timestamp | null
├── created_at: timestamp           # Solicitação
├── completed_at: timestamp | null  # Conclusão
├── error_message: str | null       # Erro (se FAILED)
└── metadata: map                   # Dados adicionais
    ├── total_messages: int
    ├── date_range: map
    └── ...
```

**Índices necessários:**

- `requested_by` + `created_at` (histórico do solicitante)
- `status` (processamento de fila)

---

## Políticas de Segurança

### Regras de Acesso

```firestore-rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Todas as collections exigem autenticação via service account
    match /{document=**} {
      allow read, write: if false;  // Acesso apenas via Admin SDK
    }
  }
}
```

### PII e Masking

- **Nunca armazenar** telefone em plaintext
- **Sempre usar** `user_id` derivado (HMAC)
- **phone_hash** é para lookup, não exposição
- **Logs de auditoria** não contêm PII

---

## Configuração de Índices

Os índices compostos devem ser criados via console ou CLI:

```bash
# Índice para conversas ativas por usuário
gcloud firestore indexes composite create \
  --collection-group=conversations \
  --field-config=field-path=user_id,order=ASCENDING \
  --field-config=field-path=status,order=ASCENDING \
  --field-config=field-path=created_at,order=DESCENDING

# Índice para trilha de auditoria
gcloud firestore indexes composite create \
  --collection-group=audit_logs \
  --field-config=field-path=conversation_id,order=ASCENDING \
  --field-config=field-path=timestamp,order=DESCENDING
```

---

## Retenção e Cleanup

| Collection      | Retenção       | Política                    |
| --------------- | -------------- | --------------------------- |
| conversations   | 365 dias       | Arquivar após 90 dias       |
| user_profiles   | Indefinido     | LGPD: excluir sob demanda   |
| audit_logs      | 7 anos         | Imutável após criação       |
| templates       | Indefinido     | Sincronizar com Meta        |
| exports         | 30 dias        | Cleanup automático          |

---

## Migração e Versionamento

- Schema versão: **1.0.0**
- Data de criação: Janeiro 2026
- Última atualização: Janeiro 2026

Para migrações futuras, criar scripts em `scripts/migrations/`.
