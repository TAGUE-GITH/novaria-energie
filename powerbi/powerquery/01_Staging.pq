// =====================================================================
//  Groupe 01_Staging : lecture brute, aucune correction (TP 1)
//  Paramètres (Accueil > Gérer les paramètres) :
//    Serveur = ".\SQLEXPRESS"            Dossier = "D:\Novaria\data\raw\"
//  Chaque bloc ci-dessous = une requête (Accueil > Nouvelle source > Requête vide > Éditeur avancé)
// =====================================================================

// ---------- Stg_Consommations (SQL Server, mode Import)
let
    Source = Sql.Database(Serveur, "Novaria_NRJ"),
    Vue = Source{[Schema = "dbo", Item = "VW_ConsommationsEnergetiques"]}[Data]
in
    Vue

// ---------- Stg_Meteo (Excel) : tout en texte, le brut est conservé ("7,8 °C", "2026 T2"...)
let
    Source = Excel.Workbook(File.Contents(Dossier & "MeteoQuartier_Brut.xlsx"), null, true),
    Feuille = Source{[Item = "MeteoQuartier_Brut", Kind = "Sheet"]}[Data],
    EnTetes = Table.PromoteHeaders(Feuille, [PromoteAllScalars = true]),
    ToutEnTexte = Table.TransformColumnTypes(EnTetes,
        List.Transform(Table.ColumnNames(EnTetes), each {_, type text}), "fr-FR")
in
    ToutEnTexte

// ---------- Stg_Tarifs (CSV UTF-8, séparateur ;)
let
    Source = Csv.Document(File.Contents(Dossier & "TarifsEnergie_Brut.csv"),
        [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    EnTetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    EnTetes

// ---------- Stg_Audits (JSON : liste -> table -> développer l'enregistrement puis "audit")
let
    Source = Json.Document(File.Contents(Dossier & "AuditsEnergetiques_Brut.json"), 65001),
    EnTable = Table.FromList(Source, Splitter.SplitByNothing(), {"Enregistrement"}),
    Developpe = Table.ExpandRecordColumn(EnTable, "Enregistrement",
        {"codeBatiment", "dateAudit", "classeEnergetique", "consommationReferenceKWhM2", "audit"}),
    DeveloppeAudit = Table.ExpandRecordColumn(Developpe, "audit",
        {"priorite", "recommandation", "coutEstimeEuro"})
in
    DeveloppeAudit
