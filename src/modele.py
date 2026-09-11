"""
Novaria - TP 7 : modèle en étoile (FactEnergie, FactAudit, DimBatiment, DimQuartier, DimEnergie, DimDate).
"""
from __future__ import annotations

import pandas as pd

from etl import ecrire

SEUIL_NIVEAU_KWH = 10_000


def dim_date(debut: str, fin: str) -> pd.DataFrame:
    d = pd.DataFrame({"Date": pd.date_range(debut, fin, freq="D")})
    d["Annee"] = d["Date"].dt.year
    d["Trimestre"] = "T" + d["Date"].dt.quarter.astype(str)
    d["MoisNum"] = d["Date"].dt.month
    d["Mois"] = d["Date"].dt.strftime("%m - %b")
    d["AnneeMois"] = d["Date"].dt.strftime("%Y-%m")
    d["DebutMois"] = d["Date"].dt.to_period("M").dt.to_timestamp()
    d["EstWeekEnd"] = d["Date"].dt.dayofweek >= 5
    return d


def construire(r: dict) -> dict:
    conso, fact, audits = r["conso"], r["fact"], r["audits"]

    dim_batiment = (conso[["IdBatiment", "CodeBatiment", "NomBatiment", "TypeBatiment", "SurfaceM2",
                           "AnneeConstruction", "NbOccupantsMoyen", "EstRenove", "IdQuartier"]]
                    .drop_duplicates("IdBatiment").sort_values("IdBatiment").reset_index(drop=True))
    dim_quartier = (conso[["IdQuartier", "CodeQuartier", "NomQuartier", "Population"]]
                    .drop_duplicates("IdQuartier").sort_values("IdQuartier").reset_index(drop=True))
    dim_energie = (conso[["IdTypeEnergie", "CodeEnergie", "LibelleEnergie", "EstRenouvelable"]]
                   .drop_duplicates("IdTypeEnergie").sort_values("IdTypeEnergie").reset_index(drop=True))
    # Une ligne par jour, années complètes : indispensable pour DATEADD / N-1
    dimdate = dim_date(f"{fact['DateMesure'].dt.year.min()}-01-01", f"{fact['DateMesure'].dt.year.max()}-12-31")

    fact_energie = fact[["IdReleve", "DateMesure", "IdBatiment", "IdQuartier", "IdTypeEnergie", "TypeFlux",
                         "QuantiteKWh", "CoutEuro", "CoutRecalcule", "EcartCout", "EmissionCO2Kg",
                         "TemperatureMoyenne", "TemperatureMoyenneMois", "DJUChauffage", "PrixApplicableKWh",
                         "MeteoTrouvee", "TarifTrouve"]].copy()
    # Colonne calculée : une valeur par ligne, sert d'axe / de filtre
    fact_energie["NiveauConsommation"] = fact_energie["QuantiteKWh"].gt(SEUIL_NIVEAU_KWH).map(
        {True: "Élevée", False: "Normale"})

    fact_audit = audits[["IdBatiment", "CodeBatiment", "DateAudit", "ClasseEnergetique",
                         "ConsommationReferenceKWhM2", "Priorite", "OrdrePriorite", "Recommandation",
                         "CoutEstimeEuro", "StatutChiffrage"]].copy()

    # Contrôles du modèle
    assert len(dim_batiment) == 12 and dim_batiment["IdBatiment"].is_unique
    assert len(dim_quartier) == 8 and dim_quartier["IdQuartier"].notna().all()
    assert len(dim_energie) == 4
    assert len(fact_audit) == 12
    assert fact_energie["DateMesure"].isin(dimdate["Date"]).all()
    for cle, dim in [("IdBatiment", dim_batiment), ("IdQuartier", dim_quartier), ("IdTypeEnergie", dim_energie)]:
        assert fact_energie[cle].isin(dim[cle]).all(), f"clé orpheline {cle}"

    modele = {"FactEnergie": fact_energie, "FactAudit": fact_audit, "DimBatiment": dim_batiment,
              "DimQuartier": dim_quartier, "DimEnergie": dim_energie, "DimDate": dimdate}
    for nom, df in modele.items():
        if nom != "FactEnergie":
            ecrire(df, "06_modele", nom)
    fact_energie.to_csv(ecrire_chemin("06_modele", "FactEnergie.csv.gz"), index=False, sep=";", decimal=",")
    return modele


def ecrire_chemin(dossier: str, nom: str):
    from etl import OUT
    (OUT / dossier).mkdir(parents=True, exist_ok=True)
    return OUT / dossier / nom
