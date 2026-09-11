/* ============================================================
   PROJET NOVARIA
   Base de données des consommations énergétiques
   Compatible SQL Server / SQL Server Express
   ============================================================ */

USE master;
GO

/* ============================================================
   1. Création de la base
   ============================================================ */

IF DB_ID('Novaria_NRJ') IS NULL
BEGIN
    CREATE DATABASE Novaria_NRJ;
END;
GO

USE Novaria_NRJ;
GO

/* ============================================================
   2. Suppression des objets pour rejouer le script
   ============================================================ */

IF OBJECT_ID('dbo.VW_ConsommationsEnergetiques', 'V') IS NOT NULL
    DROP VIEW dbo.VW_ConsommationsEnergetiques;
GO

IF OBJECT_ID('dbo.ConsommationEnergetique', 'U') IS NOT NULL
    DROP TABLE dbo.ConsommationEnergetique;

IF OBJECT_ID('dbo.BatimentEnergie', 'U') IS NOT NULL
    DROP TABLE dbo.BatimentEnergie;

IF OBJECT_ID('dbo.TypeEnergie', 'U') IS NOT NULL
    DROP TABLE dbo.TypeEnergie;

IF OBJECT_ID('dbo.Batiment', 'U') IS NOT NULL
    DROP TABLE dbo.Batiment;

IF OBJECT_ID('dbo.Quartier', 'U') IS NOT NULL
    DROP TABLE dbo.Quartier;
GO

/* ============================================================
   3. Table des quartiers
   ============================================================ */

CREATE TABLE dbo.Quartier
(
    IdQuartier      INT IDENTITY(1,1) PRIMARY KEY,
    CodeQuartier    VARCHAR(10) NOT NULL UNIQUE,
    NomQuartier     VARCHAR(100) NOT NULL,
    Population      INT NOT NULL,
    Latitude        DECIMAL(9,6) NULL,
    Longitude       DECIMAL(9,6) NULL
);
GO

INSERT INTO dbo.Quartier
(
    CodeQuartier,
    NomQuartier,
    Population,
    Latitude,
    Longitude
)
VALUES
('CTR', 'Centre-ville', 32000, 45.833600, 1.261100),
('NOR', 'Quartier Nord', 28000, 45.857100, 1.258200),
('NES', 'Nord-Est', 35000, 45.853200, 1.291400),
('EST', 'Quartier Est', 31000, 45.832000, 1.303100),
('SES', 'Sud-Est', 37000, 45.807900, 1.293500),
('SUD', 'Quartier Sud', 29000, 45.802100, 1.259900),
('SOU', 'Sud-Ouest', 26000, 45.814800, 1.226700),
('OUE', 'Quartier Ouest', 32000, 45.839300, 1.220400);
GO

/* ============================================================
   4. Table des bâtiments publics
   ============================================================ */

CREATE TABLE dbo.Batiment
(
    IdBatiment          INT IDENTITY(1,1) PRIMARY KEY,
    CodeBatiment        VARCHAR(20) NOT NULL UNIQUE,
    NomBatiment         VARCHAR(150) NOT NULL,
    TypeBatiment        VARCHAR(50) NOT NULL,
    IdQuartier          INT NOT NULL,
    SurfaceM2           DECIMAL(10,2) NOT NULL,
    AnneeConstruction   SMALLINT NULL,
    NbOccupantsMoyen    INT NULL,
    EstRenove            BIT NOT NULL DEFAULT 0,
    DateMiseEnService   DATE NULL,

    CONSTRAINT FK_Batiment_Quartier
        FOREIGN KEY (IdQuartier)
        REFERENCES dbo.Quartier(IdQuartier)
);
GO

