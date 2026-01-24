# Segurança, LGPD e retenção

- Acesso a exports restrito a service accounts com papel mínimo (Storage Object Admin restrito ao bucket de exports).
- Exports nunca são públicos; links `gs://` não são expostos ao cliente final.
- Dados pessoais (telefone, nome) só aparecem no export quando `include_pii=true` e após autorização.
- Minimização: armazenamos telefone apenas em `profiles/{user_key}`; demais coleções usam `user_key`.
- Retenção recomendada:
  - Habilitar Object Versioning no bucket de exports.
  - Avaliar Bucket Lock (WORM) com política de retenção conforme jurídico.
  - Definir lifecycle para expirar exports após prazo acordado (ex.: 180 dias), exceto quando legalmente retidos.
- Auditoria: eventos são append-only com cadeia de hash (prev_hash → hash) em `conversations/{user_key}/audit/*`.
- Logs: jamais logar PII; somente `user_key`, `event_id`, `provider_message_id`, `correlation_id`.
- Secrets: `PEPPER_SECRET`, credenciais GCS/Firestore via Secret Manager; não commitar nem logar valores.
