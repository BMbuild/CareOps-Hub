# CareOps Hub

**Finalité :** CareOps Hub relie le suivi des problèmes produit au suivi des implémentations clients, pour qu'aucun client ne soit déployé avec un problème critique ouvert. Un problème critique non résolu fait automatiquement passer le client à « Non prêt ».

Projet inspiré du poste « Project Manager, Client Implementations » (Chef de projet – Implémentations clients) chez HHAeXchange. Détails dans [PRD.md](PRD.md).

**Équipe :** Brahim (espace Produit) · Sarah (espace Implémentation)

## User stories

1. **Signaler un problème** : en tant que responsable Produit, je veux enregistrer un problème technique avec sa gravité, sa fonctionnalité et les clients touchés, pour que l'équipe Implémentation voie tout de suite son impact.
   - Critère : Claude peut suggérer une gravité ; je la valide ou je la change avant d'enregistrer.
2. **Suivre la résolution** : en tant que responsable Produit, je veux changer l'état d'un problème (Ouvert, En cours, Résolu), pour que l'état de préparation des clients concernés se mette à jour sans action manuelle.
3. **Piloter les étapes** : en tant que cheffe de projet Implémentation, je veux gérer les étapes clés d'un client (échéance, responsable, statut, point de blocage), pour savoir ce qui reste à faire avant le go-live.
   - Critère : une étape dont l'échéance est dépassée est signalée « En retard ».
4. **Savoir si un client est prêt** : en tant que cheffe de projet Implémentation, je veux voir l'état de préparation de chaque client (Non prêt, À risque, Prêt, En cours) avec sa raison, pour ne jamais lancer un déploiement avec un problème critique ouvert.
5. **Communiquer avec le client** : en tant que cheffe de projet Implémentation, je veux que Claude rédige un résumé de préparation puis un brouillon d'e-mail, pour informer le client rapidement et honnêtement.
   - Critère : rien n'est envoyé automatiquement ; je relis et je modifie avant d'envoyer.

## Lancer l'application

