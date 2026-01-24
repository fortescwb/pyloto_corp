# Regras e Padrões de Código — pyloto_corp

Este documento define as **regras obrigatórias de organização, escrita e manutenção de código** para o repositório **`pyloto_corp`**.

O objetivo é garantir que o código permaneça **legível, modular, auditável, seguro e sustentável** ao longo do tempo, mesmo com crescimento do projeto, entrada de novos desenvolvedores ou uso intensivo de LLMs como apoio.

Estas regras **não são sugestões**. São **padrões a serem seguidos**.

---

## 1. Princípios Fundamentais

Antes de qualquer regra técnica, este repositório adota os seguintes princípios:

* Código é lido mais vezes do que é escrito.
* Segurança e previsibilidade vêm antes de conveniência.
* Clareza vence esperteza.
* Falhar de forma segura é sempre melhor do que “tentar adivinhar”.
* Nenhum módulo deve depender de boa-fé do usuário.

---

## 2. Tamanho Máximo de Arquivos (Modularidade)

Embora o Python não imponha limites técnicos rígidos, o projeto adota **limites práticos de engenharia** baseados em boas práticas modernas (2026).

### 2.1 Limites de linhas por arquivo

| Tamanho do arquivo  | Classificação | Ação recomendada           |
| ------------------- | ------------- | -------------------------- |
| Até 200 linhas      | Excelente     | Nenhuma                    |
| 200–400 linhas      | Bom           | Aceitável                  |
| 400–500 linhas      | Atenção       | Avaliar refatoração        |
| Acima de 500 linhas | Alerta        | Refatorar obrigatoriamente |

Arquivos acima de **500 linhas** são considerados **módulos inflados** e indicam violação de coesão ou responsabilidade única.

> Arquivos grandes demais tendem a virar “God Objects”, dificultam testes, revisão e segurança.

---

## 3. Princípio da Responsabilidade Única (SRP)

Mais importante que o número de linhas é o **propósito do arquivo**.

### Regras obrigatórias

* Cada arquivo deve ter **um único propósito claro**.
* Se for necessário “procurar demais” uma função, o arquivo já está grande demais.
* Um arquivo não deve misturar:

  * lógica de domínio + infraestrutura
  * validação + persistência
  * construção de payload + envio externo

### Pergunta de validação

> “Eu consigo explicar este arquivo em uma frase curta?”

Se a resposta for não, o arquivo deve ser dividido.

---

## 4. Tamanho de Funções e Métodos

### 4.1 Funções

* Ideal: **20 a 50 linhas**
* Máximo aceitável: **~60 linhas**
* Funções maiores que isso:

  * estão fazendo coisas demais
  * escondem regras de negócio
  * dificultam testes unitários

Funções longas devem ser quebradas em:

* funções auxiliares
* pequenos pipelines
* etapas nomeadas explicitamente

### 4.2 Classes

* Classes devem ser **concisas e focadas**.
* Classes com centenas de linhas indicam:

  * excesso de responsabilidades
  * acoplamento indevido
  * dificuldade de extensão segura

Prefira:

* composição em vez de herança
* classes pequenas e previsíveis
* contratos explícitos

---

## 5. Largura de Linha e Legibilidade (PEP 8)

Para manter legibilidade em revisões, diffs e diferentes monitores:

* **Código**: máximo **79 caracteres**
* **Docstrings e comentários**: máximo **72 caracteres**

Mesmo que ferramentas modernas permitam mais, este repositório **mantém o padrão clássico do PEP 8** por clareza e consistência.

### Observações

* Quebras de linha são preferíveis a linhas longas.
* Código legível vence código compacto.

---

## 6. Comentários e Docstrings

### Regras obrigatórias para comentários e docstrings

* **Todos os comentários devem ser em Português_BR**
* Docstrings devem explicar:

  * o “porquê” da existência
  * o contrato esperado
  * efeitos colaterais relevantes

### Comentários não devem

* repetir o que o código já diz
* explicar sintaxe óbvia
* mascarar código confuso

Se um comentário for longo demais, o código provavelmente precisa ser refatorado.

---

## 7. Organização Arquitetural

O projeto segue separação explícita por camadas:

* `domain/` → regras puras, contratos, modelos
* `application/` → casos de uso, orquestração
* `infra/` → Firestore, GCS, APIs externas
* `adapters/` → WhatsApp, HTTP, normalização
* `api/` → FastAPI, rotas, dependências

### Regras

* Domínio **não conhece infraestrutura**
* Infraestrutura **não decide regra de negócio**
* Adaptadores **não contêm lógica crítica**

---

## 8. Segurança e Zero-Trust (Obrigatório)

* Nunca assumir boa-fé do usuário.
* Todo input é potencialmente malicioso.
* Nenhum payload externo deve ser confiável.
* Logs **nunca** devem conter PII.
* Decisões críticas **não pertencem à IA**.

Arquivos devem ser escritos considerando:

* abuso
* tentativa de exploração
* auditoria futura

---

## 9. Ferramentas de Monitoramento e Qualidade

### 9.1 Ruff (Obrigatório)

* Linting
* Estilo
* Detecção de arquivos e funções excessivas
* Ordenação de imports

Ruff é considerado **ferramenta padrão** do projeto.

### 9.2 Complexidade Ciclomática

Ferramentas recomendadas:

* **Radon**
* **Xenon**

Observação importante:

> Um arquivo de 100 linhas pode ser pior que um de 300 se a lógica for profundamente aninhada.

Complexidade excessiva deve ser tratada como **problema de arquitetura**, não apenas de estilo.

---

## 10. Critérios de Aceitação para Código Novo

Antes de aceitar qualquer alteração, o código deve atender a:

* Arquivos dentro dos limites de tamanho
* Funções pequenas e testáveis
* Responsabilidade única clara
* Comentários em Português_BR
* Nenhum vazamento de PII
* Testes existentes ou adicionados
* Ruff e pytest passando

Se um desses pontos falhar, o código **não está pronto**.

---

## 11. Regra Final

> **Se o código só funciona quando tudo dá certo, ele está errado.**

O repositório `pyloto_corp` deve funcionar corretamente **inclusive quando alguém tenta quebrá-lo de propósito**.

Estas regras existem para garantir isso.

---
