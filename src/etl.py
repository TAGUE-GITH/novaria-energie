"""
Novaria - ETL des quatre sources énergétiques (TP 1 à 6).

Reproduit en Python la logique Power Query du fil rouge :
    01_Staging  -> lecture brute, aucune correction
    02_Controles -> détection (vides, doublons, valeurs impossibles)
    Rejets_*    -> lignes exclues avec leur raison
    Int_*       -> données propres, typées, au bon grain
    FactEnergie_Preparee -> consommations + météo + tarif applicable
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SQL = ROOT / "data" / "sql_export"
OUT = ROOT / "output"

MOIS_FR = {
    "jan": 1, "fev": 2, "mar": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aou": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ---------------------------------------------------------------- utilitaires
def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def nombre_fr(valeur) -> float:
    """'7,8 °C' -> 7.8 ; '19,10 €' -> 19.1 ; '134 kWh/m²' -> 134.0 ; vide -> NaN."""
    if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
        return np.nan
    if isinstance(valeur, (int, float)):
        return float(valeur)
    texte = str(valeur).replace(" ", " ").strip().replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", texte)
    return float(m.group()) if m else np.nan


def mois_fr(valeur) -> pd.Timestamp | None:
    """Ramène une date hétérogène au premier jour du mois. None si imprécise (ex. '2026 T2')."""
    if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
        return None
    texte = sans_accents(str(valeur)).lower().strip()
    patrons = [
        (r"^(\d{4})-(\d{2})-(\d{2})( 00:00:00)?$", lambda m: (m[1], m[2])),   # 2024-01-01
        (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", lambda m: (m[3], m[2])),           # 15/04/2025
        (r"^(\d{4})[-/](\d{1,2})$", lambda m: (m[1], m[2])),                  # 2024-04, 2024/06
        (r"^(\d{1,2})/(\d{4})$", lambda m: (m[2], m[1])),                     # 06/2024
    ]
    for patron, extraire in patrons:
        m = re.match(patron, texte)
        if m:
            annee, mois = extraire(m)
            return pd.Timestamp(int(annee), int(mois), 1)
    # 'janvier 2024', '1er fevrier 2024', 'mars-24', 'sept. 2024', 'aout 25'
    m = re.match(r"^(?:\d{1,2}(?:er)?\s+)?([a-z]+)\.?[\s-]+(\d{2}|\d{4})$", texte)
    if m:
        for prefixe, num in MOIS_FR.items():
            if m[1].startswith(prefixe):
                annee = int(m[2]) + (2000 if len(m[2]) == 2 else 0)
                return pd.Timestamp(annee, num, 1)
    return None


def ecrire(df: pd.DataFrame, dossier: str, nom: str) -> None:
    chemin = OUT / dossier
    chemin.mkdir(parents=True, exist_ok=True)
    df.to_csv(chemin / f"{nom}.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")


# ---------------------------------------------------------------- TP 1 : staging
def stg_consommations() -> pd.DataFrame:
    return pd.read_csv(SQL / "VW_ConsommationsEnergetiques.csv.gz", parse_dates=["DateMesure", "DateChargement"])


def stg_meteo() -> pd.DataFrame:
    return pd.read_excel(RAW / "MeteoQuartier_Brut.xlsx", dtype=str)


def stg_tarifs() -> pd.DataFrame:
    return pd.read_csv(RAW / "TarifsEnergie_Brut.csv", sep=";", dtype=str, encoding="utf-8")


def stg_audits() -> pd.DataFrame:
    with open(RAW / "AuditsEnergetiques_Brut.json", encoding="utf-8") as f:
        brut = json.load(f)
    # équivalent Power Query : Convertir en table + développer l'enregistrement "audit"
    return pd.json_normalize(brut, sep="_").rename(columns=lambda c: c.replace("audit_", ""))


def referentiels():
    quartiers = pd.read_csv(SQL / "Quartier.csv")
    batiments = pd.read_csv(SQL / "Batiment.csv")
    energies = pd.read_csv(SQL / "TypeEnergie.csv")
    return quartiers, batiments, energies


# ---------------------------------------------------------------- TP 2 : contrôles
def profil(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Équivalent des outils Qualité / Distribution / Profil de colonne de Power Query."""
    lignes = []
    for col in df.columns:
        s = df[col]
        vides = s.isna() | s.astype(str).str.strip().eq("")
        lignes.append({
            "Source": source, "Colonne": col, "Lignes": len(s),
            "Vides": int(vides.sum()), "PctVides": round(100 * vides.mean(), 1),
            "Distinctes": int(s.nunique(dropna=True)),
        })
    return pd.DataFrame(lignes)


