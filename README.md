# grok-finance

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Open Finance](https://img.shields.io/badge/Open%20Finance-Brazil-green.svg)](https://openfinancebrasil.org.br/)

> Personal finance control using **Grok** + **Open Finance** (via Meu Pluggy).

A lightweight Python tool that fetches your bank data through Open Finance, generates a clean summary, and prepares it for analysis with Grok.

---

## Overview

**grok-finance** bridges your Brazilian bank accounts and Grok:

1. Connect your banks via **Meu Pluggy** (free for personal use)
2. A Python script fetches, cleans, and summarizes transactions
3. The summary is ready to be analyzed by Grok (projections, alerts, insights)

Designed for personal use with 1–5 bank accounts, without regulatory complexity.

## Architecture

```mermaid
flowchart TD
    A[Banks<br/>Nubank, Itaú, etc.] -->|Open Finance Consent| B[Meu Pluggy<br/>API]
    B -->|JSON Data| C[Python Script<br/>Clean + Summarize]
    C -->|Clean Summary| D[Grok<br/>Analysis & Alerts]
    D -->|Insights| E[User]

    style A fill:#ffc9c9
    style B fill:#ffd8a8
    style C fill:#b2f2bb
    style D fill:#d0bfff
    style E fill:#a5d8ff
```

## Features

- Authentication with Meu Pluggy API
- List connected accounts and balances
- Fetch transactions for a given period
- Generate a concise, Grok-ready summary
- Privacy-focused (only summaries leave your environment)

## Prerequisites

- Python 3.10 or higher
- A [Meu Pluggy](https://pluggy.ai/meu-pluggy) account with your banks already connected
- API credentials (`clientId` and `clientSecret`) from the Pluggy dashboard

## Installation

```bash
git clone https://github.com/filipejesse/grok-finance.git
cd grok-finance
python -m venv venv
source venv/bin/activate          # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
PLUGGY_CLIENT_ID=your_client_id
PLUGGY_CLIENT_SECRET=your_client_secret
```

## Usage

```bash
python main.py
```

The script outputs a summary like:

```text
=== FINANCIAL SUMMARY - MONTH/YEAR ===
Accounts:
- Nubank: R$ X,XXX.XX
- Itaú: R$ X,XXX.XX

Period Movement:
- Inflows: R$ X,XXX.XX
- Outflows: R$ X,XXX.XX
- Net: R$ X,XXX.XX

Top Categories:
1. Housing: R$ X,XXX
2. Food: R$ X,XXX
...

Notable Transactions:
- [date] Description - R$ XXX
```

Paste the output into Grok and ask for analysis, projections, or alerts.

## Project Structure

```
grok-finance/
├── .env.example
├── requirements.txt
├── main.py
├── pluggy_client.py
├── processor.py
└── config.py
```

## Security

- Never commit your `.env` file
- Pluggy tokens can be revoked at any time from the dashboard
- Run the script only in an environment you control
- Only summaries (never raw transaction data) should be sent to Grok

## Roadmap

- [ ] Automatic sending of summaries to Grok API
- [ ] Scheduled runs (Cloud Function / cron)
- [ ] Smarter transaction categorization
- [ ] Multi-period support
- [ ] Monthly reports

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please make sure to update tests as appropriate.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is a personal-use tool. It is **not** a regulated financial product. Use at your own risk. The authors are not responsible for any financial decisions made based on the output of this tool.

---

Made with ❤️ for better personal finance visibility.
