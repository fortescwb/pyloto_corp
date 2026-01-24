# Módulo WhatsApp — estado atual

Cobertura completa dos 16 tipos suportados pela API oficial (texto, mídia, endereço, localização, contatos, reaction, template e interativos: botões, lista, flow, CTA URL, location request). Baseado na Graph API v24.

Documentação deste módulo:
- Arquitetura e refatoração V2: [WHATSAPP_MODULE_REFACTORING.md](WHATSAPP_MODULE_REFACTORING.md)
- Expansão para tipos extras (ADDRESS, TEMPLATE, CTA URL, LOCATION_REQUEST, FLOW): [WHATSAPP_EXTENDED_TYPES_UPDATE.md](WHATSAPP_EXTENDED_TYPES_UPDATE.md)
- Resumo de alterações e arquivos afetados: [TREE_CHANGES.txt](TREE_CHANGES.txt)

Entradas de código:
- Adapters: `src/pyloto_corp/adapters/whatsapp/`
- Domínio: `src/pyloto_corp/domain/whatsapp_message_types.py`
- Testes: `tests/adapters/`

Validação rápida:
- `pytest tests/adapters -v`
- conferência de enums: `python - <<'PY'\nfrom pyloto_corp.domain.enums import MessageType, InteractiveType\nprint([t.value for t in MessageType])\nprint([t.value for t in InteractiveType])\nPY`

Qualquer mudança estrutural no módulo deve manter aderência às regras em [regras_e_padroes.md](../../regras_e_padroes.md) e ao contrato de produto em [Funcionamento.md](../../Funcionamento.md).
