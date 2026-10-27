# Comprovantes automáticos - Google Apps Script

Este arquivo é um **rascunho não ativado**. O Streamlit permanece intacto.

## Configuração segura

1. Na planilha oficial, abra **Extensões > Apps Script**.
2. Cole o conteúdo de `comprovantes.gs` no editor e salve.
3. Confirme que o nome real da aba é `Autorizados ` (com espaço final), e que os e-mails estão na coluna C, a partir da linha 7.
4. Confirme que a coluna **M** do histórico está reservada ao status do envio e a coluna **N** ao combustível. Opcionalmente, coloque `STATUS EMAIL` em M1.
5. Mantenha `ATIVAR_ENVIOS: false`. Execute **simularEnvios** manualmente, autorize o Apps Script quando solicitado e examine o **Registro de execução**. Esta função não envia e-mails e não altera células.
6. Para teste controlado de envio real, use uma linha de teste autorizada e um e-mail de teste sob seu controle, sem afetar registros reais. Não habilite envios gerais antes de validar destinatário e conteúdo.
7. Após a aprovação, altere `ATIVAR_ENVIOS: true`, salve, vá em **Acionadores > Adicionar acionador** e escolha função `processarComprovantes`, origem **Baseado no tempo**, intervalo **A cada 5 minutos**.
8. Execute `simularEnvios` novamente antes de ativar, especialmente se houver retornos concluídos com combustível e status M vazio. Ao ativar, essas linhas serão elegíveis.

## Regras
- Envia **somente para o e-mail do motorista** da aba Autorizados (B:C).
- Envia somente após F (hora de retorno), G (KM) e N (combustível) estarem preenchidas.
- Não envia se M já contiver status; M recebe `ENVIADO <data/hora>` ou `ERRO: ...`.
- Erros devem ser investigados manualmente; não apague um status `ENVIADO` para evitar duplicações.
- Como o Streamlit grava via API, um gatilho `onEdit` não é adequado; use o gatilho de tempo.
- **Limitação:** há uma pequena janela entre envio e gravação do status em que uma falha pode causar duplicidade. Se o envio for crítico, será necessário um mecanismo adicional de idempotência.
- **Segurança:** o e-mail será enviado pela conta Google que autorizar o acionador; verifique quotas do MailApp e política corporativa.

Nenhum acionador é criado por estes arquivos.
