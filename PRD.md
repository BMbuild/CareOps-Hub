# PRD — CareOps Hub

4 novembre 2026 · Brahim Maouloud

Version en ligne (avec le schéma) : https://claude.ai/artifact/PcRuH7u88V2t9ZvEr1eG13

## Contexte et problème

CareOps Hub relie le suivi des problèmes produit au suivi des implémentations clients, pour qu'aucun client ne soit déployé avec un problème critique ouvert. Le projet s'inspire du poste « Project Manager, Client Implementations » (Chef de projet – Implémentations clients) chez HHAeXchange.

Aujourd'hui, ces deux suivis vivent souvent dans des outils séparés. Les difficultés visées :

- **Suivi des implémentations** : étapes, échéances et responsables dispersés.
- **Problèmes techniques** : leur gravité et leur état ne sont pas visibles par l'équipe d'implémentation.
- **Communication** : l'équipe Produit et l'équipe Implémentation n'ont pas la même vue de la situation.
- **Préparation au déploiement** : la décision « prêt / pas prêt » se prend à la main, sans règle claire.

## Objectifs et indicateurs de succès

Le MVP réussit si l'état de préparation d'un client se calcule tout seul à partir des données des deux espaces.

| Objectif | Indicateur | Cible MVP |
| --- | --- | --- |
| Une seule source de vérité | Problèmes et étapes visibles dans les deux espaces | 100 % des données partagées |
| Préparation automatique | Un problème critique ouvert bloque le déploiement | Règle appliquée sans action manuelle |
| Visibilité des blocages | Temps pour trouver ce qui bloque un client | Moins de 30 secondes, en une page |
| Démo réaliste | Scénario de démo de bout en bout | Brahim et Sarah le jouent en moins de 5 minutes |

Les cibles chiffrées sont des propositions à valider par l'équipe.

## Utilisateurs

Deux rôles, un par espace de travail, qui lisent les mêmes données.

| Persona | Rôle | Espace | Besoin principal | Question qu'il ou elle se pose |
| --- | --- | --- | --- | --- |
| Brahim | Responsable Produit | Produit | Suivre les fonctionnalités et les problèmes techniques | « Quels problèmes critiques bloquent un client ? » |
| Sarah | Cheffe de projet Implémentation | Implémentation | Piloter les étapes, les échéances et le go-live | « Mon client est-il prêt à déployer, et sinon pourquoi ? » |

## Portée du MVP

Le MVP comprend deux espaces de travail qui lisent et écrivent les mêmes données, plus un état de préparation calculé automatiquement.

```
┌───────────────────────────────┐          ┌───────────────────────────────┐
│ Espace Produit · Brahim       │          │ Espace Implémentation · Sarah │
│ Fonctionnalités               │          │ Étapes clés et échéances      │
│ Problèmes : gravité et état   │          │ Responsables                  │
│ Clients touchés               │          │ Points de blocage             │
└───────────────┬───────────────┘          └───────────────┬───────▲───────┘
   écrit les problèmes                        écrit les étapes     │
                ▼                                          ▼       │
          ┌────────────────────────────────────────────────┐       │
          │ Données partagées (SQLite, serveur FastAPI)    │       │
          └───────────────────────┬────────────────────────┘       │
                                  │ calcul automatique             │
                                  ▼                                │
          ┌────────────────────────────────────────────────┐       │
          │ État de préparation au déploiement             │───────┘
          │ Non prêt si un problème Critique est ouvert    │ affiché chez Sarah
          │ ou si une étape est Bloquée                    │
          └────────────────────────────────────────────────┘
```

Brahim et Sarah écrivent dans la même source ; l'état de préparation est recalculé à chaque changement et s'affiche dans l'espace de Sarah.

## Exigences fonctionnelles

### Espace Produit (Brahim)

- **P1** : Créer, modifier et supprimer une fonctionnalité (nom, description, statut).
- **P2** : Créer un problème technique lié à une fonctionnalité et à un ou plusieurs clients.
- **P3** : Donner à chaque problème une gravité : Critique, Moyenne, Faible (hypothèse à valider, voir README).
- **P4** : Suivre l'état de résolution : Ouvert, En cours, Résolu.
- **P5** : Filtrer les problèmes par gravité, état et client.

### Espace Implémentation (Sarah)

- **I1** : Créer un projet d'implémentation par client, avec une date de go-live.
- **I2** : Ajouter des étapes clés avec échéance, responsable et statut (À faire, En cours, Terminé, Bloqué).
- **I3** : Noter un point de blocage sur une étape, avec sa cause.
- **I4** : Voir les problèmes techniques qui touchent ce client, en lecture seule.
- **I5** : Signaler une étape en retard quand l'échéance est dépassée.

