# Produto — pyloto_corp

## 1. Visão do Produto

O **pyloto_corp** é o serviço responsável pelo **atendimento inicial institucional e comercial da Pyloto**, operando prioritariamente via **WhatsApp (API oficial da Meta)**.

Ele atua como **porta de entrada do ecossistema Pyloto**, realizando:

* identificação de intenção do cliente
* explicação clara das vertentes da Pyloto
* coleta estruturada de informações
* qualificação de leads
* roteamento correto do atendimento (humano, informativo ou externo)

Este repositório **não executa operação final**, **não fecha contratos** e **não gerencia pedidos operacionais**. Seu papel é **organizar o primeiro contato**, realizar **cadastros iniciais de lojistas e entregadores** e entregar **contexto pronto para ação**.

---

## 2. Objetivos Primários

1. Garantir que **todo cliente chegue ao destino correto**
2. Evitar perda de informação no handoff para humanos
3. Reduzir ruído, retrabalho e perguntas repetidas
4. Manter experiência natural, sem conversa solta
5. Operar de forma auditável, escalável e previsível

---

## 3. Outcomes Canônicos de Conversa

Para garantir previsibilidade operacional, **toda sessão deve encerrar com um único outcome terminal**.

Um cliente pode ter **múltiplas intenções**, mas a sessão possui **um destino final único**.

### 3.1 Outcomes terminais (encerramento da sessão)

Toda conversa deve terminar em **exatamente um** dos estados abaixo:

* **HANDOFF_HUMAN** — lead qualificado, pronto para continuidade humana

* **SELF_SERVE_INFO** — cliente atendido apenas com informação

* **ROUTE_EXTERNAL** — cliente encaminhado para outro canal/WhatsApp

  * após este estado, a sessão é encerrada
  * novas intenções não são aceitas
  * novo contato somente após **timeout de 30 minutos**

* **SCHEDULED_FOLLOWUP** — atendimento encerrado com follow-up agendado

* **AWAITING_USER** — atendimento pausado aguardando resposta

  * timeout padrão: **2 horas** (24/7)
  * com coleta parcial → `SCHEDULED_FOLLOWUP`
  * sem coleta → `SELF_SERVE_INFO`
  * evento de abandono registrado

* **DUPLICATE_OR_SPAM** — conversa descartada por duplicidade, flood ou spam

  * duplicate: dedupe_key/message_id já processado
  * flood: mais de N mensagens em M segundos
  * spam: baixa confiança + ausência de resposta às perguntas

* **UNSUPPORTED** — fora de escopo ou inválido

* **FAILED_INTERNAL** — falha interna ou de integração

  * cliente recebe mensagem neutra
  * sessão é encerrada
  * evento gera alerta interno
  * retry não ocorre automaticamente

> Sessões sem outcome terminal definido são consideradas falha de produto.

---

### 3.2 Multi-intent (múltiplas demandas na mesma sessão)

O sistema **não resolve múltiplas intenções em paralelo**.

* máximo de **3 intenções por sessão**
* ao atingir o limite:

  * padrão: `SCHEDULED_FOLLOWUP`
  * exceção: se lead comercial completo → `HANDOFF_HUMAN`

#### Regras estruturais

* apenas uma intenção ativa por vez (`active_intent`)
* demais intenções entram em **fila leve**
* contexto detalhado existe somente para a intenção ativa

#### Critério de escolha da `active_intent`

1. Intenção explicitamente escolhida pelo usuário
2. Intenção operacional imediata (ex.: entrega agora)
3. Intenção com maior impacto comercial
4. Em empate, a primeira intenção citada

---

### 3.3 Contenção de contexto (anti-token-bloat)

* intenções não ativas armazenam apenas:

  * `intent_type`
  * `timestamp`
  * `confidence`
* nenhuma coleta profunda fora da intenção ativa
* ao concluir uma intenção, o agente pergunta se deseja continuar

Ao avançar:

* a próxima intenção vira ativa
* o contexto anterior é **resumido e congelado**

---

### 3.4 Definição de Sessão e Ciclo de Vida

**Sessão de atendimento** é o intervalo lógico contínuo de interação entre um usuário e o sistema, iniciado com a primeira mensagem válida e encerrado por um *outcome terminal*.

#### Regras da sessão

* cada sessão possui **exatamente um outcome terminal**
* uma sessão pode conter múltiplas intenções (respeitando limites)
* a sessão é encerrada quando:

  * um outcome terminal é emitido, **ou**
  * ocorre timeout definido pelo fluxo

#### Início de nova sessão

Uma nova sessão é iniciada quando:

* o usuário envia nova mensagem **após encerramento da sessão anterior**, ou
* após timeout explícito do fluxo (ex.: `ROUTE_EXTERNAL` → 30 minutos)

Sessões são **independentes entre si**. Contexto não deve vazar entre sessões, exceto dados persistidos (LeadProfile e resumos históricos).

---

## 4. Vertentes da Pyloto

