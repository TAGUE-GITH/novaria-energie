"""
Novaria - TP 8 : page « 1 - Synthèse énergie » et décision provisoire.

Les mesures sont calculées ici comme en DAX (voir powerbi/dax/mesures.dax) pour
produire une maquette statique de la page et une décision chiffrée.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from etl import OUT, ecrire

COULEURS = {"ELEC": "#2563EB", "GAZ": "#F59E0B", "RCU": "#DC2626", "SOLAIRE": "#16A34A"}
ENCRE, GRIS = "#1F2937", "#6B7280"


def kwh(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " kWh"


def euros(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " €"


def mesures_annuelles(fe: pd.DataFrame, dims: dict) -> pd.DataFrame:
    """Consommation totale, coût, émissions, kWh/m², N-1 (période comparable)."""
    c = fe[fe["TypeFlux"] == "Consommation"].copy()
    c["Annee"] = c["DateMesure"].dt.year
    derniere = fe["DateMesure"].max()
    surface = dims["DimBatiment"]["SurfaceM2"].sum()
    lignes = []
    for annee, g in c.groupby("Annee"):
        # N-1 sur la même période : l'année en cours s'arrête au dernier jour chargé
        fin_n1 = min(pd.Timestamp(annee - 1, 12, 31), derniere - pd.DateOffset(years=1))
        n1 = c[(c["Annee"] == annee - 1) & (c["DateMesure"] <= fin_n1)]["QuantiteKWh"].sum()
        total = g["QuantiteKWh"].sum()
        lignes.append({
            "Annee": annee, "Periode": f"{g['DateMesure'].min():%d/%m} → {g['DateMesure'].max():%d/%m}",
            "ConsommationTotaleKWh": round(total), "CoutTotalEuro": round(g["CoutEuro"].sum(), 2),
            "CoutRecalculeEuro": round(g["CoutRecalcule"].sum(), 2),
            "EmissionsTCO2": round(g["EmissionCO2Kg"].sum() / 1000, 1),
            "KWhParM2": round(total / surface, 1),
            "ConsommationN1KWh": round(n1) if n1 else None,
            "EcartN1KWh": round(total - n1) if n1 else None,
            "EvolutionN1Pct": round(100 * (total - n1) / n1, 1) if n1 else None,
        })
    return pd.DataFrame(lignes)


def construire(modele: dict) -> dict:
    fe = modele["FactEnergie"].merge(modele["DimBatiment"][["IdBatiment", "NomBatiment", "CodeBatiment",
                                                            "TypeBatiment", "SurfaceM2"]], on="IdBatiment")
    fe = fe.merge(modele["DimEnergie"][["IdTypeEnergie", "CodeEnergie"]], on="IdTypeEnergie")
    fe = fe.merge(modele["DimQuartier"][["IdQuartier", "NomQuartier"]], on="IdQuartier")
    conso = fe[fe["TypeFlux"] == "Consommation"].copy()
    conso["Annee"] = conso["DateMesure"].dt.year

    kpi = mesures_annuelles(fe, modele)
    ecrire(kpi, "07_rapport", "KPI_annuels")

    # Test TP 7 : la matrice année > quartier > énergie se réconcilie avec le total global
    matrice = conso.groupby(["Annee", "NomQuartier", "CodeEnergie"])["QuantiteKWh"].sum()
    assert abs(matrice.sum() - conso["QuantiteKWh"].sum()) < 1e-6
    ecrire(matrice.round(0).reset_index(), "07_rapport", "Matrice_Annee_Quartier_Energie")

    # Colonne calculée vs mesure
    niveau = conso.groupby(["Annee", "NiveauConsommation"])["QuantiteKWh"].agg(["size", "sum"]).reset_index()
    niveau.columns = ["Annee", "NiveauConsommation", "NbReleves", "ConsommationTotaleKWh"]
    ecrire(niveau, "07_rapport", "Niveau_consommation")

    top = (conso.groupby(["CodeBatiment", "NomBatiment", "TypeBatiment", "SurfaceM2"])
           .agg(ConsommationKWh=("QuantiteKWh", "sum"), CoutEuro=("CoutEuro", "sum"),
                EmissionsKgCO2=("EmissionCO2Kg", "sum"))
           .reset_index().sort_values("ConsommationKWh", ascending=False).reset_index(drop=True))
    top["KWhParM2"] = top["ConsommationKWh"] / top["SurfaceM2"]
    top["PartPct"] = 100 * top["ConsommationKWh"] / top["ConsommationKWh"].sum()
    top_2025 = (conso[conso["Annee"] == 2025].groupby("NomBatiment")["QuantiteKWh"].sum()
                .sort_values(ascending=False))
    ecrire(top.round(1), "07_rapport", "Top_batiments")

    production = fe[fe["TypeFlux"] == "Production"]["QuantiteKWh"].sum()
    graphique(conso, kpi, top, fe)
    decision(kpi, top, top_2025, production, conso)
    return {"kpi": kpi, "top": top, "top_2025": top_2025, "production": production}


def graphique(conso: pd.DataFrame, kpi: pd.DataFrame, top: pd.DataFrame, fe: pd.DataFrame) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#D1D5DB", "axes.labelcolor": ENCRE, "xtick.color": GRIS,
                         "ytick.color": GRIS, "axes.titleweight": "bold", "axes.titlesize": 12})
    fig = plt.figure(figsize=(16, 9), facecolor="white")
    grille = fig.add_gridspec(3, 4, height_ratios=[0.55, 1.4, 1.4], hspace=0.55, wspace=0.35)
    fig.suptitle("Novaria — 1 · Synthèse énergie", x=0.02, ha="left", fontsize=20, fontweight="bold", color=ENCRE)
    fig.text(0.02, 0.925, "Bâtiments publics · consommations du 01/01/2024 au 30/06/2026 · flux « Consommation »",
             color=GRIS, fontsize=10)

    ref = kpi[kpi["Annee"] == 2025].iloc[0]
    cartes = [
        ("Consommation 2025", kwh(ref.ConsommationTotaleKWh), f"N-1 : {ref.EvolutionN1Pct:+.1f} % | {ref.EcartN1KWh:+,.0f} kWh".replace(",", " ")),
        ("kWh/m² 2025", f"{ref.KWhParM2:.0f} kWh/m²", f"{len(top)} bâtiments · {top['SurfaceM2'].sum():,.0f} m²".replace(",", " ")),
        ("Coût total 2025", euros(ref.CoutTotalEuro), f"Recalculé au tarif : {euros(ref.CoutRecalculeEuro)}"),
        ("Émissions 2025", f"{ref.EmissionsTCO2:,.0f} t CO₂".replace(",", " "), "Hors production solaire"),
    ]
    for i, (titre, valeur, detail) in enumerate(cartes):
        ax = fig.add_subplot(grille[0, i]); ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, color="#F3F4F6", zorder=0))
        ax.text(0.05, 0.75, titre, fontsize=10, color=GRIS, transform=ax.transAxes)
        ax.text(0.05, 0.35, valeur, fontsize=17, fontweight="bold", color=ENCRE, transform=ax.transAxes)
        couleur = "#16A34A" if "N-1" in detail and ref.EvolutionN1Pct < 0 else ("#DC2626" if "N-1" in detail else GRIS)
        ax.text(0.05, 0.08, detail, fontsize=9, color=couleur, transform=ax.transAxes)

    # Tendance mensuelle
    ax = fig.add_subplot(grille[1, :3])
    mensuel = conso.groupby([conso["DateMesure"].dt.to_period("M").dt.to_timestamp(), "CodeEnergie"])[
        "QuantiteKWh"].sum().unstack()
    for code in mensuel.columns:
        ax.plot(mensuel.index, mensuel[code] / 1e6, label=code, color=COULEURS[code], lw=2)
    ax.plot(mensuel.index, mensuel.sum(axis=1) / 1e6, label="Total", color=ENCRE, lw=2.5, ls="--")
    ax.set_title("Consommation mensuelle par énergie (GWh)", loc="left")
    ax.legend(ncol=4, frameon=False, fontsize=9, loc="upper right")
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.1f"))

    # Énergies par année (histogramme empilé)
    ax = fig.add_subplot(grille[1, 3])
    par_an = conso.groupby(["Annee", "CodeEnergie"])["QuantiteKWh"].sum().unstack() / 1e6
    bas = None
    for code in par_an.columns:
        ax.bar(par_an.index.astype(str), par_an[code], bottom=bas, color=COULEURS[code], label=code, width=0.6)
        bas = par_an[code] if bas is None else bas + par_an[code]
    ax.set_title("Énergie par année (GWh)", loc="left")
    ax.text(2, bas.iloc[-1] * 1.02, "S1 seul", ha="center", fontsize=8, color=GRIS)

    # Top 10 bâtiments
    ax = fig.add_subplot(grille[2, :2])
    t10 = top.head(10).iloc[::-1]
    couleurs = ["#9CA3AF"] * 7 + ["#DC2626"] * 3
    ax.barh(t10["NomBatiment"], t10["ConsommationKWh"] / 1e6, color=couleurs)
    for y, v in enumerate(t10["ConsommationKWh"] / 1e6):
        ax.text(v, y, f" {v:.1f}", va="center", fontsize=8, color=ENCRE)
    ax.set_title("Top 10 bâtiments — consommation cumulée (GWh)", loc="left")
    ax.tick_params(axis="y", labelsize=8)

    # Colonne calculée Niveau consommation x mesure
    ax = fig.add_subplot(grille[2, 2])
    niv = conso.groupby(["Annee", "NiveauConsommation"])["QuantiteKWh"].sum().unstack() / 1e6
    niv.plot(kind="bar", ax=ax, color={"Élevée": "#DC2626", "Normale": "#9CA3AF"}, width=0.7, rot=0)
    ax.set_title("Niveau consommation (colonne)\n× Consommation totale (mesure)", loc="left", fontsize=10)
    ax.set_xlabel(""); ax.legend(frameon=False, fontsize=8)

    # kWh/m² : préfigure le TP suivant
    ax = fig.add_subplot(grille[2, 3])
    km2 = top.sort_values("KWhParM2").tail(10)
    ax.barh(km2["CodeBatiment"], km2["KWhParM2"], color="#2563EB")
    ax.set_title("Intensité kWh/m² (cumul)", loc="left")
    ax.tick_params(axis="y", labelsize=8)

    # Date affichée : celle de l'exécution, ou NOVARIA_DATE_ACTUALISATION (ex. "2026-09-11 14:20") pour figer un rendu
    actualisation = pd.Timestamp(os.environ.get("NOVARIA_DATE_ACTUALISATION") or pd.Timestamp.now())
    fig.text(0.02, 0.01, f"Données actualisées le {actualisation:%d/%m/%Y à %H:%M} · source : Novaria_NRJ + fichiers bruts nettoyés",
             fontsize=8, color=GRIS)
    dossier = OUT / "07_rapport"
    dossier.mkdir(parents=True, exist_ok=True)
    fig.savefig(dossier / "synthese_energie.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def decision(kpi, top, top_2025, production, conso) -> None:
    t3 = top.head(3)
    lignes = [
        "# Décision provisoire 1 — consommation seule",
        "",
        "_Générée automatiquement par `src/run_all.py` à partir du modèle en étoile._",
        "",
        "## Indicateurs clés (flux Consommation, production solaire exclue)",
        "",
        "| Année | Période | Consommation | Coût source | kWh/m² | t CO₂ | N-1 (même période) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in kpi.itertuples():
        n1 = "—" if pd.isna(r.EvolutionN1Pct) else f"{r.EvolutionN1Pct:+.1f} %"
        lignes.append(f"| {r.Annee} | {r.Periode} | {kwh(r.ConsommationTotaleKWh)} | {euros(r.CoutTotalEuro)} | "
                      f"{r.KWhParM2:.0f} | {r.EmissionsTCO2:,.0f} | {n1} |".replace(",", " "))
    lignes += [
        "",
        f"Production photovoltaïque sur la période : **{kwh(production)}** (mesurée à part, jamais additionnée à la consommation).",
        "",
        "## Top 3 des bâtiments (consommation cumulée 2024 → S1 2026)",
        "",
        "| Rang | Bâtiment | Type | Consommation | Part du total | kWh/m² | Coût |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(t3.itertuples(), 1):
        lignes.append(f"| {i} | {r.NomBatiment} | {r.TypeBatiment} | {kwh(r.ConsommationKWh)} | "
                      f"{r.PartPct:.1f} % | {r.KWhParM2:.0f} | {euros(r.CoutEuro)} |")
    part3 = t3["PartPct"].sum()
    noms = ", ".join(t3["NomBatiment"])
    lignes += [
        "",
        "## Décision",
        "",
        f"> **Avec la consommation seule, nous traiterions d'abord : {noms}.** "
        f"Ces trois bâtiments représentent **{part3:.1f} %** de la consommation du parc. "
        f"Le classement 2025 seul est identique : {', '.join(top_2025.head(3).index)}.",
        "",
        "**Limites (décision provisoire) :**",
        "",
        "- le classement en kWh absolus favorise les grands bâtiments : rapporté à la surface, "
        f"le plus intensif est **{top.sort_values('KWhParM2', ascending=False).iloc[0]['NomBatiment']}** "
        f"({top['KWhParM2'].max():.0f} kWh/m²) ;",
        "- le climat (DJU) n'est pas encore pris en compte → TP 9 ;",
        "- les coûts réels, tarifs et abonnements → TP 10 ; les audits (classe, priorité, coût travaux) → TP 11 ;",
        "- 2026 ne couvre que le premier semestre : la variation N-1 est calculée sur la même période.",
    ]
    (OUT / "07_rapport" / "decision_provisoire.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