### Règle de préparation au déploiement

L'état se calcule automatiquement pour chaque client, dans cet ordre :

1. **Non prêt** (rouge) : au moins un problème **Critique** non résolu touche ce client, ou une étape est **Bloquée**.
2. **À risque** (orange) : une étape est en retard.
3. **Prêt** (vert) : toutes les étapes sont terminées et aucun problème Critique n'est ouvert.
4. **En cours** (gris) : tous les autres cas.

L'écran affiche toujours la raison de l'état, par exemple « Non prêt : 1 problème critique ouvert (Export EVV) ». Quand Brahim passe un problème à Résolu, l'état chez Sarah change aussitôt.

## Fonctions IA avec Claude

Claude aide à décider et à communiquer, mais ne change jamais une donnée tout seul : un humain valide chaque suggestion. Trois fonctions sont proposées ; l'équipe doit choisir lesquelles entrent dans le MVP.

| Fonction | Espace | Entrée | Sortie | Priorité proposée |
| --- | --- | --- | --- | --- |
| Résumé de préparation | Implémentation | Étapes, blocages et problèmes d'un client | 3 à 5 phrases : état, risques, prochaine action | P0 |
| Gravité suggérée | Produit | Titre et description d'un nouveau problème | Une gravité proposée et sa justification | P1 |
| E-mail de mise à jour client | Implémentation | Résumé de préparation | Brouillon d'e-mail à relire avant envoi | P1 |

Si l'appel à Claude échoue, l'application continue de fonctionner : seule la suggestion est absente.

## Modèle de données

Cinq objets suffisent. Le lien clé est `Problème.clients` : c'est lui qui fait remonter un problème dans l'état de préparation d'un client.

| Objet | Champs principaux | Modifié par |
| --- | --- | --- |
| Client | id, nom, date de go-live | Sarah |
| Fonctionnalité | id, nom, description, statut | Brahim |
| Problème | id, titre, description, gravité, état, fonctionnalité, clients (liste), date de création | Brahim |
| Étape | id, client, nom, échéance, responsable, statut, blocage (texte) | Sarah |
| État de préparation | calculé à la volée, jamais stocké : statut + liste des raisons | Personne (automatique) |

Pour le MVP, les données sont stockées dans une base SQLite côté serveur, avec un jeu de données de démo (3 clients, 4 fonctionnalités, 6 problèmes).

## Stack technique et sécurité

Un front en HTML, CSS et JavaScript simple, servi par un serveur FastAPI (Python) qui garde la clé Anthropic et stocke les données dans SQLite.

| Couche | Choix | Rôle |
| --- | --- | --- |
| Front | HTML, CSS, JavaScript (sans framework) | Deux onglets : Produit et Implémentation |
| Serveur | FastAPI (Python) | API REST pour les données, appels à Claude |
| Données | SQLite (`data/careops.db`) | Données partagées entre les deux espaces |
| IA | API Anthropic (Claude) | Résumés, gravité suggérée, e-mails |

**Sécurité de la clé API**

- La clé vit uniquement dans le fichier `.env` du serveur, lu par `python-dotenv`.
- `.env` est listé dans `.gitignore` et n'est jamais publié sur GitHub.
- Le navigateur appelle le serveur (`/api/ai/...`), jamais l'API Anthropic directement.
- Un fichier `.env.example` sans valeur réelle documente la variable `ANTHROPIC_API_KEY`.

## Hors périmètre, risques et questions ouvertes

**Hors périmètre du MVP**

- Comptes utilisateurs, connexion et droits d'accès
- Base de données hébergée et accès multi-ordinateurs
- Intégrations (Jira, Salesforce, e-mail réel)
- Données réelles de patients ou de clients : uniquement des données fictives

**Risques**

| Risque | Effet | Parade |
| --- | --- | --- |
| Clé API exposée | Usage frauduleux et facture | Clé côté serveur seulement, `.gitignore`, limite de dépenses |
| Règle de préparation trop stricte ou trop souple | État jugé faux par Sarah | Afficher toujours la raison ; ajuster les seuils après la démo |
| Suggestion de Claude erronée | Mauvaise gravité ou e-mail inexact | Validation humaine obligatoire |
| Base SQLite locale | Chaque partenaire a sa propre base | Acceptable pour une démo ; base hébergée en V2 |

**Questions ouvertes**

- [ ] Quelles fonctions IA entrent dans le MVP : les trois, ou seulement le résumé ?
- [ ] Trois niveaux de gravité (Faible, Moyenne, Critique) suffisent-ils aux équipes d'implémentation en santé ? À valider auprès d'utilisateurs.
- [ ] Faut-il un historique des changements d'état pour la démo ?
- [ ] Date de la démo et répartition du travail entre Brahim et Sarah ?