def ctl_doublons(df: pd.DataFrame, cle: list[str]) -> pd.DataFrame:
    """Regrouper par la clé métier, NombreOccurrences > 1."""
    g = df.groupby(cle, dropna=False).size().reset_index(name="NombreOccurrences")
    return g[g["NombreOccurrences"] > 1]


# ---------------------------------------------------------------- TP 3 : consommations
def int_consommations(stg: pd.DataFrame):
    ctl = stg.copy()
    for col in ["CodeBatiment", "CodeEnergie", "CodeQuartier"]:
        ctl[col] = ctl[col].astype(str).str.strip().str.upper()

    regles = [
        (ctl["IdBatiment"].isna(), "Bâtiment absent"),
        (ctl["IdTypeEnergie"].isna(), "Énergie absente"),
        (ctl["DateMesure"].isna(), "Date absente"),
        (ctl["QuantiteKWh"].isna(), "Quantité absente"),
        (ctl["QuantiteKWh"] < 0, "Quantité négative"),
        (ctl["CoutEuro"].isna(), "Coût absent"),
        (ctl["CoutEuro"] < 0, "Coût négatif"),
        (ctl["EmissionCO2Kg"] < 0, "Émission négative"),
    ]
    ctl["RaisonRejet"] = np.select([c for c, _ in regles], [r for _, r in regles], default=None)

    rejets = ctl[ctl["RaisonRejet"].notna()].copy()
    valides = ctl[ctl["RaisonRejet"].isna()].drop(columns="RaisonRejet")

    # Dédoublonnage déterministe : dernier chargement, puis IdReleve le plus élevé
    valides = valides.sort_values(["DateChargement", "IdReleve"], ascending=False)
    doublons = valides[valides.duplicated(["IdBatiment", "IdTypeEnergie", "DateMesure"])].assign(
        RaisonRejet="Doublon (relevé plus ancien)")
    valides = valides.drop_duplicates(["IdBatiment", "IdTypeEnergie", "DateMesure"])
    rejets = pd.concat([rejets, doublons])

    valides["Mois"] = valides["DateMesure"].dt.to_period("M").dt.to_timestamp()
    surface = valides["SurfaceM2"].where(valides["SurfaceM2"] > 0)          # division protégée
    valides["ConsoKWhM2"] = valides["QuantiteKWh"] / surface
    valides["EmissionCO2KgM2"] = valides["EmissionCO2Kg"] / surface
    valides = valides.sort_values(["DateMesure", "IdBatiment", "IdTypeEnergie"]).reset_index(drop=True)
    return valides, rejets


# ---------------------------------------------------------------- TP 4 : météo
ALIAS_QUARTIER = {"NORD": "NOR", "OUEST": "OUE", "SUD-EST": "SES", "NORD-EST": "NES", "SUD-OUEST": "SOU"}

BORNES_METEO = {  # domaines plausibles pour un relevé mensuel à Novaria
    "TemperatureMoyenne": (-20, 35), "TemperatureMin": (-30, 30), "TemperatureMax": (-15, 45),
    "Pluviometrie": (0, 400), "DJUChauffage": (0, 700), "Ensoleillement": (0, 400),
}


def normaliser_code_quartier(code: str, codes_valides: set[str]) -> str:
    c = str(code).strip().upper()
    c = ALIAS_QUARTIER.get(c, c)
    if c in codes_valides:
        return c
    c2 = re.sub(r"[^A-Z0-9]", "", c).replace("0", "O")   # 'EST-' -> 'EST', 'S0U' -> 'SOU'
    return c2 if c2 in codes_valides else c


