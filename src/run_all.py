"""Exécute toute la chaîne Novaria : ETL (TP 1-6) -> modèle en étoile (TP 7) -> synthèse (TP 8)."""
import etl
import modele
import rapport

if __name__ == "__main__":
    resultats = etl.executer()
    print(resultats["bilan"].to_string(index=False))
    etoile = modele.construire(resultats)
    print({nom: len(df) for nom, df in etoile.items()})
    synthese = rapport.construire(etoile)
    print(synthese["kpi"].to_string(index=False))
    print(f"Sorties écrites dans {etl.OUT}")
