#!/usr/bin/env python3
"""
horizon_aios_acl_posture.py — ACL posture loader + 3-OS translation engine
==========================================================================

Single source of truth for the Horizon AIOS ACL hardening model. Both
horizon_aios_harden.py (enforcer) and horizon_aios_doctor.py (verifier) load
the posture from here so they can never disagree.

WHAT IT DOES
------------
1. `load_posture(paths, *, etc_dir=None)` parses the AUTHORITATIVE posture file
   `$HORIZON_ETC/file_acl_hardening.toml` with the stdlib `tomllib`, deep-merges
   an optional deployer override `file_acl_hardening.local.toml` OVER it (keyed
   by rule/group `name`; local wins; `disabled = true` drops a rule/group), and
   resolves every `$HORIZON_ROOT`/`$HORIZON_SYSTEM` path variable to an absolute
   path. It returns a `Posture` (groups, must_have_full, ordered rules).

2. FAIL-SECURE: if the default TOML is missing/unreadable/corrupt — or `tomllib`
   is unavailable — it emits a loud WARN and falls back to `EMBEDDED_DEFAULT`, a
   verbatim in-code mirror of the shipped posture. Hardening NEVER silently
   no-ops because a config file went missing.

3. Translation engine: each ABSTRACT rule is mapped to native operations per OS
   — setfacl (Linux), chmod +a (macOS), icacls (Windows) — via
   `linux_rule_ops` / `macos_rule_ops` / `windows_rule_ops`. Each returns a list
   of `Op(argv, kind, msg)`; the caller runs `argv` and logs `msg` under `kind`.

The rights/flags vocabulary is documented at the top of file_acl_hardening.toml.
This module is the faithful realization of that contract. stdlib only.
"""

import collections
import os
import sys

try:
    import tomllib  # Python 3.11+
    _HAVE_TOMLLIB = True
except Exception:  # pragma: no cover - only on <3.11
    tomllib = None
    _HAVE_TOMLLIB = False


# ---------------------------------------------------------------------------
# House-style logging (mirrors harden.py so callers can print consistently).
# ---------------------------------------------------------------------------

def _warn(msg):
    print(f'  [WARN]  {msg}', file=sys.stderr)


# ---------------------------------------------------------------------------
# Well-known principals. Windows well-known SIDs keep grants locale-independent.
#   SYSTEM=S-1-5-18  Administrators=S-1-5-32-544  OWNER RIGHTS=S-1-3-4
# `owner` is the invoking user (resolved by the caller); on Unix it is the only
# meaningful must-have principal.
# ---------------------------------------------------------------------------
WINDOWS_WELL_KNOWN_SIDS = {
    'SYSTEM':         '*S-1-5-18',
    'Administrators': '*S-1-5-32-544',
    'OWNER_RIGHTS':   '*S-1-3-4',
}

# Specific-rights mask denying all write/create/append/delete while leaving
# read/execute/read-attributes intact (Windows "no-write" and Read-Only).
BRAINS_NOWRITE_MASK = '(WD,AD,WEA,WA,DE,DC)'


# ---------------------------------------------------------------------------
# EMBEDDED_DEFAULT — verbatim mirror of the shipped file_acl_hardening.toml.
# FAIL-SECURE fallback: used only if the default TOML cannot be parsed. Kept in
# lock-step with the shipped file; the self-check `embedded_matches_default()`
# asserts the rule/group set is identical to the parsed default.
# ---------------------------------------------------------------------------
EMBEDDED_DEFAULT = {
    'schema_version': 1,
    'groups': [
        {'name': 'brains',         'description': 'Horizon.AIOS group: brains'},
        {'name': 'horizon_humans', 'description': 'Horizon.AIOS Actual Humans'},
    ],
    'must_have_full': ['owner', 'SYSTEM', 'Administrators'],
    'rules': [
        {'name': 'humans-userspace-full',
         'path': '$HORIZON_ROOT', 'principal': 'horizon_humans',
         'rights': 'full', 'recursive': True, 'default': True},
        {'name': 'humans-system-readonly',
         'path': '$HORIZON_SYSTEM', 'principal': 'horizon_humans',
         'rights': 'read-exec', 'recursive': True, 'default': True},
        {'name': 'humans-root-canon-readonly',
         'path': '$HORIZON_ROOT', 'principal': 'horizon_humans',
         'rights': 'read-only',
         'canon_files': ['agents.md', 'CLAUDE.md',
                         '.claude/agents.md', '.claude/CLAUDE.md'],
         'sticky_parents': True},
        {'name': 'humans-brains-readwrite',
         'path': '$HORIZON_ROOT/brains', 'principal': 'horizon_humans',
         'rights': 'read-write', 'recursive': True, 'default': True},
        {'name': 'humans-projects-selfservice',
         'path': '$HORIZON_ROOT/projects', 'principal': 'horizon_humans',
         'rights': 'create-traverse', 'sticky': True, 'setgid': False,
         'isolate_children': True, 'exclude_children': ['shared']},
        {'name': 'humans-projects-shared',
         'path': '$HORIZON_ROOT/projects/shared', 'principal': 'horizon_humans',
         'rights': 'read-write', 'default': True, 'sticky': True,
         'setgid': True, 'group_owner': 'horizon_humans'},
        {'name': 'humans-handoffs-selfservice',
         'path': '$HORIZON_ROOT/handoffs', 'principal': 'horizon_humans',
         'rights': 'create-traverse', 'sticky': True, 'setgid': False,
         'isolate_children': True, 'exclude_children': ['shared']},
        {'name': 'humans-handoffs-shared',
         'path': '$HORIZON_ROOT/handoffs/shared', 'principal': 'horizon_humans',
         'rights': 'read-write', 'default': True, 'sticky': True,
         'setgid': True, 'group_owner': 'horizon_humans'},
        {'name': 'humans-objectives-selfservice',
         'path': '$HORIZON_ROOT/objectives', 'principal': 'horizon_humans',
         'rights': 'create-traverse', 'sticky': True, 'setgid': False,
         'isolate_children': True, 'exclude_children': ['shared']},
        {'name': 'humans-objectives-shared',
         'path': '$HORIZON_ROOT/objectives/shared', 'principal': 'horizon_humans',
         'rights': 'read-write', 'default': True, 'sticky': True,
         'setgid': True, 'group_owner': 'horizon_humans'},
        {'name': 'humans-usrbin-selfservice',
         'path': '$HORIZON_ROOT/usrbin', 'principal': 'horizon_humans',
         'rights': 'create-traverse', 'sticky': True, 'setgid': False,
         'isolate_children': True, 'exclude_children': ['shared']},
        {'name': 'humans-usrbin-shared',
         'path': '$HORIZON_ROOT/usrbin/shared', 'principal': 'horizon_humans',
         'rights': 'read-write', 'default': True, 'sticky': True,
         'setgid': True, 'group_owner': 'horizon_humans'},
        {'name': 'brains-bin-readexec',
         'path': '$HORIZON_SYSTEM/bin', 'principal': 'brains',
         'rights': 'read-exec', 'recursive': True, 'default': True},
        {'name': 'brains-skills-bin-readexec',
         'path': '$HORIZON_SYSTEM/skills_bin', 'principal': 'brains',
         'rights': 'read-exec', 'recursive': True, 'default': True},
        {'name': 'brains-system-nowrite',
         'path': '$HORIZON_SYSTEM', 'principal': 'brains',
         'rights': 'no-write', 'recursive': True, 'default': True,
         'kind': 'deny'},
        {'name': 'brains-sbin-deny',
         'path': '$HORIZON_SYSTEM/sbin', 'principal': 'brains',
         'rights': 'deny', 'recursive': True, 'default': True, 'kind': 'deny'},
        {'name': 'brains-skills-sbin-deny',
         'path': '$HORIZON_SYSTEM/skills_sbin', 'principal': 'brains',
         'rights': 'deny', 'recursive': True, 'default': True, 'kind': 'deny'},
        {'name': 'brains-logs-deny',
         'path': '$HORIZON_SYSTEM/logs', 'principal': 'brains',
         'rights': 'deny', 'recursive': True, 'default': True, 'kind': 'deny'},
    ],
}


