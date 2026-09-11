// =====================================================================
//  Groupe 03_Intermediaires (TP 3, 4, 5) : données propres, typées, au bon grain
// =====================================================================

// ---------- fnNombreFr : "7,8 °C" / "19,10 €" / "134 kWh/m²" / "0.2317" -> nombre ; vide -> null
(valeur as any) as nullable number =>
let
    Texte = if valeur = null then null else Text.Trim(Text.Replace(Text.From(valeur), ",", ".")),
    Garde = if Texte = null then null else Text.Select(Texte, {"0".."9", ".", "-"}),
    Nombre = if Garde = null or Garde = "" then null else Number.FromText(Garde, "en-US")
in
    Nombre

// ---------- fnMoisFr : date hétérogène -> 1er jour du mois ; null si imprécise ("2026 T2")
(valeur as any) as nullable date =>
let
    NomsMois = {{"jan", 1}, {"fév", 2}, {"fev", 2}, {"mar", 3}, {"avr", 4}, {"mai", 5}, {"juin", 6},
                {"juil", 7}, {"aoû", 8}, {"aou", 8}, {"sep", 9}, {"oct", 10}, {"nov", 11}, {"déc", 12}, {"dec", 12}},
    EstDate = valeur is date or valeur is datetime,
    Texte = Text.Lower(Text.Trim(Text.Replace(Text.From(valeur), "1er ", ""))),
    Mots = List.Select(Text.SplitAny(Texte, " -/."), each _ <> ""),
    Nb = (t) => try Number.From(t) otherwise null,
    Annee2 = (a) => if a = null then null else if a < 100 then 2000 + a else a,
    MoisNom = (t) => List.First(List.Transform(List.Select(NomsMois, each Text.StartsWith(t, _{0})), each _{1})),
    Resultat =
        if EstDate then Date.StartOfMonth(Date.From(valeur))
        else if List.Count(Mots) = 2 and Text.StartsWith(Mots{1}, "t") then null                // 2026 T2
        else if List.Count(Mots) >= 3 and Text.Length(Mots{0}) = 4 then #date(Nb(Mots{0}), Nb(Mots{1}), 1)  // 2024-01-01 00:00:00
        else if List.Count(Mots) = 3 then #date(Nb(Mots{2}), Nb(Mots{1}), 1)                    // 15/04/2025
        else if List.Count(Mots) = 2 and Text.Length(Mots{0}) = 4 then #date(Nb(Mots{0}), Nb(Mots{1}), 1)    // 2024-04
        else if List.Count(Mots) = 2 and Nb(Mots{0}) <> null then #date(Nb(Mots{1}), Nb(Mots{0}), 1)         // 06/2024
        else if List.Count(Mots) = 2 and MoisNom(Mots{0}) <> null then #date(Annee2(Nb(Mots{1})), MoisNom(Mots{0}), 1) // mars-24
        else null
in
    try Resultat otherwise null

// ---------- Int_Consommations (référence de Controle_Consommations)
let
    Source = Table.SelectRows(Controle_Consommations, each [RaisonRejet] = null),
    SansRaison = Table.RemoveColumns(Source, {"RaisonRejet"}),
    // Dédoublonnage déterministe : chargement le plus récent, puis IdReleve le plus élevé
    Tri = Table.Sort(SansRaison, {{"DateChargement", Order.Descending}, {"IdReleve", Order.Descending}}),
    Memoire = Table.Buffer(Tri),
    Dedoublonne = Table.Distinct(Memoire, {"IdBatiment", "IdTypeEnergie", "DateMesure"}),
    Mois = Table.AddColumn(Dedoublonne, "Mois", each Date.StartOfMonth([DateMesure]), type date),
    KWhM2 = Table.AddColumn(Mois, "ConsoKWhM2", each
        if [SurfaceM2] = null or [SurfaceM2] = 0 then null else [QuantiteKWh] / [SurfaceM2], type number),
    CO2M2 = Table.AddColumn(KWhM2, "EmissionCO2KgM2", each
        if [SurfaceM2] = null or [SurfaceM2] = 0 then null else [EmissionCO2Kg] / [SurfaceM2], type number)
in
    CO2M2

// ---------- Controle_Meteo (TP 4)
let
    Source = Stg_Meteo,
    // Codes : casse, espaces, alias ("Nord", "OUEST"), ponctuation ("EST-") et zéro saisi pour O ("S0U")
    Alias = [NORD = "NOR", OUEST = "OUE"],
    Codes = Table.TransformColumns(Source, {{"CodeQuartier", each
        let c = Text.Upper(Text.Trim(_)),
            a = Record.FieldOrDefault(Alias, c, c)
        in Text.Replace(Text.Select(a, {"A".."Z", "0".."9"}), "0", "O"), type text}}),
    Mois = Table.AddColumn(Codes, "Mois", each fnMoisFr([DateReleve]), type date),
    Mesures = Table.TransformColumns(Mois, {
        {"TemperatureMoyenne", fnNombreFr, type number}, {"TemperatureMin", fnNombreFr, type number},
        {"TemperatureMax", fnNombreFr, type number}, {"Pluviometrie", fnNombreFr, type number},
        {"DJUChauffage", fnNombreFr, type number}, {"Ensoleillement", fnNombreFr, type number}}),
    Typage = Table.TransformColumnTypes(Mesures, {{"DateImport", type datetime}}, "fr-FR"),
    Fusion = Table.NestedJoin(Typage, {"CodeQuartier"}, DimQuartier, {"CodeQuartier"}, "Ref", JoinKind.LeftOuter),
    AvecId = Table.ExpandTableColumn(Fusion, "Ref", {"IdQuartier"}),
    Raison = Table.AddColumn(AvecId, "RaisonRejet", each
        if [IdQuartier] = null then "Quartier inconnu"
        else if [Mois] = null then "Date imprécise ou illisible"
        else if [TemperatureMoyenne] = null or [DJUChauffage] = null then "Mesure obligatoire absente"
        else if [TemperatureMoyenne] < -20 or [TemperatureMoyenne] > 35
             or ([Pluviometrie] <> null and ([Pluviometrie] < 0 or [Pluviometrie] > 400))
             or [DJUChauffage] < 0 or [DJUChauffage] > 700
             or ([Ensoleillement] <> null and ([Ensoleillement] < 0 or [Ensoleillement] > 400))
             then "Valeur hors domaine"
        else if [TemperatureMoyenne] < [TemperatureMin] or [TemperatureMoyenne] > [TemperatureMax]
             then "Température moyenne hors [min ; max]"
        else null, type text)
