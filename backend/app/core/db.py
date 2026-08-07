# backend/app/db.py
"""Thin database-access layer. Centralises connection creation so routers and
services never talk to psycopg2 directly for plumbing."""
from engine.utils import data_loader


def get_db_connection():
    """Return a live psycopg2 connection (caller owns close())."""
    return data_loader.get_connection()