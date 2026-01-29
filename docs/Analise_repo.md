Análise do repositório pyloto_corp
Visão geral do repositório
O projeto pyloto_corp fornece um serviço de atendimento inicial via WhatsApp (Graph API) que qualifica leads e interage com o usuário, mas não é um CRM. O sistema é escrito em Python 3, utiliza FastAPI, armazenamento em Firestore/Redis, exporta conversas para Google Cloud Storage (GCS) e implementa deduplicação, persistência de sessão, detecção de spam/flood e logs estruturados. O documento Monitoramento_Regras‑Padroes.md resume que todas as tarefas planejadas até janeiro de 2026 foram concluídas, sem registros de violações críticas ou alertas pendentes[1][2].
O repositório segue padrões de qualidade rígidos (máximo de 200 linhas por arquivo em geral, funções com no máximo 50 linhas, injeção de dependência e ausência de PII nos logs). Algumas poucas classes ultrapassam 200 linhas, mas estão marcadas apenas como Atenção no monitoramento e não são considerados problemas críticos[3].
A arquitetura é composta por camadas bem definidas (domínio, aplicação, adaptadores e infraestrutura) e inclui testes unitários/integration para cada módulo, com cobertura >90 %. O pipeline inbound processa mensagens de webhook, aplica deduplicação, gerencia sessões, detecta abusos, invoca classificadores de intenção e outcome (AI Orchestrator), aciona LLMs para escolher o próximo estado e gerar opções de resposta e, por fim, decide a resposta final e a envia[4][5]. Esse fluxo implementa o comportamento descrito pelo usuário: receber mensagens da Graph API, criar histórico auditável, identificar o estado inicial, consultar LLMs de estado, de resposta e um decider final, atualizar estado e enviar a resposta via WhatsApp.
Principais módulos e funcionalidades
Camada/Módulo	Responsabilidades	Observações
adapters/whatsapp/normalizer.py	Extrai e normaliza conteúdos do payload do webhook (texto, mídia, localização, endereço, contatos, mensagens interativas, reações). Constrói objeto NormalizedWhatsAppMessage sem PII[6][7].	Arquivo ~287 linhas (⚠️ atenção), mas necessário para extrair mensagens.
infra/dedupe.py	Define protocolos de deduplicação (DedupeStore), implementações em memória e Redis e factory create_dedupe_store. Garante idempotência de mensagens inbound[8].	~352 linhas, mas cada função <50 linhas.
infra/secrets.py	Implementa providers para ler segredos via variáveis de ambiente ou Secret Manager da Google, com fail‑closed e logging seguro[9][10].	~268 linhas, usado pela configuração e por derivação de user_key.
domain/whatsapp_message_types.py	Define modelos Pydantic para todos os tipos de mensagem suportados (texto, imagem, vídeo, áudio, documento, sticker, localização, contatos, interativos, reações)[11][12].	~239 linhas; centraliza tipos permitidos pela Graph API.
application/pipeline.py (WhatsAppInboundPipeline)	Orquestra o fluxo inbound: deduplicação, recuperação/criação de sessão, detecção de flood/spam, chamada ao AI Orchestrator (intenção/outcome), chamada ao LLM de seleção de estado, ao LLM de geração de respostas e ao LLM decider final. Atualiza e persiste a sessão, registra auditoria e monta o resultado[4][5].	É a peça central do sistema.
ai/orchestrator.py	Implementa um classificador determinístico de intenção (IntentClassifier) e um decisor de outcome (OutcomeDecider) com regras definidas. O AIOrchestrator combina ambos e gera uma resposta padrão (fallback) dependendo do outcome[13][14].	Foi criado para substituir o “mock” citado na auditoria e fornece fallback deterministic para casos simples.
application/state_selector.py, response_generator.py e master_decider.py	Chamam serviços de LLM via um cliente (não presente no repositório) para escolher o próximo estado, gerar opções de resposta (introduzindo “Otto” na primeira mensagem do dia) e decidir a resposta final, respectivamente. Implementam pré‑validação determinística, controle de timeout e fallback caso a LLM falhe[15][16][17].	São usados pelo pipeline para integrar o comportamento inteligente solicitado pelo usuário.
infra/gcs_exporter.py, application/export.py	Permitem exportar o histórico de conversas para GCS, gerar URLs assinadas e limpar exportações antigas[18]. Não são diretamente usados no fluxo inbound, mas fornecem auditoria/auditoria externa.	
infra/session_store.py	Persistência de SessionState em memória, Redis ou Firestore (armazenando estado atual, fila de intenções e histórico da sessão). Fundamental para suportar centenas de mensagens simultâneas.	
domain/abuse_detection.py	Detecta flood (muitas mensagens em pouco tempo), spam e abuso com heurísticas configuráveis; marca a sessão com outcome DUPLICATE_OR_SPAM quando apropriado.	
O documento de monitoramento também registra que não há arquivos marcados com “alerta” ou “violação crítica”; apenas alguns arquivos grandes permanecem sob atenção por tamanho[2]. A refatoração de módulos como outbound.py e validators já removeu implementações monolíticas antigas e as delegou para subpacotes especializados[19].
Identificação de código legado
Após examinar todo o repositório, não existe uma pasta denominada legacy nem arquivos nomeados como “old” ou “deprecated”. O código foi amplamente refatorado até janeiro de 2026 e atende às regras de qualidade. Entretanto, alguns componentes podem ser considerados “legado” no contexto do novo fluxo com LLMs:
    1. AI Orchestrator e classificadores determinísticos – o IntentClassifier e o OutcomeDecider executam uma classificação de intenção com palavras‑chave e decidem o outcome com regras fixas[13][14]. Embora o pipeline utilize LLMs para selecionar estados e gerar respostas, ele ainda depende do AIOrchestrator para preencher a fila de intenções (session.intent_queue) e definir um outcome inicial antes da intervenção das LLMs[5]. Se esses componentes forem movidos para uma pasta “legacy” e removidos do caminho de importação, o pipeline falhará ao importar AIOrchestrator em application/pipeline.py e não conseguirá classificar a intenção básica. Isso quebraria passos como a detecção de capacidade de intenções e poderia deixar sessões sem outcome definido. Como o repositório não contém uma alternativa LLM para classificação de intenção, esse código não deve ser removido até que a LLM assuma essa responsabilidade.
    2. Fallbacks determinísticos nos módulos de LLM – os módulos state_selector, response_generator e master_decider implementam fallback determinístico quando a LLM falha ou não atinge um limiar de confiança. Esses trechos de código não são “legado”; eles garantem robustez e devem permanecer. Movê‑los para legacy eliminaria a proteção contra falhas de LLMs, fazendo com que o sistema não respondesse em caso de erro.
    3. Módulos grandes marcados como atenção – domain/whatsapp_message_types.py, infra/secrets.py, infra/dedupe.py, infra/firestore_conversations.py, application/export.py e adapters/whatsapp/normalizer.py são listados no monitoramento por excederem 200 linhas[3]. Todos eles são usados diretamente no pipeline ou em funcionalidades críticas, por exemplo:
    4. whatsapp_message_types.py define os tipos de mensagem aceitos e é utilizado no validador do outbound; retirar ou mover quebraria a validação de mensagens.
    5. secrets.py fornece acesso a segredos, inclusive o PEPPER_SECRET usado para derivar user_key quando uma nova sessão é criada[20].
    6. dedupe.py implementa deduplicação; sem ele, o pipeline não conseguiria descartar mensagens duplicadas[21].
    7. firestore_conversations.py implementa o armazenamento de mensagens/histórico; mover esse arquivo impediria a persistência de conversas e a posterior recuperação pelo export.
    8. application/export.py orquestra a exportação e auditoria; movê‑lo quebraria o uso em APIs de exportação.
    9. normalizer.py é necessário para extrair mensagens do payload do webhook[7].
