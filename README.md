# Open Finance Tracker

Dashboard pessoal. Não usa banco de dados: `contas.json` fornece as contas, nomes, saldos e IDs exibidos no dashboard. A API da Pluggy é consultada para carregar faturas e transações.

## Configuração

1. Instale Python 3.14 ou superior e [uv](https://docs.astral.sh/uv/).
2. Crie o arquivo `.env` na raiz usando `.env.example` como modelo e preencha `PLUGGY_CLIENT_ID` e `PLUGGY_CLIENT_SECRET`.
3. Crie `contas.json` na raiz usando `data/banks.json.example` como modelo. Preencha com os dados salvos das contas, incluindo `id`, `itemId`, `type`, `name`, `balance` e `currencyCode`. Quando `contas.json` existe, o dashboard usa esses dados localmente sem consultar o endpoint `/accounts`. Como os saldos são locais, atualize `balance` no JSON quando quiser refletir valores mais recentes. Se o arquivo não existir, as contas são consultadas na API.

O patrimônio líquido soma contas bancárias e investimentos em BRL e subtrai o saldo em aberto dos cartões em BRL. O gráfico do cartão soma o valor de cada transação no mês de fatura indicado pela Pluggy (`billForecastDate`); para compras parceladas, usa o valor da parcela (`amount`), não o total original da compra (`creditCardMetadata.totalAmount`).

Faturas e transações vêm da API da Pluggy e podem apresentar atraso em relação às movimentações mais recentes. O tempo de atualização depende da sincronização da Pluggy com a instituição financeira; se algum dado recente não aparecer, aguarde a sincronização e atualize o dashboard. Os saldos das contas exibidos a partir de `contas.json` não são atualizados automaticamente pela API: altere o arquivo local para refletir novos saldos.

4. Instale as dependências e inicie o servidor:

   ```bash
   uv sync
   uv run uvicorn app.main:app --reload
   ```

5. Acesse <http://127.0.0.1:8000>.

## Recursos do dashboard

- O histórico busca páginas da Pluggy sob demanda pelo cursor. A API entrega até 500 transações por página; a interface mostra 10 linhas por vez e carrega o próximo lote ao avançar.
- Busca por descrição/categoria, filtro específico de categoria, tipo e intervalo de datas. Os filtros e a exportação CSV incluem as transações que já foram carregadas para a conta selecionada.
- Abaixo do histórico, o resumo financeiro mostra despesas, entradas, saldo líquido e valores por categoria, respeitando a conta e os filtros selecionados. Os totais refletem apenas transações carregadas; use a paginação para incluir outros lotes.
- O cartão informa quando o arquivo `contas.json` foi salvo; atualize manualmente os saldos nesse arquivo quando necessário. A chave da instituição (por exemplo, `nubank`) continua sendo usada como identificador do banco.

As credenciais e `contas.json` são locais e estão ignorados pelo Git. A API key da Pluggy é mantida apenas no servidor e nunca é enviada ao navegador.

## Uso de inteligência artificial

Foi utilizada inteligência artificial como apoio para ajustes e melhorias no código e na documentação deste projeto. As alterações devem ser revisadas e testadas antes de uso ou publicação.

## Privacidade

Esta versão é um dashboard pessoal sem autenticação de usuários. Execute-a apenas em ambiente privado. Não a publique em um domínio ou servidor acessível pela internet sem adicionar autenticação e HTTPS: as rotas do dashboard mostram dados financeiros da conta Pluggy configurada.
