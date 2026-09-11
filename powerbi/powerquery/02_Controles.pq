// =====================================================================
//  Groupe 02_Controles (TP 2) : requêtes créées par Référence, chargement désactivé
//  Ctl_     = anomalie potentielle à examiner
//  Rejets_  = ligne effectivement exclue (avec RaisonRejet)
// =====================================================================

// ---------- Ctl_Doublons_Consommations (clé métier bâtiment + énergie + date)
let
    Source = Stg_Consommations,
    Cle = Table.SelectColumns(Source, {"IdBatiment", "IdTypeEnergie", "DateMesure"}),
    Groupe = Table.Group(Cle, {"IdBatiment", "IdTypeEnergie", "DateMesure"},
        {{"NombreOccurrences", each Table.RowCount(_), Int64.Type}}),
    Doublons = Table.SelectRows(Groupe, each [NombreOccurrences] > 1)
in
    Doublons
// Même modèle : Ctl_Doublons_Meteo (CodeQuartier + DateReleve),
// Ctl_Doublons_Tarifs (CodeEnergie + MoisTarif), Ctl_Doublons_Audits (codeBatiment + dateAudit)

// ---------- Ctl_Vides_Consommations (champs obligatoires uniquement)
let
    Source = Stg_Consommations,
    Raison = Table.AddColumn(Source, "RaisonControle", each
        if [IdBatiment] = null then "Bâtiment absent"
        else if [IdTypeEnergie] = null then "Énergie absente"
        else if [DateMesure] = null then "Date absente"
        else if [QuantiteKWh] = null then "Quantité absente"
        else null, type text),
    Anomalies = Table.SelectRows(Raison, each [RaisonControle] <> null)
in
    Anomalies

// ---------- Controle_Consommations (règles de rejet centralisées)
let
    Source = Stg_Consommations,
    Types = Table.TransformColumnTypes(Source, {
        {"IdBatiment", Int64.Type}, {"IdTypeEnergie", Int64.Type}, {"DateMesure", type date},
        {"QuantiteKWh", type number}, {"CoutEuro", type number}, {"EmissionCO2Kg", type number}}),
    Textes = Table.TransformColumns(Types, {
        {"CodeBatiment", each Text.Upper(Text.Trim(Text.Clean(_))), type text},
        {"CodeEnergie", each Text.Upper(Text.Trim(Text.Clean(_))), type text}}),
    RaisonRejet = Table.AddColumn(Textes, "RaisonRejet", each
        if [IdBatiment] = null then "Bâtiment absent"
        else if [IdTypeEnergie] = null then "Énergie absente"
        else if [DateMesure] = null then "Date absente"
        else if [QuantiteKWh] = null then "Quantité absente"
        else if [QuantiteKWh] < 0 then "Quantité négative"
        else if [CoutEuro] = null then "Coût absent"
        else if [CoutEuro] < 0 then "Coût négatif"
        else if [EmissionCO2Kg] < 0 then "Émission négative"
        else null, type text)
in
    RaisonRejet

// ---------- Rejets_Consommations
// Vide avec la vue SQL : FK, NOT NULL, CHECK >= 0 et UNIQUE protègent déjà la source.
let
    Source = Controle_Consommations,
    Rejets = Table.SelectRows(Source, each [RaisonRejet] <> null),
    Horodatage = Table.AddColumn(Rejets, "DateControle", each DateTime.LocalNow(), type datetime)
in
    Horodatage
