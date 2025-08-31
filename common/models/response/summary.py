# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    """Response model for email summary"""
    
    summary: str = Field(..., description="Résumé concis du contenu de l'email")
    key_points: list[str] = Field(..., description="Points clés extraits de la conversation")
    participants: list[str] = Field(..., description="Liste des participants à la conversation")