Embora esses arquivos precisem ser monitorados para evitar crescimento excessivo, eles não podem ser movidos para uma pasta “legacy” sem substituir suas funcionalidades por novas implementações.
    1. Clientes HTTP, validadores e construtores de payload – arquivos como adapters/whatsapp/outbound.py, http_client.py, validators/ e payload_builders/ foram refatorados recentemente para separar responsabilidades[19]. Não há código legado nesses módulos; removê‑los resultaria em falhas no envio de mensagens e na validação conforme a API do WhatsApp.
    2. Histórico de sessão e abusos – módulos de detecção de spam/flood (domain/abuse_detection.py) e de sessão (infra/session_store.py) são novos e fundamentais para permitir centenas de conversas simultâneas. Não há legados aqui; eles devem permanecer.
O que falharia ao mover esses componentes para “legacy”
A tabela abaixo resume o impacto de mover determinados arquivos para uma pasta “legacy” e removê‑los do caminho padrão:
Módulo/Arquivo	Uso atual	Consequência se movido para legacy
ai/orchestrator.py (incluindo IntentClassifier e OutcomeDecider)	Invocado pelo pipeline para classificar intenção e outcome iniciais; preenche a fila de intenções e determina se a mensagem é duplicada ou não[5].	Quebra do pipeline inbound: importações falharão; a sessão não terá outcome inicial; detecção de capacidade de intenções deixará de funcionar. É necessário manter até que a classificação via LLM substitua totalmente esse módulo.
domain/whatsapp_message_types.py	Fornece modelos Pydantic para cada tipo de mensagem; utilizados na construção/validação de payloads outbound e para mapear tipos recebidos[11].	Erro de importação nos validadores (WhatsAppMessageValidator), impedindo o envio de mídia, templates e mensagens interativas.
infra/secrets.py	Usado pela configuração (obter tokens do WhatsApp, PEPPER_SECRET, etc.)[20].	Falha na inicialização: a aplicação não consegue obter segredos; o derivador derive_user_key não funciona, impedindo criação de sessão.
infra/dedupe.py	Utilizado para deduplicação de mensagens; chamado logo no início do pipeline[22].	Duplicatas não seriam detectadas; a pipeline trataria mensagens repetidas como novas, aumentando o volume de processamento e comprometendo a idempotência.
infra/firestore_conversations.py	Implementa o ConversationStore em Firestore; necessário para salvar e recuperar mensagens e cabeçalhos[23].	O histórico de mensagens não seria persistido; LLMs e exportadores não teriam acesso ao histórico, inviabilizando as funções de lembrar contexto.
adapters/whatsapp/normalizer.py	Extrai mensagens do payload do webhook e normaliza campos[7].	A pipeline inbound não conseguiria processar o payload recebido; extract_messages retornaria vazio e nenhuma mensagem seria tratada.
application/export.py	Orquestra a exportação de histórico para GCS, incluindo renderização e auditoria[24].	A exportação de conversas e a auditoria associada seriam quebradas; não há alternativa implementada.
state_selector.py, response_generator.py, master_decider.py	Fazem chamadas às LLMs e incluem lógicas de fallback[15][16].	Sem esses módulos, o sistema perde a camada inteligente de seleção de estado e geração de resposta e não segue o fluxo solicitado.
Conclusões e recomendações
    • Não há grandes blocos de código legado a serem movidos. O repositório foi amplamente refatorado e todas as funcionalidades críticas estão separadas em camadas. O “legado” refere‑se apenas à antiga abordagem determinística de classificação de intenção/outcome. Como o pipeline inbound ainda a utiliza, esses módulos devem permanecer até que a LLM assuma integralmente a classificação de intenção e de outcomes.
    • Arquivos marcados como “atenção” pelo monitoramento são grandes, mas contêm funcionalidades ativas e não podem ser relegados à pasta “legacy” sem substituição. O time deve monitorar seu tamanho e continuar extraindo submódulos conforme crescerem.
    • Para suportar centenas de mensagens simultâneas, é crucial manter o session_store (persistência de sessões), dedupe_store e abuse_detection. Esses módulos evitam flood/spam e garantem escalabilidade.
    • Possível melhoria futura: Se a meta é que todas as decisões (intenção, estado, resposta e mensagem final) venham do LLM, o AIOrchestrator e os classificadores determinísticos poderão ser removidos em releases futuros. Nessa hipótese, após escrever um substituto baseado em LLM, mova ai/orchestrator.py e seus utilitários para uma pasta legacy e atualize as importações. Até lá, mantê‑los garante fallback e robustez.

[1] [2] [3] [18] [19] Monitoramento_Regras-Padroes.md
https://github.com/fortescwb/pyloto_corp/blob/main/Monitoramento_Regras-Padroes.md
[4] [5] [22] pipeline.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/pipeline.py
[6] [7] normalizer.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/adapters/whatsapp/normalizer.py
[8] [21] dedupe.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/infra/dedupe.py
[9] [10] [20] secrets.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/infra/secrets.py
[11] [12] whatsapp_message_types.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/domain/whatsapp_message_types.py
[13] [14] orchestrator.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/ai/orchestrator.py
[15] state_selector.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/state_selector.py
[16] response_generator.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/response_generator.py
[17] master_decider.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/master_decider.py
[23] firestore_conversations.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/infra/firestore_conversations.py
[24] export.py
https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/export.py