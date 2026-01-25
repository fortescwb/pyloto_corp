# Regras e Padrões de Código

Este documento define as **regras absolutas, congeladas e não negociáveis** de código do repositório `pyloto_corp`.

Ele é a **fonte única de verdade** sobre qualidade, estilo, segurança, testes e critérios de aceite.
Qualquer código que viole estas regras é considerado **incorreto**, independentemente de funcionar em produção.

---

## 1. Princípios Fundamentais

### 1.1 Clareza como valor primário

Código deve ser lido, entendido e auditado por terceiros sem explicações verbais.
Soluções inteligentes porém opacas são proibidas.

### 1.2 Simplicidade estrutural

Abstrações só são permitidas quando reduzem complexidade real.
Abstrações criadas "para o futuro" são consideradas débito técnico imediato.

### 1.3 Previsibilidade e determinismo

O comportamento do sistema deve ser previsível a partir do código.
Side effects implícitos, dependência de estado global ou ordem de execução são proibidos.

### 1.4 Defesa em profundidade (zero‑trust)

O sistema **não presume boa‑fé**.
Todo input externo é potencialmente malicioso e deve ser validado.

---

## 2. Estrutura de Código

### 2.1 Tamanho máximo

**Objetivo:** manter legibilidade, testabilidade e baixo custo cognitivo.

* Arquivos de código: **máx. 200 linhas**
* Funções ou métodos: **máx. 50 linhas**

Exceções:

* Só são permitidas quando a fragmentação **piorar** a clareza.
* Devem conter comentário explícito justificando a exceção.

### 2.2 Responsabilidade única

Cada arquivo deve responder claramente à pergunta:

> “Qual problema específico este módulo resolve?”
> "Eu consigo resumir o que esse arquivo faz em uma única frase?"

Arquivos que respondem a mais de uma responsabilidade são inválidos.

### 2.3 Separação de camadas

As seguintes camadas **não devem se misturar**:

* Domínio (regras, validações, contratos)
* Orquestração (fluxos, coordenação)
* Infraestrutura (IO, APIs, banco, rede)

Violação dessa separação é considerada falha arquitetural grave.

---

## 3. Estilo, Legibilidade e Nomenclatura

### 3.1 Código autoexplicativo

O código deve explicar **o que faz** apenas pela leitura.
Comentários são usados apenas para explicar **por que** algo existe.

### 3.2 Comentários

* Idioma obrigatório: **PT‑BR**
* Comentários redundantes são proibidos
* Comentários desatualizados são considerados bug

### 3.3 Nomes

* Nomes devem ser descritivos e completos
* Abreviações só são permitidas se amplamente consagradas
* Variáveis de uma letra são proibidas fora de laços muito locais

---

## 4. Tipagem, Contratos e Validação

### 4.1 Tipagem explícita

Entradas, saídas e estruturas internas devem ser tipadas sempre que a linguagem permitir.

### 4.2 Contratos claros

Toda função deve deixar explícito:

* O que espera receber
* O que retorna
* Em quais condições falha

### 4.3 Falha explícita

Falhas silenciosas são proibidas.
Toda inconsistência deve resultar em erro explícito, rastreável e testável.

---

## 5. Logs e Observabilidade

### 5.1 Proteção de dados

* **Nunca** logar PII ou payload sensível
* Logs devem ser seguros mesmo em caso de vazamento

### 5.2 Estrutura

* Logs estruturados
* Campos previsíveis
* Mensagens objetivas, sem ruído

---

## 6. Segurança (Premissa Permanente)

### 6.1 Input externo

Todo input externo deve ser tratado como hostil:

* Validar formato
* Validar limites
* Validar permissões

### 6.2 Decisões críticas

Nenhuma decisão crítica pode depender exclusivamente de dados fornecidos pelo cliente.

---

## 7. Testes — Fonte de Verdade Funcional

Testes são **obrigatórios** e representam o contrato executável do sistema.

### 7.1 O que deve ser testado

Para cada função, regra ou fluxo relevante:

#### a) Caminho Feliz (Happy Path)

* Pelo menos **1 teste** validando o comportamento esperado com dados válidos

#### b) Casos de Borda (Edge Cases)

* Entradas vazias
* Valores mínimos e máximos
* Formatos inesperados
* Campos opcionais ausentes

#### c) Tratamento de Erros

* Pelo menos **1 teste** garantindo:

  * tipo correto da exceção
  * contrato do erro respeitado

### 7.2 Proporção esperada

* Função simples/utilitária: **1–2 testes**
* Função com ramificações/validação: **3–5 testes**
* Funções críticas: testar conforme o risco, sem limite quantitativo

### 7.3 Cobertura de Código

* Cobertura mínima global: **90%**
* Alvo recomendado: **90–100%**
* PRs **não podem reduzir** cobertura existente

Cobertura é medida via `coverage.py` ou `pytest‑cov`.

### 7.4 Organização dos testes

* Um arquivo de teste por arquivo de código
* Arquivos > **500 linhas** devem ser divididos por funcionalidade

### 7.5 Boas práticas de teste

* Um conceito validado por teste
* Testes independentes
* Testes determinísticos (sem dependência de tempo, rede ou estado global)

---

## 8. Ferramentas de Qualidade

### 8.1 Obrigatórias (gate de CI)

* `ruff` — lint e estilo
* `pytest` — execução de testes
* `pytest‑cov` / `coverage.py` — cobertura

Código que falha nessas ferramentas **não é válido**.

### 8.2 Recomendadas (obrigatórias em auditoria)

* `radon` — complexidade ciclomática
* `xenon` — gates de complexidade

---

## 9. Monitoramento de Conformidade

O arquivo `Monitoramento_Regras‑Padroes.md` é a **fonte operacional** de acompanhamento e deve conter:

* Violações conscientes existentes
* Métricas atuais (tamanho, complexidade, cobertura)
* Data e commit da última auditoria

Atualização obrigatória quando:

* uma exceção for introduzida
* uma métrica regredir
* auditoria for realizada

---

## 10. Definition of Done (Critério Final de Aceite)

Um código só é considerado **pronto** quando:

* Cumpre todos os limites estruturais
* Passa em lint, testes e cobertura mínima
* Possui testes cobrindo happy path, bordas e erros
* Não introduz PII em logs
* Não degrada métricas existentes

Código fora deste padrão **não deve ser mergeado sob nenhuma hipótese**.