Stack : front HTML, CSS et JavaScript · backend **FastAPI** (Python 3.10+) · base **SQLite** (`data/careops.db`, créée au premier démarrage avec les données de démo).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload
```

Ouvrez ensuite http://localhost:8000. La documentation interactive de l'API est sur http://localhost:8000/docs.

Les fonctions IA ont besoin d'une clé Anthropic dans `.env` : `ANTHROPIC_API_KEY=` suivi de votre clé. Sans clé, l'application fonctionne normalement ; seuls les boutons Claude renvoient une erreur.

Tests : `.venv/bin/python -m pytest` (chaque test utilise une base temporaire, jamais `data/careops.db`).

## Composant 1 : création d'un ticket technique (espace Produit)

Le formulaire **+ Nouveau problème** envoie `POST /api/issues` au backend FastAPI, qui valide les champs (Pydantic) et enregistre le ticket dans SQLite. La liste est relue depuis la base (`GET /api/state`).

**Critère de succès :** un ticket est créé, enregistré, affiché, puis retrouvé après actualisation de la page, sans doublon.

**Vérification (4 novembre 2026) :**

| Étape | Résultat |
| --- | --- |
| Création dans l'interface | `POST /api/issues` → `201 Created` |
| Enregistrement en base | Ligne présente dans la table `issues`, client lié dans `issue_clients` |
| Affichage dans la liste | Ticket visible une seule fois |
| Actualisation de la page | Toujours une seule fois, gravité et statut conservés |
| Redémarrage du serveur | Ticket toujours présent |

Le test automatique `tests/test_tickets.py` rejoue ce scénario.

### Hypothèses sur les gravités et les statuts

**Gravité** (obligatoire, `Moyenne` par défaut). Trois niveaux, une hypothèse encore à valider (voir [Hypothèses et validation](#hypothèses-et-validation-assumptions-and-validation)) :

| Gravité (English) | Définition | Effet sur la préparation du client |
| --- | --- | --- |
| Critique (Critical) | Bloque une fonction essentielle (visites, EVV, facturation, conformité) sans contournement, ou crée un risque réglementaire | **Non prêt** tant qu'il n'est pas résolu |
| Moyenne (Medium) | Gêne réelle ; un contournement existe, même s'il est coûteux | Aucun |
| Faible (Low) | Défaut mineur ou esthétique | Aucun |

Seule une étape en retard met un client « À risque ». Aucune gravité ne le fait.

**Statut** (le statut initial est choisi à la création, `Ouvert` par défaut) :

| Statut | Signification | Compte comme non résolu ? |
| --- | --- | --- |
| Ouvert | Signalé, personne n'y travaille encore | Oui |
| En cours | Correctif en cours | Oui |
| Résolu | Correctif livré et vérifié | Non |

Autres hypothèses :

- Un ticket peut toucher plusieurs clients, ou aucun (problème interne).
- Seul « Résolu » lève le blocage : un ticket « En cours » bloque autant qu'un ticket « Ouvert ».
- Il n'y a pas de statut « Fermé » ou « Rejeté » dans le MVP : un ticket créé par erreur est supprimé.
- Toute autre valeur est refusée par l'API (erreur 400) et par la base (contrainte `CHECK`).
- Claude peut suggérer une gravité ; c'est toujours une personne qui la valide.

## Hypothèses et validation (Assumptions and Validation)

### H1 : trois niveaux de gravité suffisent

| | |
| --- | --- |
| **Hypothèse** | Les tickets techniques se classent en trois niveaux : Faible (Low), Moyenne (Medium) et Critique (Critical). |
| **Pourquoi nous l'avons faite** | Trois niveaux suffisent pour construire et tester le workflow des tickets. La décision qui compte pour le déploiement est binaire : le problème bloque-t-il le go-live (Critique) ou non ? Moins de niveaux, c'est aussi moins d'hésitation au moment de classer un ticket. |
| **Risque** | Nous n'avons pas vérifié que les équipes d'implémentation en santé priorisent ainsi. Un niveau intermédiaire peut manquer : par exemple un problème grave avec contournement coûteux, qui devrait alerter sans bloquer. Sans lui, ce type de problème est classé « Moyenne » et n'apparaît pas dans la préparation, ou « Critique » et bloque le déploiement à tort. Les règles d'escalade (qui prévenir, sous quel délai) ne sont pas non plus modélisées. |
| **Comment la valider** | 1. Demander à 2 ou 3 personnes qui travaillent en implémentation ou en support santé comment elles classent leurs tickets, et si 3 niveaux leur suffisent. 2. Leur faire classer les 6 tickets de démo, puis comparer leurs choix avec les nôtres. 3. Relever les tickets qu'elles voudraient voir signalés sans bloquer le déploiement. 4. Comparer avec les niveaux courants des outils de support (souvent 4, de P1 à P4). |
| **Ce qui changerait** | Si les retours montrent un besoin de catégories ou de règles d'escalade différentes, nous ajoutons un niveau (par exemple « Élevée », qui mettrait un client « À risque ») ou une règle d'escalade, et nous mettons à jour le PRD, la base et les tests. Le code est prévu pour : la liste des gravités est définie à un seul endroit par couche. |
| **Statut** | Non validée. Utilisée pour le MVP. |

## Démo en 5 minutes

1. **Produit (Brahim)** : « Horizon Soins à Domicile » est « Non prêt » à cause du problème critique « Export EVV rejeté ».
2. Passez ce problème à **Résolu** : le client reste « Non prêt », parce que l'étape « Test EVV avec l'État » est encore **Bloquée**.
3. **Implémentation (Sarah)** : passez cette étape à **En cours** : le client passe à « En cours ».
4. Cliquez sur **Générer le résumé de préparation**, puis sur **Rédiger l'e-mail au client**.
5. **Produit** : créez un nouveau problème, puis cliquez sur **Suggérer la gravité avec Claude**.

Pour voir la synchro entre les deux espaces, ouvrez deux fenêtres : une sur Produit, l'autre sur Implémentation.
**Réinitialiser la démo** remet les données de départ.

## Structure

| Fichier | Rôle |
| --- | --- |
| `app/main.py` | Serveur FastAPI : routes des données, routes IA, front |
| `app/db.py` | Schéma SQLite, données de démo, lecture et écriture |
| `app/models.py` | Validation des champs (Pydantic) |
| `app/readiness.py` | Règle de préparation au déploiement |
| `app/ai.py` | Appels à Claude (résumé, gravité, e-mail) |
| `data/seed.json` | Données de démo fictives |
| `public/` | Interface HTML, CSS et JavaScript |
| `tests/` | Tests pytest |

## Sécurité : aucun identifiant dans le dépôt

- La clé reste dans `.env`, côté serveur. Le navigateur n'appelle jamais l'API Anthropic.
- `.gitignore` exclut `.env`, `.env.*` (sauf `.env.example`), `*.pem`, `*.key`, `.venv/` et la base `data/*.db`.
- Un hook `pre-commit` ([scripts/check-secrets.sh](scripts/check-secrets.sh)) bloque tout commit qui contient un fichier `.env` ou une clé connue (Anthropic, Slack, GitHub, AWS, Google, clé privée, lien secrets.pursuit.org).
- Les clés ne passent jamais par Git, Slack ou e-mail : chaque partenaire crée son propre `.env`.
- Toutes les données sont fictives.

**Après avoir cloné le dépôt (chaque partenaire, une seule fois) :**

```bash
git config core.hooksPath .githooks
sh scripts/check-secrets.sh
git check-ignore -v .env
```

La première commande active le garde-fou. La dernière doit afficher une ligne de `.gitignore`.

**Si une clé est commitée par erreur :** révoquez-la immédiatement dans la console Anthropic, puis créez-en une nouvelle. La supprimer du code ne suffit pas, car elle reste dans l'historique Git.