def int_meteo(stg: pd.DataFrame, quartiers: pd.DataFrame):
    codes = set(quartiers["CodeQuartier"])
    m = stg.copy()
    m["CodeQuartierSource"] = m["CodeQuartier"]
    m["CodeQuartier"] = m["CodeQuartier"].map(lambda c: normaliser_code_quartier(c, codes))
    m["Mois"] = m["DateReleve"].map(mois_fr)
    for col in BORNES_METEO:
        m[col] = m[col].map(nombre_fr)
    m["DateImport"] = pd.to_datetime(m["DateImport"], errors="coerce")

    hors_domaine = pd.Series(False, index=m.index)
    for col, (bas, haut) in BORNES_METEO.items():
        hors_domaine |= m[col].notna() & ~m[col].between(bas, haut)
    incoherent = m["TemperatureMoyenne"].notna() & (
        (m["TemperatureMoyenne"] < m["TemperatureMin"]) | (m["TemperatureMoyenne"] > m["TemperatureMax"]))

    regles = [
        (~m["CodeQuartier"].isin(codes), "Quartier inconnu"),
        (m["Mois"].isna(), "Date imprécise ou illisible"),
        (m["TemperatureMoyenne"].isna() | m["DJUChauffage"].isna(), "Mesure obligatoire absente"),
        (hors_domaine, "Valeur hors domaine"),
        (incoherent, "Température moyenne hors [min ; max]"),
    ]
    m["RaisonRejet"] = np.select([c for c, _ in regles], [r for _, r in regles], default=None)
    rejets = m[m["RaisonRejet"].notna()].copy()
    valides = m[m["RaisonRejet"].isna()].drop(columns="RaisonRejet")

    # Grain quartier-mois : on garde l'import le plus récent
    valides = valides.sort_values(["DateImport", "IdReleveExterne"], ascending=False)
    doublons = valides[valides.duplicated(["CodeQuartier", "Mois"])].assign(
        RaisonRejet="Doublon quartier-mois (import plus ancien)")
    valides = valides.drop_duplicates(["CodeQuartier", "Mois"])
    rejets = pd.concat([rejets, doublons])

    valides = valides.merge(quartiers[["IdQuartier", "CodeQuartier"]], on="CodeQuartier", how="left")
    assert valides.groupby(["CodeQuartier", "Mois"]).size().max() == 1, "grain quartier-mois non unique"
    colonnes = ["IdReleveExterne", "IdQuartier", "CodeQuartier", "CodeQuartierSource", "Mois", "DateReleve",
                *BORNES_METEO, "SourceStation", "DateImport"]
    return valides[colonnes].sort_values(["Mois", "IdQuartier"]).reset_index(drop=True), rejets


# ---------------------------------------------------------------- TP 5 : tarifs et audits
def int_tarifs(stg: pd.DataFrame, energies: pd.DataFrame):
    t = stg.copy()
    t["CodeEnergie"] = t["CodeEnergie"].str.strip().str.upper()
    t["DateEffet"] = t["MoisTarif"].map(mois_fr)
    t["PrixKWhEuro"] = t["PrixKWhEuro"].map(nombre_fr)
    t["AbonnementMensuelEuro"] = t["AbonnementMensuelEuro"].map(nombre_fr)   # vide -> null, pas 0

    regles = [
        (~t["CodeEnergie"].isin(energies["CodeEnergie"]), "Énergie inconnue"),
        (t["DateEffet"].isna(), "Date d'effet illisible"),
        (t["PrixKWhEuro"].isna(), "Prix absent"),
        (t["PrixKWhEuro"] < 0, "Prix négatif"),
    ]
    t["RaisonRejet"] = np.select([c for c, _ in regles], [r for _, r in regles], default=None)
    rejets = t[t["RaisonRejet"].notna()].copy()
    valides = t[t["RaisonRejet"].isna()].drop(columns="RaisonRejet")

    doublons = valides[valides.duplicated(["CodeEnergie", "DateEffet"])].assign(
        RaisonRejet="Doublon énergie + date d'effet")
    valides = valides.drop_duplicates(["CodeEnergie", "DateEffet"])
    rejets = pd.concat([rejets, doublons])

    valides = valides.merge(energies[["IdTypeEnergie", "CodeEnergie"]], on="CodeEnergie")
    valides["MoisTarif"] = valides["DateEffet"]
    colonnes = ["IdTypeEnergie", "CodeEnergie", "DateEffet", "MoisTarif", "PrixKWhEuro",
                "AbonnementMensuelEuro", "Fournisseur", "SourceTarif"]
    return valides[colonnes].sort_values(["CodeEnergie", "DateEffet"]).reset_index(drop=True), rejets