in
    Raison

// ---------- Int_Meteo : grain quartier-mois unique, import le plus récent conservé
let
    Valides = Table.SelectRows(Controle_Meteo, each [RaisonRejet] = null),
    Tri = Table.Buffer(Table.Sort(Valides, {{"DateImport", Order.Descending}, {"IdReleveExterne", Order.Descending}})),
    GrainQuartierMois = Table.Distinct(Tri, {"IdQuartier", "Mois"})
in
    Table.RemoveColumns(GrainQuartierMois, {"RaisonRejet"})

// ---------- Rejets_Meteo : règles + doublons écartés (anti-jointure sur l'identifiant externe)
let
    Regles = Table.SelectRows(Controle_Meteo, each [RaisonRejet] <> null),
    Valides = Table.SelectRows(Controle_Meteo, each [RaisonRejet] = null),
    Ecartes = Table.NestedJoin(Valides, {"IdReleveExterne"}, Int_Meteo, {"IdReleveExterne"}, "K", JoinKind.LeftAnti),
    Doublons = Table.ReplaceValue(Table.RemoveColumns(Ecartes, {"K"}), null,
        "Doublon quartier-mois (import plus ancien)", Replacer.ReplaceValue, {"RaisonRejet"})
in
    Table.Combine({Regles, Doublons})

// ---------- Int_Tarifs (TP 5)
let
    Source = Stg_Tarifs,
    Code = Table.TransformColumns(Source, {{"CodeEnergie", each Text.Upper(Text.Trim(_)), type text}}),
    DateEffet = Table.AddColumn(Code, "DateEffet", each fnMoisFr([MoisTarif]), type date),
    Prix = Table.TransformColumns(DateEffet, {
        {"PrixKWhEuro", fnNombreFr, type number},
        {"AbonnementMensuelEuro", fnNombreFr, type number}}),          // vide reste null, pas 0
    Raison = Table.AddColumn(Prix, "RaisonRejet", each
        if [DateEffet] = null then "Date d'effet illisible"
        else if [PrixKWhEuro] = null then "Prix absent"
        else if [PrixKWhEuro] < 0 then "Prix négatif"
        else null, type text),
    Valides = Table.SelectRows(Raison, each [RaisonRejet] = null),
    UneLigneParEnergieEtDate = Table.Distinct(Valides, {"CodeEnergie", "DateEffet"}),
    Energie = Table.NestedJoin(UneLigneParEnergieEtDate, {"CodeEnergie"}, DimEnergie, {"CodeEnergie"}, "E", JoinKind.Inner),
    AvecId = Table.ExpandTableColumn(Energie, "E", {"IdTypeEnergie"})
in
    Table.RemoveColumns(AvecId, {"RaisonRejet", "MoisTarif"})

// ---------- Int_Audits (TP 5)
let
    Source = Stg_Audits,
    Renomme = Table.RenameColumns(Source, {{"codeBatiment", "CodeBatiment"}, {"dateAudit", "DateAudit"},
        {"classeEnergetique", "ClasseEnergetique"}, {"consommationReferenceKWhM2", "ConsommationReferenceKWhM2"},
        {"priorite", "Priorite"}, {"recommandation", "Recommandation"}, {"coutEstimeEuro", "CoutEstimeEuro"}}),
    Textes = Table.TransformColumns(Renomme, {
        {"CodeBatiment", each Text.Upper(Text.Trim(_)), type text},
        {"Priorite", each Text.Proper(Text.Trim(_)), type text},
        {"DateAudit", each try Date.FromText(_, [Format = "yyyy-MM-dd"])
                          otherwise Date.FromText(_, [Format = "dd/MM/yyyy"]), type date},
        {"ConsommationReferenceKWhM2", fnNombreFr, type number}}),
    Cout = Table.TransformColumnTypes(Textes, {{"CoutEstimeEuro", Currency.Type}}),
    // Null n'est pas zéro : un coût absent signifie « à chiffrer »
    Statut = Table.AddColumn(Cout, "StatutChiffrage", each
        if [CoutEstimeEuro] = null then "À chiffrer" else "Chiffré", type text),
    Fusion = Table.NestedJoin(Statut, {"CodeBatiment"}, DimBatiment, {"CodeBatiment"}, "Ref", JoinKind.LeftOuter),
    AvecId = Table.ExpandTableColumn(Fusion, "Ref", {"IdBatiment"})
in
    Table.SelectRows(AvecId, each [IdBatiment] <> null)
// Rejets_Audits : même requête, Table.SelectRows(AvecId, each [IdBatiment] = null) -> BAT-INCONNU
