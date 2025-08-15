import os
from datetime import datetime
from Helper_ODBCConnection import get_conn_it_ticketing
import sys
import subprocess
import json
import re
import pandas as pd
import unicodedata
from typing import Union, Optional


this_program_name = os.path.basename(sys.argv[0])  # e.g., 'my_app.exe'
env_mode = "prod"  # change to "prod" before deployment


def clean_names(
        df: pd.DataFrame,
        case_type: str = "snake",
        remove_special: bool = True,
        strip_underscores: Union[str, bool] = True,
        strip_accents: bool = True,
        truncate_limit: Optional[int] = None,
        enforce_string: bool = True,
        preserve_original_labels: bool = False
) -> pd.DataFrame:
    """
    Clean DataFrame column names to mimic pyjanitor.clean_names functionality.

    Parameters:
    -----------
    df : pd.DataFrame whose column names are to be cleaned.
    case_type : str, default 'lower'
        Specification for case type. Options are:
        - 'lower': lowercase
        - 'upper': uppercase
        - 'snake': snake_case
        - 'preserve': preserve original case
    remove_special : bool, default False
        If True, removes all characters except letters, numbers, and underscores.
    strip_underscores : str or bool, default True
        Removes leading and/or trailing underscores. Options:
        - True or 'both': strips from both sides
        - 'left' or 'l': strips from left side only
        - 'right' or 'r': strips from right side only
        - False: no stripping
    strip_accents : bool, default True
        If True, removes accents from characters (converts to ASCII equivalents).
    truncate_limit : int, optional
        Truncates column names to this many characters.
    enforce_string : bool, default True
        If True, ensures all column names are strings.
    preserve_original_labels : bool, default False
        If True, stores original column names in df.attrs['original_labels'].

    Returns:
    --------
    pd.DataFrame with cleaned column names.
    """
    # Store original labels if requested
    if preserve_original_labels:
        df.attrs['original_labels'] = list(df.columns)

    def _clean_name(name: str) -> str:
        # Ensure string type
        if enforce_string:
            name = str(name)

        # Strip accents if requested
        if strip_accents:
            name = _strip_accents(name)

        # Handle case conversion
        if case_type == "lower":
            name = name.lower()
        elif case_type == "upper":
            name = name.upper()
        elif case_type == "snake":
            name = _to_snake_case(name)
        elif case_type == "preserve":
            pass  # Keep original case
        else:
            raise ValueError(f"Invalid case_type: {case_type}. Must be one of: 'lower', 'upper', 'snake', 'preserve'")

        # Remove special characters if requested
        if remove_special:
            # Keep only letters, numbers, and underscores
            name = re.sub(r"[^a-zA-Z0-9_]", "", name)
        else:
            # Replace non-alphanumeric characters (except underscores) with underscores
            name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Collapse multiple underscores
        name = re.sub(r"_+", "_", name)

        # Strip underscores based on option
        if strip_underscores:
            if strip_underscores is True or strip_underscores == "both":
                name = name.strip("_")
            elif strip_underscores in ["left", "l"]:
                name = name.lstrip("_")
            elif strip_underscores in ["right", "r"]:
                name = name.rstrip("_")

        # Truncate if limit specified
        if truncate_limit and len(name) > truncate_limit:
            name = name[:truncate_limit]
            # Clean up any trailing underscore after truncation
            if strip_underscores:
                name = name.rstrip("_")

        return name

    # Apply cleaning to column names
    df = df.rename(columns=lambda x: _clean_name(str(x) if enforce_string else x))

    return df


def _strip_accents(text: str) -> str:
    """
    Remove accents from characters, converting to ASCII equivalents.
    """
    # Normalize to NFD (decomposed form) and filter out combining characters
    normalized = unicodedata.normalize('NFD', text)
    ascii_text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return ascii_text


def _to_snake_case(text: str) -> str:
    """
    Convert text to snake_case.
    """
    # Insert underscore before uppercase letters that follow lowercase letters
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
    # Convert to lowercase
    text = text.lower()
    # Replace any non-alphanumeric characters with underscores
    text = re.sub(r'[^a-z0-9_]', '_', text)
    # Collapse multiple underscores
    text = re.sub(r'_+', '_', text)
    return text



def get_email_addresses_df():
    """
    Get agent names and email addresses from the database.
    
    Returns:
        list: List of tuples containing (name, email) pairs
    """
    conn = get_conn_it_ticketing("IT_Ticketing")
    cursor = conn.cursor()

    try:
        # Get all users with email addresses using cursor to avoid SQLAlchemy warning
        query = "SELECT * FROM Users WHERE email_address IS NOT NULL"
        cursor.execute(query)
        
        # Create DataFrame from cursor results
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        # Convert rows to list of lists to ensure proper DataFrame creation
        rows_list = [list(row) for row in rows]
        df = pd.DataFrame(rows_list, columns=columns).copy()
        df = clean_names(df)

        # Create full name and return name-email pairs
        df['full_name'] = df['first_name'] + ' ' + df['last_name']
        
        return df
    except Exception as e:
        print(f"Error executing users query: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

print( get_email_addresses_df())