ORDRE_PRIORITE = {"Faible": 1, "Moyenne": 2, "Haute": 3, "Urgente": 4}


def int_audits(stg: pd.DataFrame, batiments: pd.DataFrame):
    a = stg.rename(columns={"codeBatiment": "CodeBatiment", "dateAudit": "DateAudit",
                            "classeEnergetique": "ClasseEnergetique",
                            "consommationReferenceKWhM2": "ConsommationReferenceKWhM2",
                            "priorite": "Priorite", "recommandation": "Recommandation",
                            "coutEstimeEuro": "CoutEstimeEuro"}).copy()
    a["CodeBatiment"] = a["CodeBatiment"].str.strip().str.upper()
    # ISO (2024-04-12) d'abord, puis format français (15/05/2024) : jamais d'inversion jour/mois
    a["DateAudit"] = pd.to_datetime(a["DateAudit"], format="%Y-%m-%d", errors="coerce").fillna(
        pd.to_datetime(a["DateAudit"], format="%d/%m/%Y", errors="coerce"))
    a["ConsommationReferenceKWhM2"] = a["ConsommationReferenceKWhM2"].map(nombre_fr)
    a["CoutEstimeEuro"] = pd.to_numeric(a["CoutEstimeEuro"])                  # null reste null
    a["Priorite"] = a["Priorite"].str.strip().str.capitalize()
    a["ClasseEnergetique"] = a["ClasseEnergetique"].str.strip().str.upper()
    a["StatutChiffrage"] = np.where(a["CoutEstimeEuro"].isna(), "À chiffrer", "Chiffré")
    a["OrdrePriorite"] = a["Priorite"].map(ORDRE_PRIORITE)

    a = a.merge(batiments[["IdBatiment", "CodeBatiment"]], on="CodeBatiment", how="left")
    regles = [
        (a["IdBatiment"].isna(), "Bâtiment inconnu du référentiel"),
        (a["OrdrePriorite"].isna(), "Priorité non normalisée"),
        (a["CoutEstimeEuro"] < 0, "Coût négatif"),
    ]
    a["RaisonRejet"] = np.select([c for c, _ in regles], [r for _, r in regles], default=None)
    rejets = a[a["RaisonRejet"].notna()].copy()
    valides = a[a["RaisonRejet"].isna()].drop(columns="RaisonRejet")
    doublons = valides[valides.duplicated(["CodeBatiment", "DateAudit"])].assign(RaisonRejet="Doublon audit")
    valides = valides.drop_duplicates(["CodeBatiment", "DateAudit"])
    rejets = pd.concat([rejets, doublons])
    valides["IdBatiment"] = valides["IdBatiment"].astype(int)
    return valides.reset_index(drop=True), rejets


# ---------------------------------------------------------------- TP 6 : combinaison
def fact_energie_preparee(conso: pd.DataFrame, meteo: pd.DataFrame, tarifs: pd.DataFrame) -> pd.DataFrame:
    n_avant, kwh_avant = len(conso), conso["QuantiteKWh"].sum()

    # Météo : jointure gauche quartier + mois, la clé droite doit être unique
    met = meteo[["IdQuartier", "Mois", "TemperatureMoyenne", "DJUChauffage", "Pluviometrie", "Ensoleillement"]]
    met = met.rename(columns={"TemperatureMoyenne": "TemperatureMoyenneMois"}).assign(MeteoTrouvee=True)
    f = conso.merge(met, on=["IdQuartier", "Mois"], how="left", validate="many_to_one")
    f["MeteoTrouvee"] = f["MeteoTrouvee"].fillna(False).astype(bool)
    assert len(f) == n_avant, "la fusion météo a multiplié les faits"

    # Tarif : dernier tarif dont la date d'effet <= mois de consommation (jointure "as of")
    tar = tarifs[["IdTypeEnergie", "DateEffet", "PrixKWhEuro"]].sort_values("DateEffet")
    f = f.sort_values("Mois")
    f = pd.merge_asof(f, tar, left_on="Mois", right_on="DateEffet", by="IdTypeEnergie", direction="backward")
    f = f.rename(columns={"PrixKWhEuro": "PrixApplicableKWh", "DateEffet": "DateEffetTarif"})
    f["TarifTrouve"] = f["PrixApplicableKWh"].notna()
    assert len(f) == n_avant and np.isclose(f["QuantiteKWh"].sum(), kwh_avant), "réconciliation KO"

    production = f["TypeFlux"].eq("Production")
    f["CoutRecalcule"] = np.where(production, 0.0, (f["QuantiteKWh"] * f["PrixApplicableKWh"]).round(2))
    f["EcartCout"] = (f["CoutRecalcule"] - f["CoutEuro"]).round(2)
    return f.sort_values(["DateMesure", "IdBatiment", "IdTypeEnergie"]).reset_index(drop=True)


