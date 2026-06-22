#!/usr/bin/env python3
"""
brain_credential.py — Horizon AIOS Brain Credential Manager
============================================================

Stores and retrieves brain OS account passwords in the native OS keystore
(Windows Credential Manager / macOS Keychain / Linux Secret Service) via
the 'keyring' library.

CLI Usage (admin/root only):
    python brain_credential.py get <brain-name>      # print password to stdout
    python brain_credential.py rotate <brain-name>   # generate new password, update OS + keyring
    python brain_credential.py delete <brain-name>   # remove credential from keyring
    python brain_credential.py list                  # list brain names with stored credentials

Importable interface (used by create_brain.py):
    from brain_credential import store_password
    store_password(brain_name, password)  -> bool

Keyring service name : "horizon_aios"
Keyring username key : "brain_account:<brain-name>"
"""

import os
import platform
import secrets
import subprocess
import sys

# ---------------------------------------------------------------------------
# Keyring availability
# ---------------------------------------------------------------------------

_KEYRING_AVAILABLE = False
_keyring = None

try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    pass

KEYRING_SERVICE = 'horizon_aios'


def _keyring_username(brain_name: str) -> str:
    return f'brain_account:{brain_name}'


def _warn_no_keyring(brain_name: str = '<name>') -> None:
    print(
        '[WARN] No keyring backend available. Install \'keyring\' (pip install keyring) '
        'or manage the password manually:',
        file=sys.stderr,
    )
    print(
        f'  Windows: Set-LocalUser -Name "{brain_name}" -Password (Read-Host -AsSecureString)',
        file=sys.stderr,
    )
    print(f'  Linux/macOS: sudo passwd {brain_name}', file=sys.stderr)


# ---------------------------------------------------------------------------
# Admin / root check
# ---------------------------------------------------------------------------

