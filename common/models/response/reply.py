# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class ReplyResponse(BaseModel):
    """Response model for AI-generated email reply"""
    
    subject: str = Field(..., description="Sujet de la réponse (Re: ...)")
    body: str = Field(..., description="Corps de la réponse générée par l'IA")
    tone: str = Field(..., description="Ton utilisé (professionnel, amical, etc.)")