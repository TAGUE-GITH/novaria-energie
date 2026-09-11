// =====================================================================
//  Groupe 04_Modele (TP 6, 7, 8) : seules ces requêtes sont chargées dans le modèle
// =====================================================================

// ---------- FactEnergie (ex FactEnergie_Preparee, TP 6)
let
    Source = Int_Consommations,
    // 1. Météo : jointure gauche quartier + mois (clé unique côté Int_Meteo -> pas de duplication)
    Meteo = Table.NestedJoin(Source, {"IdQuartier", "Mois"}, Int_Meteo, {"IdQuartier", "Mois"}, "M", JoinKind.LeftOuter),
    MeteoDev = Table.ExpandTableColumn(Meteo, "M", {"TemperatureMoyenne", "DJUChauffage"},
        {"TemperatureMoyenneMois", "DJUChauffage"}),
    MeteoTrouvee = Table.AddColumn(MeteoDev, "MeteoTrouvee", each [DJUChauffage] <> null, type logical),
    // 2. Tarif applicable : dernière date d'effet <= mois de consommation
    TarifsBuf = Table.Buffer(Int_Tarifs),
    Tarif = Table.AddColumn(MeteoTrouvee, "PrixApplicableKWh", each
        let e = [IdTypeEnergie], m = [Mois],
            Candidats = Table.SelectRows(TarifsBuf, (t) => t[IdTypeEnergie] = e and t[DateEffet] <= m)
        in if Table.IsEmpty(Candidats) then null else Table.Max(Candidats, "DateEffet")[PrixKWhEuro], type number),
    TarifTrouve = Table.AddColumn(Tarif, "TarifTrouve", each [PrixApplicableKWh] <> null, type logical),
    // 3. Coût recalculé et écart avec le coût source
    Cout = Table.AddColumn(TarifTrouve, "CoutRecalcule", each
        if [TypeFlux] = "Production" then 0
        else if [PrixApplicableKWh] = null then null
        else Number.Round([QuantiteKWh] * [PrixApplicableKWh], 2), type number),
    Ecart = Table.AddColumn(Cout, "EcartCout", each
        if [CoutRecalcule] = null then null else [CoutRecalcule] - [CoutEuro], type number),
    // 4. On ne garde que clés + mesures (les attributs vivent dans les dimensions)
    Final = Table.SelectColumns(Ecart, {"IdReleve", "DateMesure", "IdBatiment", "IdQuartier", "IdTypeEnergie",
        "TypeFlux", "QuantiteKWh", "CoutEuro", "CoutRecalcule", "EcartCout", "EmissionCO2Kg",
        "TemperatureMoyenne", "TemperatureMoyenneMois", "DJUChauffage", "PrixApplicableKWh",
        "MeteoTrouvee", "TarifTrouve"})
in
    Final
// Contrôle : Table.RowCount(FactEnergie) = Table.RowCount(Int_Consommations)

// ---------- DimBatiment (12 lignes)
let
    Source = Table.SelectColumns(Int_Consommations, {"IdBatiment", "CodeBatiment", "NomBatiment", "TypeBatiment",
        "SurfaceM2", "AnneeConstruction", "NbOccupantsMoyen", "EstRenove", "IdQuartier"}),
    Unique = Table.Distinct(Source, {"IdBatiment"}),
    Types = Table.TransformColumnTypes(Unique, {{"IdBatiment", Int64.Type}, {"AnneeConstruction", Int64.Type},
        {"NbOccupantsMoyen", Int64.Type}, {"SurfaceM2", type number}, {"EstRenove", type logical},
        {"IdQuartier", Int64.Type}})
in
    Table.Sort(Types, {"IdBatiment"})

// ---------- DimQuartier (8 lignes)
let
    Source = Table.SelectColumns(Int_Consommations, {"IdQuartier", "CodeQuartier", "NomQuartier", "Population"}),
    Unique = Table.Distinct(Source, {"IdQuartier"})
in
    Table.TransformColumnTypes(Unique, {{"IdQuartier", Int64.Type}, {"Population", Int64.Type}})

// ---------- DimEnergie (4 lignes ; pas de tarif ici : il varie dans le temps)
let
    Source = Table.SelectColumns(Int_Consommations, {"IdTypeEnergie", "CodeEnergie", "LibelleEnergie", "EstRenouvelable"}),
    Unique = Table.Distinct(Source, {"IdTypeEnergie"})
in
    Table.TransformColumnTypes(Unique, {{"IdTypeEnergie", Int64.Type}, {"EstRenouvelable", type logical}})

// ---------- DimDate (années complètes ; Modélisation > Marquer comme table de dates)
let
    Debut = #date(Date.Year(List.Min(Int_Consommations[DateMesure])), 1, 1),
    Fin = #date(Date.Year(List.Max(Int_Consommations[DateMesure])), 12, 31),
    Dates = List.Dates(Debut, Duration.Days(Fin - Debut) + 1, #duration(1, 0, 0, 0)),
    Table0 = Table.TransformColumnTypes(Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}), {{"Date", type date}}),
    Annee = Table.AddColumn(Table0, "Annee", each Date.Year([Date]), Int64.Type),
    Trim = Table.AddColumn(Annee, "Trimestre", each "T" & Text.From(Date.QuarterOfYear([Date])), type text),
    MoisNum = Table.AddColumn(Trim, "MoisNum", each Date.Month([Date]), Int64.Type),
    MoisNom = Table.AddColumn(MoisNum, "Mois", each Date.ToText([Date], "MMMM", "fr-FR"), type text),
    AnneeMois = Table.AddColumn(MoisNom, "AnneeMois", each Date.ToText([Date], "yyyy-MM"), type text)
in
    AnneeMois

// ---------- FactAudit (12 lignes : un bâtiment peut recevoir plusieurs audits -> fait, pas dimension)
let
    Source = Table.SelectColumns(Int_Audits, {"IdBatiment", "CodeBatiment", "DateAudit", "ClasseEnergetique",
        "ConsommationReferenceKWhM2", "Priorite", "Recommandation", "CoutEstimeEuro", "StatutChiffrage"})
in
    Source

// ---------- Actualisation (TP 8)
let
    Source = #table(type table [DerniereActualisation = datetime], {{DateTime.LocalNow()}})
in
    Source

// ---------- Relations (vue Modèle) : toutes 1 -> *, filtre simple vers le fait
//   DimDate[Date]                 1 -> * FactEnergie[DateMesure]
//   DimBatiment[IdBatiment]       1 -> * FactEnergie[IdBatiment]
//   DimBatiment[IdBatiment]       1 -> * FactAudit[IdBatiment]
//   DimQuartier[IdQuartier]       1 -> * DimBatiment[IdQuartier]   (flocon léger)
//   DimEnergie[IdTypeEnergie]     1 -> * FactEnergie[IdTypeEnergie]
//   FactEnergie[IdQuartier] reste disponible mais sans relation active (évite l'ambiguïté de chemin).