INSERT INTO dbo.Batiment
(
    CodeBatiment,
    NomBatiment,
    TypeBatiment,
    IdQuartier,
    SurfaceM2,
    AnneeConstruction,
    NbOccupantsMoyen,
    EstRenove,
    DateMiseEnService
)
VALUES
('BAT-MAIRIE', 'Hôtel de ville', 'Administration', 1, 8500, 1895, 420, 1, '1895-06-01'),
('BAT-MEDIA', 'Médiathèque centrale', 'Médiathèque', 1, 6200, 2001, 700, 1, '2001-09-15'),
('BAT-ECO-N', 'École primaire du Nord', 'École', 2, 4100, 1974, 380, 0, '1974-09-01'),
('BAT-GYM-NE', 'Gymnase Nord-Est', 'Gymnase', 3, 5200, 1982, 240, 1, '1982-01-10'),
('BAT-ECO-E', 'Groupe scolaire de l''Est', 'École', 4, 5900, 1998, 610, 1, '1998-09-01'),
('BAT-HLM-SE', 'Résidence sociale des Horizons', 'HLM', 5, 17500, 1968, 980, 0, '1968-03-01'),
('BAT-PISC', 'Piscine municipale NeoWave', 'Piscine', 6, 7800, 1992, 850, 1, '1992-07-01'),
('BAT-STADE', 'Stade municipal', 'Équipement sportif', 6, 9800, 1987, 520, 0, '1987-05-12'),
('BAT-ECO-SO', 'École des Jardins', 'École', 7, 3600, 1959, 290, 1, '1959-09-01'),
('BAT-ATELIER', 'Ateliers municipaux', 'Services techniques', 8, 11200, 1978, 310, 0, '1978-04-01'),
('BAT-COLLECTE', 'Centre de collecte Ouest', 'Déchets', 8, 6700, 2008, 180, 1, '2008-11-20'),
('BAT-HLM-N', 'Résidence sociale du Parc', 'HLM', 2, 14200, 1972, 760, 1, '1972-06-01');
GO

/* ============================================================
   5. Types d'énergie
   ============================================================ */

CREATE TABLE dbo.TypeEnergie
(
    IdTypeEnergie       INT IDENTITY(1,1) PRIMARY KEY,
    CodeEnergie         VARCHAR(20) NOT NULL UNIQUE,
    LibelleEnergie      VARCHAR(100) NOT NULL,
    Unite               VARCHAR(20) NOT NULL,
    PrixUnitaireEuro    DECIMAL(10,5) NOT NULL,
    EmissionCO2KgParKWh DECIMAL(10,5) NOT NULL,
    EstRenouvelable     BIT NOT NULL DEFAULT 0
);
GO

INSERT INTO dbo.TypeEnergie
(
    CodeEnergie,
    LibelleEnergie,
    Unite,
    PrixUnitaireEuro,
    EmissionCO2KgParKWh,
    EstRenouvelable
)
VALUES
('ELEC', 'Électricité', 'kWh', 0.25160, 0.05200, 0),
('GAZ',  'Gaz naturel', 'kWh', 0.11840, 0.22700, 0),
('RCU',  'Réseau de chaleur urbain', 'kWh', 0.09650, 0.08500, 1),
('SOLAIRE', 'Production photovoltaïque', 'kWh', 0.00000, 0.00000, 1);
GO

/* ============================================================
   6. Énergies utilisées par chaque bâtiment
   ============================================================ */

CREATE TABLE dbo.BatimentEnergie
(
    IdBatiment       INT NOT NULL,
    IdTypeEnergie    INT NOT NULL,
    TypeFlux         VARCHAR(20) NOT NULL,

    CONSTRAINT PK_BatimentEnergie
        PRIMARY KEY (IdBatiment, IdTypeEnergie),

    CONSTRAINT CK_BatimentEnergie_TypeFlux
        CHECK (TypeFlux IN ('Consommation', 'Production')),

    CONSTRAINT FK_BatimentEnergie_Batiment
        FOREIGN KEY (IdBatiment)
        REFERENCES dbo.Batiment(IdBatiment),

    CONSTRAINT FK_BatimentEnergie_TypeEnergie
        FOREIGN KEY (IdTypeEnergie)
        REFERENCES dbo.TypeEnergie(IdTypeEnergie)
);
GO

/* Tous les bâtiments consomment de l'électricité */
INSERT INTO dbo.BatimentEnergie
SELECT IdBatiment, 1, 'Consommation'
FROM dbo.Batiment;

/* Bâtiments chauffés au gaz */
INSERT INTO dbo.BatimentEnergie
VALUES
(3, 2, 'Consommation'),
(4, 2, 'Consommation'),
(8, 2, 'Consommation'),
(9, 2, 'Consommation'),
(10, 2, 'Consommation');

/* Bâtiments raccordés au réseau de chaleur */
INSERT INTO dbo.BatimentEnergie
VALUES
(1, 3, 'Consommation'),
(2, 3, 'Consommation'),
(5, 3, 'Consommation'),
(6, 3, 'Consommation'),
(7, 3, 'Consommation'),
(11, 3, 'Consommation'),
(12, 3, 'Consommation');

/* Bâtiments équipés de panneaux photovoltaïques */
INSERT INTO dbo.BatimentEnergie
VALUES
(2, 4, 'Production'),
(5, 4, 'Production'),
(7, 4, 'Production'),
(10, 4, 'Production'),
(11, 4, 'Production');
GO