# ---------------------------------------------------------------------------
# Rule / Posture model
# ---------------------------------------------------------------------------

# Defaults for every optional rule flag (matches the TOML "flags" documentation).
_RULE_DEFAULTS = {
    'recursive': False,
    'default': False,
    'sticky': False,
    'setgid': None,            # None = leave as-is; True/False = set/clear sgid
    'isolate_children': False,
    'exclude_children': (),
    'kind': 'grant',           # 'grant' | 'deny' (deny phase runs after grants)
    'canon_files': None,
    'sticky_parents': False,
    'group_owner': None,
    'raw': None,               # per-OS escape hatch: {'linux':[...], ...}
}

VALID_RIGHTS = {
    'full', 'read-exec', 'read-only', 'read-write',
    'create-traverse', 'no-write', 'deny', 'none',
}

Op = collections.namedtuple('Op', ['argv', 'kind', 'msg'])
Op.__new__.__defaults__ = (None, None, None)


class Rule:
    """A resolved posture rule. `path` is absolute; `$HORIZON_*` already expanded."""

    def __init__(self, data, paths):
        self.name = data['name']
        self.principal = data.get('principal')
        self.rights = data.get('rights')
        self.raw_path = data.get('path')
        self.path = _expand_path(self.raw_path, paths) if self.raw_path else None
        for key, default in _RULE_DEFAULTS.items():
            setattr(self, key, data.get(key, default))
        # canon_files/exclude_children normalized to plain lists.
        if self.canon_files is not None:
            self.canon_files = list(self.canon_files)
        self.exclude_children = list(self.exclude_children or ())
        self._paths = paths

    # -- shape predicates (drive per-OS translation) -------------------------
    def is_canon(self):
        return bool(self.canon_files)

    def is_shared_dropzone(self):
        return self.group_owner is not None

    def is_selfservice_parent(self):
        # Detect by rule-name convention OR the create-traverse rights, so a
        # deployer override that relaxes a '-selfservice' rule (e.g. projects ->
        # read-write to allow listing) is still treated as a self-service area
        # (children stay isolated). Shipped rules are create-traverse either way,
        # so Linux output is unchanged for the default posture.
        return (self.name or '').endswith('-selfservice') or \
            self.rights == 'create-traverse'

    def canon_abs_files(self, *, dry_run=False):
        """Absolute canon file paths (existing only, or all candidates in dry-run
        so the plan is visible before the files exist)."""
        root = self._paths['horizon_root']
        out = []
        for rel in (self.canon_files or ()):
            cand = os.path.join(root, *rel.replace('\\', '/').split('/'))
            if dry_run or os.path.isfile(cand):
                out.append(cand)
        return out

    def __repr__(self):
        return f'<Rule {self.name} {self.principal}:{self.rights} {self.path}>'


class Posture:
    """Loaded, merged, resolved posture. One source for harden + doctor."""

    def __init__(self, schema_version, groups, must_have_full, rules, paths,
                 *, source):
        self.schema_version = schema_version
        self.groups = groups                  # list of {'name','description'}
        self.must_have_full = must_have_full  # list of principal names
        self.rules = rules                    # list[Rule], file order
        self.paths = paths
        self.source = source                  # 'toml', 'toml+local', 'embedded'

    # -- ordering: grant-before-deny (engine invariant) ----------------------
    def grant_rules(self):
        return [r for r in self.rules if r.kind != 'deny']

    def deny_rules(self):
        return [r for r in self.rules if r.kind == 'deny']

    def ordered_rules(self):
        """All grants (file order) then all denies (file order)."""
        return self.grant_rules() + self.deny_rules()

    # -- derived sets both harden and doctor consume -------------------------
    def human_shared_dirs(self):
        """Absolute parents of the SELF-SERVICE areas (rules whose name ends in
        '-selfservice'): projects/, handoffs/, objectives/, usrbin/. Derived from
        the posture so harden + doctor agree from ONE source."""
        out = []
        for r in self.rules:
            if r.is_selfservice_parent() and r.principal == 'horizon_humans':
                out.append(r.path)
        return out

    def human_shared_dir_names(self):
        return [os.path.basename(p) for p in self.human_shared_dirs()]

    def brains_readexec_dirs(self):
        """Absolute dirs where brains get read-exec (bin, skills_bin)."""
        return [r.path for r in self.rules
                if r.principal == 'brains' and r.rights == 'read-exec']

    def brains_deny_dirs(self):
        """Absolute dirs with a full brains deny (sbin, skills_sbin, logs)."""
        return [r.path for r in self.rules
                if r.principal == 'brains' and r.rights == 'deny']

    def group_names(self):
        return [g['name'] for g in self.groups]

    def canon_relpaths(self):
        for r in self.rules:
            if r.is_canon():
                return list(r.canon_files)
        return []


# ---------------------------------------------------------------------------
# Path variable expansion
# ---------------------------------------------------------------------------

