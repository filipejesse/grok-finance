# grok-finance

Controle financeiro pessoal usando **Grok** + **Open Finance** (via Meu Pluggy).

> Script Python que puxa os dados dos seus bancos, gera um resumo limpo e entrega pro Grok analisar.

## Visão geral

O **grok-finance** automatiza a ponte entre suas contas bancárias e o Grok:

1. Conecta seus bancos pelo **Meu Pluggy** (gratuito para uso pessoal)
2. Um script Python busca, limpa e resume as transações
3. O resumo é enviado ao Grok para análise, projeções e alertas

Ideal para quem quer visão consolidada de 1 a 5 bancos sem complexidade regulatória.

## Arquitetura

```
Bancos
   ↓
Meu Pluggy (API)
   ↓
Script Python (limpeza + resumo)
   ↓
Grok (análise)
```

## Funcionalidades atuais

- Autenticação na API do Meu Pluggy
- Listagem de contas conectadas
- Busca de transações do período
- Geração de resumo enxuto (texto)
- Formato otimizado para colar no Grok

## Pré-requisitos

- Python 3.10+
- Conta no [Meu Pluggy](https://pluggy.ai/meu-pluggy) com os bancos já conectados
- Credenciais da API (`clientId` e `clientSecret`)

## Instalação

```bash
git clone https://github.com/filipejesse/grok-finance.git
cd grok-finance
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz:

```env
PLUGGY_CLIENT_ID=seu_client_id
PLUGGY_CLIENT_SECRET=seu_client_secret
```

## Uso

```bash
python main.py
```

O script imprime (ou salva) um resumo no formato:

```text
=== RESUMO FINANCEIRO - MÊS/ANO ===
Contas:
- Nubank: R$ X.XXX,XX
...

Movimentação:
- Entradas: R$ X.XXX
- Saídas: R$ X.XXX
...
```

Cole o resultado no Grok e peça a análise.

## Estrutura do projeto

```
grok-finance/
├── .env.example
├── requirements.txt
├── main.py
├── pluggy_client.py
├── processor.py
└── config.py
```

## Segurança

- Nunca commite o `.env`
- O token do Meu Pluggy pode ser revogado a qualquer momento no dashboard
- O script só deve rodar em ambiente controlado por você
- Apenas o resumo (não os dados brutos) deve ir para o Grok

## Roadmap

- [ ] Envio automático do resumo para a API do Grok
- [ ] Agendamento (Cloud Function / cron)
- [ ] Categorização mais inteligente
- [ ] Suporte a mais de um período
- [ ] Relatórios mensais

## Contribuição

Contribuições são bem-vindas. Abra uma issue ou envie um pull request.

## Licença

MIT

## Aviso

Este projeto é de uso pessoal. Não é um produto financeiro regulado. Use por sua conta e risco.