/* ============================================================
   7. Table des relevés énergétiques
   ============================================================ */

CREATE TABLE dbo.ConsommationEnergetique
(
    IdReleve            BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdBatiment          INT NOT NULL,
    IdTypeEnergie       INT NOT NULL,
    DateMesure          DATE NOT NULL,
    TypeFlux            VARCHAR(20) NOT NULL,
    QuantiteKWh         DECIMAL(14,3) NOT NULL,
    CoutEuro            DECIMAL(14,2) NOT NULL,
    EmissionCO2Kg       DECIMAL(14,3) NOT NULL,
    TemperatureMoyenne  DECIMAL(5,2) NULL,
    SourceDonnee        VARCHAR(50) NOT NULL,
    DateChargement      DATETIME2 NOT NULL DEFAULT SYSDATETIME(),

    CONSTRAINT CK_Consommation_TypeFlux
        CHECK (TypeFlux IN ('Consommation', 'Production')),

    CONSTRAINT CK_Consommation_Quantite
        CHECK (QuantiteKWh >= 0),

    CONSTRAINT FK_Consommation_Batiment
        FOREIGN KEY (IdBatiment)
        REFERENCES dbo.Batiment(IdBatiment),

    CONSTRAINT FK_Consommation_TypeEnergie
        FOREIGN KEY (IdTypeEnergie)
        REFERENCES dbo.TypeEnergie(IdTypeEnergie),

    CONSTRAINT UQ_Consommation_Releve
        UNIQUE (IdBatiment, IdTypeEnergie, DateMesure)
);
GO

/* ============================================================
   8. Génération des dates
   ============================================================ */

DECLARE @DateDebut DATE = '2024-01-01';
DECLARE @DateFin   DATE = '2026-06-30';

;WITH Calendrier AS
(
    SELECT @DateDebut AS DateMesure

    UNION ALL

    SELECT DATEADD(DAY, 1, DateMesure)
    FROM Calendrier
    WHERE DateMesure < @DateFin
),
DonneesBase AS
(
    SELECT
        be.IdBatiment,
        be.IdTypeEnergie,
        be.TypeFlux,
        c.DateMesure,
        b.SurfaceM2,
        b.TypeBatiment,
        te.PrixUnitaireEuro,
        te.EmissionCO2KgParKWh,

        /* Température saisonnière fictive */
        CAST(
            12
            + 10 * SIN(
                2 * PI()
                * (DATEPART(DAYOFYEAR, c.DateMesure) - 172)
                / 365.0
            )
            + ((ABS(CHECKSUM(NEWID())) % 600) / 100.0 - 3)
            AS DECIMAL(5,2)
        ) AS TemperatureMoyenne

    FROM Calendrier c
    CROSS JOIN dbo.BatimentEnergie be
    INNER JOIN dbo.Batiment b
        ON b.IdBatiment = be.IdBatiment
    INNER JOIN dbo.TypeEnergie te
        ON te.IdTypeEnergie = be.IdTypeEnergie
),
CalculConsommation AS
(
    SELECT
        *,

        CAST(
            CASE
                /* Production solaire */
                WHEN IdTypeEnergie = 4 THEN
                    CASE
                        WHEN MONTH(DateMesure) IN (5, 6, 7, 8)
                            THEN SurfaceM2 * 0.080
                        WHEN MONTH(DateMesure) IN (3, 4, 9, 10)
                            THEN SurfaceM2 * 0.045
                        ELSE SurfaceM2 * 0.015
                    END

                /* Électricité */
                WHEN IdTypeEnergie = 1 THEN
                    SurfaceM2
                    * CASE TypeBatiment
                        WHEN 'Piscine'             THEN 0.55
                        WHEN 'HLM'                 THEN 0.32
                        WHEN 'École'               THEN 0.18
                        WHEN 'Gymnase'             THEN 0.25
                        WHEN 'Médiathèque'         THEN 0.28
                        WHEN 'Administration'      THEN 0.26
                        WHEN 'Services techniques' THEN 0.34
                        WHEN 'Déchets'             THEN 0.38
                        ELSE 0.22
                      END

                /* Gaz ou réseau de chaleur */
                ELSE
                    SurfaceM2
                    * CASE
                        WHEN TemperatureMoyenne < 0  THEN 0.95
                        WHEN TemperatureMoyenne < 5  THEN 0.75
                        WHEN TemperatureMoyenne < 10 THEN 0.52
                        WHEN TemperatureMoyenne < 15 THEN 0.28
                        ELSE 0.06
                      END
            END

            /* Variation journalière aléatoire de ±10 % */
            * (
                0.90
                + (ABS(CHECKSUM(NEWID())) % 21) / 100.0
              )

            /* Moindre occupation le week-end,
               sauf piscines, gymnases et HLM */
            * CASE
                WHEN DATEPART(WEEKDAY, DateMesure) IN (1, 7)
                     AND TypeBatiment NOT IN
                         ('Piscine', 'Gymnase', 'HLM', 'Équipement sportif')
                    THEN 0.55
                ELSE 1
              END

            AS DECIMAL(14,3)
        ) AS QuantiteCalculee

    FROM DonneesBase
)
INSERT INTO dbo.ConsommationEnergetique
(
    IdBatiment,
    IdTypeEnergie,
    DateMesure,
    TypeFlux,
    QuantiteKWh,
    CoutEuro,
    EmissionCO2Kg,
    TemperatureMoyenne,
    SourceDonnee
)
SELECT
    IdBatiment,
    IdTypeEnergie,
    DateMesure,
    TypeFlux,
    QuantiteCalculee,

    CASE
        WHEN TypeFlux = 'Production' THEN 0
        ELSE ROUND(QuantiteCalculee * PrixUnitaireEuro, 2)
    END,

    CASE
        WHEN TypeFlux = 'Production' THEN 0
        ELSE ROUND(QuantiteCalculee * EmissionCO2KgParKWh, 3)
    END,

    TemperatureMoyenne,

    CASE IdTypeEnergie
        WHEN 1 THEN 'Compteur électrique'
        WHEN 2 THEN 'Facturation fournisseur gaz'
        WHEN 3 THEN 'Réseau de chaleur NeoCity'
        WHEN 4 THEN 'Onduleur photovoltaïque'
    END