def _expand_path(raw, paths):
    """Expand $HORIZON_ROOT / $HORIZON_SYSTEM in a rule path to an absolute path.
    $HORIZON_SYSTEM is tried first (longer/more specific) so it is not shadowed."""
    s = raw
    s = s.replace('$HORIZON_SYSTEM', paths['horizon_system'])
    s = s.replace('$HORIZON_ROOT', paths['horizon_root'])
    # Normalize any '<abs>/sub' produced by the join above.
    return os.path.normpath(s)


# ---------------------------------------------------------------------------
# Deep-merge of the .local override over the shipped default
# ---------------------------------------------------------------------------

def _merge_named_list(base_list, override_list):
    """Deep-merge two lists of dicts keyed by `name`.
      - override entry with an existing name merges its fields (override wins);
      - a new name is appended (preserving order after existing entries);
      - `disabled = true` drops the entry entirely.
    """
    by_name = collections.OrderedDict((d['name'], dict(d)) for d in base_list)
    appended = []
    for od in override_list:
        name = od.get('name')
        if not name:
            _warn('override entry without a `name` ignored: ' + repr(od))
            continue
        if od.get('disabled'):
            by_name.pop(name, None)
            # A brand-new disabled entry is simply a no-op.
            appended = [a for a in appended if a.get('name') != name]
            continue
        if name in by_name:
            merged = dict(by_name[name])
            merged.update({k: v for k, v in od.items() if k != 'disabled'})
            by_name[name] = merged
        else:
            existing = next((a for a in appended if a.get('name') == name), None)
            if existing is not None:
                existing.update({k: v for k, v in od.items() if k != 'disabled'})
            else:
                appended.append({k: v for k, v in od.items() if k != 'disabled'})
    return list(by_name.values()) + appended


def _deep_merge(default_doc, local_doc):
    """Merge a parsed local TOML doc over the parsed default doc."""
    merged = dict(default_doc)
    if 'schema_version' in local_doc:
        merged['schema_version'] = local_doc['schema_version']
    if 'must_have_full' in local_doc:
        merged['must_have_full'] = list(local_doc['must_have_full'])
    if local_doc.get('groups'):
        merged['groups'] = _merge_named_list(default_doc.get('groups', []),
                                             local_doc['groups'])
    if local_doc.get('rules'):
        merged['rules'] = _merge_named_list(default_doc.get('rules', []),
                                            local_doc['rules'])
    return merged


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

DEFAULT_TOML_NAME = 'file_acl_hardening.toml'
LOCAL_TOML_NAME = 'file_acl_hardening.local.toml'


def _etc_dir(paths, etc_dir):
    if etc_dir:
        return etc_dir
    return os.path.join(paths['horizon_system'], 'ai_os_etc')


def _load_toml_file(path):
    with open(path, 'rb') as fh:
        return _normalize_must_have(tomllib.load(fh))


def _normalize_must_have(doc):
    """Lift a `must_have_full` key that TOML parsed INTO the last [[groups]]
    table back up to the top level. In the shipped file_acl_hardening.toml the
    `must_have_full = [...]` line follows the [[groups]] array-of-tables with no
    intervening header, so tomllib (correctly) attaches it to the last group.
    The authoritative file is fixed; the loader faithfully recovers the intent.
    Idempotent and a no-op when the key is already top-level (or absent)."""
    if doc.get('must_have_full') is not None:
        return doc
    groups = doc.get('groups', [])
    for g in groups:
        if 'must_have_full' in g:
            out = dict(doc)
            out['must_have_full'] = list(g['must_have_full'])
            out['groups'] = [{k: v for k, v in gg.items()
                              if k != 'must_have_full'} for gg in groups]
            return out
    return doc


def load_posture(paths, *, etc_dir=None):
    """Load, merge, and resolve the ACL posture.

    Returns a `Posture`. FAIL-SECURE: on any failure reading/parsing the shipped
    default (missing file, corrupt TOML, no tomllib) emit a loud WARN and fall
    back to the EMBEDDED_DEFAULT so hardening never silently no-ops.
    """
    etc = _etc_dir(paths, etc_dir)
    default_path = os.path.join(etc, DEFAULT_TOML_NAME)
    local_path = os.path.join(etc, LOCAL_TOML_NAME)

    default_doc = None
    source = 'toml'
    if not _HAVE_TOMLLIB:
        _warn('tomllib is unavailable (Python < 3.11?). FAIL-SECURE: using the '
              'EMBEDDED default ACL posture so hardening is not skipped.')
        default_doc = _copy_embedded()
        source = 'embedded'
    else:
        try:
            default_doc = _load_toml_file(default_path)
        except FileNotFoundError:
            _warn(f'ACL posture file MISSING: {default_path}. FAIL-SECURE: using '
                  'the EMBEDDED default posture (hardening still enforced).')
            default_doc = _copy_embedded()
            source = 'embedded'
        except Exception as exc:  # tomllib.TOMLDecodeError, OSError, ...
            _warn(f'ACL posture file UNREADABLE/CORRUPT ({exc}). FAIL-SECURE: '
                  'using the EMBEDDED default posture (hardening still enforced).')
            default_doc = _copy_embedded()
            source = 'embedded'

    # Deep-merge the optional deployer override (only when the default parsed OK
    # from disk — an embedded fallback means the etc dir is untrustworthy).
    if source == 'toml' and _HAVE_TOMLLIB and os.path.isfile(local_path):
        try:
            local_doc = _load_toml_file(local_path)
            default_doc = _deep_merge(default_doc, local_doc)
            source = 'toml+local'
        except Exception as exc:
            _warn(f'ACL posture LOCAL override unreadable ({local_path}: {exc}). '
                  'Ignoring the override; applying the shipped default only.')

    return _build_posture(default_doc, paths, source=source)


def _copy_embedded():
    import copy
    return copy.deepcopy(EMBEDDED_DEFAULT)


def _build_posture(doc, paths, *, source):
    schema_version = doc.get('schema_version', 1)
    groups = [dict(g) for g in doc.get('groups', [])]
    must_have_full = list(doc.get('must_have_full', []))
    rules = []
    for rdata in doc.get('rules', []):
        if rdata.get('disabled'):
            continue
        if rdata.get('rights') and rdata['rights'] not in VALID_RIGHTS:
            _warn(f'rule {rdata.get("name")!r} has unknown rights '
                  f'{rdata["rights"]!r}; applying it verbatim may be a no-op.')
        rules.append(Rule(rdata, paths))
    return Posture(schema_version, groups, must_have_full, rules, paths,
                   source=source)


