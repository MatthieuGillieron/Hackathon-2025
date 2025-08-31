# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import Dict, List


class EmailAnalysis(BaseModel):
    """Analysis result for email classification"""
    
    important: int = Field(..., description="Nombre d'emails importants")
    events: int = Field(..., description="Nombre d'emails liés à des événements")
    notifications: int = Field(..., description="Nombre de notifications")
    promotions: int = Field(..., description="Nombre d'emails promotionnels")
    others: int = Field(..., description="Nombre d'autres emails")
    total: int = Field(..., description="Nombre total d'emails analysés")
    details: List[str] = Field(..., description="Détails des catégories principales")