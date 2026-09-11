# Compte rendu — TP Novaria 1 à 8

Chaque section reprend l'objectif du TP, la démarche suivie, les règles retenues et les chiffres
obtenus. Les fichiers cités se trouvent dans `output/`.

---

## TP 1 — Connecter les quatre sources

| Requête | Source | Connecteur | Particularité |
|---|---|---|---|
| `Stg_Consommations` | vue SQL `VW_ConsommationsEnergetiques` | SQL Server, mode Import | 26 448 relevés journaliers, du 01/01/2024 au 30/06/2026 |
| `Stg_Meteo` | `MeteoQuartier_Brut.xlsx` | Excel | lu entièrement en texte pour conserver le brut |
| `Stg_Tarifs` | `TarifsEnergie_Brut.csv` | Texte/CSV, UTF-8, `;` | décimales mixtes |
| `Stg_Audits` | `AuditsEnergetiques_Brut.json` | JSON | liste → table → développer l'enregistrement puis `audit` |

Les quatre requêtes sont rangées dans le groupe `01_Staging`. Aucune donnée source n'est corrigée à
la main, et les chemins sont paramétrés (`Serveur`, `Dossier`) pour que l'actualisation fonctionne
sans manipulation. Code : `powerbi/powerquery/01_Staging.pq`.

---

## TP 2 — Contrôler la qualité

**Profil des colonnes** (`02_controles/Profil_colonnes.csv`), calculé sur toutes les lignes :

- Météo : une valeur vide dans chacune des colonnes TemperatureMoyenne, TemperatureMin, Pluviometrie,
  DJUChauffage, Ensoleillement et DateImport.
- Tarifs : l'abonnement SOLAIRE est vide. C'est normal pour de l'autoproduction, donc ce n'est pas une anomalie.
- Audits : le coût de BAT-ATELIER est vide. Cela signifie « à chiffrer », pas une ligne invalide.

**Types réels contre types détectés.** Météo : 29 dates en texte libre (`janvier 2024`, `mars-24`,
`06/2024`, `Sept. 2024`, `2026 T2`…) et des unités dans les nombres (`7,8 °C`, `84 mm`, `315 DJU`,
`198 h`). Tarifs : `juillet 2025`, `0.2317` au lieu de `0,2317`, `19,10 €`. Audits : `15/05/2024`, `134 kWh/m²`.

**Doublons sur clé métier** (`Ctl_Doublons_*`) :

| Source | Clé métier | Doublons |
|---|---|---|
| Consommations | bâtiment + énergie + date | 0 |
| Météo | quartier + mois | 11, visibles une fois codes et dates normalisés |
| Tarifs | énergie + date d'effet | 1 (ELEC 2026-01-01 en double) |
| Audits | bâtiment + date | 0 |

**Valeurs impossibles** : pluviométrie de −18 mm, −6 mm et 642 mm ; DJU de −45 ; ensoleillement de
−12 h ; température moyenne de 38,7 °C ; moyenne supérieure au maximum (22,1 °C pour un maximum de
12,1 °C) ; prix RCU de −0,1072 € ; bâtiment `BAT-INCONNU`.

**Réconciliation** (`02_controles/Bilan_reconciliation.csv`) : `initial = valides + rejets` est vérifié
pour les quatre sources.

`Rejets_Consommations` est vide, et c'est attendu : la vue SQL est protégée par des clés étrangères,
des contraintes NOT NULL, `CHECK (QuantiteKWh >= 0)` et `UNIQUE (IdBatiment, IdTypeEnergie, DateMesure)`.

---

## TP 3 — Nettoyer les consommations → `Int_Consommations`

1. Les codes bâtiment et énergie sont nettoyés (`Text.Clean`, `Text.Trim`, `Text.Upper`).
2. Les types sont explicites : dates, entiers pour les identifiants, décimaux pour kWh, € et CO₂.
3. Les règles de rejet sont centralisées dans `Controle_Consommations[RaisonRejet]` : bâtiment,
   énergie, date ou quantité absente, puis quantité, coût ou émission négative.
4. Le dédoublonnage est déterministe sur `IdBatiment + IdTypeEnergie + DateMesure`. On garde le
   `DateChargement` le plus récent, puis le plus grand `IdReleve`. En M, le tri est figé par
   `Table.Buffer` avant `Table.Distinct`.
