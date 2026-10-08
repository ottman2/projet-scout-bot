# GandaltF4 CS2 Scouting Bot

Bot Discord Python pour consulter des informations publiques de CS2 depuis l’API officielle FACEIT Data API v4.

## Installation

Python 3.13 est utilisé pour le développement actuel.

```bash
python -m venv .venv
```

Windows PowerShell :

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows cmd.exe :

```bat
.venv\Scripts\activate.bat
```

Installer les dépendances épinglées :

```bash
python -m pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` à la racine du projet :

```dotenv
FACEIT_API_KEY=your_key_here
DISCORD_TOKEN=your_token_here
```

Les deux variables sont requises au démarrage. Ne pas publier ce fichier ni y inscrire de secrets dans le code.

## Lancement

Depuis la racine du dépôt :

```bash
python -m src.main
```

Le bot doit avoir l’intent Discord `message_content` activé pour lire les commandes préfixées.

## Commandes

- `!setmatch <équipe>` : rapport d’avant-match avec maps et membres de l’équipe.
- `!scout <équipe>` : statistiques de maps de l’équipe.
- `!player <pseudo>` : profil, statistiques, équipes, maps et historique de compétitions disponibles.
- `!veto <équipe>` : compare les statistiques FACEIT 5v5 de GandaltF4 à celles de l'adversaire, puis recommande un pick et un ban.

## Architecture

- `src/bot/commands/` : commandes et rendu Discord.
- `src/services/faceit_client.py` : client HTTP partagé, authentification, timeout, classification d’erreurs et retries 429 bornés.
- `src/services/faceit.py` : accès aux ressources FACEIT Data API v4.
- `src/services/*_service.py` : agrégation des données utilisées par les commandes.
- `src/core/analyzer.py` et `src/core/player_analyzer.py` : normalisation des maps, des saisons et des pages.
- `src/config.py` : chargement et validation de la configuration.

## Tests

```bash
pytest
```

Les tests n’effectuent aucune requête réelle vers FACEIT et n’ont pas besoin de clés API.

## Limitations

Le bot utilise l'API officielle FACEIT Data API v4. La commande `!player` parcourt les pages disponibles des équipes et tournois, et interroge l'historique depuis `from=0`. L'API borne l'offset d'historique à 1000 ; des saisons plus anciennes ou absentes des résultats peuvent donc rester inaccessibles. Une saison ESEA n'est retenue que si son nom l'identifie explicitement, si son organisateur est identifié comme ESEA, ou si elle suit le format FACEIT ESEA `Sxx EU Open10`. Les champs statistiques varient selon les données FACEIT ; une statistique absente, notamment le K/D par map, n'est pas estimée. Le VETO ne retient que les maps du pool officiel communiqué : D2 (`Dust2` sur FACEIT), Nuke, Inferno, Cache, Anubis, Ancient et Mirage. Les maps comme Overpass ou Train sont ignorées. Le PICK est limité au pool jouable GandaltF4 : D2, Nuke, Cache, Inferno. Les bans donnent priorité aux trois maps hors de ce pool jouable, avec les maps de notre pool en solutions de repli ; les maps officielles restent listées même si leurs stats manquent, clairement marquées N/A. La liste est à réévaluer après les bans adverses ; elle ne simule pas toute la séquence BO. Le score compare les maps avec winrate disponible : confiance faible sous 10 matchs, moyenne de 10 à 29, élevée à partir de 30 (volume minimum entre les deux équipes). Son score vaut `(différence WR + 5 × différence K/D) × facteur confiance`, avec K/D inclus seulement s'il existe des deux côtés; les facteurs sont 0,5/0,75/1,0. À ±10 points, la map devient favorable/défavorable. `TARGET_CHANNEL_ID` est réservé à de futurs rapports automatiques et n'est pas utilisé par les commandes actuelles.
