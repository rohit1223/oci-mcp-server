# authentication.py
# ------------------
from pathlib import Path
import oci
from oci.auth.signers import SecurityTokenSigner
from typing import Tuple, Dict
from config import PROFILE_NAME, REGION

def get_session_token_signer(
    profile_name: str = PROFILE_NAME,
    region: str = REGION
) -> Tuple[Dict[str, str], SecurityTokenSigner]:
    """
    Reads OCI session files and returns a (config, signer) tuple.
    Raises:
        FileNotFoundError: if token or key files are missing.
        ValueError: if token is empty.
    """
    session_dir = Path.home() / '.oci' / 'sessions' / profile_name
    token_file = session_dir / 'token'
    key_file = session_dir / 'oci_api_key.pem'

    if not token_file.exists():
        raise FileNotFoundError(f"Session token not found at {token_file}")
    token = token_file.read_text().strip()
    if not token:
        raise ValueError("Session token is empty")

    if not key_file.exists():
        raise FileNotFoundError(f"API key not found at {key_file}")
    private_key = oci.signer.load_private_key_from_file(str(key_file))

    signer = SecurityTokenSigner(token=token, private_key=private_key)
    config = {'region': region}
    return config, signer