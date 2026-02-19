# Wan 2.2 Backend API

Backend FastAPI pour sécuriser les clés API RunPod.

## Installation locale

```bash
pip install -r requirements.txt
```

## Configuration

Créez un fichier `.env` :
```
RUNPOD_API_KEY=votre_cle
RUNPOD_ENDPOINT_ID=votre_endpoint_id
```

## Lancer en local

```bash
uvicorn main:app --reload
```

API disponible sur http://localhost:8000

## Endpoints

- `POST /generate` - Lance une génération
- `GET /status/{job_id}` - Récupère le statut
- `POST /cancel/{job_id}` - Annule un job

## Déploiement

### Railway (recommandé)

1. Créez un compte sur https://railway.app
2. New Project → Deploy from GitHub
3. Ajoutez les variables d'environnement
4. Deploy !

### Vercel

1. Installez Vercel CLI: `npm i -g vercel`
2. `vercel` dans le dossier
3. Ajoutez les variables d'environnement dans le dashboard