def embedded_matches_default(paths=None, *, etc_dir=None):
    """Unit-check helper: True iff the EMBEDDED fallback's (name, principal,
    rights, kind) rule signature and group set equal the parsed shipped default.
    Returns (ok, detail)."""
    if not _HAVE_TOMLLIB:
        return (False, 'tomllib unavailable — cannot compare against the file')
    paths = paths or {'horizon_root': '/', 'horizon_system': '/horizon_system'}
    etc = _etc_dir(paths, etc_dir)
    try:
        disk = _load_toml_file(os.path.join(etc, DEFAULT_TOML_NAME))
    except Exception as exc:
        return (False, f'could not read shipped default: {exc}')
    disk = _normalize_must_have(disk)

    def sig(doc):
        rules = [(r['name'], r.get('principal'), r.get('rights'),
                  r.get('kind', 'grant')) for r in doc.get('rules', [])]
        groups = [g['name'] for g in doc.get('groups', [])]
        return (doc.get('schema_version'), groups,
                list(doc.get('must_have_full', [])), rules)

    if sig(disk) == sig(EMBEDDED_DEFAULT):
        return (True, 'embedded fallback matches shipped default')
    return (False, 'embedded fallback DIVERGED from shipped default — update '
                   'EMBEDDED_DEFAULT in horizon_aios_acl_posture.py')


# ===========================================================================
# TRANSLATION ENGINE
# ===========================================================================
# Each translator maps ONE abstract rule to native ops for its OS. The caller
# executes op.argv (argv-style, no shell) and logs op.msg under op.kind. Ops
# with argv=None are log-only. Child-enumeration ops are produced ONLY when
# `dry_run` is False (matching the historical behavior: dry-run does not walk
# the filesystem to enumerate peers), so a dry-run plan is deterministic.
# ---------------------------------------------------------------------------

# --- Linux (setfacl) --------------------------------------------------------
# Abstract rights -> POSIX.1e perm triad. POSIX ACLs have NO deny; "no-write"
# for brains is expressed as r-x (reads intact, writes removed) and full "deny"
# as --- plus an owner-only mode clamp on the directory.
_LINUX_PERM = {
    'full':            'rwx',
    'read-exec':       'r-x',
    'read-only':       'r--',
    'read-write':      'rwx',
    'create-traverse': '-wx',
    'no-write':        'r-x',
    'deny':            '---',
    'none':            '---',
}


def linux_rule_ops(rule, paths, *, dry_run=False):
    """Translate one rule to setfacl/chmod/chgrp ops on Linux."""
    if rule.raw is not None and rule.raw.get('linux'):
        return _linux_raw_ops(rule, dry_run=dry_run)

    if rule.is_canon():
        return _linux_canon_ops(rule, dry_run=dry_run)
    if rule.is_shared_dropzone():
        return _linux_shared_ops(rule, dry_run=dry_run)
    if rule.is_selfservice_parent():
        return _linux_selfservice_ops(rule, dry_run=dry_run)
    return _linux_standard_ops(rule, dry_run=dry_run)


def _g(principal):
    return f'g:{principal}'


def _linux_standard_ops(rule, *, dry_run):
    """full / read-exec / read-only / read-write / no-write / deny / none."""
    ops = []
    path = rule.path
    perm = _LINUX_PERM.get(rule.rights)
    if perm is None:
        return [Op(None, 'warn', f'{rule.name}: unsupported rights {rule.rights!r} on Linux')]
    if not (os.path.isdir(path) or os.path.isfile(path) or dry_run):
        return [Op(None, 'warn', f'{rule.name}: path missing, skipping: {path}')]

    ace = f'{_g(rule.principal)}:{perm}'
    rflag = ['-R'] if rule.recursive else []
    ops.append(Op(['setfacl'] + rflag + ['-m', ace, path], None, None))
    if rule.default:
        ops.append(Op(['setfacl'] + rflag + ['-d', '-m', ace, path], None, None))
    # Full deny also clamps the directory's base mode to owner-only (the setfacl
    # --- entry alone leaves the stat mode at 0o770; doctor asserts 0o700).
    if rule.rights == 'deny':
        ops.append(Op(['chmod', '-R', 'u=rwX,go=', path], None, None))
        kind, verb = 'deny', 'DENY (--- + owner-only 700)'
    elif rule.rights in ('no-write',):
        kind, verb = 'deny', f'no-write ({perm})'
    elif rule.rights in ('read-exec', 'read-only'):
        kind, verb = 'grant', f'{rule.rights} ({perm})'
    else:
        kind, verb = 'grant', f'{rule.rights} ({perm})'
    ops.append(Op(None, kind, f'{rule.name}: {rule.principal} {verb} -> {path}'))
    return ops


def _linux_canon_ops(rule, *, dry_run):
    """read-only on named canon files + sticky bit on each canon PARENT dir."""
    ops = []
    perm = _LINUX_PERM['read-only']  # r--
    files = rule.canon_abs_files(dry_run=dry_run)
    for f in files:
        ops.append(Op(['setfacl', '-m', f'{_g(rule.principal)}:{perm}', f], None, None))
        ops.append(Op(None, 'deny', f'{rule.name}: {rule.principal} Read-Only ({perm}) -> {f}'))
    if rule.sticky_parents:
        parents = sorted({os.path.dirname(f) for f in files})
        for parent in parents:
            if os.path.isdir(parent) or dry_run:
                ops.append(Op(['chmod', '+t', parent], None, None))
                ops.append(Op(None, 'grant',
                              f'{rule.name}: sticky bit (owner-only delete) on canon parent: {parent}'))
    return ops