5. `Mois = Date.StartOfMonth(DateMesure)` prépare les rapprochements avec la météo et les tarifs.
6. `ConsoKWhM2` et `EmissionCO2KgM2` renvoient null si la surface est nulle (division protégée).

Contrôle : 26 448 lignes avant et après, total de kWh identique, aucun écart à expliquer.

---

## TP 4 — Nettoyer la météo → `Int_Meteo`

| Étape | Règle |
|---|---|
| Codes quartier | casse et espaces (`ctr ` → CTR), alias (`Nord` → NOR, `OUEST` → OUE), ponctuation (`EST-` → EST), zéro saisi à la place de O (`S0U` → SOU) |
| Dates | 9 formats reconnus et ramenés au 1er du mois. `2026 T2` est rejeté car un trimestre ne désigne pas un mois précis |
| Unités | suppression de `°C`, `°`, `mm`, `DJU`, `h`, virgule décimale convertie |
| Domaines | T° moyenne entre −20 et 35, pluie entre 0 et 400 mm, DJU entre 0 et 700, soleil entre 0 et 400 h, et min ≤ moyenne ≤ max |
| Obligatoires | TemperatureMoyenne et DJUChauffage ; les autres mesures peuvent rester null |
| Grain | une ligne par quartier et par mois, en gardant l'import le plus récent |
| Référentiel | jointure gauche avec les quartiers ; les codes non trouvés sont rejetés |

Résultat : 225 lignes valides et 21 rejets (`03_rejets/Rejets_Meteo.csv`) :

- 6 valeurs hors domaine ;
- 2 mesures obligatoires absentes ;
- 1 température incohérente ;
- 1 date imprécise ;
- 11 doublons quartier-mois.

Le contrôle du grain (nombre maximal de lignes par quartier et par mois = 1) est vérifié par une assertion.

Point d'attention : la ligne MET-1008 (OUE) porte la date « 1er février 2024 » mais a été importée
le 07/01/2024. Elle entre en doublon avec le relevé de février et la météo de janvier 2024 manque
pour OUE. Il faut le signaler au fournisseur, sans corriger la donnée à la main.

---

## TP 5 — Nettoyer les tarifs et les audits

**`Int_Tarifs`** : 17 lignes.

- Les codes sont nettoyés (`GAZ ` → GAZ) et `juillet 2025` devient la date d'effet 2025-07-01.
- `0.2317` et `0,2317` donnent le même nombre, et `19,10 €` devient 19,10.
- Rejets : le prix RCU négatif (−0,1072) et le doublon ELEC 2026-01-01.
- L'abonnement SOLAIRE vide reste null.

**`Int_Audits`** : 12 audits.

- `BAT-ECO-SO ` est corrigé par suppression de l'espace.
- La date `15/05/2024` est lue au format jour/mois. Les dates ISO sont lues en premier pour éviter
  toute inversion jour/mois.
- `134 kWh/m²` devient 134.
- Les priorités sont normalisées : Faible, Moyenne, Haute, Urgente, avec une colonne d'ordre.
- Le coût null de BAT-ATELIER donne `StatutChiffrage = "À chiffrer"`. Il n'est jamais remplacé par 0.
- `BAT-INCONNU` (classe G, coût 0) ne figure pas dans le référentiel : il part dans `Rejets_Audits`.

---

## TP 6 — Combiner → `FactEnergie_Preparee`

| Table | Grain |
|---|---|
| Int_Consommations | bâtiment × énergie × jour |
| Int_Meteo | quartier × mois |
| Int_Tarifs | énergie × date d'effet |
| Int_Audits | bâtiment × date d'audit |

- **Météo** : jointure gauche sur quartier + mois. La clé droite est validée unique, donc aucune duplication.
- **Tarif** : on prend le dernier tarif dont la date d'effet est antérieure ou égale au mois de
  consommation (jointure « as-of »).
- **Coût** : `CoutRecalcule = kWh × prix applicable` (0 pour la production) et `EcartCout = recalculé − source`.
- **Correspondances manquantes** : elles restent visibles grâce à `MeteoTrouvee` et `TarifTrouve`
  (`05_combinaison/Correspondances_manquantes.csv`) :
  - 1 489 faits sans météo, répartis sur 15 couples quartier-mois ;
  - 3 655 faits sans tarif. Ce sont tous de la **production** solaire antérieure à 2026 : il n'y a
    pas de prix d'achat pour de l'autoproduction, donc c'est attendu.