def _check_privileges() -> None:
    """Exit with a clear message if not running elevated."""
    os_name = platform.system()
    if os_name == 'Windows':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if not is_admin:
            print(
                '[ERROR] This script must be run as Administrator.\n'
                '  Right-click your terminal and choose "Run as administrator",\n'
                '  then re-run the script.',
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if os.geteuid() != 0:
            print(
                '[ERROR] This script must be run as root.\n'
                '  Re-run with: sudo python brain_credential.py <command> <brain-name>',
                file=sys.stderr,
            )
            sys.exit(1)


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------

def _generate_password() -> str:
    """Generate a cryptographically random 64-character URL-safe password."""
    return secrets.token_urlsafe(48)


# ---------------------------------------------------------------------------
# OS account password update
# ---------------------------------------------------------------------------

def _update_os_account_password(brain_name: str, password: str) -> bool:
    """
    Update the OS account password for brain_name.
    Returns True on success, False on failure.
    """
    os_name = platform.system()
    try:
        if os_name == 'Windows':
            # Pass the password via an environment variable (AIOS_BRAIN_PW) read
            # inside PowerShell as $env:AIOS_BRAIN_PW, rather than interpolating
            # it into the command string. Avoids quoting/injection fragility and
            # keeps the secret off the process command line.
            subprocess.run(
                [
                    'powershell', '-NonInteractive', '-Command',
                    f'Set-LocalUser -Name "{brain_name}" '
                    f'-Password (ConvertTo-SecureString $env:AIOS_BRAIN_PW '
                    f'-AsPlainText -Force)',
                ],
                check=True,
                env=dict(os.environ, AIOS_BRAIN_PW=password),
            )
        elif os_name == 'Linux':
            proc = subprocess.run(
                ['chpasswd'],
                input=f'{brain_name}:{password}',
                text=True,
                check=True,
            )
        else:  # macOS / Darwin
            subprocess.run(
                ['dscl', '.', '-passwd',
                 f'/Local/Default/Users/{brain_name}', password],
                check=True,
            )
        return True
    except subprocess.CalledProcessError as exc:
        print(f'[ERROR] Failed to update OS account password: {exc}', file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Keyring operations
# ---------------------------------------------------------------------------

def store_password(brain_name: str, password: str) -> bool:
    """
    Store brain account password in the OS keystore.

    Returns True on success, False if keyring is unavailable or the
    operation fails.  This function is safe to import and call from
    create_brain.py without crashing provisioning if keyring is absent.
    """
    if not _KEYRING_AVAILABLE:
        _warn_no_keyring(brain_name)
        return False

    try:
        _keyring.set_password(KEYRING_SERVICE, _keyring_username(brain_name), password)
        return True
    except _keyring.errors.NoKeyringError:
        _warn_no_keyring(brain_name)
        return False
    except Exception as exc:
        print(f'[ERROR] keyring.set_password failed: {exc}', file=sys.stderr)
        return False


def _get_password(brain_name: str) -> str | None:
    """
    Retrieve stored password for brain_name from the OS keystore.
    Returns the password string, or None if not found / keyring unavailable.
    """
    if not _KEYRING_AVAILABLE:
        _warn_no_keyring(brain_name)
        return None

    try:
        return _keyring.get_password(KEYRING_SERVICE, _keyring_username(brain_name))
    except _keyring.errors.NoKeyringError:
        _warn_no_keyring(brain_name)
        return None
    except Exception as exc:
        print(f'[ERROR] keyring.get_password failed: {exc}', file=sys.stderr)
        return None


def _delete_credential(brain_name: str) -> bool:
    """
    Remove stored credential for brain_name from the OS keystore.
    Returns True on success or if the credential did not exist.
    """
    if not _KEYRING_AVAILABLE:
        _warn_no_keyring(brain_name)
        return False

    try:
        _keyring.delete_password(KEYRING_SERVICE, _keyring_username(brain_name))
        return True
    except _keyring.errors.PasswordDeleteError:
        # Credential did not exist — treat as success
        return True
    except _keyring.errors.NoKeyringError:
        _warn_no_keyring(brain_name)
        return False
    except Exception as exc:
        print(f'[ERROR] keyring.delete_password failed: {exc}', file=sys.stderr)
        return False


def _list_brains() -> list[str]:
    """
    Return a list of brain names that have stored credentials.

    keyring has no universal enumerate API, so we use backend-specific
    approaches where possible and fall back to an empty list with a note.
    """
    if not _KEYRING_AVAILABLE:
        _warn_no_keyring()
        return []

    try:
        # keyring >= 23.x: some backends expose get_credential for enumeration,
        # but there is no universal list API.  Try the keyring.core backend's
        # get_keyring() to check for SecretService (Linux) which supports enumeration.
        backend = _keyring.get_keyring()
        backend_name = type(backend).__name__

        # SecretService (Linux/D-Bus): enumerate via secretstorage if available
        if 'SecretService' in backend_name:
            try:
                import secretstorage
                bus = secretstorage.dbus_init()
                collection = secretstorage.get_default_collection(bus)
                prefix = 'brain_account:'
                brains = []
                for item in collection.get_all_items():
                    attrs = item.get_attributes()
                    svc = attrs.get('service', '')
                    uname = attrs.get('username', '')
                    if svc == KEYRING_SERVICE and uname.startswith(prefix):
                        brains.append(uname[len(prefix):])
                return sorted(brains)
            except Exception:
                pass

        print(
            '[INFO] Enumeration not supported by the active keyring backend '
            f'({backend_name}).\n'
            '  Use "brain_credential.py get <name>" to check individual brains.',
            file=sys.stderr,
        )
        return []

    except Exception as exc:
        print(f'[ERROR] Failed to list credentials: {exc}', file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_get(brain_name: str) -> int:
    """Print the stored password to stdout. Admin-only."""
    password = _get_password(brain_name)
    if password is None:
        print(
            f'[ERROR] No stored credential found for brain "{brain_name}" '
            f'in service "{KEYRING_SERVICE}".',
            file=sys.stderr,
        )
        return 1
    print(password)
    return 0


def cmd_rotate(brain_name: str) -> int:
    """Generate a new password, update the OS account, and store in keyring."""
    new_password = _generate_password()

    os_ok = _update_os_account_password(brain_name, new_password)
    if not os_ok:
        print('[ERROR] OS account password update failed. Keyring NOT updated.', file=sys.stderr)
        return 1

    kr_ok = store_password(brain_name, new_password)
    if not kr_ok:
        print(
            '[WARN] OS account password was rotated but keyring storage failed.\n'
            '  The new password was not stored. Reset manually if needed.',
            file=sys.stderr,
        )
        return 1

    print(f'[OK] Password rotated for brain "{brain_name}" and stored in keyring.')
    return 0


def cmd_delete(brain_name: str) -> int:
    """Remove stored credential from keyring."""
    ok = _delete_credential(brain_name)
    if ok:
        print(f'[OK] Credential deleted for brain "{brain_name}".')
        return 0
    return 1


def cmd_list() -> int:
    """List brain names with stored credentials."""
    brains = _list_brains()
    if brains:
        print(f'Stored brain credentials (service: {KEYRING_SERVICE}):')
        for name in brains:
            print(f'  {name}')
    else:
        print('No brain credentials found (or enumeration not supported by backend).')
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(
            'Usage:\n'
            '  brain_credential.py get <brain-name>\n'
            '  brain_credential.py rotate <brain-name>\n'
            '  brain_credential.py delete <brain-name>\n'
            '  brain_credential.py list',
            file=sys.stderr,
        )
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'list':
        _check_privileges()
        sys.exit(cmd_list())

    if len(sys.argv) < 3:
        print(f'[ERROR] Command "{command}" requires a <brain-name> argument.', file=sys.stderr)
        sys.exit(1)

    brain_name = sys.argv[2]
    _check_privileges()

    if command == 'get':
        sys.exit(cmd_get(brain_name))
    elif command == 'rotate':
        sys.exit(cmd_rotate(brain_name))
    elif command == 'delete':
        sys.exit(cmd_delete(brain_name))
    else:
        print(f'[ERROR] Unknown command: {command}', file=sys.stderr)
        print('  Valid commands: get, rotate, delete, list', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