def _linux_selfservice_ops(rule, *, dry_run):
    """create-traverse parent: -wx (write+traverse, NO read) + sticky + clear
    sgid + isolating default ACL, then strip each existing non-excluded child to
    ---. The parent is NEVER -R (that would clobber the -wx traverse ACE); the
    per-child strip IS -R (per child)."""
    ops = []
    area = rule.path
    if not (os.path.isdir(area) or dry_run):
        return [Op(None, 'warn', f'{rule.name}: area missing, skipping: {area}')]

    grp = _g(rule.principal)
    # Parent access perm follows the CONFIGURED rights (shipped: create-traverse
    # -> -wx; a deployer override e.g. read-write -> rwx to allow listing).
    perm = _LINUX_PERM.get(rule.rights, '-wx')
    # Parent access ACE only (no -R, or a -R would clobber the traverse ACE).
    ops.append(Op(['setfacl', '-m', f'{grp}:{perm}', area], None, None))
    # New entries born owner-only: isolating default ACL.
    if rule.isolate_children:
        ops.append(Op(['setfacl', '-d', '-m', f'{grp}:---', area], None, None))
        ops.append(Op(['setfacl', '-d', '-m', 'o::---', area], None, None))
    if rule.sticky:
        ops.append(Op(['chmod', '+t', area], None, None))
    if rule.setgid is False:
        ops.append(Op(['chmod', 'g-s', area], None, None))
    elif rule.setgid is True:
        ops.append(Op(['chmod', 'g+s', area], None, None))
    ops.append(Op(None, 'grant',
                  f'{rule.name}: {rule.principal} self-service ({perm}) + sticky + '
                  f'isolating default on {os.path.basename(area)} parent -> {area}'))
    # Existing children (excluding exclude_children): strip group to --- (access
    # + default), recursively. Enumeration only outside dry-run (deterministic
    # plan; matches historical behavior).
    if rule.isolate_children and not dry_run:
        try:
            children = [os.path.join(area, d) for d in os.listdir(area)
                        if os.path.isdir(os.path.join(area, d))
                        and d not in rule.exclude_children]
        except OSError as exc:
            children = []
            ops.append(Op(None, 'warn', f'{rule.name}: cannot enumerate children {area}: {exc}'))
        for child in children:
            ops.append(Op(['setfacl', '-R', '-m', f'{grp}:---', child], None, None))
            ops.append(Op(['setfacl', '-R', '-d', '-m', f'{grp}:---', child], None, None))
            ops.append(Op(None, 'deny',
                          f'{rule.name}: {rule.principal} isolated from peer entry -> {child}'))
    return ops


def _linux_shared_ops(rule, *, dry_run):
    """shared/ drop-zone: group-owned, setgid+sticky, group rwx (access +
    default). setgid+sticky+group-rwx collapses to mode 3770."""
    ops = []
    shared = rule.path
    if not os.path.isdir(shared) and not dry_run:
        ops.append(Op(['mkdir', '-p', shared], None, None))
    grp = _g(rule.principal)
    if rule.group_owner:
        ops.append(Op(['chgrp', rule.group_owner, shared], None, None))
    # setgid+sticky+group-rwx -> 3770 (owner rwx, group rwx, other ---).
    ops.append(Op(['chmod', '3770', shared], None, None))
    ops.append(Op(['setfacl', '-m', f'{grp}:rwx', shared], None, None))
    if rule.default:
        ops.append(Op(['setfacl', '-d', '-m', f'{grp}:rwx', shared], None, None))
    ops.append(Op(None, 'grant',
                  f'{rule.name}: {rule.principal} shared drop-zone (rwx, setgid+sticky) -> {shared}'))
    return ops


def _linux_raw_ops(rule, *, dry_run):
    ops = []
    for arg in rule.raw['linux']:
        ops.append(Op(['setfacl', '-m', arg, rule.path], None, None))
    ops.append(Op(None, 'grant', f'{rule.name}: raw linux escape hatch -> {rule.path}'))
    return ops


def linux_traverse_ops(posture, paths):
    """Linux-only reachability step (NOT an abstract rule): brains need execute
    (--x) on the AIOS root and the brains/ parent to reach their granted paths
    (bin/skills_bin) and their own workspace (brains/<name>/). Execute-only =
    traverse without listing, preserving inter-brain isolation. mode bits alone
    cannot express a named-group traverse ACE, so this is setfacl-specific and
    lives outside the rule set."""
    if 'brains' not in posture.group_names():
        return []
    ops = []
    root = paths['horizon_root']
    brains = os.path.join(root, 'brains')
    for trav in (root, brains):
        if os.path.isdir(trav):
            ops.append(Op(['setfacl', '-m', 'g:brains:--x', trav], None, None))
    ops.append(Op(None, 'grant', 'brains traverse (--x) on AIOS root + brains/'))
    return ops


# ---------------------------------------------------------------------------
# Self-service ASSERT & REPAIR (per-OS ops).
#
# The rule translators (above) APPLY the posture; they clobber the named-group
# ACE on the self-service parent to -wx and add a --- ACE to existing children,
# so a drifted READ bit on the horizon_humans ACE itself is already re-clamped.
# What they do NOT catch, and what these repair generators additionally assert:
#   - a STRAY named-principal ACE on the PARENT (e.g. `u:someone:r-x` or
#     `g:othergroup:rwx`, access OR default) — the translator only re-pins the
#     horizon_humans ACE and clamps `other::`, so an added third-party ACE would
#     survive. Repair STRIPS EVERYTHING not in config (Linux `setfacl -b`, macOS
#     `chmod -N`, Windows `/reset` + `/inheritance:r`) then re-establishes exactly
#     the configured entries, so the root can carry ONLY the base owner/group/other,
#     the configured horizon_humans ACE (no read), the mask, and the isolating
#     default — plus the sticky bit (mode bits are left untouched by the strip);
#   - a child whose BASE MODE drifted (e.g. `chmod 755 projects/alice`) — the
#     translator's `g:...:---` ACE leaves `other::r-x` and the group mode bits
#     intact, so peers could still read the child. Repair re-asserts `chmod 700`
#     (owner rwx, group ---, other ---) and REMOVES any horizon_humans ACE
#     outright (owner-only means no residual named ACE), not just clamps it.
# These are idempotent: on a clean tree they set what is already set.
# ---------------------------------------------------------------------------

def _selfservice_perm(rule):
    """Configured parent access perm for the self-service group ACE (shipped:
    create-traverse -> -wx; a deployer override e.g. read-write -> rwx)."""
    return _LINUX_PERM.get(rule.rights, '-wx')


