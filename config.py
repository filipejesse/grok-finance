"""Fixed rules and personal context. Edit this file to fit your finances."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

PLUGGY_CLIENT_ID = os.getenv("PLUGGY_CLIENT_ID", "")
PLUGGY_CLIENT_SECRET = os.getenv("PLUGGY_CLIENT_SECRET", "")
# The Pluggy API has no "list my items" endpoint: copy each connection's item ID
# from the Meu Pluggy dashboard, comma-separated.
PLUGGY_ITEM_IDS = [i.strip() for i in os.getenv("PLUGGY_ITEM_IDS", "").split(",") if i.strip()]

# Months of history fetched besides the current one (sent only as a short recap).
PREVIOUS_MONTHS = 1

# Outflows at or above this value are always listed as atypical.
ATYPICAL_MIN_AMOUNT = 500.0
# Outflows this many times above their category's average are also atypical.
ATYPICAL_CATEGORY_FACTOR = 3.0
MAX_ATYPICAL = 10
TOP_CATEGORIES = 5

# Free-form lines appended to the summary so Grok knows your fixed commitments.
FIXED_CONTEXT = [
    "Salário: dia 5",
    "Aluguel: dia 10",
]

# Pluggy categories (case-insensitive substring) that just move money between
# your own accounts or pay the card bill. Ignored to avoid double counting.
IGNORED_CATEGORIES = [
    "same person transfer",
    "credit card payment",
]

# Keyword rules applied to the description before Pluggy's own category.
# First match wins. Keys are matched case-insensitively.
KEYWORD_RULES = {
    "aluguel": "Moradia",
    "condominio": "Moradia",
    "ifood": "Alimentação",
    "uber": "Transporte",
    "99app": "Transporte",
}

# Pluggy categories (English) -> labels shown in the summary.
CATEGORY_LABELS = {
    "housing": "Moradia",
    "rent": "Moradia",
    "utilities": "Contas da casa",
    "food and drinks": "Alimentação",
    "groceries": "Mercado",
    "eating out": "Restaurantes",
    "food delivery": "Alimentação",
    "transportation": "Transporte",
    "taxi and ride-hailing": "Transporte",
    "gas stations": "Combustível",
    "health": "Saúde",
    "pharmacy": "Farmácia",
    "education": "Educação",
    "shopping": "Compras",
    "online shopping": "Compras",
    "leisure": "Lazer",
    "digital services": "Assinaturas",
    "travel": "Viagem",
    "taxes": "Impostos",
    "bank fees": "Tarifas bancárias",
    "investments": "Investimentos",
    "transfers": "Transferências",
    "salary": "Salário",
    "income": "Renda",
}
UNCATEGORIZED = "Outros"
