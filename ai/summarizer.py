"""
Résumé IA d'entreprise pour StockInvest Pro.

Utilise OpenAI API si configuré (config.ini: ai.use_openai=true), sinon
retombe sur un résumé local basé sur un template structuré alimenté par
les données quant/fondamentales déjà calculées (pas de génération libre
non vérifiable).
"""

from dataclasses import dataclass

from core.models import CompanyInfo, QuantScore
from utils.logger import logger


@dataclass
class CompanySummary:
    """Résumé structuré généré pour l'onglet Deep Dive."""

    ticker: str
    overview: str
    positives: list[str]
    risks: list[str]
    key_events: list[str]
    source: str  # "openai" ou "local"


class CompanySummarizer:
    """Génère un résumé d'entreprise, avec fallback local si OpenAI n'est pas configuré."""

    def __init__(self, use_openai: bool = False, openai_api_key: str | None = None) -> None:
        self.use_openai = use_openai and bool(openai_api_key)
        self.openai_api_key = openai_api_key

    def summarize(
        self,
        company: CompanyInfo,
        quant_score: QuantScore,
        recent_headlines: list[str] | None = None,
    ) -> CompanySummary:
        if self.use_openai:
            try:
                return self._summarize_openai(company, quant_score, recent_headlines or [])
            except Exception as exc:
                logger.warning(f"Échec résumé OpenAI pour {company.ticker}, fallback local: {exc}")

        return self._summarize_local(company, quant_score, recent_headlines or [])

    def _summarize_openai(
        self, company: CompanyInfo, quant_score: QuantScore, headlines: list[str]
    ) -> CompanySummary:
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_api_key)

        prompt = (
            f"Entreprise: {company.name} ({company.ticker}), secteur {company.sector.value}. "
            f"Score quantitatif global: {quant_score.global_score}/100. "
            f"Points forts identifiés: {', '.join(quant_score.strengths)}. "
            f"Points faibles identifiés: {', '.join(quant_score.weaknesses)}. "
            f"Titres de news récents: {'; '.join(headlines[:5]) if headlines else 'aucun'}. "
            "Rédige un résumé factuel et neutre en 3 parties strictement basées sur ces données "
            "(ne pas inventer de chiffres) : Vue d'ensemble, Points positifs (liste), Risques (liste)."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""

        return CompanySummary(
            ticker=company.ticker,
            overview=content,
            positives=quant_score.strengths,
            risks=quant_score.weaknesses,
            key_events=headlines[:5],
            source="openai",
        )

    def _summarize_local(
        self, company: CompanyInfo, quant_score: QuantScore, headlines: list[str]
    ) -> CompanySummary:
        """Résumé template déterministe, sans dépendance externe."""
        overview = (
            f"{company.name} ({company.ticker}) évolue dans le secteur {company.sector.value}. "
            f"Le score quantitatif multi-facteurs actuel est de {quant_score.global_score}/100, "
            f"calculé par comparaison avec les entreprises du même secteur."
        )

        return CompanySummary(
            ticker=company.ticker,
            overview=overview,
            positives=quant_score.strengths,
            risks=quant_score.weaknesses,
            key_events=headlines[:5],
            source="local",
        )
