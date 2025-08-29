#!/usr/bin/env python3
"""
API Connector Factory - Creates properly configured API connectors for different account types
"""

import logging
from typing import Optional
from pathlib import Path
from .api_connector import KISAPIConnector

logger = logging.getLogger(__name__)

def create_api_connector(account_type: str = "MOCK", config_path: str = "") -> Optional[KISAPIConnector]:
    """
    Create a properly configured KISAPIConnector instance
    
    Args:
        account_type: "REAL" or "MOCK"
        config_path: Configuration file path
        
    Returns:
        KISAPIConnector instance or None if creation failed
    """
    try:
        is_mock = account_type.upper() == "MOCK"
        
        connector = KISAPIConnector(config_path=config_path, is_mock=is_mock)
        
        logger.info(f"API Connector created for {account_type} account")
        return connector
        
    except Exception as e:
        logger.error(f"Failed to create API connector for {account_type}: {e}")
        return None

def get_api_connector(account_type: str = "MOCK") -> Optional[KISAPIConnector]:
    """
    Get API connector with simplified interface
    
    Args:
        account_type: "REAL" or "MOCK"
        
    Returns:
        KISAPIConnector instance or None
    """
    return create_api_connector(account_type)