# ---------------------------------------------------------------- orchestration
def executer() -> dict:
    quartiers, batiments, energies = referentiels()
    stg = {"Consommations": stg_consommations(), "Meteo": stg_meteo(),
           "Tarifs": stg_tarifs(), "Audits": stg_audits()}
    for nom, df in stg.items():
        ecrire(df.head(200) if nom == "Consommations" else df, "01_staging", f"Stg_{nom}")

    # TP 2 : profil + doublons sur clé métier (avant nettoyage)
    cles = {"Consommations": ["IdBatiment", "IdTypeEnergie", "DateMesure"],
            "Meteo": ["CodeQuartier", "DateReleve"], "Tarifs": ["CodeEnergie", "MoisTarif"],
            "Audits": ["codeBatiment", "dateAudit"]}
    profils = pd.concat([profil(df, nom) for nom, df in stg.items()])
    ecrire(profils, "02_controles", "Profil_colonnes")
    for nom, df in stg.items():
        ecrire(ctl_doublons(df, cles[nom]), "02_controles", f"Ctl_Doublons_{nom}")

    conso, rej_conso = int_consommations(stg["Consommations"])
    meteo, rej_meteo = int_meteo(stg["Meteo"], quartiers)
    tarifs, rej_tarifs = int_tarifs(stg["Tarifs"], energies)
    audits, rej_audits = int_audits(stg["Audits"], batiments)
    fact = fact_energie_preparee(conso, meteo, tarifs)

    resultats = {
        "Consommations": (stg["Consommations"], conso, rej_conso),
        "Meteo": (stg["Meteo"], meteo, rej_meteo),
        "Tarifs": (stg["Tarifs"], tarifs, rej_tarifs),
        "Audits": (stg["Audits"], audits, rej_audits),
    }
    bilan = []
    for nom, (brut, valide, rejet) in resultats.items():
        ecrire(rejet, "03_rejets", f"Rejets_{nom}")
        ecrire(valide if nom != "Consommations" else valide.head(500), "04_intermediaires", f"Int_{nom}")
        bilan.append({"Source": nom, "Initial": len(brut), "Valides": len(valide), "Rejets": len(rejet),
                      "Reconcilie": len(brut) == len(valide) + len(rejet)})
    bilan = pd.DataFrame(bilan)
    ecrire(bilan, "02_controles", "Bilan_reconciliation")

    # Réconciliation TP 6 par énergie / quartier / année
    recon = fact.groupby([fact["DateMesure"].dt.year.rename("Annee"), "CodeQuartier", "CodeEnergie"]).agg(
        KWhFact=("QuantiteKWh", "sum")).join(
        conso.groupby([conso["DateMesure"].dt.year.rename("Annee"), "CodeQuartier", "CodeEnergie"]).agg(
            KWhInt=("QuantiteKWh", "sum"))).reset_index()
    recon["Ecart"] = (recon["KWhFact"] - recon["KWhInt"]).round(3)
    ecrire(recon, "05_combinaison", "Reconciliation_Fact_vs_Int")
    ecrire(fact[~fact["MeteoTrouvee"] | ~fact["TarifTrouve"]]
           .groupby(["CodeQuartier", "CodeEnergie", "Mois", "MeteoTrouvee", "TarifTrouve"]).size()
           .reset_index(name="NbFaits"), "05_combinaison", "Correspondances_manquantes")

    return {"quartiers": quartiers, "batiments": batiments, "energies": energies, "stg": stg,
            "profils": profils, "conso": conso, "meteo": meteo, "tarifs": tarifs, "audits": audits,
            "rejets": {"Consommations": rej_conso, "Meteo": rej_meteo, "Tarifs": rej_tarifs, "Audits": rej_audits},
            "fact": fact, "bilan": bilan, "recon": recon}
