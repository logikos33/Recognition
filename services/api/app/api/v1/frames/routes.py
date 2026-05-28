"""
Recognition — Frames Routes.
"""
import logging

from flask import Blueprint

logger = logging.getLogger(__name__)

frames_bp = Blueprint("frames", __name__, url_prefix="/api/frames")