def linux_selfservice_repair_ops(rule, children):
    """Assert+repair ops (Linux) for ONE self-service area:
      a. Parent: STRIP EVERYTHING not in the harden config, then re-establish
         exactly the configured entries. `setfacl -b` removes ALL extended ACEs —
         so a stray `u:someone:r-x` / `g:othergroup:rwx` (access OR default) that
         drifted onto the root is GONE — then re-pin the configured group ACE
         (shipped -wx), clamp `other::---`, and re-apply the isolating defaults.
      b. For each existing (non-excluded) child: re-assert owner-only —
         `chmod 700` (repairs a drifted base mode like 755), REMOVE any
         horizon_humans named-group ACE (access + default) so the child carries
         no residual group ACE, and clamp `other::---`.
    `children` is the caller-enumerated list of absolute child dirs (empty in
    dry-run, matching the translators' deterministic-plan convention)."""
    ops = []
    area = rule.path
    grp = _g(rule.principal)
    perm = _selfservice_perm(rule)
    # a. Parent: STRIP EVERYTHING not in config, then re-establish exactly the
    # configured entries (posture rule: the root may carry ONLY the base
    # owner/group/other, the horizon_humans ACE, the mask, and the isolating
    # default). `setfacl -b` removes ALL extended ACEs — the access ACL's named
    # principals + mask AND the entire default ACL — so a stray `u:someone:r-x`
    # or `g:othergroup:rwx` (access or default) injected on the root is gone. `-b`
    # leaves the base mode bits (incl. the sticky bit) untouched. We then re-add
    # exactly the configured entries: re-adding a named group ACE makes setfacl
    # auto-recompute the access mask, and re-adding a default entry makes setfacl
    # copy the default base entries (default:user::/group::/other::) from the
    # access base, so the resulting default ACL is complete and getfacl-clean.
    ops.append(Op(['setfacl', '-b', area], None, None))
    ops.append(Op(['setfacl', '-m', f'{grp}:{perm}', area], None, None))
    ops.append(Op(['setfacl', '-m', 'o::---', area], None, None))
    if rule.isolate_children:
        ops.append(Op(['setfacl', '-d', '-m', f'{grp}:---', area], None, None))
        ops.append(Op(['setfacl', '-d', '-m', 'o::---', area], None, None))
    ops.append(Op(None, 'grant',
                  f'{rule.name}: REPAIR parent -> setfacl -b (strip stray ACEs), '
                  f'then group={perm}, other=---, isolating default re-asserted -> {area}'))
    # b. Children: owner-only. `setfacl -b` strips ALL extended ACLs (the stray
    # horizon_humans ACE AND any widened mask/group-class the drift left behind —
    # a bare `-x g:P` would remove the named ACE but leave `mask::r-x` /
    # `group::r-x` from a `chmod 755`, still exposing the child to the owning
    # group). With no extended ACL, `chmod 700` fully expresses owner-only:
    # owner rwx, group ---, other ---. Order: strip ACLs, THEN clamp the mode
    # (so chmod acts on the real group class, not a residual mask).
    for child in children:
        ops.append(Op(['setfacl', '-R', '-b', child], None, None))
        ops.append(Op(['chmod', '-R', 'u=rwX,go=', child], None, None))
        ops.append(Op(None, 'deny',
                      f'{rule.name}: REPAIR child owner-only (setfacl -b + '
                      f'chmod 700; {rule.principal} ACE removed) -> {child}'))
    return ops


def macos_selfservice_repair_ops(rule, children):
    """Assert+repair ops (macOS). Parent: STRIP the entire ACL (`chmod -N` removes
    ALL ACEs, incl. stray named principals) then re-establish exactly the config:
    re-add the isolating inherited group deny + clamp other via mode bits. Children:
    owner-only mode + strip the horizon_humans ACE. DRY-RUN PRINT ONLY on a Linux
    host."""
    ops = []
    area = rule.path
    grp = f'group:{rule.principal}'
    # Parent: remove the entire ACL first (strips any stray named-principal ACE),
    # then re-add ONLY the configured isolating deny + clamp other. `chmod -N`
    # leaves the base mode bits (incl. sticky) intact.
    ops.append(Op(['chmod', '-N', area], 'grant',
                  f'{rule.name}: REPAIR strip ACL / stray ACEs on parent -> {area}'))
    if rule.isolate_children:
        ops.append(Op(['chmod', '+a', f'{grp} deny list,search,{_MACOS_INHERIT}',
                       area], 'grant',
                      f'{rule.name}: REPAIR isolating inherited deny -> {area}'))
    ops.append(Op(['chmod', 'o-rwx', area], 'grant',
                  f'{rule.name}: REPAIR parent other=--- -> {area}'))
    for child in children:
        ops.append(Op(['chmod', '-R', 'go=', child], 'deny',
                      f'{rule.name}: REPAIR child owner-only mode -> {child}'))
        ops.append(Op(['chmod', '-R', '-a#', '0', child], 'deny',
                      f'{rule.name}: REPAIR strip inherited/group ACEs -> {child}'))
    return ops


def windows_selfservice_repair_ops(rule, paths, children, *, owner=None):
    """Assert+repair ops (Windows). Parent: STRIP EVERYTHING not in config, then
    re-establish exactly the config principals. `/reset` drops ALL explicit ACEs
    (incl. any stray non-config principal) and re-enables inheritance; `/inheritance:r`
    then removes the just-inherited ACEs — critically the root's horizon_humans
    (OI)(CI)F, which would otherwise flow down as INHERITED READ on projects/
    (the (WD,AD,X) this-folder grant cannot subtract an inherited read). Net parent
    end state: must-haves + horizon_humans create-but-not-list only — no read, no
    strays — at read-parity with Linux -wx. Children: break inheritance, re-grant
    owner/SYSTEM/Administrators + OWNER RIGHTS Full, and REMOVE the horizon_humans
    ACE. DRY-RUN PRINT ONLY on a Linux host."""
    ops = []
    area = rule.path
    grp = rule.principal
    ops.append(Op(['icacls', area, '/reset'], 'info',
                  f'{rule.name}: REPAIR strip stray ACEs on parent (/reset) -> {area}'))
    ops.append(Op(['icacls', area, '/inheritance:r'], 'info',
                  f'{rule.name}: REPAIR drop inherited read (root {grp} Full) -> {area}'))
    ops.extend(windows_must_have_grants(area, owner))
    ops.append(Op(['icacls', area, '/grant', f'{grp}:(WD,AD,X)'], 'grant',
                  f'{rule.name}: REPAIR {grp} create-but-not-list (no read) -> {area}'))
    for child in children:
        ops.append(Op(['icacls', child, '/inheritance:r'], 'info',
                      f'{rule.name}: REPAIR break inheritance on child -> {child}'))
        ops.extend(windows_must_have_grants(child, owner))
        ops.append(Op(['icacls', child, '/grant',
                       f'{WINDOWS_WELL_KNOWN_SIDS["OWNER_RIGHTS"]}:(OI)(CI)F'],
                      'grant', f'{rule.name}: REPAIR OWNER RIGHTS Full -> {child}'))
        ops.append(Op(['icacls', child, '/remove:g', grp], 'deny',
                      f'{rule.name}: REPAIR remove {grp} ACE (owner-only) -> {child}'))
    return ops