1. **Sistemas sob medida**
2. **SaaS – O Pyloto da sua Comunicação**
3. **Pyloto Entrega**
4. **Institucional**

---

## 5. Fluxo Base de Entrada

### ENTRY_UNKNOWN

Usado quando a intenção inicial é vaga.

Comportamento obrigatório:

* explicação curta da Pyloto
* apresentação das vertentes
* solicitação explícita de escolha

---

## 6. Fluxo — Sistemas sob Medida

### Coleta mínima obrigatória

* tipo de cliente
* problema atual
* funcionalidades desejadas
* número de usuários
* cidade/estado
* prazo esperado
* orçamento (opcional)

  * se recusado → `unknown`
  * não insistir

Resultado:

* resumo estruturado
* `HANDOFF_HUMAN`

---

## 7. Fluxo — SaaS Pyloto

### Coleta mínima

* tipo de negócio
* canais utilizados
* volume de atendimentos
* principal dor
* objetivo com automação
* orçamento mensal (opcional)

  * se recusado → `unknown`

Resultado:

* `HANDOFF_HUMAN`

---

## 8. Fluxo — Pyloto Entrega

### DELIVERY_ROUTER

1. Solicitar entrega agora
2. Cadastro de entregador
3. Cadastro de lojista

### 8.1 Solicitação de entrega

* não atendida neste sistema
* outcome: `ROUTE_EXTERNAL`

### 8.2 Cadastro de entregador

* nome
* cidade
* veículo
* disponibilidade

Outcome: `HANDOFF_HUMAN`

### 8.3 Cadastro de lojista

* empresa
* cidade
* segmento
* volume de entregas

Outcome: `HANDOFF_HUMAN`

---

## 9. Contrato de Handoff para CRM

### LeadProfile

* name
* phone
* city
* is_business
* business_name
* role

### ConversationHandoff

* intent_primary
* intents_detected[]
* resolved_intents[]
* open_intents[]
* summary
* requirements
* deadline
* routing
* confidence
* qualification_level (`low|medium|high`)
* qualification_reasons[]

Regras de qualificação:

### Definição de coleta completa (campos críticos por fluxo)

#### Sistemas sob Medida — campos críticos

* problema atual claramente descrito
* funcionalidades desejadas
* número estimado de usuários
* cidade/estado
* prazo esperado

#### SaaS – Pyloto da sua Comunicação — campos críticos

* tipo de negócio
* canais utilizados
* volume médio de atendimentos
* principal dor
* objetivo com automação

> Orçamento é opcional e **não bloqueia** qualificação alta.

### Classificação

* **high**: intenção comercial + coleta completa + urgência ou decisor
* **medium**: intenção comercial + coleta parcial (até 1 campo crítico ausente)
* **low**: informativo ou coleta insuficiente (2+ campos críticos ausentes)

### Campo `confidence`

`confidence` representa a **confiança do sistema na classificação da intenção primária**, variando de **0.0 a 1.0**.

* deriva de classificador (LLM/regras)
* usada apenas para priorização interna e desempate
* **não** representa interesse comercial
* **não** deve ser exposta ao cliente

---

## 10. Qualidade e Segurança

* batch-safe
* idempotência
* logs estruturados
* sem PII em logs
* segredos fora do repositório
* fixtures sanitizadas

---

## 11. Critério de Sucesso

* 100% das sessões com outcome válido
* handoff humano sem retrabalho
* nenhum cliente sem destino
* execução isolada e previsível

---

## 12. Status

Documento de produto final

---

## 13. Sobre Detalhes de Versão da Graph API

A URL base da API da Meta (Graph API) mais atual em
janeiro de 2026 é:
`https://graph.facebook.com`

Para o envio de mensagens via WhatsApp Cloud API, a estrutura do endpoint utiliza o ID do seu número de telefone da seguinte forma:

`https://graph.facebook.com{phone-number-id}/messages`

Detalhes Importantes:

    Versão Atual: A versão v24.0 foi lançada em 8 de outubro de 2025 e é a versão estável mais recente disponível no início de 2026.
    Protocolo: Todas as chamadas devem ser feitas obrigatoriamente via HTTPS.

Exceção de Vídeos: Para uploads de arquivos de vídeo, a URL base muda ligeiramente para `https://graph-video.facebook.com`.

---

## 14. Legado planejado — `src/pyloto_corp/ai/orchestrator.py`

* Status: LEGACY — Planned removal in v2.0
* Motivo: depende de fallback determinístico enquanto estabilidade de LLM não atinge threshold
* Plano de remoção (checklist):
  1. Confirmar que `application/orchestration_*` substitui todas as chamadas deste arquivo
  2. Validar que métricas de estabilidade de LLM permanecem >= threshold por período sustentado
  3. Manter fallback determinístico ativo até a remoção
  4. Remover imports/uso do arquivo, apagar testes relacionados e atualizar documentação
  5. Registrar a remoção em changelog/auditoria

---