FROM CalculConsommation
OPTION (MAXRECURSION 0);
GO

/* ============================================================
   9. Index pour Power BI et les analyses
   ============================================================ */

CREATE INDEX IX_Consommation_DateMesure
    ON dbo.ConsommationEnergetique(DateMesure);

CREATE INDEX IX_Consommation_Batiment_Date
    ON dbo.ConsommationEnergetique(IdBatiment, DateMesure);

CREATE INDEX IX_Consommation_Energie_Date
    ON dbo.ConsommationEnergetique(IdTypeEnergie, DateMesure);
GO

/* ============================================================
   10. Vue simplifiée pour Power BI
   ============================================================ */

CREATE VIEW dbo.VW_ConsommationsEnergetiques
AS
SELECT
    ce.IdReleve,
    ce.DateMesure,

    q.IdQuartier,
    q.CodeQuartier,
    q.NomQuartier,
    q.Population,

    b.IdBatiment,
    b.CodeBatiment,
    b.NomBatiment,
    b.TypeBatiment,
    b.SurfaceM2,
    b.AnneeConstruction,
    b.NbOccupantsMoyen,
    b.EstRenove,

    te.IdTypeEnergie,
    te.CodeEnergie,
    te.LibelleEnergie,
    te.EstRenouvelable,

    ce.TypeFlux,
    ce.QuantiteKWh,
    ce.CoutEuro,
    ce.EmissionCO2Kg,
    ce.TemperatureMoyenne,
    ce.SourceDonnee,
    ce.DateChargement

FROM dbo.ConsommationEnergetique ce
INNER JOIN dbo.Batiment b
    ON b.IdBatiment = ce.IdBatiment
INNER JOIN dbo.Quartier q
    ON q.IdQuartier = b.IdQuartier
INNER JOIN dbo.TypeEnergie te
    ON te.IdTypeEnergie = ce.IdTypeEnergie;
GO

/* ============================================================
   11. Contrôles
   ============================================================ */

SELECT COUNT(*) AS NombreDeReleves
FROM dbo.ConsommationEnergetique;

SELECT TOP (20) *
FROM dbo.VW_ConsommationsEnergetiques
ORDER BY DateMesure DESC, NomBatiment;

SELECT
    YEAR(DateMesure) AS Annee,
    TypeFlux,
    LibelleEnergie,
    ROUND(SUM(QuantiteKWh), 0) AS TotalKWh,
    ROUND(SUM(CoutEuro), 2) AS CoutTotalEuro,
    ROUND(SUM(EmissionCO2Kg), 0) AS EmissionsCO2Kg
FROM dbo.VW_ConsommationsEnergetiques
GROUP BY
    YEAR(DateMesure),
    TypeFlux,
    LibelleEnergie
ORDER BY
    Annee,
    TypeFlux,
    LibelleEnergie;
GO