import secrets
from fastapi import Header, HTTPException
from database import get_user_by_token, reset_quota_if_needed

def generate_token():
    """Génère un token unique sécurisé"""
    return secrets.token_urlsafe(32)

async def verify_token_and_quota(x_api_token: str = Header(...)):
    """
    Vérifie le token et le quota de l'utilisateur.
    À utiliser comme dépendance FastAPI sur les routes protégées.
    """
    user = get_user_by_token(x_api_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Token invalide ou compte inactif")
    
    # Remet le quota à zéro si nouveau jour
    reset_quota_if_needed(user["id"], user["last_reset"])
    
    # Recharge l'user après reset potentiel
    user = get_user_by_token(x_api_token)
    
    if user["videos_today"] >= user["quota_daily"]:
        raise HTTPException(
            status_code=429,
            detail=f"Quota journalier atteint ({user['quota_daily']} vidéos/jour). Revenez demain !"
        )
    
    return user


async def verify_token_only(x_api_token: str = Header(...)):
    """
    Vérifie uniquement le token, sans vérifier le quota.
    À utiliser pour les routes qui ne consomment pas de quota.
    """
    user = get_user_by_token(x_api_token)
    if not user:
        raise HTTPException(status_code=401, detail="Token invalide ou compte inactif")
    return user
