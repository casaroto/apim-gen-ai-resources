# APIM Gen AI Resources



Objetivo: Demonstrar como o uso de GenAI permite aumento de providade e qualidade, ao utilizar MCP, skills e agents para gestão do ciclo de vida completo de APIs.
A ideia final é aumentar a qualidade das APIs expostas. APIs são um dos maiores vetores de problemas de segurança atualmente, e ainda há um baixo nível de maturidade de gestão de APIs em muitas empresas.

Produtos e soluções utilizadas: é dado enfase no uso de soluções Open Source, mas também há exemplos para uso com produtos comerciais Google APIGee e IBM API Connect.

Observação: para uso com o IBM API Connect é indicado o uso da ferramenta nativa do produto. https://www.ibm.com/docs/en/api-connect/software/12.1.0?topic=agent-api-overview
Esse conjunto de ferramentas cobre tudo que é proposto neste repositório.

Este repositório reúne recursos para um ciclo completo de trabalho com APIs usando GenAI.

Os exemplos permitem:

1. subir um backend de exemplo;
2. gerar uma especificação OpenAPI;
3. validar e corrigir problemas de segurança com Spectral/OWASP;
4. executar instâncias locais de API Management;
5. fazer deploy da API via MCP;
6. testar a API publicada com Newman/Postman.

## Estrutura principal

- `book-backend-demo/`: backend Express de exemplo para a API de livros, com OpenAPI e smoke tests.
- `skills/openapi-spec-generation/`: skill para gerar especificações OpenAPI 3.0.3 a partir de rotas Express.
- `skills/fix-openapi-spectral/`: skill para corrigir achados do Spectral e OWASP API Security em arquivos OpenAPI.
- `run-apim-instances/`: arquivos `docker-compose.yml` para subir instâncias locais de APIM, como Kong e WSO2.
- `mcp/deploy/`: servidores MCP para deploy em gateways/APIMs como Kong, WSO2, Apigee e IBM API Connect.
- `mcp/tests/`: MCPs para validação com Spectral e testes com Postman/Newman.

## Backend de exemplo

O backend principal está em `book-backend-demo/backend/` e expõe endpoints simples como `/health`, `/books`, `/books/{id}` e criação de livros.

Para subir o backend junto com Kong:

```bash
cd book-backend-demo
docker compose up --build
```

Depois, valide a API:

```bash
./test-api.sh
```

## Gerar OpenAPI com a skill

Use a skill `openapi-spec-generation` quando quiser gerar ou atualizar uma especificação OpenAPI a partir de um arquivo de rotas Express.

Exemplo de pedido para o agente:

```text
Use a skill openapi-spec-generation para gerar uma spec OpenAPI do arquivo book-backend-demo/backend/server.js.
```

A saída esperada é um arquivo `.openapi.yaml` ou `.yaml` seguindo OpenAPI 3.0.3, com endpoints, schemas, responses e segurança inferida quando houver middleware de autenticação.

## Rodar instâncias locais de APIM

Os arquivos em `run-apim-instances/` servem para subir gateways e plataformas locais:

```bash
cd run-apim-instances/kong
docker compose up -d
```

```bash
cd run-apim-instances/wso2
docker compose up -d
```

Use essas instâncias como alvo para importar, publicar e testar APIs durante o ciclo de desenvolvimento.

## Deploy da API via MCP

Os MCPs de deploy ficam em `mcp/deploy/`:

- `mcp/deploy/kong/mcp-kong-deploy-http/`: deploy em Kong via Admin API.
- `mcp/deploy/wso2/mcp-wso2-deploy-http/`: importação, publicação, assinatura e invocação em WSO2.
- `mcp/deploy/apigee/mcp-apigee-deploy-http/`: deploy em Apigee.
- `mcp/deploy/ibm-apic/mcp-apic-deploy-http/`: publicação de produtos/APIs no IBM API Connect.

Exemplo de uso com um agente:

```text
Use o MCP de deploy para publicar a OpenAPI book-backend-demo/openapi.yaml no gateway local.
```

Cada MCP possui seu próprio `config.properties`, `Dockerfile` e ferramentas específicas para o APIM alvo.

## Corrigir erros de segurança com Spectral

Use a skill `fix-openapi-spectral` depois de rodar o MCP de Spectral ou receber achados de lint/security.

Exemplo:

```text
Use a skill fix-openapi-spectral para corrigir os erros de segurança encontrados em book-backend-demo/openapi.yaml.
```

A skill corrige a especificação OpenAPI preservando o contrato da API sempre que possível, incluindo ajustes como `operationId`, tags, descrições, responses `401/429/500`, headers, schemas e security schemes.

## Testar a API publicada

Para validar a especificação:

```text
Use o MCP Spectral para validar book-backend-demo/openapi.yaml com severidade hint.
```

Para executar testes funcionais gerados a partir da OpenAPI:

```text
Use o MCP Postman/Newman para testar book-backend-demo/openapi.yaml contra a URL publicada no gateway.
```

## Fluxo recomendado

1. Suba o backend em `book-backend-demo/`.
2. Gere ou atualize a OpenAPI com `openapi-spec-generation`.
3. Valide com o MCP Spectral.
4. Corrija os achados com `fix-openapi-spectral`.
5. Suba uma instância APIM em `run-apim-instances/`.
6. Faça o deploy usando o MCP correspondente em `mcp/deploy/`.
7. Execute testes com Newman/Postman em `mcp/tests/postman/`.
