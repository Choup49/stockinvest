# StockInvest Pro

Terminal quantitatif desktop professionnel — aide à la décision financière inspirée de Bloomberg Terminal / TradingView.

**Ce projet n'est PAS un robot de trading.** Il ne prédit pas les prix. Il analyse des données existantes (prix, fondamentaux, sentiment) pour aider l'utilisateur à prendre de meilleures décisions.

---

## Installation

```bash
# 1. Cloner / copier le projet, puis se placer à la racine
cd StockInvestPro

# 2. Créer un environnement virtuel (recommandé)
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
python main.py
```

Au premier lancement, `config.ini` est créé automatiquement s'il n'existe pas, et la base SQLite `stockinvest.db` est initialisée avec toutes les tables.

---

## Configuration (`config.ini`)

```ini
[database]
url = sqlite:///stockinvest.db          # ou postgresql://user:pass@host/db

[pipeline]
min_dollar_volume = 250000              # filtre de liquidité ($/jour)
default_period = 2y                     # fenêtre d'historique par défaut

[ai]
use_openai = false                      # true pour activer les résumés OpenAI
openai_api_key =                        # requis si use_openai = true

[theme]
background = #0B0C10
surface = #15171C
border = #2A2D35
```

---

## Architecture

```
StockInvestPro/
├── main.py              # point d'entrée
├── core/                # modèles métier, enums, exceptions (aucune logique)
├── data/                # ingestion Yahoo Finance, nettoyage, features, persistance
├── quant/                # moteur multi-facteurs (Value/Growth/Quality/Momentum/Risk/Technical)
├── ai/                   # sentiment, détection d'anomalies, résumés IA
├── backtest/              # simulateur de stratégie + métriques de performance
├── ui/                   # PySide6 — AUCUNE logique métier, uniquement présentation
├── utils/                 # config, logger
└── tests/                 # tests unitaires (pytest)
```

**Règle d'architecture stricte** : `ui/` ne fait jamais de calcul. Chaque widget appelle des services de `data`/`quant`/`ai`/`backtest` et affiche le résultat. Ça permet de tester tout le moteur sans jamais lancer Qt.

### Flux de données

```
yfinance (data/fetcher.py)
    → nettoyage (data/cleaner.py) → QualityReport
    → feature engineering (data/features.py)
    → extraction facteurs (quant/factors.py)
    → normalisation sectorielle (quant/normalizer.py)
    → scoring multi-facteurs (quant/scoring.py) → QuantScore /100
    → persistance (data/repository.py)
    → affichage (ui/pages/*)
```

---

## Utilisation

- **Command Center** : vue d'ensemble marché — heatmap secteurs, régime de marché, top movers.
- **Deep Dive** : analyse complète d'une entreprise — chart, fondamentaux, score quant, sentiment, résumé IA.
- **Quant Engine** : tableau de tous les scores, filtrable par pays/secteur/score minimum, exportable en CSV.
- **Simulator** : configuration de stratégie (Top-N, rééquilibrage, frais, slippage) et résultats de backtest (CAGR, Sharpe, Max Drawdown, comparaison benchmark).

Cliquer sur un ticker dans le Market Watch (panneau gauche) ou dans le tableau Quant Engine ouvre automatiquement le Deep Dive correspondant.

---

## Tests

```bash
pytest tests/ -v
```

Chaque module métier (`cleaner`, `features`, `factors`, `scoring`, `backtest`) est testé indépendamment de l'UI.

---

## Extension

- **Nouvelle source de données** : implémenter une classe respectant l'interface de `YahooFinanceFetcher` dans `data/`, puis l'injecter dans le pipeline.
- **Nouveau facteur quantitatif** : ajouter l'extraction dans `quant/factors.py`, l'enum dans `core/enums.py::FactorType`, et le poids dans `quant/scoring.py::FACTOR_WEIGHTS` (la somme des poids doit rester égale à 1.0, validé automatiquement au démarrage).
- **PostgreSQL** : changer uniquement `database.url` dans `config.ini`, aucune autre modification nécessaire.
- **Packaging exécutable** :
  ```bash
  pyinstaller --name StockInvestPro --windowed --onefile main.py
  ```

---

## Stack technique

Python 3.11+ · PySide6/Qt6 · pyqtgraph · pandas/numpy/polars · yfinance · SQLAlchemy · HuggingFace Transformers · scikit-learn · loguru · PyInstaller
