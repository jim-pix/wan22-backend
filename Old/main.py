from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from typing import Optional
from dotenv import load_dotenv
from database import init_db, create_user, list_users, increment_video_count, deactivate_user, activate_user, delete_user, update_quota, list_loras, create_lora, update_lora, delete_lora, get_lora_by_id
from auth import verify_token_and_quota, generate_token

# Charger le .env
load_dotenv()

app = FastAPI()

# Initialiser la base de données au démarrage
init_db()

# CORS pour autoriser l'interface à appeler le backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wonderful-queijadas-b5ad58.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "changeme")  # ← à mettre dans votre .env !

if not RUNPOD_API_KEY or not RUNPOD_ENDPOINT_ID:
    raise ValueError("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set")

RUNPOD_BASE_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"


class GenerateRequest(BaseModel):
    user_prompt: str
    image_base64: str
    workflow_type: int = 1
    video_format: str = "16:9"
    size_scale: int = 65
    video_length: int = 81
    frame_rate: int = 8
    rife_multiplier: int = 2
    motion_amplitude: float = 1.0
    color_protect: bool = False
    correct_strength: float = 0.0
    workflow_name: str = "animation_image"


class CreateUserRequest(BaseModel):
    email: str
    quota_daily: int = 3  # nombre de vidéos par jour


class TriggerWord(BaseModel):
    label: str   # ex: "Cinématique"
    word: str    # ex: "cine_style"


class CreateLoraRequest(BaseModel):
    name: str
    filename: str                        # ex: "cinematic-style.safetensors"
    description: Optional[str] = None
    category: str = "style"             # "style" | "character"
    trigger_words: list[TriggerWord] = []
    default_strength: float = 0.8       # entre 0.0 et 1.0
    preview_url: Optional[str] = None


class UpdateLoraRequest(BaseModel):
    name: Optional[str] = None
    filename: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    trigger_words: Optional[list[TriggerWord]] = None
    default_strength: Optional[float] = None
    preview_url: Optional[str] = None
    is_active: Optional[int] = None


# ─────────────────────────────────────────────
# ROUTES ADMIN (protégées par ADMIN_SECRET)
# ─────────────────────────────────────────────

@app.post("/admin/create-user")
async def admin_create_user(
    request: CreateUserRequest,
    x_admin_secret: str = Header(...)
):
    """Crée un nouvel utilisateur beta avec son token"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    token = generate_token()
    success = create_user(request.email, token, request.quota_daily)
    
    if not success:
        raise HTTPException(status_code=400, detail="Email déjà existant")
    
    return {
        "message": f"Utilisateur {request.email} créé",
        "token": token,
        "quota_daily": request.quota_daily,
        "instructions": f"Partagez ce token à l'utilisateur. Il doit l'envoyer dans le header X-Api-Token"
    }


@app.get("/admin/users")
async def admin_list_users(x_admin_secret: str = Header(...)):
    """Liste tous les utilisateurs"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return list_users()



@app.post("/admin/deactivate-user")
async def admin_deactivate_user(email: str, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not deactivate_user(email):
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return {"message": f"Utilisateur {email} désactivé"}


@app.post("/admin/activate-user")
async def admin_activate_user(email: str, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not activate_user(email):
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return {"message": f"Utilisateur {email} réactivé"}


@app.delete("/admin/delete-user")
async def admin_delete_user(email: str, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not delete_user(email):
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return {"message": f"Utilisateur {email} supprimé définitivement"}


@app.post("/admin/update-quota")
async def admin_update_quota(email: str, quota_daily: int, x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not update_quota(email, quota_daily):
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return {"message": f"Quota de {email} mis à jour : {quota_daily} vidéos/jour"}


# ─────────────────────────────────────────────
# ROUTES ADMIN — LORAS
# ─────────────────────────────────────────────

@app.post("/admin/loras")
async def admin_create_lora(request: CreateLoraRequest, x_admin_secret: str = Header(...)):
    """Ajoute un nouveau LoRA au catalogue"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    trigger_words = [tw.dict() for tw in request.trigger_words]
    success = create_lora(
        name=request.name,
        filename=request.filename,
        description=request.description,
        category=request.category,
        trigger_words=trigger_words,
        default_strength=request.default_strength,
        preview_url=request.preview_url
    )
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du LoRA")
    return {"message": f"LoRA '{request.name}' ajouté avec succès"}


@app.put("/admin/loras/{lora_id}")
async def admin_update_lora(lora_id: int, request: UpdateLoraRequest, x_admin_secret: str = Header(...)):
    """Modifie un LoRA existant"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    kwargs = {k: v for k, v in request.dict().items() if v is not None}
    if "trigger_words" in kwargs:
        kwargs["trigger_words"] = [tw.dict() if hasattr(tw, "dict") else tw for tw in kwargs["trigger_words"]]
    if not update_lora(lora_id, **kwargs):
        raise HTTPException(status_code=404, detail="LoRA non trouvé")
    return {"message": f"LoRA {lora_id} mis à jour"}


@app.delete("/admin/loras/{lora_id}")
async def admin_delete_lora(lora_id: int, x_admin_secret: str = Header(...)):
    """Supprime un LoRA du catalogue"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not delete_lora(lora_id):
        raise HTTPException(status_code=404, detail="LoRA non trouvé")
    return {"message": f"LoRA {lora_id} supprimé"}


@app.get("/admin/loras")
async def admin_list_loras(x_admin_secret: str = Header(...)):
    """Liste tous les LoRAs (actifs et inactifs) pour l'admin"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Accès refusé")
    return list_loras(active_only=False)

# ─────────────────────────────────────────────
# ROUTES PUBLIQUES
# ─────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Wan 2.2 Backend API"}


@app.get("/loras")
async def get_loras(user=Depends(verify_token_and_quota)):
    """Retourne la liste des LoRAs disponibles (utilisateurs authentifiés)"""
    return list_loras(active_only=True)


@app.get("/me")
async def get_me(user=Depends(verify_token_and_quota)):
    """Retourne les infos de quota de l'utilisateur connecté"""
    return {
        "email": user["email"],
        "videos_today": user["videos_today"],
        "quota_daily": user["quota_daily"],
        "remaining": user["quota_daily"] - user["videos_today"]
    }


# ─────────────────────────────────────────────
# ROUTES PROTÉGÉES (nécessitent un token valide)
# ─────────────────────────────────────────────

@app.post("/generate")
async def generate_video(
    request: GenerateRequest,
    user=Depends(verify_token_and_quota)
):
    """Lance une génération vidéo (quota vérifié automatiquement)"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RUNPOD_BASE_URL}/run",
                headers={
                    "Authorization": f"Bearer {RUNPOD_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={"input": request.dict()}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"RunPod error: {response.text}"
                )
            
            # Incrémente le compteur seulement si RunPod a accepté le job
            increment_video_count(user["id"])
            
            return response.json()
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="RunPod timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}")
async def get_status(job_id: str, user=Depends(verify_token_and_quota)):
    """Récupère le statut d'un job"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{RUNPOD_BASE_URL}/status/{job_id}",
                headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"RunPod error: {response.text}"
                )
            
            return response.json()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str, user=Depends(verify_token_and_quota)):
    """Annule un job en cours"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{RUNPOD_BASE_URL}/cancel/{job_id}",
                headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"}
            )
            
            if response.status_code not in [200, 204]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"RunPod error: {response.text}"
                )
            
            return {"status": "cancelled", "job_id": job_id}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