- **Réconciliation** : nombre de faits et kWh identiques avant et après, écart nul pour chaque
  combinaison énergie × quartier × année (`05_combinaison/Reconciliation_Fact_vs_Int.csv`).

**Constat métier** : la vue SQL valorise toute la période au tarif de janvier 2024. Avec les tarifs
en vigueur, le coût baisse de 37 k€ en 2024, de 164 k€ en 2025 (−4,2 %) et de 105 k€ au premier
semestre 2026.

---

## TP 7 — Modèle en étoile et mesures

```
            DimDate ──┐
        DimEnergie ───┼──► FactEnergie (26 448)
DimQuartier ─► DimBatiment ─┤
                            └──► FactAudit (12)
```

- DimBatiment compte 12 lignes, DimQuartier 8, DimEnergie 4, et DimDate 1 096 jours (années
  complètes 2024 à 2026, nécessaires à `DATEADD`).
- Toutes les relations sont de un à plusieurs, avec un filtre simple des dimensions vers les faits.
  Il n'y a ni relation plusieurs-à-plusieurs ni relation bidirectionnelle.
- Les tarifs ne sont pas dans DimEnergie, car ils varient dans le temps.
- Les audits forment un fait (`FactAudit`) et non une dimension, car un bâtiment peut être audité plusieurs fois.

**Colonne calculée ou mesure ?**

- La colonne `Niveau consommation` (Élevée si un relevé dépasse 10 000 kWh) est calculée une fois
  par ligne au moment de l'actualisation. Elle sert d'axe, de légende ou de segment.
- La mesure `Consommation totale` est recalculée selon le contexte de filtre (année, quartier, énergie…).

**Correction apportée à la mesure du sujet** : `SUM(QuantiteKWh)` additionnerait la production
solaire (1,45 GWh) à la consommation. La mesure filtre donc `TypeFlux = "Consommation"`, et une
mesure séparée `Production solaire` est ajoutée.

Le test de la matrice année > quartier > énergie est validé : les sous-totaux se réconcilient avec
le total global (`07_rapport/Matrice_Annee_Quartier_Energie.csv`). Mesures : `powerbi/dax/mesures.dax`.

---

## TP 8 — Page « Synthèse énergie » et décision provisoire

Maquette : `output/07_rapport/synthese_energie.png`. Elle comprend :

- des cartes KPI avec une étiquette N-1 colorée ;
- la tendance mensuelle par énergie ;
- un histogramme empilé par énergie et par année ;
- le Top 10 des bâtiments ;
- la colonne `Niveau consommation` croisée avec la mesure ;
- l'intensité en kWh/m² ;
- la date de dernière actualisation.

| Année | Consommation | Coût source | kWh/m² | N-1 (même période) |
|---|---:|---:|---:|---:|
| 2024 | 22 922 391 kWh | 3 947 488 € | 228 | — |
| 2025 | 22 842 739 kWh | 3 937 338 € | 227 | −0,3 % |
| S1 2026 | 15 485 720 kWh | 2 380 998 € | 154 | −0,3 % |

La mesure N-1 est bornée à la période comparable. Une simple `DATEADD` comparerait le premier
semestre 2026 à toute l'année 2025 et afficherait −32 %, ce qui serait trompeur.

**Décision provisoire 1.** Avec la consommation seule, nous traiterions d'abord :

1. la Résidence sociale des Horizons : 11,5 GWh, 18,8 % du parc ;
2. la Résidence sociale du Parc : 9,4 GWh, 15,3 % ;
3. la Piscine municipale NeoWave : 6,8 GWh, 11,1 %.

Ces trois bâtiments représentent 45,2 % de la consommation, et le classement 2025 seul est identique.

**Limites.** Ce classement en valeur absolue favorise les grands bâtiments. Rapportée à la surface,
la piscine domine (870 kWh/m²) et les deux HLM sont à 660 kWh/m². Le climat (DJU), les coûts réels
et les audits seront intégrés dans les TP 9 à 11 pour réviser cette décision.
