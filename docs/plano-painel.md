# Plano do painel Media Saver

## Objetivo

Organizar pelo navegador os arquivos recebidos pelo Telegram, reutilizando a
biblioteca Python existente. Desenvolver primeiro no PC, sem contratar serviços.

## Primeira entrega: biblioteca demonstrativa

- Criar `frontend/` com React, TypeScript e Vite; CSS local, sem tema pago.
- Tela em português, adaptada para computador e celular.
- Lista com nome, tipo, tamanho e data; busca por nome e filtro por tipo.
- Resumo da quantidade e tamanho dos arquivos de exemplo.
- Estados de biblioteca vazia e busca sem resultados.
- Usar dados fictícios, identificados como demonstração. Não carregar `data/`
  nem credenciais no navegador. Ações sem backend não devem simular sucesso real.
- Validar navegação por teclado, layout em telas pequenas e build de produção.

Concluída quando a biblioteca de exemplo puder ser explorada localmente e o
build passar. Sugestão de commit: `feat: criar interface demonstrativa da biblioteca`.

## Segunda entrega: autenticação e leitura real

- Definir o vínculo entre a sessão web e o usuário do Telegram antes de expor dados.
- API deve obter o proprietário da identidade autenticada, nunca confiar em um
  ID de usuário enviado livremente pelo navegador.
- Criar listagem paginada, busca e resumo de espaço, reaproveitando `Library`.
- Separar acesso HTTP do componente visual para substituir os dados de exemplo.
- Testar ausência de autenticação e acesso cruzado entre usuários.
- Mostrar carregamento, erros e sessão expirada na interface.

## Terceira entrega: gerenciamento real

- Download autenticado, renomeação e exclusão com confirmação visual.
- Reutilizar regras da biblioteca; preservar as verificações do dono no servidor.
- Atualizar a lista e o espaço após alterações; explicar falhas sem perder dados.
- Testar os fluxos completos e executar build/testes do frontend no CI.

## Quarta entrega: publicação

- Escolher hospedagem após estimar armazenamento, usuários e orçamento.
- Preferência: servidor sempre ligado, sem dependência do Render.
- Preparar Docker, HTTPS, configuração de segredos, backup e restauração.
- Contratar serviços e publicar somente depois de definir custos com o usuário.

## Organização proposta

```text
frontend/             interface React/TypeScript (a criar)
media_bot/api.py       rotas HTTP
media_bot/bot.py       comandos do Telegram
media_bot/library.py   operações compartilhadas e SQLite
tests/                testes Python
docs/                 planejamento e decisões
```

Extrair serviços adicionais apenas quando houver regras compartilhadas que
justifiquem isso. Não duplicar SQL na interface nem mover todo o código agora.

## Custos

React, TypeScript, Vite, Python, FastAPI e SQLite não exigem licença paga para
este desenvolvimento. Rodar localmente usa o computador, disco e conexão existentes.
Domínio próprio, servidor e armazenamento externo podem gerar cobranças na publicação.
Não é necessária API de IA paga para esta primeira versão.

GitHub Actions: runners padrão são gratuitos em repositórios públicos; privados
têm franquias conforme o plano e podem cobrar excedentes. Referência:
https://docs.github.com/en/billing/concepts/product-billing/github-actions

## Atualização: integração local

Listagem e download conectados ao SQLite, com chave local e proprietário fixo no servidor.
Dados fictícios removidos. Busca e filtros usam a listagem real.
Próximas etapas: autenticação multiusuário para hospedagem, gerenciamento web e favoritos persistentes.
