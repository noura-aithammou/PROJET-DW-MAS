# SPECIFICATION DU PIPELINE — PROJET AVIS BANCAIRES (Google Maps)

Ce document fournit une spécification du pipeline de traitement des avis clients extraits de Google Maps pour les agences bancaires marocaines.

## Objectif
Centraliser, nettoyer, enrichir et analyser les avis clients afin de produire des jeux de données analytiques et des tableaux de bord exploitables pour les décideurs : tendances de satisfaction, thèmes récurrents, classement des agences, alertes opérationnelles.

## Livrables
- Données brutes (CSV/JSON) stockées dans un répertoire dédié.
- Table de staging PostgreSQL pour garantir un point d'ingestion stable.
- Table enrichie avec informations sémantiques.
- Schéma en étoile pour les analyses (fact_reviews, dim_bank, dim_branch, dim_location, dim_topic, dim_sentiment).
- Dashboards interactifs et exports .

## Pile technique (versions recommandées)
- Python 3.8+
- dbt
- Airflow
- Selenium / ChromeDriver / BeautifulSoup
- Transformers (BERT), spaCy, NLTK
- PostgreSQL >= 12
- Looker Studio pour les dashboards

## Vue d'ensemble du pipeline
1. Extraction (Scraping)
2. Ingestion (chargement en staging)
3. Nettoyage & Enrichissement sémantique
4. Transformation & Modélisation (dbt)
5. Orchestration / Automatisation (Airflow)
6. Visualisation et exports

---

## Étape 1 — Extraction (Scraping)
**Objectif :** Collecter automatiquement les avis Google Maps pour une liste de banques et de villes.  

**Entrées :** liste des banques/branches, paramètres de scraping (périmètre, fréquence).  
**Sorties :** fichiers JSON/CSV bruts.

### Technologies utilisées
- Selenium (navigation web automatisée)
- ChromeDriver (contrôle de Chrome)
- pandas (sérialisation des résultats)
- time, random (temporisations aléatoires)
- BeautifulSoup (parsing HTML)

### Logique détaillée
- Charger la liste des cibles (banque, ville, identifiant agence si disponible)
- Pour chaque cible :
  - Charger la page Google Maps correspondante et attendre le chargement des avis
  - Gérer le scroll infini et les popups
  - Extraire : id_avis, texte, note, date, auteur, id_agence, nom_agence, avis
  - Enregistrer les données horodatées
- Stocker les résultats pour l’étape suivante

### Bonnes pratiques & contraintes
- Respecter les conditions d'utilisation de Google Maps
- Utiliser des temporisations aléatoires et rotation d'IP/proxy si nécessaire
- Journaliser les erreurs et raisons d'échec
- Limiter la fréquence et prévoir un mécanisme de reprise (checkpointing)

---

## Étape 2 — Ingestion (Chargement en staging)
**Objectif :** Charger les fichiers bruts dans une table de staging PostgreSQL pour garantir un point d'ingestion stable.  
**Entrées :** fichiers CSV/JSON  
**Sorties :** table PostgreSQL staging  

**Logique :**
- Valider le schéma des fichiers entrants
- Nettoyer les valeurs extrêmes/invalides
- Charger par batch et journaliser les fichiers traités
- En cas d'erreur : rollback et stockage pour revue

---

## Étape 3 — Nettoyage & enrichissement sémantique
**Objectif :** Produire un dataset enrichi prêt pour l'analyse (langue, sentiment, topics, entités nommées, normalisation des adresses).  
**Entrées :** table staging  
**Sorties :** table enrichie ou fichiers intermédiaires  

**Technologies :** transformers (BERT), spaCy, NLTK, pandas  
**Logique :**
- Nettoyage textuel : normalisation, lowercasing, suppression ponctuation, tokenisation
- Détection de la langue et adaptation des modèles
- Sentiment : score brut + label (pos/neg/neu)
- Topic extraction : LDA/BERT embeddings
- Enrichissements additionnels : entités nommées, intentions, normalisation d'adresse

---

## Étape 4 — Transformation & Modélisation (dbt)
**Objectif :** Transformer les données enrichies en modèles analytiques structurés et produire documentation et tests.  
**Logique :**
- Déduplication, normalisation et jointures
- Construction du star schema
- Tests de qualité : unicité, non-null, distribution des dates
- Documentation des modèles

---

## Étape 5 — Orchestration & Automatisation (Airflow)
**Objectif :** Planifier et orchestrer les étapes précédentes avec gestion des dépendances et des retries.  
**Logique :**
- Définir retries et backoff
- Configurer les connexions
- Notifications d’échec critique

---

## Étape 6 — Visualisation et Dashboards
**Objectif :** Fournir des tableaux de bord interactifs et KPI synthétiques  
**Bonnes pratiques :**
- Utiliser des vues matérialisées ou marts pour optimiser les temps de réponse
- Documenter les métriques (définition, fenêtre temporelle, agrégation)