# --- macOS (chmod +a) -------------------------------------------------------
# IMPLEMENTED but DRY-RUN PRINT ONLY on a Linux host. macOS ACLs are ordered and
# support allow+deny ACEs and inheritance flags (file_inherit/directory_inherit).
# FIDELITY GAPS are flagged inline; see the module report.
_MACOS_ALLOW = {
    'full':            'read,write,execute,delete,append,readattr,writeattr,readextattr,writeextattr',
    'read-exec':       'read,execute',
    'read-only':       'read',
    'read-write':      'read,write,execute,delete,append',
    'create-traverse': 'add_file,add_subdirectory,execute',  # create+enter, NO list/read
    'no-write':        'read,execute',   # FIDELITY GAP: modeled as allow r-x (parity
                                         # with the Linux POSIX r-x); a true deny-write
                                         # ACE would be chmod +a "group:P deny write,append,delete".
}
_MACOS_INHERIT = 'file_inherit,directory_inherit'


def macos_rule_ops(rule, paths, *, dry_run=True):
    """Translate one rule to `chmod +a` ops on macOS (printed, never applied on
    a Linux host)."""
    if rule.raw is not None and rule.raw.get('macos'):
        return [Op(['chmod', '+a', a, rule.path], 'grant',
                   f'{rule.name}: raw macos escape hatch') for a in rule.raw['macos']]

    ops = []
    path = rule.path
    grp = f'group:{rule.principal}'

    if rule.is_canon():
        for f in rule.canon_abs_files(dry_run=dry_run):
            ops.append(Op(['chmod', '+a', f'{grp} allow read', f], 'deny',
                          f'{rule.name}: {rule.principal} read-only -> {f}'))
        if rule.sticky_parents:
            for parent in sorted({os.path.dirname(f)
                                  for f in rule.canon_abs_files(dry_run=dry_run)}):
                ops.append(Op(['chmod', '+t', parent], 'grant',
                              f'{rule.name}: sticky canon parent -> {parent}'))
        return ops

    if rule.rights == 'deny':
        ops.append(Op(['chmod', '+a',
                       f'{grp} deny read,write,execute,delete,append,'
                       f'readattr,writeattr,readextattr,writeextattr,'
                       f'{_MACOS_INHERIT}', path],
                      'deny', f'{rule.name}: {rule.principal} full deny -> {path}'))
        ops.append(Op(['chmod', '-R', 'go=', path], 'deny',
                      f'{rule.name}: owner-only mode clamp -> {path}'))
        return ops

    if rule.rights == 'none':
        ops.append(Op(['chmod', '-a', f'{grp} allow read,write,execute', path],
                      'deny', f'{rule.name}: strip {rule.principal} ACE -> {path}'))
        return ops

    if rule.is_shared_dropzone():
        if rule.group_owner:
            ops.append(Op(['chgrp', rule.group_owner, path], 'grant',
                          f'{rule.name}: group-own shared -> {path}'))
        ops.append(Op(['chmod', '3770', path], 'grant',
                      f'{rule.name}: setgid+sticky shared -> {path}'))
        ops.append(Op(['chmod', '+a',
                       f'{grp} allow {_MACOS_ALLOW["read-write"]},{_MACOS_INHERIT}',
                       path], 'grant',
                      f'{rule.name}: {rule.principal} shared rwx -> {path}'))
        return ops

    allow = _MACOS_ALLOW.get(rule.rights)
    if allow is None:
        return [Op(None, 'warn', f'{rule.name}: unsupported rights {rule.rights!r} on macOS')]
    spec = allow
    if rule.default:
        spec = f'{allow},{_MACOS_INHERIT}'
    ops.append(Op(['chmod', '+a', f'{grp} allow {spec}', path],
                  'grant', f'{rule.name}: {rule.principal} {rule.rights} -> {path}'))
    if rule.is_selfservice_parent():
        # New entries born owner-only: deny inheritance to group + everyone.
        # FIDELITY GAP: macOS has no direct 'default:other:---'; approximated by
        # an inherited deny on 'everyone' for the group principal only.
        if rule.isolate_children:
            ops.append(Op(['chmod', '+a',
                           f'{grp} deny list,search,{_MACOS_INHERIT}', path],
                          'deny', f'{rule.name}: isolating inherited deny -> {path}'))
        if rule.sticky:
            ops.append(Op(['chmod', '+t', path], 'grant',
                          f'{rule.name}: sticky parent -> {path}'))
        if rule.setgid is False:
            ops.append(Op(['chmod', 'g-s', path], 'grant',
                          f'{rule.name}: clear setgid -> {path}'))
    return ops


# --- Windows (icacls) -------------------------------------------------------
# IMPLEMENTED but DRY-RUN PRINT ONLY on a Linux host. Preserves the historical
# harden_windows structure: inheritance break at HORIZON_ROOT + re-grant
# must_have_full, additive vs --strict, grant-before-deny. Self-service
# isolation uses OWNER RIGHTS (*S-1-3-4) on children, never a group Deny (which
# would lock the owner out — the owner is a horizon_humans member).
_WINDOWS_GRANT = {
    'full':       '(OI)(CI)F',
    'read-exec':  '(OI)(CI)RX',
    'read-only':  '(OI)(CI)R',
    'read-write': '(OI)(CI)M',
}


def windows_must_have_grants(path, owner):
    """Ops that (re)grant Full to the must-have principals on `path`."""
    ops = []
    if owner:
        ops.append(Op(['icacls', path, '/grant', f'{owner}:(OI)(CI)F'],
                      'grant', f'owner Full control (preserved): {owner} -> {path}'))
    for label in ('SYSTEM', 'Administrators'):
        sid = WINDOWS_WELL_KNOWN_SIDS[label]
        ops.append(Op(['icacls', path, '/grant', f'{sid}:(OI)(CI)F'],
                      'grant', f'{label} Full control (preserved) -> {path}'))
    return ops


def windows_rule_ops(rule, paths, *, owner=None, strict=False, dry_run=True,
                     broad_allow=frozenset()):
    """Translate one rule to icacls ops on Windows (printed, never applied on a
    Linux host).

    `broad_allow` names principals that already hold a broad INHERITED Full
    (from a tree-wide `full` rule, i.e. horizon_humans via humans-userspace-full).
    For such a principal, an abstract read-exec/read-only rule on a SUBTREE means
    'reduce to read-only', which on Windows requires an explicit Deny-Write ACE
    (an Allow cannot subtract the inherited Full) — matching the historical
    harden_windows B2 behavior. A principal WITHOUT a broad allow (brains) instead
    gets a positive RX/R grant.
    """
    if rule.raw is not None and rule.raw.get('windows'):
        return [Op(['icacls', rule.path, '/grant', a], 'grant',
                   f'{rule.name}: raw windows escape hatch') for a in rule.raw['windows']]

    path = rule.path
    grp = rule.principal
    ops = []

    if rule.is_canon():
        for f in rule.canon_abs_files(dry_run=dry_run):
            ops.append(Op(['icacls', f, '/deny', f'{grp}:{BRAINS_NOWRITE_MASK}'],
                          'deny', f'{rule.name}: {grp} Read-Only on root canon -> {f}'))
        return ops

    # Read-only reduction for a broad-Full holder => explicit Deny-Write.
    if rule.rights in ('read-exec', 'read-only') and grp in broad_allow:
        ops.append(Op(['icacls', path, '/deny', f'{grp}:(OI)(CI){BRAINS_NOWRITE_MASK}'],
                      'deny', f'{rule.name}: {grp} Read-Only (DENY write/delete) -> {path}'))
        return ops

    if rule.rights == 'no-write':
        ops.append(Op(['icacls', path, '/deny', f'{grp}:(OI)(CI){BRAINS_NOWRITE_MASK}'],
                      'deny', f'{rule.name}: {grp} DENY write/delete (Read-Only) -> {path}'))
        return ops

    if rule.rights == 'deny':
        if strict:
            ops.append(Op(['icacls', path, '/inheritance:r'], 'info',
                          f'{rule.name}: STRICT strip inheritance -> {path}'))
            ops.extend(windows_must_have_grants(path, owner))
        ops.append(Op(['icacls', path, '/deny', f'{grp}:(OI)(CI)F'],
                      'deny', f'{rule.name}: {grp} DENY (full) -> {path}'))
        return ops

    if rule.rights == 'none':
        ops.append(Op(['icacls', path, '/remove:g', grp], 'deny',
                      f'{rule.name}: remove {grp} ACE -> {path}'))
        return ops

    if rule.is_shared_dropzone():
        # shared/ is group-accessible: grant the group Modify, inheritable.
        ops.append(Op(['icacls', path, '/grant', f'{grp}:(OI)(CI)M'],
                      'grant', f'{rule.name}: {grp} shared drop-zone (Modify) -> {path}'))
        return ops

    if rule.is_selfservice_parent():
        # Parent: break inheritance so grant-B Full does not flow to children,
        # re-establish must-haves, then grant create-but-not-list (WD,AD,X),
        # this-folder-only (no OI/CI).
        ops.append(Op(['icacls', path, '/inheritance:r'], 'info',
                      f'{rule.name}: break inheritance on self-service parent -> {path}'))
        ops.extend(windows_must_have_grants(path, owner))
        ops.append(Op(['icacls', path, '/grant', f'{grp}:(WD,AD,X)'],
                      'grant', f'{rule.name}: {grp} create-but-not-list (self-service) -> {path}'))
        # Existing children: isolate via OWNER RIGHTS, NEVER a group Deny.
        if rule.isolate_children and not dry_run:
            try:
                children = [os.path.join(path, d) for d in os.listdir(path)
                            if os.path.isdir(os.path.join(path, d))
                            and d not in rule.exclude_children]
            except OSError:
                children = []
            for child in children:
                ops.append(Op(['icacls', child, '/inheritance:r'], 'info',
                              f'{rule.name}: break inheritance on child -> {child}'))
                ops.extend(windows_must_have_grants(child, owner))
                ops.append(Op(['icacls', child, '/grant',
                               f'{WINDOWS_WELL_KNOWN_SIDS["OWNER_RIGHTS"]}:(OI)(CI)F'],
                              'grant', f'{rule.name}: OWNER RIGHTS Full (peers opaque, '
                                       f'no {grp} ACE) -> {child}'))
        return ops

    # Standard grant: full / read-exec / read-only / read-write.
    mask = _WINDOWS_GRANT.get(rule.rights)
    if mask is None:
        return [Op(None, 'warn', f'{rule.name}: unsupported rights {rule.rights!r} on Windows')]
    ops.append(Op(['icacls', path, '/grant', f'{grp}:{mask}'],
                  'grant', f'{rule.name}: {grp} {rule.rights} ({mask}) -> {path}'))
    return ops


# ---------------------------------------------------------------------------
# Dispatch table (harden picks the translator for the detected OS).
# ---------------------------------------------------------------------------
TRANSLATORS = {
    'Linux':  linux_rule_ops,
    'Darwin': macos_rule_ops,
    'Windows': windows_rule_ops,
}


if __name__ == '__main__':
    # Tiny self-check + human-review dump for macOS/Windows translation.
    import argparse
    import platform as _platform

    ap = argparse.ArgumentParser(description='ACL posture loader / translator dump')
    ap.add_argument('--horizon-root', default=None)
    ap.add_argument('--os', dest='os_name', default=None,
                    choices=['Linux', 'Darwin', 'Windows'],
                    help='Force an OS for the translated-command dump.')
    ap.add_argument('--owner', default='owner')
    ap.add_argument('--self-check', action='store_true',
                    help='Verify the embedded fallback matches the shipped default.')
    a = ap.parse_args()

    if a.horizon_root:
        hr = os.path.abspath(a.horizon_root)
    else:
        hr = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    _paths = {'horizon_root': hr, 'horizon_system': os.path.join(hr, 'horizon_system')}

    if a.self_check:
        okk, detail = embedded_matches_default(_paths)
        print(f'[{"OK" if okk else "FAIL"}] {detail}')
        sys.exit(0 if okk else 1)

    posture = load_posture(_paths)
    os_name = a.os_name or _platform.system()
    print(f'# Posture source: {posture.source}; OS: {os_name}; {len(posture.rules)} rules\n')
    translate = TRANSLATORS[os_name]
    broad = frozenset(r.principal for r in posture.rules if r.rights == 'full')
    for rule in posture.ordered_rules():
        if os_name == 'Linux':
            ops = translate(rule, _paths, dry_run=True)
        elif os_name == 'Windows':
            ops = translate(rule, _paths, owner=a.owner, dry_run=True,
                            broad_allow=broad)
        else:
            ops = translate(rule, _paths, dry_run=True)
        print(f'## {rule.name}  ({rule.principal}:{rule.rights}, kind={rule.kind})')
        for op in ops:
            if op.argv:
                print('   ' + ' '.join(op.argv))
        print()
    if os_name == 'Linux':
        for op in linux_traverse_ops(posture, _paths):
            if op.argv:
                print('   ' + ' '.join(op.argv))
