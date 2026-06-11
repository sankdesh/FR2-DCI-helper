# Helper script to parse RRC file and extract relevant information
#
# Branch: feature/dci00-dci10-fallback
# -------------------------------------------------------------------
# This file is a sibling "branch" of FR2_dci_helper.py.  It carries the
# same DCI 0_1 / 1_1 modelling as trunk and additionally adds a compact
# DCI Size Summary covering the C-RNTI fallback formats DCI 0_0 and
# DCI 1_0 in both UE-Specific Search Space (USS) and Common Search
# Space Type-3 (CSS-3), per TS 38.212 SS7.3.1.1.1 / 7.3.1.2.1 / 7.3.1.0
# and TS 38.331 V17 ServingCellConfigCommon -> initialDownlinkBWP /
# initialUplinkBWP -> genericParameters (BWP-DownlinkCommon /
# BWP-UplinkCommon).
#
# Trunk file FR2_dci_helper.py is intentionally left untouched so it
# remains available as the stable reference.
import re
import math
import os
import sys
import textwrap

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

if os.name == "nt":
    os.system("")

USE_COLOR = sys.stdout is not None and sys.stdout.isatty()

def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if USE_COLOR else s

BOLD    = lambda s: _c("1",  s)
DIM     = lambda s: _c("2",  s)
CYAN    = lambda s: _c("36", s)
GREEN   = lambda s: _c("32", s)
YELLOW  = lambda s: _c("33", s)
MAGENTA = lambda s: _c("35", s)

def _parse_cli():
    """CLI handler.  Supported invocations:

        FR2_dci_helper [PATH] [options]

    Options:
        --rrc-source {auto|reconfig|setup}
              Controls RRC merge behaviour when the capture contains BOTH
              rrcSetup and rrcReconfiguration:
                auto/reconfig  prefer rrcReconfiguration (default, spec-correct)
                setup          ignore Reconfig; read every IE from rrcSetup

        --format {full|summary|quiet}
              Output verbosity:
                full     banner + all per-field tables + compact summary + config files (default)
                summary  banner + compact summary + config files; no per-field tables
                quiet    write config files only; single-line confirmation

        --output-dir DIR  (-o DIR)
              Directory for dci_0_1_fields_config / dci_1_1_fields_config.
              Default: same folder as the input RRC file.

        --no-config
              Analyse and print only; do NOT write config files.

        --no-color
              Force ANSI color off (useful when piping or logging).

        --show-optional
              When --format=full, also print the Conditional/Optional fields
              tables for DCI 0_1 and 1_1 (hidden by default).

        --gui
              Open the GUI window even when a file path is given.

    Returns (filepath_or_None, rrc_source, fmt, output_dir, no_config,
             no_color, show_optional, gui).
    When filepath_or_None is None the GUI should be launched.

    Input must be a **raw RRC text capture** (ASN.1-style or QCAT/QXDM export with
    ``rrcSetup`` / ``rrcReconfiguration`` / ``message c1`` lines). Do not pass
    saved FR2_dci_helper console output (e.g. ``verify_*.txt`` prints); the tool
    detects that pattern and exits with an error.
    """
    args = sys.argv[1:]
    path = None
    rrc_source = 'auto'
    fmt = 'full'
    output_dir = None
    no_config = False
    no_color = False
    show_optional = False
    launch_gui = False
    i = 0

    def _next_val(flag):
        nonlocal i
        i += 1
        if i >= len(args):
            print(f"ERROR: {flag} requires an argument", file=sys.stderr)
            sys.exit(2)
        return args[i]

    while i < len(args):
        a = args[i]

        if a in ('-h', '--help'):
            print(
                "Usage: FR2_dci_helper [PATH] [options]\n\n"
                "  PATH                    RRC text file (.txt).  If omitted the GUI opens.\n\n"
                "  --rrc-source auto       (default) prefer rrcReconfiguration when both messages present\n"
                "               reconfig  alias for 'auto'\n"
                "               setup     prefer rrcSetup; ignore Reconfig overrides\n\n"
                "  --format full           (default) banner + all per-field tables + summary + configs\n"
                "           summary        banner + compact summary + configs; no per-field tables\n"
                "           quiet          write config files only; single-line confirmation\n\n"
                "  -o DIR / --output-dir DIR\n"
                "                          folder for dci_0_1_fields_config / dci_1_1_fields_config\n"
                "                          (default: same folder as the input file)\n\n"
                "  --no-config             analyse only; do NOT write config files\n"
                "  --no-color              force ANSI color off\n"
                "  --show-optional         with --format full, also print conditional/optional field tables\n"
                "  --gui                   open GUI even when PATH is given\n"
            )
            sys.exit(0)

        elif a in ('--rrc-source',):
            v = _next_val(a).lower()
            if v not in ('auto', 'reconfig', 'setup'):
                print(f"ERROR: --rrc-source must be auto|reconfig|setup, got '{v}'",
                      file=sys.stderr)
                sys.exit(2)
            rrc_source = v

        elif a.startswith('--rrc-source='):
            v = a.split('=', 1)[1].lower()
            if v not in ('auto', 'reconfig', 'setup'):
                print(f"ERROR: --rrc-source must be auto|reconfig|setup, got '{v}'",
                      file=sys.stderr)
                sys.exit(2)
            rrc_source = v

        elif a == '--format':
            v = _next_val(a).lower()
            if v not in ('full', 'summary', 'quiet'):
                print(f"ERROR: --format must be full|summary|quiet, got '{v}'",
                      file=sys.stderr)
                sys.exit(2)
            fmt = v

        elif a.startswith('--format='):
            v = a.split('=', 1)[1].lower()
            if v not in ('full', 'summary', 'quiet'):
                print(f"ERROR: --format must be full|summary|quiet, got '{v}'",
                      file=sys.stderr)
                sys.exit(2)
            fmt = v

        elif a in ('-o', '--output-dir'):
            output_dir = _next_val(a)

        elif a.startswith('--output-dir='):
            output_dir = a.split('=', 1)[1]

        elif a == '--no-config':
            no_config = True

        elif a == '--no-color':
            no_color = True

        elif a == '--show-optional':
            show_optional = True

        elif a == '--gui':
            launch_gui = True

        elif a.startswith('-'):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            sys.exit(2)

        elif path is None:
            path = a

        else:
            print(f"ERROR: unexpected positional argument '{a}'", file=sys.stderr)
            sys.exit(2)

        i += 1

    return path, rrc_source, fmt, output_dir, no_config, no_color, show_optional, launch_gui


_cli_path, _RRC_SOURCE, _FORMAT, _OUTPUT_DIR, _NO_CONFIG, _NO_COLOR, _SHOW_OPTIONAL, _LAUNCH_GUI = _parse_cli()

# Override color if --no-color was passed
if _NO_COLOR:
    USE_COLOR = False

# Launch GUI when no file given or --gui flag present
if _cli_path is None or _LAUNCH_GUI:
    import importlib
    _gui_mod = importlib.import_module(__name__) if False else None
    # Defer GUI launch until after all helpers are defined (end of file).
    _DO_GUI = True
    # Provide a dummy filepath for module-level code; main() won't run.
    if _cli_path is None:
        import tempfile as _tempfile
        filepath = _tempfile.mktemp(suffix='.txt')  # placeholder never opened
    else:
        filepath = _cli_path
else:
    _DO_GUI = False
    filepath = _cli_path

_RRC_PREFER_SETUP = (_RRC_SOURCE == 'setup')

if _DO_GUI:
    # Provide empty rows so module-level code that references `rows` /
    # `rrclength` at definition time (pattern constants etc.) still works.
    rows = []
    rrclength = 0
else:
    f = open(filepath, 'r', encoding='utf-8', errors='replace')

    # Returns a file lines as a list where lines are list items
    rows = f.readlines()
    rrclength = len(rows)

    # When --rrc-source=setup is in effect AND the capture contains both an
    # rrcSetup and a later rrcReconfiguration message, truncate `rows` so that
    # every downstream parser (including the global ones that don't take a
    # scan_from argument such as numericalparser2 and writtenparser2) only sees
    # the rrcSetup section.  Without this, a parser whose target IE is absent
    # from rrcSetup but present in rrcReconfiguration (e.g. reportTriggerSize)
    # would still pick up the Reconfig value from later in the file, defeating
    # the user's intent of "ignore Reconfig overrides".
    if _RRC_PREFER_SETUP:
        _setup_idx = -1
        _reconfig_idx = -1
        for _i, _ln in enumerate(rows):
            if _setup_idx < 0 and re.search(r"\brrcSetup\b", _ln):
                _setup_idx = _i
            if _reconfig_idx < 0 and re.search(r"\brrcReconfiguration\b", _ln):
                _reconfig_idx = _i
            if _setup_idx >= 0 and _reconfig_idx >= 0:
                break
        if _setup_idx >= 0 and _reconfig_idx > _setup_idx:
            rows = rows[:_reconfig_idx]
            rrclength = len(rows)

# Patterns from RRC for parsing
BWPDownlink = 'downlinkBWP-ToAddModList'
locationAndBandwidth = 'locationAndBandwidth'
BWPUplink = 'uplinkBWP-ToAddModList'
subcarrierSpacing = 'subcarrierSpacing'
# Dedicated PDSCH/PUSCH config (exclude pdsch-ConfigCommon / pusch-ConfigCommon)
pdschConfig = r"pdsch-Config(?:\s+setup\s*:|:)"
puschConfigC = 'pusch-ConfigC'
Rbgsize = 'rbg-Size'
puschConfig = r"pusch-Config(?:\s+setup\s*:|:)"
dynamicSwitch = 'dynamicSwitch'
resourceAllocationType0 = 'resourceAllocationType0'
resourceAllocationType1 = 'resourceAllocationType1'
bwpDedicated = 'bwp-Dedicated'
puschTimeAllocationList1 = 'pusch-TimeDomainAllocationList: s'
pdschTimeAllocationList1 = 'pdsch-TimeDomainAllocationList: s'
# Strict patterns: only match the legacy R15 IEs, never the R16 / R17
# DCI-x-y / -r16 / -r17 variants which carry the same name as a prefix
# (e.g. pusch-TimeDomainAllocationListDCI-0-1-r16 or
# pdsch-TimeDomainAllocationList-r16).  Those overrides are looked up
# separately by parse_pusch_tda_r16_dci01_count / parse_pdsch_tda_r16_count.
puschTimeAllocationList = r"\bpusch-TimeDomainAllocationList\b(?!-r1\d)(?!DCI)"
pdschTimeAllocationList = r"\bpdsch-TimeDomainAllocationList\b(?!-r1\d)(?!DCI)"
transformprecoderdisabled = r'transformPrecoder[\s:]+disabled'
transformprecoderenabled = r'transformPrecoder[\s:]+enabled'
nrofSRSPorts = 'nrofSRS-Ports'
Maxrank = 'maxRank'
codebooksubset1 = 'fullyAndPartialAndNonCoherent'
codebooksubset2 = 'partialAndNonCoherent'
codebooksubset3 = 'nonCoherent'
codebook = r'txConfig[\s:]+codebook'
noncodebook = r'txConfig[\s:]+nonCodebook'
DMRSUplinkconfig = 'DMRS-UplinkConfig'
DMRSDownlinkForPDSCH = r'dmrs-DownlinkForPDSCH-MappingTypeA\s+setup'
DMRStype1 = 'type1'
DMRStype2 = 'type2'
maxlength = 'maxLength'
reporttriggersize = 'reportTriggerSize'
ptrsuplinkconfig = 'phaseTrackingRS'
frequencyHoppingOffsetLists = 'frequencyHoppingOffsetLists'
srsResourceSetToAddModList = 'srs-ResourceSetToAddModList'
codebook1 = 'codebook'
noncodebook1 = 'nonCodebook'
antennaswitching = 'antennaSwitching'
beammanagement = 'beamManagement'
srsconfig = 'srs-Config'
physicalcellgroupconfig = 'physicalCellGroupConfig'
semistatic = 'semiStatic'
dynamic = 'dynamic'
static = 'static'
prbbundlingtype = 'prb-BundlingType'
ratematch1 = 'rateMatchPatternGroup1'
ratematch2 = 'rateMatchPatternGroup2'
zpcsiresresourcesetstoaddmodlist = 'aperiodic-ZP-CSI-RS-ResourceSetsToAddModList'
scelltoaddmodlist = 'sCellToAddModList'
dataulack = 'dl-DataToUL-ACK'
tciindci = 'tci-PresentInDCI'
maxcodeblocks = 'maxCodeBlockGroupsPerTransportBlock'
maxcodewordsscheduledDCI = 'maxNrofCodeWordsScheduledByDCI'
blockgroupflushindicator = 'codeBlockGroupFlushIndicator'
supuplink = 'SupplementaryUplink'
uplinkbwptoaddmodlist = 'uplinkBWP-ToAddModList'
downlinkbwptoaddmodlist = 'downlinkBWP-ToAddModList'
vrbtoprbinterleaver = 'vrb-ToPRB-Interleaver'
betaoffset = 'betaOffsets: semiStatic'


# Numerical value parser from two patterns
def numericalparser1(pattern1, pattern2, defaultvalue, scan_from=0):
    s = max(0, scan_from)
    locationandbandwidthvalue = defaultvalue
    while s < rrclength:
        row = rows[s]
        bwpdownlinkpattern = re.compile(pattern1)
        bwpdownlinkrow = bwpdownlinkpattern.search(row)
        if bwpdownlinkrow is not None:
            break
        else:
            s = s+1
    while s < rrclength:
        locationandbandwidthpattern = re.compile(pattern2)
        locationandbandwidthrow = locationandbandwidthpattern.search(rows[s])
        if locationandbandwidthrow is not None:
            locationandbancwidthvaluepattern = re.compile(r'(\d+)')
            locationandbandwidthvalue = locationandbancwidthvaluepattern.search(rows[s])
            locationandbandwidthvalue = locationandbandwidthvalue.group()
            locationandbandwidthvalue = int(locationandbandwidthvalue)
            break
        else:
            s = s+1
    return locationandbandwidthvalue


def srs_resource_set_to_add_mod_count(header_idx: int):
    """Count SRS resource sets under srs-ResourceSetToAddModList (brace-style RRC)."""
    n = 0
    for j in range(header_idx + 1, min(header_idx + 400, rrclength)):
        if "srs-ResourceToAddModList" in rows[j]:
            break
        if re.search(r"srs-ResourceSetId\s+\d+", rows[j]):
            n += 1
    return n if n > 0 else None


def _parse_physical_cell_id():
    """Return the Physical Cell ID (N_ID^cell).

    Primary source: scramblingID0 inside the PDSCH DMRS config
    (TS 38.211 §7.4.1.1.1 — when not configured it equals N_ID^cell,
    and the network almost always explicitly writes it equal to the PCI).
    Fallback: log-header line 'Physical Cell ID = <n>'.
    Returns None when neither is found.
    """
    # Primary: scramblingID0 (integer 0-1007)
    sid_pat = re.compile(r"\bscramblingID0\s+(\d+)")
    for ln in rows:
        m = sid_pat.search(ln)
        if m:
            return int(m.group(1))
    # Fallback: QCAT/QXDM log header
    hdr_pat = re.compile(r"Physical\s+Cell\s+ID\s*=\s*(\d+)", re.I)
    for ln in rows:
        m = hdr_pat.search(ln)
        if m:
            return int(m.group(1))
    return None


def _parse_log_header_cell_fields():
    """Optional QCAT/QXDM header fields (first ~50 lines only)."""
    out = {}
    nci_pat = re.compile(r"NR\s+Cell\s+Global\s+ID\s*=\s*(\S+)", re.I)
    freq_pat = re.compile(r"^Freq\s*=\s*(.+)$", re.I)
    for ln in rows[:50]:
        m = nci_pat.search(ln)
        if m:
            val = m.group(1).strip()
            if val.upper() != "N/A":
                out["ncgi"] = val
        m = freq_pat.search(ln.strip())
        if m:
            val = m.group(1).strip()
            if val.upper() != "N/A":
                out["freq"] = val
    return out


def _detect_saved_fr2_output_text():
    """True when rows look like a prior FR2_dci_helper console capture, not raw RRC.

    Users sometimes re-open ``verify_*.txt`` or redirect output and pass it back as
    input — that yields empty cell identity, bogus N_RB, and CSS aligned None.
    """
    if rrclength < 15:
        return False
    head = "".join(rows[: min(220, rrclength)])
    if "Path to RRC file" in head:
        return True
    if "Cell parameters" in head and "DCI Format 1_1" in head:
        return True
    if "DCI Size Summary" in head and "TOTAL DCI SIZE" in head:
        return True
    return False


def _abort_if_saved_output_instead_of_rrc():
    if not _detect_saved_fr2_output_text():
        return
    print(
        "\nERROR: This file looks like saved FR2_dci_helper output (banner / tables / "
        "interactive prompt), not a raw RRC text capture.\n\n"
        "  Pass the original RRC export instead (lines such as 'message c1 : rrcReconfiguration', "
        "'rrcSetup', or 'DL_DCCH / RRCReconfiguration' from QCAT/QXDM/Wireshark text export).\n"
        "  Files named verify_*.txt in this repo are usually verification prints, not inputs.\n",
        file=sys.stderr,
    )
    sys.exit(2)


def _parse_cell_identity_fields(scan_from=0):
    """Extract spCell identity IEs from the first spCellConfig at/after scan_from.

    Returns a dict that may contain phys_cell_id, serv_cell_index, band,
    ssb_arfcn, and point_a_arfcn (all ints where applicable).
    """
    sp_cfg = re.compile(r"\bspCellConfig\b")
    phys_pat = re.compile(r"\bphysCellId\s*[: ]?\s*(\d+)")
    serv_pat = re.compile(r"\bservCellIndex\s*[: ]?\s*(\d+)")
    ssb_pat = re.compile(r"\babsoluteFrequencySSB\s+(\d+)")
    pointa_pat = re.compile(r"\babsoluteFrequencyPointA\s+(\d+)")
    band_list_pat = re.compile(r"\bfrequencyBandList\b")
    band_num_pat = re.compile(r"^\s*(\d+)\s*,?\s*$")

    start = max(0, scan_from)
    for i in range(start, rrclength):
        if sp_cfg.search(rows[i]) is None:
            continue
        end = min(i + 500, rrclength)
        out = {}
        depth = 0
        for j in range(i, end):
            ln = rows[j]
            before = depth
            depth += ln.count("{") - ln.count("}")
            if j > i and depth <= 0 and before > 0:
                break
            m = phys_pat.search(ln)
            if m and "phys_cell_id" not in out:
                out["phys_cell_id"] = int(m.group(1))
            m = serv_pat.search(ln)
            if m and "serv_cell_index" not in out:
                out["serv_cell_index"] = int(m.group(1))
            m = ssb_pat.search(ln)
            if m and "ssb_arfcn" not in out:
                out["ssb_arfcn"] = int(m.group(1))
            m = pointa_pat.search(ln)
            if m and "point_a_arfcn" not in out:
                out["point_a_arfcn"] = int(m.group(1))
            if band_list_pat.search(ln) and "band" not in out:
                for k in range(j + 1, min(j + 8, end)):
                    bm = band_num_pat.search(rows[k])
                    if bm:
                        out["band"] = int(bm.group(1))
                        break
        if out:
            return out
    return {}


def _enrich_cell_identity_loose(fields):
    """Fill missing identity keys from patterns outside ``spCellConfigCommon``.

    Reconfiguration-only captures often have ``spCellConfigDedicated`` only (no
    common ARFCNs / band list under ``spCellConfig``).  ``measObjectNR`` still
    carries ``freqBandIndicatorNR`` and ``ssbFrequency`` (same ARFCN role as
    ``absoluteFrequencySSB`` for display).  Only fills keys that are still absent.
    """
    out = dict(fields)
    if all(
        out.get(k) is not None
        for k in ("band", "ssb_arfcn", "point_a_arfcn")
    ):
        return out
    band_nr = re.compile(r"\bfreqBandIndicatorNR\s+(\d+)")
    ssb_abs = re.compile(r"\babsoluteFrequencySSB\s+(\d+)")
    ssb_mo = re.compile(r"\bssbFrequency\s+(\d+)")
    point_a = re.compile(r"\babsoluteFrequencyPointA\s+(\d+)")

    for i in range(rrclength):
        ln = rows[i]
        if out.get("band") is None:
            m = band_nr.search(ln)
            if m:
                out["band"] = int(m.group(1))
        if out.get("ssb_arfcn") is None:
            m = ssb_abs.search(ln) or ssb_mo.search(ln)
            if m:
                out["ssb_arfcn"] = int(m.group(1))
        if out.get("point_a_arfcn") is None:
            m = point_a.search(ln)
            if m:
                out["point_a_arfcn"] = int(m.group(1))
        if all(
            out.get(k) is not None
            for k in ("band", "ssb_arfcn", "point_a_arfcn")
        ):
            break
    return out


def parse_cell_identity_prefer_reconfig():
    """Prefer NR-DC SCG, then rrcReconfiguration, then whole file for spCell IEs."""
    chosen = {}
    nrdc = _find_nrdc_nrscg_start_index()
    if nrdc >= 0:
        chosen = _parse_cell_identity_fields(nrdc) or {}
    if not chosen:
        start, both = _find_reconfig_start_index()
        if both:
            chosen = _parse_cell_identity_fields(start) or {}
    if not chosen:
        chosen = _parse_cell_identity_fields(0) or {}
    return _enrich_cell_identity_loose(chosen)


def _print_cell_param_rows(rows_of_pairs):
    """Print one or more rows of key: value pairs for the cell summary block."""
    for pairs in rows_of_pairs:
        print("  " + "   ".join(
            f"{DIM(k + ':') if USE_COLOR else k + ':'} {BOLD(v) if USE_COLOR else v}"
            for k, v in pairs
        ))


def _find_reconfig_start_index():
    """Return (start_index, both_present).
    If the capture contains BOTH rrcSetup and rrcReconfiguration messages, the
    start_index is the line where the first rrcReconfiguration appears, so that
    downstream parsing ignores any stale values from the earlier rrcSetup block.
    Otherwise start_index is 0 (search the whole file).

    When the user selected --rrc-source=setup we short-circuit to (0, False)
    so every downstream parser scans the file from the top (rrcSetup appears
    earlier than rrcReconfiguration in a typical capture, so the first match
    a parser finds is the Setup-side value).  This is the explicit way to
    align the script's output with a Wireshark dissector profile that was
    bound to the pre-Reconfig cell context.
    """
    if _RRC_PREFER_SETUP:
        return 0, False
    has_setup = False
    has_reconfig = False
    reconfig_idx = None
    for i in range(rrclength):
        ln = rows[i]
        if re.search(r"\brrcSetup\b", ln):
            has_setup = True
        if re.search(r"\brrcReconfiguration\b", ln):
            has_reconfig = True
            if reconfig_idx is None:
                reconfig_idx = i
    if has_setup and has_reconfig and reconfig_idx is not None:
        return reconfig_idx, True
    return 0, False


def _find_nrdc_nrscg_start_index():
    """Detect the NR-DC SCG section inside an RRC Reconfiguration log.
    Returns the line index of 'mrdc-SecondaryCellGroup nr-SCG' when it appears
    underneath an 'mrdc-SecondaryCellGroupConfig setup' IE, otherwise -1.

    The returned index is the starting anchor used to scope SCG-specific
    parsing (e.g. the PUSCH pusch-TimeDomainAllocationList for DCI 0_1).

    When the user selected --rrc-source=setup we short-circuit to -1.
    NR-DC SCG content only exists inside an rrcReconfiguration payload, so
    asking for Setup-side values implies SCG scoping is also off.
    """
    if _RRC_PREFER_SETUP:
        return -1
    cfg_pat = re.compile(r"mrdc-SecondaryCellGroupConfig\s+setup")
    scg_pat = re.compile(r"mrdc-SecondaryCellGroup\s+nr-SCG")
    cfg_idx = -1
    for i in range(rrclength):
        if cfg_pat.search(rows[i]):
            cfg_idx = i
            break
    if cfg_idx < 0:
        return -1
    for i in range(cfg_idx, min(cfg_idx + 500, rrclength)):
        if scg_pat.search(rows[i]):
            return i
    return -1


def _resolve_active_dedicated_bwp_block_start(direction):
    """Return (list_header_line_index, bwp_entry_open_brace_line_index,
    active_bwp_id_str) for the active dedicated BWP-Downlink / BWP-Uplink
    entry.

    direction is 'DL' or 'UL'.

    Per TS 38.331 S6.3.2, the active dedicated BWP is the list entry whose
    bwp-Id equals firstActiveDownlinkBWP-Id / firstActiveUplinkBWP-Id.  If
    that IE is absent, bwp-Id defaults to 1.  ``list_header_line_index`` is
    the line of ``downlinkBWP-ToAddModList`` / ``uplinkBWP-ToAddModList`` for
    the chosen list (use this as ``scan_from`` for helpers that re-locate the
    list by name).  ``bwp_entry_open_brace_line_index`` is the inner ``{``
    that opens the matching BWP entry (for banner display).

    Lists are tried from the last occurrence in the file toward the first
    until one contains an entry whose bwp-Id matches the active id (handles
    multi-cell captures where the last ``firstActive*BWP-Id`` belongs to a
    later list than an earlier MCG-only list).

    Returns (-1, -1, '') when the list is missing or no entry matches active id.
    """
    if direction == 'DL':
        active_pat = re.compile(r"\bfirstActiveDownlinkBWP-Id\s+(\d+)")
        list_pat = re.compile(r"\bdownlinkBWP-ToAddModList\b")
    elif direction == 'UL':
        active_pat = re.compile(r"\bfirstActiveUplinkBWP-Id\s+(\d+)")
        list_pat = re.compile(r"\buplinkBWP-ToAddModList\b")
    else:
        return -1, -1, ''

    active_id = 1
    for i in range(rrclength):
        m = active_pat.search(rows[i])
        if m:
            active_id = int(m.group(1))

    list_indices = [i for i in range(rrclength) if list_pat.search(rows[i])]
    for list_idx in reversed(list_indices):
        entry_start = _walk_bwp_list_for_active_entry(list_idx, active_id)
        if entry_start >= 0:
            # Anchor parsers at the list header line (see docstring).
            return list_idx, entry_start, str(active_id)
    return -1, -1, ''


def _walk_bwp_list_for_active_entry(list_idx, active_id):
    """Return the start line index of the BWP list entry whose bwp-Id matches
    active_id inside downlinkBWP-ToAddModList / uplinkBWP-ToAddModList
    starting at list_idx, or -1 if not found."""
    if list_idx < 0:
        return -1

    depth = 0
    entry_start = -1
    current_bwp_id = None
    max_j = min(list_idx + 8000, rrclength)
    j = list_idx
    while j < max_j:
        ln = rows[j]
        before = depth
        depth += ln.count('{') - ln.count('}')

        if before == 1 and depth == 2:
            entry_start = j
            current_bwp_id = None
        if before == 2 and depth == 1 and entry_start >= 0:
            if current_bwp_id == active_id:
                return entry_start
            entry_start = -1
            current_bwp_id = None

        if depth >= 2 and entry_start >= 0 and current_bwp_id is None:
            m = re.search(r"\bbwp-Id\s+(\d+)", ln)
            if m:
                current_bwp_id = int(m.group(1))

        if depth == 0 and before > 0 and j > list_idx + 1:
            break
        j += 1

    if entry_start >= 0 and current_bwp_id == active_id:
        return entry_start
    return -1


def parse_scalar_prefer_reconfig(field_regex, value_regex=r"\d+"):
    """Generic 'prefer Reconfiguration over Setup' parser for a scalar RRC field.
    Returns (value_as_int_or_None, was_picked_from_reconfig_bool).

    field_regex : regex that locates the field, e.g. r"\\bmaxRank\\b"
    value_regex : regex capturing the value token; first match group or full
                  match is used. Default extracts the first integer.
    """
    start, both = _find_reconfig_start_index()
    pat = re.compile(field_regex)
    val_pat = re.compile(value_regex)

    def _extract_from(offset):
        for i in range(offset, rrclength):
            if pat.search(rows[i]) is None:
                continue
            for j in range(i, min(i + 5, rrclength)):
                m = val_pat.search(rows[j])
                if m is not None:
                    s = m.group(1) if m.groups() else m.group(0)
                    m2 = re.search(r"\d+", s)
                    if m2:
                        return int(m2.group(0))
        return None

    v = _extract_from(start)
    if v is not None:
        return v, both
    if start > 0:
        v = _extract_from(0)
        if v is not None:
            return v, False
    return None, False


def parse_maxrank_prefer_reconfig():
    return parse_scalar_prefer_reconfig(r"\bmaxRank\b")


def parse_nrofsrsports_prefer_reconfig():
    """nrofSRS-Ports is encoded as 'port1', 'ports2', 'ports4' in ASN.1 style.
    Extract the trailing integer from that token."""
    return parse_scalar_prefer_reconfig(r"\bnrofSRS-Ports\b", r"ports?(\d+)")


def parse_betaoffsets_prefer_reconfig(scan_from=-1):
    """Detect whether betaOffsets is configured as 'dynamic' in PUSCH-Config.
    Per TS 38.212 Table 7.3.1.1.2-28, the 'Beta offset indicator' DCI field is
    2 bits only when betaOffsets is set to 'dynamic'; when it is 'semiStatic' or
    absent the field is 0 bits (offsets are RRC-signaled, not DCI-dynamic).

    scan_from : when >= 0, restrict the search to lines at/after that index
    (used for NR-DC SCG scoping where only the nr-SCG section is authoritative).
    In that mode the Setup/Reconfig preference is not applied because the scope
    is already the SCG RRC-Reconfiguration payload.

    Returns (dynamic_configured_bool, was_from_reconfig_bool).
    """
    anchor = re.compile(r"\bbetaOffsets\s+dynamic\b")

    def _present_from(offset):
        for i in range(offset, rrclength):
            if anchor.search(rows[i]):
                return True
        return False

    if scan_from >= 0:
        return _present_from(scan_from), False

    start, both = _find_reconfig_start_index()
    if _present_from(start):
        return True, both
    if start > 0 and _present_from(0):
        return True, False
    return False, False


def parse_ptrs_maxnrofports_prefer_reconfig():
    """Look inside the (pusch) phaseTrackingRS block for the maxNrofPorts value.
    Returns (ptrs_configured_bool, maxnrofports_int_or_None, was_from_reconfig_bool).
    The ASN.1 token is 'n1' or 'n2'; we return 1 or 2 accordingly.
    """
    start, both = _find_reconfig_start_index()
    ptrs_anchor = re.compile(r"\bphaseTrackingRS\b")
    maxnr_pat = re.compile(r"\bmaxNrofPorts\s+n(\d+)")

    def _extract_from(offset):
        found_any = False
        for i in range(offset, rrclength):
            if ptrs_anchor.search(rows[i]) is None:
                continue
            found_any = True
            for j in range(i, min(i + 120, rrclength)):
                m = maxnr_pat.search(rows[j])
                if m:
                    return True, int(m.group(1))
        return found_any, None

    configured, val = _extract_from(start)
    if configured and val is not None:
        return True, val, both
    if start > 0:
        configured2, val2 = _extract_from(0)
        if configured2:
            return True, val2, False
    if configured:
        return True, None, both
    return False, None, False


def parse_dmrstype_dl_prefer_reconfig():
    """Parse the DL DMRS config type (for DCI 1_1 Antenna ports field).
    The relevant IE is 'dmrs-DownlinkForPDSCH-MappingTypeA setup'; within it
    we look for 'dmrs-Type type1' or 'dmrs-Type type2'.
    Prefers the RRC Reconfiguration section over RRC Setup.
    Defaults to 'type1' when not explicitly configured.

    Returns (dmrs_type_str, was_from_reconfig_bool).
    """
    anchor_pat = re.compile(DMRSDownlinkForPDSCH)
    type_pat = re.compile(r"\bdmrs-Type\s+(type\d+)")
    start, both = _find_reconfig_start_index()

    def _extract_from(offset):
        for i in range(offset, rrclength):
            if anchor_pat.search(rows[i]) is None:
                continue
            for j in range(i, min(i + 40, rrclength)):
                m = type_pat.search(rows[j])
                if m:
                    return m.group(1)
        return None

    v = _extract_from(start)
    if v is not None:
        return v, both
    if start > 0:
        v = _extract_from(0)
        if v is not None:
            return v, False
    return DMRStype1, False


def count_codebook_srs_resource_sets_prefer_reconfig():
    """Count distinct SRS resource sets with usage=codebook configured in the
    active UL BWP.  Applies the same Reconfig > Setup preference used for
    other UL-scoped parameters.

    Per TS 38.212 S7.3.1.1.2: SRS resource set indicator is 2 bits when
    txConfig=codebook and exactly two (or more) SRS resource sets are
    configured with usage=codebook; 0 bits otherwise.

    Returns (count_int, was_from_reconfig_bool).
    """
    anchor_pat = re.compile(r"\bsrs-ResourceSetToAddModList\b")
    set_id_pat = re.compile(r"\bsrs-ResourceSetId\s+(\d+)")
    usage_pat = re.compile(r"\busage[\s:]+codebook\b")
    start, both = _find_reconfig_start_index()

    def _count_from(offset):
        codebook_ids = set()
        for i in range(offset, rrclength):
            if anchor_pat.search(rows[i]) is None:
                continue
            current_id = None
            depth = 0
            for j in range(i, min(i + 400, rrclength)):
                depth += rows[j].count('{') - rows[j].count('}')
                if j > i and depth <= 0:
                    break
                m = set_id_pat.search(rows[j])
                if m:
                    current_id = int(m.group(1))
                if usage_pat.search(rows[j]) and current_id is not None:
                    codebook_ids.add(current_id)
            break  # only process the first srs-ResourceSetToAddModList block
        return len(codebook_ids)

    count = _count_from(start)
    if count > 0:
        return count, both
    if start > 0:
        count = _count_from(0)
        if count > 0:
            return count, False
    return 0, False


# ---------------------------------------------------------------------------
# Initial BWP parsers for fallback DCI 0_0 / 1_0 (TS 38.331 V17, page 805)
#
#   ServingCellConfigCommon
#     -> downlinkConfigCommon (DownlinkConfigCommon)
#         -> initialDownlinkBWP (BWP-DownlinkCommon)
#             -> genericParameters (BWP)
#                 -> { locationAndBandwidth, subcarrierSpacing }
#     -> uplinkConfigCommon   (UplinkConfigCommon)
#         -> initialUplinkBWP (BWP-UplinkCommon)   ... same shape
#
# Notes
#  * BWP-DownlinkDedicated / BWP-UplinkDedicated (the "dedicated" variant
#    referenced from ServingCellConfig) does NOT carry genericParameters.
#    We therefore skip any 'initialDownlinkBWP' / 'initialUplinkBWP' anchor
#    that is not followed by a 'genericParameters' sub-block.
#  * For NR-DC SCG inputs the SCG primary cell's
#    'mrdc-SecondaryCellGroup nr-SCG' branch is used; otherwise the RRC
#    Reconfiguration section is preferred over RRC Setup, matching the
#    convention already in place for FDRA / TDA / Beta-offset etc.
# ---------------------------------------------------------------------------


def _parse_initial_bwp_lab_scs(direction, scan_from=0):
    """direction in {'DL','UL'}.  Scan from `scan_from` for the first
    'initialDownlinkBWP' / 'initialUplinkBWP' anchor that is followed by a
    'genericParameters {' block, then return (locationAndBandwidth_int,
    subcarrierSpacing_int_kHz_value).  Either component is None if not
    found within the block.
    """
    if direction == 'DL':
        anchor = re.compile(r"\binitialDownlinkBWP\b")
    else:
        anchor = re.compile(r"\binitialUplinkBWP\b")
    gp_pat  = re.compile(r"\bgenericParameters\b")
    lab_pat = re.compile(r"\blocationAndBandwidth\s+(\d+)")
    scs_pat = re.compile(r"\bsubcarrierSpacing\s+kHz(\d+)")

    s = max(0, scan_from)
    while s < rrclength:
        if anchor.search(rows[s]) is None:
            s += 1
            continue
        # Look ahead for genericParameters within a small window (the
        # BWP-DownlinkCommon block is short).  If we don't find it, this
        # anchor is likely the dedicated variant under ServingCellConfig
        # (no genericParameters), so skip and continue searching.
        gp_idx = -1
        for j in range(s, min(s + 40, rrclength)):
            if gp_pat.search(rows[j]):
                gp_idx = j
                break
        if gp_idx < 0:
            s += 1
            continue
        lab = scs = None
        for j in range(gp_idx, min(gp_idx + 40, rrclength)):
            if lab is None:
                m = lab_pat.search(rows[j])
                if m:
                    lab = int(m.group(1))
            if scs is None:
                m = scs_pat.search(rows[j])
                if m:
                    scs = int(m.group(1))
            if lab is not None and scs is not None:
                break
        return lab, scs
    return None, None


def parse_initial_dl_bwp_lab_scs_prefer_reconfig():
    """Returns (lab, scs, source_label).
    source_label in {'SCG (mrdc-SecondaryCellGroup nr-SCG)',
                     'rrcReconfiguration', 'rrcSetup', 'not found'}.
    """
    nrdc = _find_nrdc_nrscg_start_index()
    if nrdc >= 0:
        lab, scs = _parse_initial_bwp_lab_scs('DL', scan_from=nrdc)
        if lab is not None:
            return lab, scs, 'SCG (mrdc-SecondaryCellGroup nr-SCG)'
    start, both = _find_reconfig_start_index()
    if both:
        lab, scs = _parse_initial_bwp_lab_scs('DL', scan_from=start)
        if lab is not None:
            return lab, scs, 'rrcReconfiguration'
    lab, scs = _parse_initial_bwp_lab_scs('DL', scan_from=0)
    if lab is not None:
        return lab, scs, ('rrcSetup' if not both else 'rrcReconfiguration')
    return None, None, 'not found'


def parse_initial_ul_bwp_lab_scs_prefer_reconfig():
    """Returns (lab, scs, source_label) for the initial UL BWP."""
    nrdc = _find_nrdc_nrscg_start_index()
    if nrdc >= 0:
        lab, scs = _parse_initial_bwp_lab_scs('UL', scan_from=nrdc)
        if lab is not None:
            return lab, scs, 'SCG (mrdc-SecondaryCellGroup nr-SCG)'
    start, both = _find_reconfig_start_index()
    if both:
        lab, scs = _parse_initial_bwp_lab_scs('UL', scan_from=start)
        if lab is not None:
            return lab, scs, 'rrcReconfiguration'
    lab, scs = _parse_initial_bwp_lab_scs('UL', scan_from=0)
    if lab is not None:
        return lab, scs, ('rrcSetup' if not both else 'rrcReconfiguration')
    return None, None, 'not found'


# ---------------------------------------------------------------------------
# Fallback DCI size helpers (TS 38.212 SS7.3.1.1.1, 7.3.1.2.1, 7.3.1.0)
# ---------------------------------------------------------------------------


def dci00_size(n_rb_ul, sul_configured, in_uss):
    """Natural (pre-alignment) size of DCI Format 0_0 per TS 38.212 S7.3.1.1.1.

    Fields (in order):
      Identifier for DCI formats          = 1
      Frequency domain resource assignment = ceil(log2(N*(N+1)/2))    (RA Type-1)
      Time domain resource assignment      = 4
      Frequency hopping flag               = 1
      Modulation and coding scheme         = 5
      New data indicator                   = 1
      Redundancy version                   = 2
      HARQ process number                  = 4
      TPC command for scheduled PUSCH      = 2
      UL/SUL indicator                     = 1   (USS only when SUL is RRC-configured)

    `in_uss` controls whether the UL/SUL bit is included; UL/SUL is only
    present in DCI 0_0 monitored on UE-Specific SS, never in CSS Type-3.
    """
    if n_rb_ul is None or n_rb_ul <= 0:
        return None
    fdra = math.ceil(math.log2(n_rb_ul * (n_rb_ul + 1) / 2))
    bits = (1
            + fdra
            + 4
            + 1
            + 5
            + 1
            + 2
            + 4
            + 2)
    if in_uss and sul_configured:
        bits += 1
    return bits


def dci10_size(n_rb_dl):
    """Natural (pre-alignment) size of DCI Format 1_0 per TS 38.212 S7.3.1.2.1.

    Fields (in order):
      Identifier for DCI formats              = 1
      Frequency domain resource assignment    = ceil(log2(N*(N+1)/2))
      Time domain resource assignment         = 4
      VRB-to-PRB mapping                      = 1
      Modulation and coding scheme            = 5
      New data indicator                      = 1
      Redundancy version                      = 2
      HARQ process number                     = 4
      Downlink assignment index               = 2
      TPC command for scheduled PUCCH         = 2
      PUCCH resource indicator                = 3
      PDSCH-to-HARQ_feedback timing indicator = 3
    """
    if n_rb_dl is None or n_rb_dl <= 0:
        return None
    fdra = math.ceil(math.log2(n_rb_dl * (n_rb_dl + 1) / 2))
    bits = (1
            + fdra
            + 4
            + 1
            + 5
            + 1
            + 2
            + 4
            + 2
            + 2
            + 3
            + 3)
    return bits


def align_fallback(d00, d10):
    """Align DCI 0_0 / 1_0 monitored in the same search-space location per
    TS 38.212 S7.3.1.0.  The aligned size is max(d00, d10); the smaller one
    pads its FDRA so both formats become the same size for blind decoding.
    Returns None if either side is missing."""
    if d00 is None or d10 is None:
        return None
    return max(d00, d10)


def srs_codebook_resource_count():
    """For transformPrecoder=enabled: count SRS resources in the SRS-ResourceSet
    that has 'usage codebook' (or 'usage: codebook'). Walks each set under
    srs-ResourceSetToAddModList, finds the one with usage=codebook, then counts
    integer entries inside its srs-ResourceIdList { ... } block."""
    for s in range(rrclength):
        if "srs-ResourceSetToAddModList" not in rows[s]:
            continue
        end = min(s + 600, rrclength)
        i = s + 1
        while i < end:
            if not re.search(r"srs-ResourceSetId\s+\d+", rows[i]):
                i += 1
                continue
            set_start = i
            depth = 0
            set_end = end
            for k in range(i, end):
                depth += rows[k].count("{") - rows[k].count("}")
                if k > i and depth <= 0:
                    set_end = k
                    break
            has_codebook_usage = any(
                re.search(r"\busage[\s:]+codebook\b", rows[k])
                for k in range(set_start, set_end + 1)
            )
            if has_codebook_usage:
                for k in range(set_start, set_end + 1):
                    if "srs-ResourceIdList" in rows[k]:
                        j = k + 1
                        while j < end and "{" not in rows[j]:
                            j += 1
                        if j >= end:
                            return None
                        n = 0
                        d = 0
                        for m in range(j, end):
                            ln = rows[m]
                            d += ln.count("{") - ln.count("}")
                            if d >= 1 and re.match(r"^\s*\d+\s*,?\s*$", ln):
                                n += 1
                            if d <= 0 and m > j:
                                break
                        return n if n > 0 else None
                return None
            i = set_end + 1
        return None
    return None


def dl_data_to_ul_ack_count(header_idx: int):
    """Count entries in the dl-DataToUL-ACK list. Handles two RRC text styles:
       Form 1 (QCAT digit-on-anchor): 'dl-DataToUL-ACK: 8'
       Form 2 (brace list, one int per line):
           dl-DataToUL-ACK
           {
             2,
             3,
             ...
           }
    """
    if header_idx < 0 or header_idx >= rrclength:
        return None
    m = re.search(r"dl-DataToUL-ACK\s*:\s*(\d+)", rows[header_idx])
    if m:
        return int(m.group(1))
    j = header_idx
    while j < min(header_idx + 5, rrclength) and "{" not in rows[j]:
        j += 1
    if j >= rrclength or "{" not in rows[j]:
        return None
    n = 0
    depth = 0
    for k in range(j, min(header_idx + 200, rrclength)):
        ln = rows[k]
        opens = ln.count("{")
        closes = ln.count("}")
        if depth >= 1 and re.match(r"^\s*\d+\s*,?\s*$", ln):
            n += 1
        depth += opens - closes
        if depth <= 0 and k > j:
            break
    return n if n > 0 else None


# Numerical value parser from one pattern
def numericalparser2(pattern1, defaultvalue):
    p_src = pattern1
    pat = re.compile(p_src)
    s = 0
    value = defaultvalue
    digit_re = re.compile(r"(\d+)")
    while s < rrclength:
        if pat.search(rows[s]) is None:
            s = s + 1
            continue
        if p_src == srsResourceSetToAddModList:
            c = srs_resource_set_to_add_mod_count(s)
            if c is not None:
                return c
        m = digit_re.search(rows[s])
        if m is not None:
            return int(m.group(1))
        for j in range(s + 1, min(s + 30, rrclength)):
            m = digit_re.search(rows[j])
            if m is not None:
                return int(m.group(1))
        return defaultvalue
    return value


# Double index parser where parsing is needed to stop to the certain point before end of the file
def doubleindexparser(pattern1, pattern2, pattern3, scan_from=0):
    s1 = max(0, scan_from)
    s2 = s1
    value = 1
    while s1 < rrclength:
        row1 = rows[s1]
        pattern1 = re.compile(pattern1)
        pattern1row = pattern1.search(row1)
        if pattern1row is not None:
            s2 = s1
            break
        else:
            s1 = s1+1
    while s2 < rrclength:
        row2 = rows[s2]
        pattern2 = re.compile(pattern2)
        pattern2row = pattern2.search(row2)
        if pattern2row is not None:
            break
        else:
            s2 = s2+1
    while s1 < s2:
        pattern3 = re.compile(pattern3)
        pattern3row = pattern3.search(rows[s1])
        if pattern3row is not None:
            valuepattern = re.compile(r'(\d+)')
            value = valuepattern.search(rows[s1])
            value = value.group()
            value = int(value)
            break
        else:
            s1 = s1+1
    return value


# Parses written value from different options
def writtenparser1(pattern1, pattern2, pattern3, pattern4, pattern5, defaultvalue, scan_from=0):
    s = max(0, scan_from)
    value = defaultvalue
    while s < rrclength:
        row = rows[s]
        pattern1 = re.compile(pattern1)
        pattern1row = pattern1.search(row)
        if pattern1row is not None:
            break
        else:
            s = s+1
    while s < rrclength:
        pattern2comp = re.compile(pattern2)
        pattern2row = pattern2comp.search(rows[s])
        pattern3comp = re.compile(pattern3)
        pattern3row = pattern3comp.search(rows[s])
        pattern4comp = re.compile(pattern4)
        pattern4row = pattern4comp.search(rows[s])
        pattern5comp = re.compile(pattern5)
        pattern5row = pattern5comp.search(rows[s])
        if pattern2row is not None:
            value = pattern2
            break
        elif pattern3row is not None:
            value = pattern3
            break
        elif pattern4row is not None:
            value = pattern4
            break
        elif pattern5row is not None:
            value = pattern5
            break
        else:
            s = s+1
    return value


# Parses one writen value
def writtenparser2(pattern, defaultvalue):
    s = 0
    value = defaultvalue
    while s < rrclength:
        row = rows[s]
        pattern1 = re.compile(pattern)
        pattern1row = pattern1.search(row)
        if pattern1row is not None:
            value = pattern
            break
        else:
            s = s+1
    return value


# --- PDSCH-Config block parsing (DL dedicated BWP) --------------------------------
_PDSCH_CFG_HDR = re.compile(r"\bpdsch-Config\s+(?:setup\s*)?:\s*")
_RA_LINE = re.compile(
    r"\bresourceAllocation(?:\s*:\s*|\s+)(dynamicSwitch|resourceAllocationType0|resourceAllocationType1)\b"
)
_RBG_SIZE_LINE = re.compile(r"\brbg-Size\s+config(\d+)\b", re.I)
_SCELL_LIST_HDR = re.compile(r"\bsCellToAddModList\b")


def parse_pdsch_ra_and_rbg_in_first_block(scan_from: int):
    """Parse the first ``pdsch-Config`` at/after ``scan_from`` and return
    (resourceAllocation token, rbg_config_asn_digit, header_line_index).

    ``header_line_index`` is the matching ``pdsch-Config`` line, or ``-1`` when
    no block is found / no opening brace is seen within the search window.

    The token matches constants ``dynamicSwitch`` / ``resourceAllocationType0`` /
    ``resourceAllocationType1`` for ``calculatefrdabitsdl``.

    ``rbg_config_asn_digit`` is 1 for ``config1`` or 2 for ``config2`` (TS 38.214
    Table 5.1.2.2.1-1), defaulting to 1 when ``rbg-Size`` is absent.
    """
    hdr = -1
    lo = max(0, scan_from)
    for i in range(lo, rrclength):
        if _PDSCH_CFG_HDR.search(rows[i]):
            hdr = i
            break
    if hdr < 0:
        return None, 1, -1
    ra = None
    rbg = 1
    depth = 0
    started = False
    for j in range(hdr, min(hdr + 500, rrclength)):
        ln = rows[j]
        if not started:
            if "{" in ln:
                started = True
                depth = ln.count("{") - ln.count("}")
            if ra is None:
                m = _RA_LINE.search(ln)
                if m:
                    ra = m.group(1)
            m2 = _RBG_SIZE_LINE.search(ln)
            if m2:
                v = int(m2.group(1))
                if v in (1, 2):
                    rbg = v
            if not started:
                continue
        else:
            if ra is None:
                m = _RA_LINE.search(ln)
                if m:
                    ra = m.group(1)
            m2 = _RBG_SIZE_LINE.search(ln)
            if m2:
                v = int(m2.group(1))
                if v in (1, 2):
                    rbg = v
            before = depth
            depth += ln.count("{") - ln.count("}")
            if before > 0 and depth <= 0:
                break
    if not started:
        return None, 1, -1
    return ra, rbg, hdr


def _find_last_downlink_bwp_to_add_mod_list_header(scan_lo: int, scan_hi: int) -> int:
    last = -1
    for i in range(max(0, scan_lo), min(scan_hi, rrclength)):
        if re.search(r"\bdownlinkBWP-ToAddModList\b", rows[i]):
            last = i
    return last


def _iter_all_dl_bwp_list_entries(list_idx: int, scan_hi: int):
    """Yield (entry_start_line, entry_end_exclusive) for each BWP entry in the
    ``downlinkBWP-ToAddModList`` opened at ``list_idx`` (brace-depth logic matches
    ``_walk_bwp_list_for_active_entry``)."""
    if list_idx < 0:
        return
    depth = 0
    entry_start = -1
    max_j = min(list_idx + 8000, scan_hi, rrclength)
    j = list_idx
    while j < max_j:
        ln = rows[j]
        before = depth
        depth += ln.count("{") - ln.count("}")
        if before == 1 and depth == 2:
            entry_start = j
        if before == 2 and depth == 1 and entry_start >= 0:
            yield entry_start, j + 1
            entry_start = -1
        if depth == 0 and before > 0 and j > list_idx + 1:
            break
        j += 1


def _first_location_and_bandwidth_in_range(lo: int, hi: int):
    pat = re.compile(r"\blocationAndBandwidth\s+(\d+)\b")
    for i in range(lo, hi):
        m = pat.search(rows[i])
        if m:
            return int(m.group(1))
    return None


def _lab_backscan_before_pdsch(pdsch_line: int, scan_lo: int):
    """Last ``locationAndBandwidth`` value found scanning upward from a
    ``pdsch-Config`` line (stops at ``uplinkBWP-ToAddModList`` to avoid UL LAB)."""
    pat = re.compile(r"\blocationAndBandwidth\s+(\d+)\b")
    last = None
    lo = max(0, scan_lo)
    for i in range(pdsch_line - 1, lo - 1, -1):
        if i < 0:
            break
        if re.search(r"\buplinkBWP-ToAddModList\b", rows[i]):
            break
        m = pat.search(rows[i])
        if m:
            last = int(m.group(1))
    return last


def collect_max_fdr_bits_dci11_window(dai_lo, dai_hi, fallback_lab):
    """Compute maximum DCI 1_1 FDRA bit-width among DL ``pdsch-Config`` blocks in a window.

    Sources:
      (1) Every ``bwp-Dedicated`` entry under the **last** ``downlinkBWP-ToAddModList``
          in ``[dai_lo, dai_hi)`` that contains a ``pdsch-Config``;
      (2) Any other ``pdsch-Config`` in the window (e.g. SCell configs), using backward
          scan for ``locationAndBandwidth`` or ``fallback_lab`` from the active DL BWP.

    Returns ``(max_bits, note_string, detail_rows)`` where ``note_string`` is non-empty
    only when ``max_bits`` exceeds the **active** BWP FDRA width passed by the caller
    for display (caller compares).  ``detail_rows`` is a list of
    ``(bits, bwp_id_or_None, ra_str, n_rb, line_1based)``.
    """
    lo = max(0, dai_lo)
    hi = min(dai_hi, rrclength)
    rows_out = []
    seen_pdsch = set()

    def _add_candidate(pstart, lab_guess, bwp_id_guess):
        if pstart in seen_pdsch:
            return
        if lab_guess is None or lab_guess == 0:
            if fallback_lab and int(fallback_lab) > 0:
                lab_guess = int(fallback_lab)
            else:
                return
        ra, rbg_asn, ph = parse_pdsch_ra_and_rbg_in_first_block(pstart)
        if ph < 0:
            return
        ra_use = ra if ra is not None else resourceAllocationType0
        gw = getbwprbandstartrb(lab_guess)
        if gw is None:
            return
        nrb, srb = gw
        nom = getnominalresourceblockgroup(rbg_asn, nrb)
        if nom is None or nom <= 0:
            nom = 4
        bits = calculatefrdabitsdl(ra_use, nrb, srb, nom)
        if bits is None:
            return
        seen_pdsch.add(pstart)
        rows_out.append((bits, bwp_id_guess, str(ra_use), nrb, pstart + 1))

    hdr = _find_last_downlink_bwp_to_add_mod_list_header(lo, hi)
    if hdr >= 0:
        for estart, eend in _iter_all_dl_bwp_list_entries(hdr, hi):
            lab = _first_location_and_bandwidth_in_range(estart, eend)
            pstart = -1
            for i in range(estart, eend):
                if _PDSCH_CFG_HDR.search(rows[i]):
                    pstart = i
                    break
            if pstart < 0:
                continue
            bwp_id = None
            for i in range(estart, min(estart + 40, eend)):
                m = re.search(r"\bbwp-Id\s+(\d+)", rows[i])
                if m:
                    bwp_id = m.group(1)
                    break
            _add_candidate(pstart, lab, bwp_id)

    for i in range(lo, hi):
        if not _PDSCH_CFG_HDR.search(rows[i]):
            continue
        if i in seen_pdsch:
            continue
        lab2 = _lab_backscan_before_pdsch(i, lo)
        _add_candidate(i, lab2, None)

    if not rows_out:
        return 0, "", []
    max_bits = max(r[0] for r in rows_out)
    arg = max(rows_out, key=lambda x: x[0])
    note = (
        f"Max FDRA in cell-group window = {max_bits} (list@{hdr + 1 if hdr >= 0 else '?'}, "
        f"bwp-Id={arg[1]}, RA={arg[2]}, N_RB={arg[3]}, pdsch-Config line {arg[4]}). "
        f"TS 38.212: DCI 1_1 payload may be zero-padded to the largest monitored "
        f"format 1_1 (e.g. multiple CORESET/search spaces or PCell/SCell alignment)."
    )
    return max_bits, note, rows_out


def time_domain_allocation_list_count(header_idx: int):
    """Count PDSCH/PUSCH time-domain allocation entries (QCAT digit line or RRC brace list)."""
    if header_idx < 0 or header_idx >= rrclength:
        return None
    line = rows[header_idx]
    m = re.search(r":\s*s\s+(\d+)", line)
    if m:
        return int(m.group(1))
    if header_idx + 1 < rrclength:
        m2 = re.search(r"^\s*(\d+)\s*$", rows[header_idx + 1])
        if m2:
            return int(m2.group(1))
    j0 = header_idx + 1
    while j0 < rrclength and "{" not in rows[j0] and "startSymbolAndLength" not in rows[j0]:
        j0 += 1
    if j0 >= rrclength:
        return None
    depth = 0
    n = 0
    started = False
    for j in range(j0, min(header_idx + 600, rrclength)):
        ln = rows[j]
        before = depth
        o = ln.count("{")
        c = ln.count("}")
        if "startSymbolAndLength" in ln and before >= 2:
            n += 1
        depth += o - c
        started = started or o > 0
        if started and depth <= 0:
            break
    return n if n > 0 else None


# Numerical parser for two values
def doublenumericalparser(pattern1, pattern2, pattern3, defaultvalue, scan_from=0):
    """Scan for pattern1 (section anchor), then within that section match
    pattern2 (dedicated form) or pattern3 (generic form) to extract a count.

    scan_from : optional starting line index. When set (e.g. to the
    'mrdc-SecondaryCellGroup nr-SCG' anchor for NR-DC SCG logs) the search is
    restricted to lines at or after that index, so MCG-side configuration is
    ignored."""
    p1_src = pattern1
    p2_src = pattern2
    p3_src = pattern3
    s = max(0, scan_from)
    while s < rrclength:
        if re.search(p1_src, rows[s]):
            break
        s = s + 1
    start_scan = max(0, scan_from) if s >= rrclength else s
    t = start_scan
    while t < rrclength:
        row = rows[t]
        if re.search(p2_src, row):
            next_line = rows[t + 1] if t + 1 < rrclength else ""
            m = re.search(r"(\d+)", next_line)
            if m is not None:
                return int(m.group(1))
            cnt = time_domain_allocation_list_count(t)
            if cnt is not None:
                return cnt
        if re.search(p3_src, row):
            cnt = time_domain_allocation_list_count(t)
            if cnt is not None:
                return cnt
        t = t + 1
    return defaultvalue


def parse_pusch_tda_r16_dci01_count(scan_from=0):
    """Count entries in pusch-TimeDomainAllocationListDCI-0-1-r16 starting
    from `scan_from`.  Returns int or None.

    Per TS 38.214 S6.1.2.1.1, when this R16 IE is configured (setup) it
    overrides the legacy pusch-TimeDomainAllocationList for DCI 0_1 only;
    DCI 0_0 still uses the legacy list.  Returns None when the IE is absent
    from the scoped slice or when it is set to `release : NULL`.

    Counting is delegated to time_domain_allocation_list_count() which
    handles both the QCAT one-liner form and the brace-list form, and which
    matches `startSymbolAndLength-r16` (the R16 entries) via substring.
    """
    s = max(0, scan_from)
    anchor_pat = re.compile(r"\bpusch-TimeDomainAllocationListDCI-0-1-r16\b")
    release_pat = re.compile(r"\brelease\s*:\s*NULL\b")
    while s < rrclength:
        ln = rows[s]
        if anchor_pat.search(ln):
            if release_pat.search(ln):
                s += 1
                continue
            cnt = time_domain_allocation_list_count(s)
            if cnt is not None:
                return cnt
        s += 1
    return None


def parse_pdsch_tda_r16_count(scan_from=0):
    """Count entries in pdsch-TimeDomainAllocationList-r16 starting from
    `scan_from`.  Returns int or None.

    Per TS 38.214 S5.1.2.1.1, when this R16 IE is configured (setup) it
    overrides the legacy pdsch-TimeDomainAllocationList for DCI 1_1.  DCI
    1_0 fallback TDA is fixed at 4 bits (TS 38.212 S7.3.1.2.1) so the
    override only affects the DCI 1_1 per-field table here.  Returns None
    when the IE is absent or set to `release : NULL`.
    """
    s = max(0, scan_from)
    anchor_pat = re.compile(r"\bpdsch-TimeDomainAllocationList-r16\b")
    release_pat = re.compile(r"\brelease\s*:\s*NULL\b")
    while s < rrclength:
        ln = rows[s]
        if anchor_pat.search(ln):
            if release_pat.search(ln):
                s += 1
                continue
            cnt = time_domain_allocation_list_count(s)
            if cnt is not None:
                return cnt
        s += 1
    return None


# BITWIDTH CALCULATIONS:
# UL/SUL indication size, DCI 0-1
def ulsulsize(defaultvalue):
    if defaultvalue == 'SupplementaryUplink':
        value = 1
        value = int(value)
    else:
        value = 0
        value = int(value)
    return value


# Bandwidth part indicator size DCI 0-1
def bwpindsize(defaultvalue):
    if defaultvalue is None:
        defaultvalue = 0
    defaultvalue = int(defaultvalue)
    if defaultvalue <= 3:
        value = math.ceil(math.log(defaultvalue+1, 2))
        value = int(value)
    else:
        value = math.ceil(math.log(defaultvalue, 2))
        value = int(value)
    return value


# Calculating BWP in RB and the staring RB
def getbwprbandstartrb(locationandbandwidth):
    value = int(locationandbandwidth)
    n = 1
    while n <= 275:
        m = 0
        while m <= (275-n):
            if n-1 <= 138:
                if value == (275*(n-1)+m):
                    nrb = n
                    startrb = m
                    return nrb, startrb
                else:
                    m = m+1
            else:
                if value == (275*(275-n+1) + 275-1-m):
                    nrb = n
                    startrb = m
                    return nrb, startrb
                else:
                    m = m+1
        n = n+1


# Get Nominal Resource block group size P, UL DCI 0_1
def getnominalresourceblockgroup(puschrbgsize, nrb):
    value = None
    nrb = int(nrb)
    puschrbgsize = int(puschrbgsize)
    if puschrbgsize == 1 and nrb <= 36 and nrb >= 1:
        value = 2
        value = int(value)
        return value
    elif puschrbgsize == 2 and nrb <= 36 and nrb >= 1:
        value = 4
        value = int(value)
        return value
    elif puschrbgsize == 1 and nrb <= 72 and nrb >= 37:
        value = 4
        value = int(value)
        return value
    elif puschrbgsize == 2 and nrb <= 72 and nrb >= 37:
        value = 8
        value = int(value)
        return value
    elif puschrbgsize == 1 and nrb <= 144 and nrb >= 73:
        value = 8
        value = int(value)
        return value
    elif puschrbgsize == 2 and nrb <= 144 and nrb >= 73:
        value = 16
        value = int(value)
        return value
    elif nrb <= 275 and nrb >= 145:
        value = 16
        value = int(value)
        return value
    else:
        return None


# Calculate size of Frequency domain allocation field DCI 0-1
def calculatefrdabitsul(ulresourceallocationvalue, frequencyhoppingoffsetlistsvalue, nrb, startrb, nominalrbg):
    nrb = int(nrb)
    ulnrf1 = math.ceil(math.log((nrb*(nrb+1)/2), 2))
    ulnrbg = math.ceil((nrb+(startrb % nominalrbg))/nominalrbg)
    if frequencyhoppingoffsetlistsvalue == 2 or frequencyhoppingoffsetlistsvalue == 4:
        value = ulnrf1 - frequencyhoppingoffsetlistsvalue
        value = int(value)
        return value
    elif ulresourceallocationvalue == 'resourceAllocationType1':
        value = ulnrf1
        value = int(value)
        return value
    elif ulresourceallocationvalue == 'resourceAllocationType0':
        value = ulnrbg
        value = int(value)
        return value
    elif ulresourceallocationvalue == 'dynamicSwitch':
        value = max(ulnrf1, ulnrbg)+1
        value = int(value)
        return value
    else:
        return None


# Calculate size of Frequency domain allocation field DCI 1-1
def calculatefrdabitsdl(dlresourceallocationvalue, nrb, startrb, nominalrbg):
    ulnrf1 = math.ceil(math.log((nrb*(nrb+1)/2), 2))
    ulnrbg = math.ceil((nrb+(startrb % nominalrbg))/nominalrbg)
    if dlresourceallocationvalue == 'resourceAllocationType1':
        value = ulnrf1
        value = int(value)
        return value
    elif dlresourceallocationvalue == 'resourceAllocationType0':
        value = ulnrbg
        value = int(value)
        return value
    elif dlresourceallocationvalue == 'dynamicSwitch':
        value = max(ulnrf1, ulnrbg)+1
        value = int(value)
        return value
    else:
        return None


# Calculate size of time domain allocation field DCI 0-1 / 1-1
def tdrabits(timedomainallocationlistvalue):
    """Bit-width of the Time-domain resource assignment field.

    Per TS 38.214 / 38.212:
      - When pdsch-TimeDomainAllocationList / pusch-TimeDomainAllocationList
        is configured, the bit-width is ceil(log2(N)) where N is the entry
        count.
      - When the list is absent, the UE uses the default tables (16 entries),
        giving 4 bits (log2(16) = 4).

    Robust against `None` (delta Reconfig with no list, missing IE, etc.).
    """
    if timedomainallocationlistvalue is None:
        return 4
    n = int(timedomainallocationlistvalue)
    if n <= 1:
        return 0
    return int(math.ceil(math.log2(n)))


# Calculate frequency hopping DCI 0-1
def numberulhopping(frequencyhoppingoffsetlistsvalue):
    if frequencyhoppingoffsetlistsvalue is None:
        value = 0
        value = int(value)
        return value
    else:
        value = 1
        value = int(value)
        return value


# Calculate size of DL assignment DCI 0-1
def firstdlassignment(pdschharqackcodebookvalue):
    if pdschharqackcodebookvalue == dynamic:
        value = 2
        value = int(value)
        return value
    else:
        value = 1
        value = int(value)
        return value


# Calculate size of precoding information and number of layers DCI 0-1
def sizeofprecodingandnumberoflayers(transformprecodervalue, antennaportsvalue, maxrankvalue, codebooksubsetvalue, txconfigvalue):
    """Bit-width of "Precoding information and number of layers" (DCI 0_1).
    Implements 3GPP TS 38.212 Table 7.3.1.1.2-5.

    Two scenarios:
      (1) transformPrecoder == enabled  -> ceil(log2(N_SRS_codebook_resources)).
      (2) transformPrecoder == disabled -> lookup by (nrofSRS-Ports, maxRank, codebookSubset).
    For txConfig == nonCodebook the field is 0 bits.
    """
    if txconfigvalue == noncodebook:
        return 0

    if transformprecodervalue == transformprecoderenabled:
        n = srs_codebook_resource_count()
        if n is None or n <= 1:
            return 0
        return math.ceil(math.log2(n))

    if antennaportsvalue is None or maxrankvalue is None:
        return None
    if antennaportsvalue == 1:
        return 0

    subset = codebooksubsetvalue if codebooksubsetvalue in (codebooksubset1, codebooksubset2, codebooksubset3) else codebooksubset1

    table = {
        (2, codebooksubset1): {1: 3, 2: 4},
        (2, codebooksubset2): {1: 3, 2: 4},
        (2, codebooksubset3): {1: 1, 2: 2},
        (4, codebooksubset1): {1: 5, 2: 6, 3: 6, 4: 6},
        (4, codebooksubset2): {1: 4, 2: 5, 3: 6, 4: 6},
        (4, codebooksubset3): {1: 2, 2: 4, 3: 5, 4: 6},
    }
    rank_map = table.get((antennaportsvalue, subset))
    if rank_map is None:
        return None
    rank = max(1, min(maxrankvalue, max(rank_map.keys())))
    return rank_map.get(rank)


# Calculate size of antenna ports field, DCI 0-1
def antennaports01(transformprecodervalue, dmrstypevalue, maxlegthvalue):
    if transformprecodervalue == transformprecoderenabled and dmrstypevalue == DMRStype1 and maxlegthvalue == 1:
        value = 2
        value = int(value)
        return value
    elif transformprecodervalue == transformprecoderenabled and dmrstypevalue == DMRStype1 and maxlegthvalue == 2:
        value = 4
        value = int(value)
        return value
    elif transformprecodervalue == transformprecoderdisabled and dmrstypevalue == DMRStype1 and maxlegthvalue == 1:
        value = 3
        value = int(value)
        return value
    elif transformprecodervalue == transformprecoderdisabled and dmrstypevalue == DMRStype1 and maxlegthvalue == 2:
        value = 4
        value = int(value)
        return value
    elif transformprecodervalue == transformprecoderdisabled and dmrstypevalue == DMRStype2 and maxlegthvalue == 1:
        value = 4
        value = int(value)
        return value
    elif transformprecodervalue == transformprecoderdisabled and dmrstypevalue == DMRStype2 and maxlegthvalue == 2:
        value = 5
        value = int(value)
        return value


# Calculate size of SRS request field DCI 1-1, DCI 0-1
def nsrsrequest(supplementaryuplinkvalue):
    if supplementaryuplinkvalue is None:
        value = 2
        value = int(value)
        return value
    else:
        value = 3
        value = int(value)
        return value


# Calculations for size of SRS resource indicator field DCI 0-1
def srsindicatorfield(srsresourcesettoaddmodlistvalue, usageofsrsresourcesetvalue, txconfigvalue, maxrankvalue):
    if srsresourcesettoaddmodlistvalue is None or maxrankvalue is None:
        return None
    array = list()
    k = 1
    minsrsrank = min(maxrankvalue, srsresourcesettoaddmodlistvalue)
    while k <= minsrsrank:
        factorialsrs = math.factorial(srsresourcesettoaddmodlistvalue)
        factorialk = math.factorial(k)
        subtractionsrsk = srsresourcesettoaddmodlistvalue - k
        factorialsrsk = math.factorial(subtractionsrsk)
        array.append(factorialsrs / (factorialk * factorialsrsk))
        k = k + 1
    sumarray = sum(array)
    if txconfigvalue == codebook and usageofsrsresourcesetvalue == codebook1:
        value = math.ceil(math.log(srsresourcesettoaddmodlistvalue, 2))
        value = int(value)
        return value
    elif txconfigvalue == noncodebook and usageofsrsresourcesetvalue == noncodebook1:
        value = math.ceil(math.log(sumarray, 2))
        value = int(value)
        return value


# PTRS-DMRS association field, DCI 0-1 (3GPP TS 38.212 S7.3.1.1.2).
def prtsdmrsfield(ptrs_configured, transformprecodervalue, maxrankvalue,
                  nrofsrsports, ptrs_maxnrofports, srsindicatorfieldvalue):
    """Bit-width of the PTRS-DMRS association field per TS 38.212 S7.3.1.1.2.

    0 bits if any of the following holds:
      (a) PTRS-UplinkConfig is NOT configured AND transform precoder is disabled.
      (b) transform precoder is enabled.
      (c) maxRank == 1.

    2 bits when ALL of the following hold (per S7.3.1.1.2 / Tables 7.3.1.1.2-25
    and 7.3.1.1.2-26):
      - one or two PTRS ports configured via maxNrofPorts in PTRS-UplinkConfig
        (n1 -> 1 port, n2 -> 2 ports);
      - antenna ports (nrofSRS-Ports) is 2, 4, or 8;
      - SRS resource set indicator field is absent, OR present and equal to
        '00'/'01' at runtime (DCI-size calc assumes the field-presence test);
      - maxRank <= 4 (or maxMIMO-Layers <= 4 if parsed; not modelled here).

    Example: 1 PTRS port (maxNrofPorts=n1), 2 antenna ports, SRS res-set-ind
    absent, maxRank=2 -> 2 bits.
    Otherwise 0 bits.
    """
    tp_enabled = (transformprecodervalue == transformprecoderenabled)
    tp_disabled = (transformprecodervalue == transformprecoderdisabled)

    if tp_enabled:
        return 0
    if tp_disabled and not ptrs_configured:
        return 0
    if isinstance(maxrankvalue, int) and maxrankvalue == 1:
        return 0

    ok_ptrs_ports = ptrs_maxnrofports in (1, 2)
    ok_ant_ports  = nrofsrsports in (2, 4, 8)
    ok_maxrank    = isinstance(maxrankvalue, int) and maxrankvalue <= 4

    if ok_ptrs_ports and ok_ant_ports and ok_maxrank:
        return 2
    return 0


# Calculate DMRS sequence initialization field, DCI 0-1
def dmrssequencefield(transformprecodervalue):
    if transformprecodervalue == transformprecoderdisabled:
        value = 1
        value = int(value)
        return value
    else:
        value = 0
        value = int(value)
        return value


# Calculate VRB-to-PRB field length, DCI 1-1
def vrbprbfield(dlresourceallocationvalue, vrbprb):
    if dlresourceallocationvalue == resourceAllocationType0 or vrbprb is None:
        value = 0
        value = int(value)
        return value
    else:
        value = 1
        value = int(value)
        return value


# Calculate PRB bundling size indicator field length, DCI 1-1
def prbbundlefield(prbbundlingvalue):
    if prbbundlingvalue == dynamic:
        value = 1
        value = int(value)
        return value
    else:
        value = 0
        value = int(value)
        return value


# Calculate ZP CSI-RS trigger field length DCI 1-1
def zpcsirstriggerfield(zpcsirstriggervalue):
    value = math.ceil(math.log(zpcsirstriggervalue+1, 2))
    value = int(value)
    return value


# Calculate DL assignment index DCI 1-1
def DLassignment(servingcellvalue, pdschharqackcodebookvalue):
    if servingcellvalue == scelltoaddmodlist and pdschharqackcodebookvalue == dynamic:
        value = 4
        value = int(value)
        return value
    elif servingcellvalue != scelltoaddmodlist and pdschharqackcodebookvalue == dynamic:
        value = 2
        value = int(value)
        return value
    else:
        value = 0
        value = int(value)
        return value


# Calculate PDSCH-to-HARQ feedback timing indicator field length DCI 1-1
def pdschtoharqtimingind(dldatatoulackvalue):
    if dldatatoulackvalue is None:
        return 0
    try:
        n = int(dldatatoulackvalue)
    except (TypeError, ValueError):
        return 0
    if n <= 1:
        return 0
    value = math.ceil(math.log(n, 2))
    value = int(value)
    return value


# Calculate size of antenna ports field, DCI 1-1
def antennaportsfield(dmrstypevalue, maxlengthvalue):
    if dmrstypevalue == DMRStype1 and maxlengthvalue == 1:
        value = 4
        value = int(value)
        return value
    elif dmrstypevalue == DMRStype1 and maxlengthvalue == 2:
        value = 5
        value = int(value)
        return value
    elif dmrstypevalue == DMRStype2 and maxlengthvalue == 1:
        value = 5
        value = int(value)
        return value
    elif dmrstypevalue == DMRStype2 and maxlengthvalue == 2:
        value = 6
        value = int(value)
        return value
    else:
        value = None
        return value


# Calculate Transmission configuration indication DCI 1-1
def transmissionconfigurationfield(tcipresentindcivalue):
    if tcipresentindcivalue is None:
        value = 0
        value = int(value)
        return value
    else:
        value = 3
        value = int(value)
        return value


# Calculate CBG transmission information, CBGTI DCI 1-1
def cbgtransmissioninformationfield11(maxcodeblockgroupspertransportblockvalue, maxnrofcodewordsscheduledbydcivalue):
    value = maxcodeblockgroupspertransportblockvalue * maxnrofcodewordsscheduledbydcivalue
    value = int(value)
    return value


# Calculate rate matching indicator size, DCI 1-1
def ratematchingindicatorsizefield(ratematchpatterngroup1value, ratematchpatterngroup2value):
    if ratematchpatterngroup1value == ratematch1 and ratematchpatterngroup2value == ratematch2:
        value = 2
        value = int(value)
        return value
    elif ratematchpatterngroup1value == ratematch1 or ratematchpatterngroup2value == ratematch2:
        value = 1
        value = int(value)
        return value
    else:
        value = 0
        value = int(value)
        return value


# Beta offset indicator field, DCI 0-1 (TS 38.212 Table 7.3.1.1.2-28)
def betaoffsetfield(betaoffsets_configured):
    """2 bits when the RRC betaOffsets IE is configured under PUSCH-Config,
    0 bits when absent."""
    return 2 if betaoffsets_configured else 0


def codeblockflushindicatorfield(codeblockflushindicatorvalue):
    if codeblockflushindicatorvalue == blockgroupflushindicator:
        value = 1
        value = int(value)
        return value
    else:
        value = 0
        value = int(value)
        return value

# Check if value is zero
def checkvalue(value, name):
    if value != 0 and value is not None:
        print(name, value)


def _write_wireshark_config(
    rrc_filepath,
    cell_label,
    output_dir,
    # DCI 0_1 variable fields
    ulsulfieldvalue, ulbwpfieldvalue, frdabitsul, tdrabitsul, ulhopping,
    dlassignment, srsindicatorfieldvalue, precodingnumberoflayers,
    antennaports01fieldvalue, srsrequestfieldvalue, reporttriggersizevalue,
    maxcodeblockgroupspertransportblockvalue01, prtsdmrsfieldvalue,
    betaoffsetfieldvalue, dmrssequencefieldvalue, totallength01,
    # DCI 1_1 variable fields
    dlbwpfieldvalue, frdabitsdl, tdrabitsdl, vrbprbfieldvalue,
    prbbundlefieldvalue, ratematchingindicatorsizefieldvalue,
    zpcsirstriggerfieldvalue, DLassignmentfieldvalue,
    pdschtoharqtimingindfieldvalue, antennaportsvaluefieldvalue,
    transmissionconfigurationfieldvalue, srsrequestfieldvalue_dl,
    cbgtransmissioninformationfieldvalue11, codeblockflushindicatorfieldvalue,
    totallength11,
    pdcch_monitoring_adapt_bits,
):
    """Write dci_0_1_fields_config and dci_1_1_fields_config (Wireshark CSV
    format) next to the input RRC file, using the exact per-field bit-widths
    computed by main().

    Column ordering matches the existing reference files in this folder:
      dci_0_1_fields_config  - 25 width columns after TRUE,Name,Total,FALSE,""
      dci_1_1_fields_config  - 28 width columns after TRUE,Name,Total,FALSE,""

    The cell_label (e.g. 'Cell_871_0') is derived from the Physical Cell ID
    extracted from the RRC file header.
    """
    import os

    def _cv(v):
        return str(v) if v is not None else "0"

    def _row(name, total, widths):
        fields = ['"TRUE"', f'"{name}"', f'"{total}"', '"FALSE"', '""']
        fields += [f'"{w}"' for w in widths]
        return ",".join(fields)

    # --- DCI 0_1 (25 width columns) ---
    # Col  0: Identifier (fixed 1)
    # Col  1: Carrier indicator (fixed 0)
    # Col  2: UL/SUL indicator
    # Col  3: Bandwidth part indicator
    # Col  4: Frequency domain resource assignment
    # Col  5: Time domain resource assignment
    # Col  6: Frequency hopping flag
    # Col  7: MCS (fixed 5)
    # Col  8: New data indicator (fixed 1)
    # Col  9: Redundancy version (fixed 2)
    # Col 10: HARQ process number (fixed 4)
    # Col 11: 1st downlink assignment index (DAI)
    # Col 12: 2nd downlink assignment index (fixed 0)
    # Col 13: TPC for PUSCH (fixed 2)
    # Col 14: SRS resource indicator
    # Col 15: Precoding information and number of layers
    # Col 16: Antenna port(s)
    # Col 17: SRS request
    # Col 18: CSI request
    # Col 19: CBG transmission information
    # Col 20: PTRS-DMRS association
    # Col 21: Beta offset indicator
    # Col 22: DMRS sequence initialization
    # Col 23: UL-SCH indicator (fixed 1)
    # Col 24: PDCCH monitoring adaptation indicator (0 or 1 bit)
    # NOTE: Transform precoder indication (Rel-18) is shown in the display table
    #       but omitted here — Wireshark does not yet support this field.
    w01 = [
        "1",
        "0",
        _cv(ulsulfieldvalue),
        _cv(ulbwpfieldvalue),
        _cv(frdabitsul),
        _cv(tdrabitsul),
        _cv(ulhopping),
        "5",
        "1",
        "2",
        "4",
        _cv(dlassignment),
        "0",
        "2",
        _cv(srsindicatorfieldvalue),
        _cv(precodingnumberoflayers),
        _cv(antennaports01fieldvalue),
        _cv(srsrequestfieldvalue),
        _cv(reporttriggersizevalue),
        _cv(maxcodeblockgroupspertransportblockvalue01),
        _cv(prtsdmrsfieldvalue),
        _cv(betaoffsetfieldvalue),
        _cv(dmrssequencefieldvalue),
        "1",
        _cv(pdcch_monitoring_adapt_bits),
    ]
    dci01_line = _row(cell_label, totallength01, w01)

    # --- DCI 1_1 (28 width columns) ---
    # Col  0: Identifier (fixed 1)
    # Col  1: Carrier indicator (fixed 0)
    # Col  2: Bandwidth part indicator
    # Col  3: Frequency domain resource assignment
    # Col  4: Time domain resource assignment
    # Col  5: VRB-to-PRB mapping
    # Col  6: PRB bundling size indicator
    # Col  7: Rate matching indicator
    # Col  8: ZP CSI-RS trigger
    # Col  9: MCS TB1 (fixed 5)
    # Col 10: NDI TB1 (fixed 1)
    # Col 11: RV TB1 (fixed 2)
    # Col 12: TB2 disabled indicator (FALSE)
    # Col 13: MCS TB2 placeholder (5-bit field; excluded from DCI size when FALSE)
    # Col 14: NDI TB2 placeholder (1-bit; excluded when FALSE)
    # Col 15: RV TB2 placeholder  (2-bit; excluded when FALSE)
    # Col 16: HARQ process number (fixed 4)
    # Col 17: Downlink assignment index
    # Col 18: TPC for PUCCH (fixed 2)
    # Col 19: PUCCH resource indicator (fixed 3)
    # Col 20: PDSCH-to-HARQ feedback timing indicator
    # Col 21: Antenna port(s)
    # Col 22: Transmission configuration indication
    # Col 23: SRS request
    # Col 24: CBG transmission information
    # Col 25: CBG flushing out information
    # Col 26: DMRS sequence initialization (fixed 1)
    # Col 27: PDCCH monitoring adaptation indicator (0 or 1 bit)
    w11 = [
        "1",
        "0",
        _cv(dlbwpfieldvalue),
        _cv(frdabitsdl),
        _cv(tdrabitsdl),
        _cv(vrbprbfieldvalue),
        _cv(prbbundlefieldvalue),
        _cv(ratematchingindicatorsizefieldvalue),
        _cv(zpcsirstriggerfieldvalue),
        "5",
        "1",
        "2",
        "FALSE",
        "5",   # MCS TB2 placeholder (Wireshark col present even when TB2 disabled)
        "1",   # NDI TB2 placeholder
        "2",   # RV TB2 placeholder
        "4",   # HARQ process number (4 bits, fixed)
        _cv(DLassignmentfieldvalue),
        "2",
        "3",
        _cv(pdschtoharqtimingindfieldvalue),
        _cv(antennaportsvaluefieldvalue),
        _cv(transmissionconfigurationfieldvalue),
        _cv(srsrequestfieldvalue_dl),
        _cv(cbgtransmissioninformationfieldvalue11),
        _cv(codeblockflushindicatorfieldvalue),
        "1",
        _cv(pdcch_monitoring_adapt_bits),
    ]
    dci11_line = _row(cell_label, totallength11, w11)

    out_dir = (os.path.abspath(output_dir) if output_dir
               else os.path.dirname(os.path.abspath(rrc_filepath)))
    os.makedirs(out_dir, exist_ok=True)
    path01 = os.path.join(out_dir, "dci_0_1_fields_config")
    path11 = os.path.join(out_dir, "dci_1_1_fields_config")

    with open(path01, "w", encoding="utf-8") as f_out:
        f_out.write(dci01_line + "\n")
    with open(path11, "w", encoding="utf-8") as f_out:
        f_out.write(dci11_line + "\n")

    return path01, path11


# Check if value is None
def checkvalue2(value):
    if value is None:
        value = 0
        value = int(value)
        return value
    else:
        return value


def _interactive_line_input(prompt):
    """Read one line from a real interactive console; return '' otherwise.

    PyInstaller --noconsole and GUI subprocesses often have sys.stdin that
    is non-None but not a TTY, or that raises EOFError on input() — never call
    input() in those cases.
    """
    stdin = sys.stdin
    if stdin is None:
        return ""
    try:
        if not stdin.isatty():
            return ""
    except (AttributeError, ValueError, OSError):
        return ""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def main():
    _abort_if_saved_output_instead_of_rrc()

    nrdc_scg_start = _find_nrdc_nrscg_start_index()
    _nrdc_scg = (nrdc_scg_start >= 0)
    _reconfig_start, _both_msgs = _find_reconfig_start_index()

    # Structural anchors per TS 38.331 S6.3.2 / TS 38.213 S12: DCI 0_1 / 1_1
    # sizes are derived from the *active dedicated* DL/UL BWP entry whose
    # bwp-Id matches firstActiveDownlinkBWP-Id / firstActiveUplinkBWP-Id in
    # the latest *BWP-ToAddModList.  When that cannot be resolved, fall back
    # to the legacy temporal anchor (first rrcReconfiguration line when both
    # Setup and Reconfig are present).
    _dl_dedicated_list, _dl_dedicated_entry, _dl_anchor_id = (
        _resolve_active_dedicated_bwp_block_start('DL'))
    _ul_dedicated_list, _ul_dedicated_entry, _ul_anchor_id = (
        _resolve_active_dedicated_bwp_block_start('UL'))

    if _nrdc_scg:
        _dl_scope = nrdc_scg_start
        _dl_scope_label = "NR-DC SCG (mrdc-SecondaryCellGroup nr-SCG)"
    elif _dl_dedicated_list >= 0:
        _dl_scope = _dl_dedicated_list
        _dl_scope_label = f"active dedicated DL BWP (bwp-Id={_dl_anchor_id})"
    elif _both_msgs:
        _dl_scope = _reconfig_start
        _dl_scope_label = (
            "rrcReconfiguration (temporal fall-back; structural BWP resolution failed)")
    else:
        _dl_scope = 0
        _dl_scope_label = "whole file"

    if _nrdc_scg:
        _ul_scope = nrdc_scg_start
        _ul_scope_label = "NR-DC SCG (mrdc-SecondaryCellGroup nr-SCG)"
    elif _ul_dedicated_list >= 0:
        _ul_scope = _ul_dedicated_list
        _ul_scope_label = f"active dedicated UL BWP (bwp-Id={_ul_anchor_id})"
    elif _both_msgs:
        _ul_scope = _reconfig_start
        _ul_scope_label = (
            "rrcReconfiguration (temporal fall-back; structural BWP resolution failed)")
    else:
        _ul_scope = 0
        _ul_scope_label = "whole file"

    def _scope_src_note(scope_label):
        if scope_label.startswith("active dedicated"):
            direction = "UL" if "UL BWP" in scope_label else "DL"
            return f" [from active dedicated {direction} BWP]"
        if scope_label.startswith("NR-DC"):
            return " [from NR-DC SCG (mrdc-SecondaryCellGroup nr-SCG)]"
        if "temporal fall-back" in scope_label:
            return " [from rrcReconfiguration (temporal fall-back)]"
        return ""

    _dl_src_note = _scope_src_note(_dl_scope_label)
    _ul_src_note = _scope_src_note(_ul_scope_label)

    # RRC slice for physicalCellGroupConfig + sCellToAddModList when inferring DAI
    # bit width (4 bits when ``sCellToAddModList`` appears in this window).  NR-DC SCG
    # runs use the SCG branch only; MN-terminated captures stop before the first nr-SCG.
    if _nrdc_scg:
        _dai_lo, _dai_hi = nrdc_scg_start, rrclength
    else:
        _nr_demarc = _find_nrdc_nrscg_start_index()
        _dai_lo, _dai_hi = 0, (_nr_demarc if _nr_demarc >= 0 else rrclength)

    # FDRA-related parameters: scan from the structural / SCG anchor first, then
    # fall back to the whole file when the anchor misses (delta Reconfig that
    # does not re-include the IE).  This is the consistent treatment for
    # locationAndBandwidth, subcarrierSpacing, resourceAllocation and the
    # time-domain allocation lists.
    dllocationandbandwidthvalue = numericalparser1(BWPDownlink, locationAndBandwidth, 0, scan_from=_dl_scope)
    if dllocationandbandwidthvalue == 0 and _dl_scope > 0:
        dllocationandbandwidthvalue = numericalparser1(BWPDownlink, locationAndBandwidth, 0)
    if dllocationandbandwidthvalue == 0:
        raw = _interactive_line_input(
            "DL locationAndBandwidth not found in file (needed for frequency-domain bit-width).\n"
            "Enter value (e.g. 17875 for FR2 n258 100MHz), or press Enter to keep 0: "
        )
        if raw.isdigit():
            dllocationandbandwidthvalue = int(raw)
        elif not raw:
            print("WARNING: DL locationAndBandwidth not found in file — FDRA bit-width will be 0.")

    ullocationandbandwidthvalue = numericalparser1(BWPUplink, locationAndBandwidth, 0, scan_from=_ul_scope)
    if ullocationandbandwidthvalue == 0 and _ul_scope > 0:
        ullocationandbandwidthvalue = numericalparser1(BWPUplink, locationAndBandwidth, 0)
    if ullocationandbandwidthvalue == 0:
        raw = _interactive_line_input(
            "UL locationAndBandwidth not found in file.\n"
            "Enter value (or press Enter to keep 0): "
        )
        if raw.isdigit():
            ullocationandbandwidthvalue = int(raw)
        elif not raw:
            print("WARNING: UL locationAndBandwidth not found in file — FDRA bit-width will be 0.")

    subcarrierspacingdlvalue = numericalparser1(BWPDownlink, subcarrierSpacing, 0, scan_from=_dl_scope)
    if subcarrierspacingdlvalue == 0 and _dl_scope > 0:
        subcarrierspacingdlvalue = numericalparser1(BWPDownlink, subcarrierSpacing, 0)
    subcarrierspacingulvalue = numericalparser1(BWPUplink, subcarrierSpacing, 0, scan_from=_ul_scope)
    if subcarrierspacingulvalue == 0 and _ul_scope > 0:
        subcarrierspacingulvalue = numericalparser1(BWPUplink, subcarrierSpacing, 0)

    _ra_blk, _rbg_blk, _pdsch_hdr = parse_pdsch_ra_and_rbg_in_first_block(_dl_scope)
    if _pdsch_hdr >= 0:
        pdschrbgsizevalue = _rbg_blk
    else:
        pdschrbgsizevalue = doubleindexparser(
            pdschConfig, puschConfigC, Rbgsize, scan_from=_dl_scope)
    if _ra_blk is not None:
        dlresourceallocationvalue = _ra_blk
    else:
        dlresourceallocationvalue = writtenparser1(
            pdschConfig, dynamicSwitch, resourceAllocationType0, resourceAllocationType1,
            'tyhja', None, scan_from=_dl_scope)
        if dlresourceallocationvalue is None and _dl_scope > 0:
            dlresourceallocationvalue = writtenparser1(
                pdschConfig, dynamicSwitch, resourceAllocationType0, resourceAllocationType1,
                'tyhja', None)
    puschrbgsizevalue = numericalparser1(puschConfig, Rbgsize, 1, scan_from=_ul_scope)

    ulresourceallocationvalue = writtenparser1(puschConfig, dynamicSwitch, resourceAllocationType0, resourceAllocationType1, 'tyhja', None, scan_from=_ul_scope)
    if ulresourceallocationvalue is None and _ul_scope > 0:
        ulresourceallocationvalue = writtenparser1(puschConfig, dynamicSwitch, resourceAllocationType0, resourceAllocationType1, 'tyhja', None)
    # PDSCH TDA list - per TS 38.214 S5.1.2.1.1, the R16 override
    # `pdsch-TimeDomainAllocationList-r16` (when configured) supersedes the
    # legacy `pdsch-TimeDomainAllocationList` for DCI 1_1.  We try the
    # override first with the same scoping as the legacy lookup, then fall
    # through to the legacy list with its existing Reconfig-then-Setup
    # fall-back.
    _pdsch_r16_count = parse_pdsch_tda_r16_count(scan_from=_dl_scope)
    if _pdsch_r16_count is None and _dl_scope > 0:
        _pdsch_r16_count = parse_pdsch_tda_r16_count(scan_from=0)
    if _pdsch_r16_count is not None:
        pdschtimedomainallocationlistvalue = _pdsch_r16_count
        _tdr_dl_src_label = "pdsch-TimeDomainAllocationList-r16 (R16 override)"
    else:
        pdschtimedomainallocationlistvalue = doublenumericalparser(
            pdschConfig, pdschTimeAllocationList1, pdschTimeAllocationList, None,
            scan_from=_dl_scope)
        if pdschtimedomainallocationlistvalue is None and _dl_scope > 0:
            pdschtimedomainallocationlistvalue = doublenumericalparser(
                pdschConfig, pdschTimeAllocationList1, pdschTimeAllocationList, None)
        _tdr_dl_src_label = "pdsch-TimeDomainAllocationList"

    # PUSCH TDA list - per TS 38.214 S6.1.2.1.1, the R16 override
    # `pusch-TimeDomainAllocationListDCI-0-1-r16` (when configured) takes
    # precedence over the legacy `pusch-TimeDomainAllocationList` for DCI
    # 0_1 only (DCI 0_0 still uses the legacy list, but its TDA bit-width
    # is fixed at 4 bits per TS 38.212 S7.3.1.1.1 anyway).  Same scoping
    # rules as the legacy path: NR-DC SCG > Reconfig-scoped > whole file.
    if _nrdc_scg:
        _pusch_r16_count = parse_pusch_tda_r16_dci01_count(scan_from=nrdc_scg_start)
    else:
        _pusch_r16_count = parse_pusch_tda_r16_dci01_count(scan_from=_ul_scope)
        if _pusch_r16_count is None and _ul_scope > 0:
            _pusch_r16_count = parse_pusch_tda_r16_dci01_count(scan_from=0)

    if _pusch_r16_count is not None:
        puschtimedomainallocationlistvalue = _pusch_r16_count
        _tdr_ul_src_label = "pusch-TimeDomainAllocationListDCI-0-1-r16 (R16 override)"
    else:
        if _nrdc_scg:
            puschtimedomainallocationlistvalue = doublenumericalparser(
                puschConfig, puschTimeAllocationList1, puschTimeAllocationList,
                None, scan_from=nrdc_scg_start)
        else:
            puschtimedomainallocationlistvalue = doublenumericalparser(
                puschConfig, puschTimeAllocationList1, puschTimeAllocationList,
                None, scan_from=_ul_scope)
            # Do NOT fall back to a whole-file scan when _ul_scope is resolved:
            # if the active dedicated pusch-Config (from the latest rrcReconfiguration)
            # does not contain a pusch-TimeDomainAllocationList, Table 6.1.2.1.1-1A
            # directs the UE to use the Default A table (16 entries → 4 bits), not
            # an older config's list that was replaced by the new Setup.  A None result
            # from the scoped scan is the correct signal to fall to Default A.
        _tdr_ul_src_label = "pusch-TimeDomainAllocationList"
    transformprecodervalue = writtenparser1(puschConfig, transformprecoderdisabled, transformprecoderenabled, 'tyhja', 'tyhja', None)
    antennaportsvalue, _nrofsrs_from_reconfig = parse_nrofsrsports_prefer_reconfig()
    maxrankvalue, _maxrank_from_reconfig = parse_maxrank_prefer_reconfig()
    codebooksubsetvalue = writtenparser1(puschConfig, codebooksubset1, codebooksubset2, codebooksubset3, 'tyhja', None)
    txconfigvalue = writtenparser1(puschConfig, codebook, noncodebook, 'tyhja', 'tyhja', None)
    dmrstypevalue = writtenparser1(DMRSUplinkconfig, DMRStype1, DMRStype2, 'tyhja', 'tyhja', DMRStype1)
    dmrstypevalue_dl, _dmrstype_dl_from_reconfig = parse_dmrstype_dl_prefer_reconfig()
    maxlengthvalue = numericalparser2(maxlength, 1)
    reporttriggersizevalue = numericalparser2(reporttriggersize, 0)
    ptrsuplinkconfigvalue = writtenparser2(ptrsuplinkconfig, None)
    ptrs_configured, ptrs_maxnrofports, _ptrs_from_reconfig = parse_ptrs_maxnrofports_prefer_reconfig()
    frequencyhoppingoffsetlistsvalue = numericalparser2(frequencyHoppingOffsetLists, None)
    srsresourcesettoaddmodlistvalue = numericalparser2(srsResourceSetToAddModList, None)
    usageofsrsresourcesetvalue = writtenparser1(srsconfig, codebook1, noncodebook1, antennaswitching, beammanagement, None)
    pdschharqackcodebookvalue = writtenparser1(
        physicalcellgroupconfig, semistatic, dynamic, 'tyhja', 'tyhja', dynamic,
        scan_from=_dai_lo)
    prbbundlingvalue = writtenparser1(prbbundlingtype, dynamic, static, 'tyhja', 'tyhja', None)
    ratematchpatterngroup1value = writtenparser2(ratematch1, None)
    ratematchpatterngroup2value = writtenparser2(ratematch2, None)
    zpcsirstriggervalue = numericalparser2(zpcsiresresourcesetstoaddmodlist, 0)
    _dai_scell_to_add_mod = any(
        _SCELL_LIST_HDR.search(rows[i])
        for i in range(_dai_lo, min(_dai_hi, rrclength)))
    servingcellvalue = scelltoaddmodlist if _dai_scell_to_add_mod else 1
    dldatatoulackvalue = None
    for _i in range(rrclength):
        if re.search(r"\bdl-DataToUL-ACK\b", rows[_i]):
            dldatatoulackvalue = dl_data_to_ul_ack_count(_i)
            break
    tcipresentindcivalue = writtenparser2(tciindci, None)
    maxcodeblockgroupspertransportblockvalue = numericalparser1(pdschConfig, maxcodeblocks, 0)
    maxcodeblockgroupspertransportblockvalue01 = numericalparser1(puschConfig, maxcodeblocks, 0)
    maxnrofcodewordsscheduledbydcivalue = numericalparser2(maxcodewordsscheduledDCI, 0)
    codeblockflushindicatorvalue = writtenparser2(blockgroupflushindicator, None)
    supplementaryuplinkvalue = writtenparser2(supuplink, None)
    numberofuplinkbwpvalue = numericalparser2(uplinkbwptoaddmodlist, None)
    numberofdownlinkbwpvalue = numericalparser2(downlinkbwptoaddmodlist, None)
    vrbprb = writtenparser2(vrbtoprbinterleaver, None)
    if _nrdc_scg:
        betaoffsets_configured, _betaoffsets_from_reconfig = parse_betaoffsets_prefer_reconfig(scan_from=nrdc_scg_start)
    else:
        betaoffsets_configured, _betaoffsets_from_reconfig = parse_betaoffsets_prefer_reconfig()
    srs_codebook_set_count, _srs_set_from_reconfig = count_codebook_srs_resource_sets_prefer_reconfig()
    srs_resource_set_indicator_bits = 2 if srs_codebook_set_count >= 2 else 0
    ulsulfieldvalue = ulsulsize(supplementaryuplinkvalue)
    dlbwpfieldvalue = bwpindsize(numberofdownlinkbwpvalue)
    ulbwpfieldvalue = bwpindsize(numberofuplinkbwpvalue)
    dlnrb, dlstartrb = getbwprbandstartrb(dllocationandbandwidthvalue)
    ulnrb, ulstartrb = getbwprbandstartrb(ullocationandbandwidthvalue)
    ulnominalrbg = getnominalresourceblockgroup(puschrbgsizevalue, ulnrb)
    dlnominalrbg = getnominalresourceblockgroup(pdschrbgsizevalue, dlnrb)
    frdabitsul = calculatefrdabitsul(ulresourceallocationvalue, frequencyhoppingoffsetlistsvalue, ulnrb, ulstartrb, ulnominalrbg)
    frdabitsdl = calculatefrdabitsdl(dlresourceallocationvalue, dlnrb, dlstartrb, dlnominalrbg)
    tdrabitsul = tdrabits(puschtimedomainallocationlistvalue)
    tdrabitsdl = tdrabits(pdschtimedomainallocationlistvalue)
    ulhopping = numberulhopping(frequencyhoppingoffsetlistsvalue)
    dlassignment = firstdlassignment(pdschharqackcodebookvalue)
    precodingnumberoflayers = sizeofprecodingandnumberoflayers(transformprecodervalue, antennaportsvalue, maxrankvalue, codebooksubsetvalue, txconfigvalue)
    antennaports01fieldvalue = antennaports01(transformprecodervalue, dmrstypevalue, maxlengthvalue)
    srsrequestfieldvalue = nsrsrequest(supplementaryuplinkvalue)
    srsindicatorfieldvalue = srsindicatorfield(srsresourcesettoaddmodlistvalue, usageofsrsresourcesetvalue, txconfigvalue, maxrankvalue)
    prtsdmrsfieldvalue = prtsdmrsfield(ptrs_configured, transformprecodervalue, maxrankvalue,
                                       antennaportsvalue, ptrs_maxnrofports, srsindicatorfieldvalue)
    dmrssequencefieldvalue = dmrssequencefield(transformprecodervalue)
    vrbprbfieldvalue = vrbprbfield(dlresourceallocationvalue, vrbprb)
    prbbundlefieldvalue = prbbundlefield(prbbundlingvalue)
    zpcsirstriggerfieldvalue = zpcsirstriggerfield(zpcsirstriggervalue)
    DLassignmentfieldvalue = DLassignment(servingcellvalue, pdschharqackcodebookvalue)
    pdschtoharqtimingindfieldvalue = pdschtoharqtimingind(dldatatoulackvalue)
    antennaportsvaluefieldvalue = antennaportsfield(dmrstypevalue_dl, maxlengthvalue)
    transmissionconfigurationfieldvalue = transmissionconfigurationfield(tcipresentindcivalue)
    codeblockflushindicatorfieldvalue = codeblockflushindicatorfield(codeblockflushindicatorvalue)
    cbgtransmissioninformationfieldvalue11 = cbgtransmissioninformationfield11(maxcodeblockgroupspertransportblockvalue, maxnrofcodewordsscheduledbydcivalue)
    ratematchingindicatorsizefieldvalue = ratematchingindicatorsizefield(ratematchpatterngroup1value, ratematchpatterngroup2value)
    betaoffsetfieldvalue = betaoffsetfield(betaoffsets_configured)

    # Rel-16/17 PDCCH monitoring adaptation indicator (TS 38.212 §7.3.1.1.2 / §7.3.1.2.2)
    # 1 bit when search-space group switching OR availability indication is configured:
    #   Rel-16: availabilityIndicator-r16 or searchSpaceSwitchTrigger-r16 in SearchSpace
    #   Rel-17: searchSpaceGroupIdList-r17 or searchSpaceSwitchConfig-r17 in PDCCH-Config
    _pdcch_mon_adapt = any(
        re.search(
            r"searchSpaceSwitchConfig.r17|searchSpaceGroupIdList.r17"
            r"|availabilityIndicator.r16|searchSpaceSwitchTrigger.r16",
            rows[i])
        for i in range(rrclength))
    pdcch_monitoring_adapt_bits = 1 if _pdcch_mon_adapt else 0
    if pdcch_monitoring_adapt_bits:
        _pdcch_mon_c = (
            "searchSpaceSwitchConfig-r17 / searchSpaceGroupIdList-r17 / "
            "availabilityIndicator-r16 / searchSpaceSwitchTrigger-r16 "
            "configured -> 1 bit")
    else:
        _pdcch_mon_c = (
            "searchSpaceSwitchConfig-r17 / searchSpaceGroupIdList-r17 / "
            "availabilityIndicator-r16 / searchSpaceSwitchTrigger-r16 "
            "not configured -> 0 bits")

    # Rel-18 Transform precoder indication field (TS 38.212 §7.3.1.1.2)
    # 1 bit added to DCI format 0_1 when dynamicTransformPrecoderFieldPresenceDCI-0-1-r18
    # is set to 'enabled' in the active UL BWP's pusch-Config.
    # When present, the 1-bit field indicates whether transform precoding (DFT-s-OFDM)
    # is applied for the scheduled PUSCH transmission.
    _ul_scan_start = _ul_scope if _ul_scope >= 0 else 0
    _transform_prec_indicator = any(
        re.search(
            r"\bdynamicTransformPrecoderFieldPresenceDCI-0-1-r18\s+enabled\b",
            rows[i])
        for i in range(_ul_scan_start, rrclength))
    transform_prec_indicator_bits = 1 if _transform_prec_indicator else 0
    if transform_prec_indicator_bits:
        _transform_prec_c = (
            "dynamicTransformPrecoderFieldPresenceDCI-0-1-r18 = enabled "
            "-> 1 bit (TS 38.212 Rel-18 §7.3.1.1.2)")
    else:
        _transform_prec_c = (
            "dynamicTransformPrecoderFieldPresenceDCI-0-1-r18 not configured "
            "-> 0 bits")

    # ------------------------------------------------------------------ #
    #  Physical Cell ID (from RRC file header)                           #
    # ------------------------------------------------------------------ #
    _pci = _parse_physical_cell_id()
    _cell_label = f"Cell_{_pci}_0" if _pci is not None else "Cell_unknown_0"

    # ------------------------------------------------------------------ #
    #  Standard reference banner                                          #
    # ------------------------------------------------------------------ #
    SPEC_REF  = "3GPP TS 38.212 \u00a77.3.1  +  TS 38.331 V17 ServingCellConfigCommon"
    INPUT_SRC = "Input: RRC text file (.txt)"
    if _RRC_PREFER_SETUP:
        RRC_MODE = ("RRC source: rrcSetup (--rrc-source=setup; rrcReconfiguration "
                    "overrides ignored)")
    else:
        RRC_MODE = ("RRC source: rrcReconfiguration when present, else rrcSetup "
                    "(default; --rrc-source=auto)")
    line1 = f"  {SPEC_REF}    {INPUT_SRC}  "
    line2 = f"  {RRC_MODE}  "
    _dl_banner_detail = (
        f"{_dl_scope_label}, BWP entry line {_dl_dedicated_entry + 1}"
        if (_dl_scope_label.startswith("active dedicated") and _dl_dedicated_entry >= 0)
        else f"{_dl_scope_label}, line {_dl_scope + 1}")
    _ul_banner_detail = (
        f"{_ul_scope_label}, BWP entry line {_ul_dedicated_entry + 1}"
        if (_ul_scope_label.startswith("active dedicated") and _ul_dedicated_entry >= 0)
        else f"{_ul_scope_label}, line {_ul_scope + 1}")
    line3 = (f"  DL anchor: {_dl_banner_detail}  |  "
             f"UL anchor: {_ul_banner_detail}  ")
    banner_w = max(len(line1), len(line2), len(line3), 74)
    line1 = line1.ljust(banner_w)
    line2 = line2.ljust(banner_w)
    line3 = line3.ljust(banner_w)
    _line3_warn = ("temporal fall-back" in _dl_scope_label or
                   "temporal fall-back" in _ul_scope_label)
    print()
    print(CYAN("\u2554" + "\u2550" * banner_w + "\u2557"))
    print(CYAN("\u2551") + BOLD(CYAN(line1)) + CYAN("\u2551"))
    print(CYAN("\u2551") + (YELLOW(line2) if _RRC_PREFER_SETUP else DIM(line2)) + CYAN("\u2551"))
    print(CYAN("\u2551") + (YELLOW(line3) if _line3_warn else DIM(line3)) + CYAN("\u2551"))
    print(CYAN("\u255a" + "\u2550" * banner_w + "\u255d"))

    def print_dci_table(fmt_name, fields):
        """Print ALL DCI fields as a numbered table with a comment column.
        Wraps long comments to stay readable, uses Unicode box-drawing,
        and colorises headers/zero-bit rows when stdout is a TTY.
        fields = list of (name, bits, comment)."""
        NUM_W  = 4
        BITS_W = 6
        name_w = max((len(n) for n, _, _ in fields), default=30)
        name_w = max(name_w, 30)
        TOTAL_BUDGET = 140
        cmt_w_budget = TOTAL_BUDGET - (NUM_W + name_w + BITS_W + 13)
        cmt_w = max(40, min(70, cmt_w_budget))

        def _wrap(text, w):
            lines = textwrap.wrap(text, width=w, break_long_words=False,
                                  break_on_hyphens=False) or [""]
            return lines

        total_bits = sum((b if b is not None else 0) for _, b, _ in fields)
        field_count = len(fields)

        top    = "\u250c" + "\u2500"*(NUM_W+2) + "\u252c" + "\u2500"*(name_w+2) + "\u252c" + "\u2500"*(BITS_W+2) + "\u252c" + "\u2500"*(cmt_w+2) + "\u2510"
        mid    = "\u251c" + "\u2500"*(NUM_W+2) + "\u253c" + "\u2500"*(name_w+2) + "\u253c" + "\u2500"*(BITS_W+2) + "\u253c" + "\u2500"*(cmt_w+2) + "\u2524"
        botsep = "\u2520" + "\u2500"*(NUM_W+2) + "\u2542" + "\u2500"*(name_w+2) + "\u2542" + "\u2500"*(BITS_W+2) + "\u2542" + "\u2500"*(cmt_w+2) + "\u2528"
        bot    = "\u2514" + "\u2500"*(NUM_W+2) + "\u2534" + "\u2500"*(name_w+2) + "\u2534" + "\u2500"*(BITS_W+2) + "\u2534" + "\u2500"*(cmt_w+2) + "\u2518"
        v = "\u2502"

        print()
        print("  " + BOLD(MAGENTA(f"DCI {fmt_name}")))
        print("  " + DIM(f"DCI Size: ") + BOLD(GREEN(f"{total_bits} bits")) +
              DIM(f"    Fields: {field_count}"))
        print("  " + top)

        h_num  = f"{'#':>{NUM_W}}"
        h_name = f"{'Field Name':<{name_w}}"
        h_bits = f"{'Bits':>{BITS_W}}"
        h_cmt  = f"{'Comment / How derived':<{cmt_w}}"
        header = (v + f" {BOLD(h_num)} " + v + f" {BOLD(h_name)} "
                  + v + f" {BOLD(h_bits)} " + v + f" {BOLD(h_cmt)} " + v)
        print("  " + header)
        print("  " + mid)

        # Fixed-width "always-present" field names — dimmer to reduce noise
        _FIXED_NAMES = frozenset({
            "Identifier for DCI formats",
            "Modulation and coding scheme",
            "Modulation and coding scheme (TB1)",
            "New data indicator",
            "New data indicator (TB1)",
            "Redundancy version",
            "Redundancy version (TB1)",
            "HARQ process number",
            "TPC command for scheduled PUSCH",
            "TPC command for scheduled PUCCH",
            "PUCCH resource indicator",
            "UL-SCH indicator",
            "DMRS sequence initialization",
        })

        for idx, (name, bits, comment) in enumerate(fields, start=1):
            b_str = "?" if bits is None else str(bits)
            is_zero = (bits == 0)
            is_fixed = (name in _FIXED_NAMES)
            comment_lines = _wrap(comment, cmt_w)

            num_cell = f"{idx}"
            if is_zero:
                bits_color = DIM
                name_color = DIM
            elif bits is None:
                bits_color = YELLOW
                name_color = BOLD
            elif is_fixed:
                bits_color = GREEN
                name_color = lambda s: s  # no extra style for fixed fields
            else:
                # Variable non-zero field: highlight in CYAN
                bits_color = lambda s: BOLD(CYAN(s))
                name_color = lambda s: BOLD(CYAN(s))

            for li, cline in enumerate(comment_lines):
                if li == 0:
                    n_raw = f"{num_cell:>{NUM_W}}"
                    name_raw = f"{name:<{name_w}}"
                    bits_raw = f"{b_str:>{BITS_W}}"
                    n_disp    = DIM(n_raw) if is_zero else n_raw
                    name_disp = name_color(name_raw)
                    bits_disp = bits_color(bits_raw)
                else:
                    n_disp    = " " * NUM_W
                    name_disp = " " * name_w
                    bits_disp = " " * BITS_W
                cmt_raw  = f"{cline:<{cmt_w}}"
                cmt_disp = DIM(cmt_raw) if is_zero else cmt_raw
                print("  " + v + f" {n_disp} " + v + f" {name_disp} "
                      + v + f" {bits_disp} " + v + f" {cmt_disp} " + v)

        print("  " + botsep)
        total_label = "TOTAL DCI SIZE"
        total_bits_str = str(total_bits)
        print("  " + v + " " * (NUM_W + 2)
              + v + f" {BOLD(f'{total_label:<{name_w}}')} "
              + v + f" {BOLD(GREEN(f'{total_bits_str:>{BITS_W}}'))} "
              + v + f" {'':<{cmt_w}} " + v)
        print("  " + bot)
        print()

    # ------------------------------------------------------------------ #
    #  Build per-field comment strings from parsed values                 #
    # ------------------------------------------------------------------ #
    _fdr_win_max, _fdr_win_note, _fdr_win_rows = collect_max_fdr_bits_dci11_window(
        _dai_lo, _dai_hi, dllocationandbandwidthvalue)

    # Bandwidth part indicator
    _dlbwp_c = (f"downlinkBWP-ToAddModList: {numberofdownlinkbwpvalue} BWP(s) "
                f"-> ceil(log2({numberofdownlinkbwpvalue}+1)) = {dlbwpfieldvalue} bit(s)")
    _ulbwp_c = (f"uplinkBWP-ToAddModList: {numberofuplinkbwpvalue} BWP(s) "
                f"-> ceil(log2({numberofuplinkbwpvalue}+1)) = {ulbwpfieldvalue} bit(s)")

    # Frequency domain resource assignment
    if dlresourceallocationvalue == resourceAllocationType0:
        _frdl_c = (f"RA type0 (RBG){_dl_src_note}: nrb={dlnrb}, nominalRBG={dlnominalrbg} "
                   f"-> ceil({dlnrb}/{dlnominalrbg}) = {frdabitsdl} bits")
    elif dlresourceallocationvalue == resourceAllocationType1:
        _frdl_c = (f"RA type1 (RIV){_dl_src_note}: nrb={dlnrb} "
                   f"-> ceil(log2({dlnrb}x{dlnrb+1}/2)) = {frdabitsdl} bits")
    elif dlresourceallocationvalue == dynamicSwitch:
        _frdl_c = f"RA dynamic{_dl_src_note}: max(type0,type1)+1 = {frdabitsdl} bits"
    else:
        _frdl_c = f"resourceAllocation not found in pdsch-Config{_dl_src_note} -> None"

    if frdabitsdl is not None and _fdr_win_max > frdabitsdl and _fdr_win_note:
        _frdl_c = _frdl_c + "  |  " + _fdr_win_note

    if frequencyhoppingoffsetlistsvalue in (2, 4):
        _frul_c = (f"Freq hopping ({frequencyhoppingoffsetlistsvalue} offsets){_ul_src_note}: "
                   f"ulnrf1-{frequencyhoppingoffsetlistsvalue} = {frdabitsul} bits")
    elif ulresourceallocationvalue == resourceAllocationType1:
        _frul_c = (f"RA type1 (RIV){_ul_src_note}: nrb={ulnrb} "
                   f"-> ceil(log2({ulnrb}x{ulnrb+1}/2)) = {frdabitsul} bits")
    elif ulresourceallocationvalue == resourceAllocationType0:
        _frul_c = (f"RA type0 (RBG){_ul_src_note}: nrb={ulnrb}, nominalRBG={ulnominalrbg} "
                   f"-> ceil({ulnrb}/{ulnominalrbg}) = {frdabitsul} bits")
    elif ulresourceallocationvalue == dynamicSwitch:
        _frul_c = f"RA dynamic{_ul_src_note}: max(type0,type1)+1 = {frdabitsul} bits"
    else:
        _frul_c = "resourceAllocation not found in pusch-Config -> None"

    # Time domain resource assignment - the source label is set above by
    # the override-then-legacy lookup so the per-field table makes it
    # obvious whether the bit-width came from the legacy R15 list or from
    # the R16 override IE (TS 38.214 S5.1.2.1.1 / S6.1.2.1.1).
    _tdr_dl_c = (f"{_tdr_dl_src_label}: {pdschtimedomainallocationlistvalue} entries "
                 f"-> ceil(log2({pdschtimedomainallocationlistvalue})) = {tdrabitsdl} bits")
    _tdr_ul_src = _ul_src_note
    if puschtimedomainallocationlistvalue is None:
        _tdr_ul_c = (f"No pusch-TimeDomainAllocationList in active pusch-Config"
                     f"{_tdr_ul_src} -> Default A (16 entries) = 4 bits "
                     f"(TS 38.214 Table 6.1.2.1.1-1A)")
    else:
        _tdr_ul_c = (f"{_tdr_ul_src_label}{_tdr_ul_src}: "
                     f"{puschtimedomainallocationlistvalue} entries "
                     f"-> ceil(log2({puschtimedomainallocationlistvalue})) = {tdrabitsul} bits")

    # VRB-to-PRB mapping
    _vrb_c = ("vrb-ToPRB-Interleaver present + RA type1 -> 1 bit"
              if vrbprbfieldvalue else
              "vrb-ToPRB-Interleaver not configured or RA type0 -> 0 bits")

    # PRB bundling
    _prb_c = ("prb-BundlingType = dynamic -> 1 bit"
              if prbbundlefieldvalue else
              "prb-BundlingType = static (or not configured) -> 0 bits")

    # Rate matching indicator
    if ratematchingindicatorsizefieldvalue == 2:
        _rm_c = "rateMatchPatternGroup1 + rateMatchPatternGroup2 both configured -> 2 bits"
    elif ratematchingindicatorsizefieldvalue == 1:
        _rm_c = "one rateMatchPatternGroup configured -> 1 bit"
    else:
        _rm_c = "no rateMatchPatternGroup configured -> 0 bits"

    # ZP CSI-RS trigger
    _zp_c = (f"aperiodic-ZP-CSI-RS: {zpcsirstriggervalue} resource set(s) -> {zpcsirstriggerfieldvalue} bits"
             if zpcsirstriggerfieldvalue else
             "aperiodic-ZP-CSI-RS not configured -> 0 bits")

    # Downlink assignment index
    _win = rows[_dai_lo:min(_dai_hi, rrclength)]
    _harq_src = (
        f"physicalCellGroupConfig in cell-group window (lines {_dai_lo + 1}–{_dai_hi})"
        if any('physicalCellGroupConfig' in r for r in _win)
        else "physicalCellGroupConfig absent in window (delta reconfig?) -> defaulted to dynamic")
    if DLassignmentfieldvalue == 4:
        _dlai_c = (f"pdschHARQ-ACK-Codebook=dynamic + sCellToAddModList in cell-group window "
                   f"-> 4 bits [{_harq_src}]")
    elif DLassignmentfieldvalue == 2:
        _dlai_c = (f"pdschHARQ-ACK-Codebook=dynamic, no sCellToAddModList in window "
                   f"-> 2 bits [{_harq_src}]")
    elif DLassignmentfieldvalue == 1:
        _dlai_c = f"pdschHARQ-ACK-Codebook=semi-static + serving cell -> 1 bit [{_harq_src}]"
    else:
        _dlai_c = f"pdschHARQ-ACK-Codebook not determined -> 0 bits"

    # 1st DL assignment index (in DCI 0-1)
    if dlassignment == 2:
        _ulai_c = f"pdschHARQ-ACK-Codebook=dynamic -> 2 bits [{_harq_src}]"
    elif dlassignment == 1:
        _ulai_c = f"pdschHARQ-ACK-Codebook=semi-static + serving cell -> 1 bit [{_harq_src}]"
    else:
        _ulai_c = f"pdschHARQ-ACK-Codebook not determined -> 0 bits"

    # PDSCH-to-HARQ feedback timing indicator
    if pdschtoharqtimingindfieldvalue:
        _harqt_c = (f"dl-DataToUL-ACK: {dldatatoulackvalue} values "
                    f"-> ceil(log2({dldatatoulackvalue})) = {pdschtoharqtimingindfieldvalue} bits")
    else:
        _harqt_c = "dl-DataToUL-ACK not configured -> 0 bits"

    # Antenna ports DCI 1-1
    _dmrstype_dl_src = ("Reconfig" if _dmrstype_dl_from_reconfig else
                        ("default type1" if dmrstypevalue_dl == DMRStype1 else "Setup"))
    if antennaportsvaluefieldvalue:
        _ap11_c = (f"DL DMRS type={dmrstypevalue_dl} [{_dmrstype_dl_src}], "
                   f"maxLength={maxlengthvalue} -> {antennaportsvaluefieldvalue} bits "
                   f"(TS 38.212 Table 7.3.1.2.2-1)")
    else:
        _ap11_c = (f"DL DMRS type={dmrstypevalue_dl} [{_dmrstype_dl_src}], "
                   f"maxLength={maxlengthvalue} -> 0 bits (see TS 38.212 Table 7.3.1.2.2-1)")

    # Transmission configuration indication
    _tci_c = ("tci-PresentInDCI enabled -> 3 bits"
              if transmissionconfigurationfieldvalue else
              "tci-PresentInDCI not configured -> 0 bits")

    # SRS request
    _srsr_c = (f"supplementaryUplink {'configured' if ulsulfieldvalue else 'not configured'} "
               f"-> {srsrequestfieldvalue} bits")

    # CBGTI DCI 1-1
    if cbgtransmissioninformationfieldvalue11:
        _cbgti11_c = (f"maxCodeBlockGroups={maxcodeblockgroupspertransportblockvalue} x "
                      f"maxNrofCodeWords={maxnrofcodewordsscheduledbydcivalue} "
                      f"= {cbgtransmissioninformationfieldvalue11} bits")
    else:
        _cbgti11_c = "maxCodeBlockGroupsPerTransportBlock not configured -> 0 bits"

    # CBGFI
    _cbgfi_c = ("codeBlockGroupFlushIndicator present -> 1 bit"
                if codeblockflushindicatorfieldvalue else
                "codeBlockGroupFlushIndicator not configured -> 0 bits")

    # UL/SUL indicator (DCI 0-1)
    _sul_c = ("supplementaryUplink configured -> 1 bit"
              if ulsulfieldvalue else
              "supplementaryUplink not configured -> 0 bits")

    # Frequency hopping flag (DCI 0-1)
    _fh_c = (f"frequencyHoppingOffsetLists: {frequencyhoppingoffsetlistsvalue} offsets -> 1 bit"
             if ulhopping else
             "frequencyHoppingOffsetLists not configured -> 0 bits")

    # CBGTI DCI 0-1
    if maxcodeblockgroupspertransportblockvalue01:
        _cbgti01_c = (f"maxCodeBlockGroupsPerTransportBlock = {maxcodeblockgroupspertransportblockvalue01} "
                      f"(PUSCH-Config) -> {maxcodeblockgroupspertransportblockvalue01} bits")
    else:
        _cbgti01_c = "maxCodeBlockGroupsPerTransportBlock not configured in pusch-Config -> 0 bits"

    # SRS resource indicator
    if srsindicatorfieldvalue:
        _srsi_c = (f"txConfig={txconfigvalue}, usage={usageofsrsresourcesetvalue} "
                   f"-> {srsindicatorfieldvalue} bits")
    else:
        _srsi_c = "srs-ResourceSetToAddModList absent or txConfig/usage conditions not met -> 0 bits"

    if txconfigvalue == noncodebook:
        _pre_c = "txConfig=nonCodebook -> 0 bits"
    elif transformprecodervalue == transformprecoderenabled:
        _srs_n = srs_codebook_resource_count()
        if _srs_n is None:
            _pre_c = "transformPrecoder=enabled, no SRS-ResourceSet with usage=codebook found -> 0 bits"
        else:
            _pre_c = (f"transformPrecoder=enabled, SRS resources in codebook set={_srs_n} "
                      f"-> ceil(log2({_srs_n})) = {precodingnumberoflayers} bits "
                      f"(TS 38.212 7.3.1.1.2 scenario 1)")
    elif antennaportsvalue is None or maxrankvalue is None:
        _pre_c = "nrofSRS-Ports or maxRank not parsed from RRC -> ? bits"
    else:
        _subset_label = (codebooksubsetvalue if codebooksubsetvalue in
                         (codebooksubset1, codebooksubset2, codebooksubset3)
                         else f"{codebooksubset1} (default)")
        if _ul_src_note:
            _mr_src = _sp_src = _ul_src_note
        else:
            _mr_src = " [from rrcReconfiguration]" if _maxrank_from_reconfig else ""
            _sp_src = " [from rrcReconfiguration]" if _nrofsrs_from_reconfig else ""
        _pre_c = (f"transformPrecoder=disabled, nrofSRS-Ports={antennaportsvalue}{_sp_src}, "
                  f"maxRank={maxrankvalue}{_mr_src}, codebookSubset={_subset_label} "
                  f"-> {precodingnumberoflayers} bits (TS 38.212 Table 7.3.1.1.2-5)")

    # Antenna ports DCI 0-1
    if antennaports01fieldvalue:
        _ap01_c = (f"nrofSRS-Ports={antennaportsvalue}, maxRank={maxrankvalue} "
                   f"-> {antennaports01fieldvalue} bits")
    else:
        _ap01_c = "nrofSRS-Ports or maxRank not determined -> 0 bits"

    # CSI request
    _csi_c = (f"reportTriggerSize = {reporttriggersizevalue} -> {reporttriggersizevalue} bits"
              if reporttriggersizevalue else
              "reportTriggerSize not configured -> 0 bits")

    _ptrs_src = _ul_src_note if _ul_src_note else (" [from rrcReconfiguration]" if _ptrs_from_reconfig else "")
    _tp_is_enabled = (transformprecodervalue == transformprecoderenabled)
    _tp_is_disabled = (transformprecodervalue == transformprecoderdisabled)
    _ptrs_ports_lbl = ("n1 (1 PTRS port)" if ptrs_maxnrofports == 1
                       else "n2 (2 PTRS ports)" if ptrs_maxnrofports == 2
                       else f"maxNrofPorts={ptrs_maxnrofports}")
    _srs_ind_lbl = ("SRS res-set-ind field absent"
                    if srsindicatorfieldvalue == 0 else
                    f"SRS res-set-ind field present ({srsindicatorfieldvalue} bits)")
    if _tp_is_enabled:
        _ptrs_c = "transformPrecoder=enabled -> 0 bits (TS 38.212 \u00a77.3.1.1.2)"
    elif _tp_is_disabled and not ptrs_configured:
        _ptrs_c = ("PTRS-UplinkConfig not configured & transformPrecoder=disabled "
                   "-> 0 bits (TS 38.212 \u00a77.3.1.1.2)")
    elif isinstance(maxrankvalue, int) and maxrankvalue == 1:
        _ptrs_c = (f"maxRank=1{_ptrs_src} -> 0 bits "
                   f"(TS 38.212 \u00a77.3.1.1.2)")
    elif prtsdmrsfieldvalue == 2:
        _ptrs_c = (f"{_ptrs_ports_lbl}{_ptrs_src}, nrofSRS-Ports={antennaportsvalue}, "
                   f"{_srs_ind_lbl}, maxRank={maxrankvalue} (<=4) "
                   f"-> 2 bits (TS 38.212 \u00a77.3.1.1.2, Tables 7.3.1.1.2-25/26)")
    else:
        _unmet = []
        if ptrs_maxnrofports not in (1, 2):
            _unmet.append(f"maxNrofPorts={ptrs_maxnrofports} not n1/n2")
        if antennaportsvalue not in (2, 4, 8):
            _unmet.append(f"nrofSRS-Ports={antennaportsvalue} not in (2,4,8)")
        if not (isinstance(maxrankvalue, int) and maxrankvalue <= 4):
            _unmet.append(f"maxRank={maxrankvalue} not <=4")
        _ptrs_c = ("2-bit preconditions unmet (" + "; ".join(_unmet) + ") -> 0 bits "
                   "(TS 38.212 \u00a77.3.1.1.2)")

    # DMRS sequence initialization (DCI 0-1)
    _dmrs01_c = ("transformPrecoder=disabled -> 1 bit"
                 if dmrssequencefieldvalue else
                 "transformPrecoder=enabled -> 0 bits")

    # Beta offset indicator
    if _nrdc_scg:
        _beta_src = _ul_src_note
    elif _betaoffsets_from_reconfig:
        _beta_src = _ul_src_note if _ul_src_note else " [from rrcReconfiguration]"
    else:
        _beta_src = ""
    # Check whether betaOffsets semiStatic is the reason for 0 bits
    _beta_semistatic = any(
        re.search(r"\bbetaOffsets\s+semiStatic\b", rows[i])
        for i in range(rrclength)
    )
    if betaoffsets_configured:
        _beta_c = (f"betaOffsets=dynamic in pusch-Config{_beta_src} "
                   f"-> 2 bits (TS 38.212 Table 7.3.1.1.2-28)")
    elif _beta_semistatic:
        _beta_c = (f"betaOffsets=semiStatic (not dynamic){_beta_src} "
                   f"-> 0 bits (TS 38.212 Table 7.3.1.1.2-28)")
    else:
        _beta_c = (f"betaOffsets IE not configured in pusch-Config{_beta_src} "
                   f"-> 0 bits")

    # ------------------------------------------------------------------ #
    #  DCI Format 1_1 (DL)                                               #
    # ------------------------------------------------------------------ #
    fixedlength11 = 1 + 5 + 1 + 2 + 4 + 2 + 3 + 1
    modifiablelength11 = (checkvalue2(dlbwpfieldvalue) + checkvalue2(frdabitsdl) +
                          checkvalue2(tdrabitsdl) + checkvalue2(DLassignmentfieldvalue) +
                          checkvalue2(pdschtoharqtimingindfieldvalue) +
                          checkvalue2(antennaportsvaluefieldvalue) + checkvalue2(srsrequestfieldvalue) +
                          checkvalue2(vrbprbfieldvalue) + checkvalue2(prbbundlefieldvalue) +
                          checkvalue2(ratematchingindicatorsizefieldvalue) +
                          checkvalue2(zpcsirstriggerfieldvalue) +
                          checkvalue2(codeblockflushindicatorfieldvalue) +
                          checkvalue2(transmissionconfigurationfieldvalue) +
                          checkvalue2(cbgtransmissioninformationfieldvalue11))
    totallength11 = fixedlength11 + modifiablelength11 + pdcch_monitoring_adapt_bits

    fields11 = [
        ('Identifier for DCI formats',               1,                                       "Fixed 1 bit (TS 38.212 \u00a77.3.1.2.2)"),
        ('Carrier indicator',                         0,                                       "Cross-carrier scheduling not configured -> 0 bits"),
        ('Bandwidth part indicator',                  dlbwpfieldvalue,                         _dlbwp_c),
        ('Frequency domain resource assignment',      frdabitsdl,                              _frdl_c),
        ('Time domain resource assignment',           tdrabitsdl,                              _tdr_dl_c),
        ('VRB-to-PRB mapping',                        vrbprbfieldvalue,                        _vrb_c),
        ('PRB bundling size indicator',               prbbundlefieldvalue,                     _prb_c),
        ('Rate matching indicator',                   ratematchingindicatorsizefieldvalue,     _rm_c),
        ('ZP CSI-RS trigger',                         zpcsirstriggerfieldvalue,                _zp_c),
        ('Modulation and coding scheme (TB1)',         5,                                       "Fixed 5 bits (TS 38.212 \u00a77.3.1.2.2)"),
        ('New data indicator (TB1)',                  1,                                       "Fixed 1 bit"),
        ('Redundancy version (TB1)',                  2,                                       "Fixed 2 bits"),
        ('HARQ process number',                       4,                                       "Fixed 4 bits"),
        ('Downlink assignment index',                 DLassignmentfieldvalue,                  _dlai_c),
        ('TPC command for scheduled PUCCH',           2,                                       "Fixed 2 bits"),
        ('PUCCH resource indicator',                  3,                                       "Fixed 3 bits"),
        ('PDSCH-to-HARQ feedback timing indicator',  pdschtoharqtimingindfieldvalue,           _harqt_c),
        ('Antenna port(s)',                           antennaportsvaluefieldvalue,              _ap11_c),
        ('Transmission configuration indication',    transmissionconfigurationfieldvalue,      _tci_c),
        ('SRS request',                              srsrequestfieldvalue,                    _srsr_c),
        ('CBG transmission information (CBGTI)',      cbgtransmissioninformationfieldvalue11,  _cbgti11_c),
        ('CBG flushing out information (CBGFI)',      codeblockflushindicatorfieldvalue,        _cbgfi_c),
        ('DMRS sequence initialization',              1,                                       "Fixed 1 bit (TS 38.212 \u00a77.3.1.2.2)"),
        ('PDCCH monitoring adaptation indication',    pdcch_monitoring_adapt_bits,             _pdcch_mon_c),
    ]
    if _FORMAT == 'full':
        print_dci_table('Format 1_1 (PDSCH - Normal)', fields11)

    # DCI 1_1 - Conditional / Optional fields (TS 38.212 7.3.1.2.2)
    fields11_optional = [
        # After TPC / before PUCCH resource indicator
        ('Second TPC command for scheduled PUCCH',   0,
         "SecondTPCFieldDCI-1-1 not configured -> 0 bits"),
        # After PDSCH-to-HARQ feedback timing indicator
        ('One-shot HARQ-ACK request',                0,
         "pdsch-HARQ-ACK-OneShotFeedback-r16 / pdsch-HARQ-ACK-EnhType3ToAddModList not configured -> 0 bits"),
        ('Enhanced Type 3 codebook indicator',       0,
         "pdsch-HARQ-ACK-EnhType3DCI-Field not configured -> 0 bits"),
        ('PDSCH group index',                        0,
         "pdsch-HARQ-ACK-Codebook-r16=enhancedDynamic not configured -> 0 bits"),
        ('New feedback indicator',                   0,
         "pdsch-HARQ-ACK-Codebook-r16=enhancedDynamic not configured -> 0 bits"),
        ('Number of requested PDSCH group(s)',       0,
         "pdsch-HARQ-ACK-Codebook-r16=enhancedDynamic not configured -> 0 bits"),
        ('HARQ-ACK retransmission indicator',        0,
         "pdsch-HARQ-ACK-Retx not configured -> 0 bits"),
        # After SRS request
        ('SRS offset indicator',                     0,
         "AvailableSlotOffset not configured for any aperiodic SRS resource set -> 0 bits"),
        # After DMRS sequence initialization
        ('Priority indicator',                       0,
         "priorityIndicatorDCI-1-1 not configured -> 0 bits"),
        ('ChannelAccess-CPext',                      0,
         "channelAccessMode-r16 not configured (licensed spectrum) -> 0 bits"),
        ('Minimum scheduling offset indicator',      0,
         "minimumSchedulingOffsetK0 not configured -> 0 bits"),
        ('SCell dormancy indication',                0,
         "dormancyGroupWithinActiveTime not configured -> 0 bits"),
        ('PUCCH Cell indicator',                     0,
         "pucch-sSCellDyn not configured -> 0 bits"),
    ]
    if _FORMAT == 'full' and _SHOW_OPTIONAL:
        print_dci_table('Format 1_1 \u2013 Conditional/Optional Fields (TS 38.212 \u00a77.3.1.2.2)', fields11_optional)

    # ------------------------------------------------------------------ #
    #  DCI Format 0_1 (UL)                                               #
    # ------------------------------------------------------------------ #
    fixedlength01 = 1 + 5 + 1 + 2 + 4 + 2 + 1
    modifiablelength01 = (checkvalue2(ulsulfieldvalue) + checkvalue2(ulbwpfieldvalue) +
                          checkvalue2(frdabitsul) + checkvalue2(tdrabitsul) +
                          checkvalue2(dlassignment) + checkvalue2(precodingnumberoflayers) +
                          checkvalue2(antennaports01fieldvalue) + checkvalue2(srsrequestfieldvalue) +
                          checkvalue2(reporttriggersizevalue) + checkvalue2(prtsdmrsfieldvalue) +
                          checkvalue2(dmrssequencefieldvalue) + checkvalue2(ulhopping) +
                          checkvalue2(srsindicatorfieldvalue) + checkvalue2(betaoffsetfieldvalue) +
                          checkvalue2(maxcodeblockgroupspertransportblockvalue01))
    totallength01 = fixedlength01 + modifiablelength01 + pdcch_monitoring_adapt_bits + transform_prec_indicator_bits

    # Core DCI 0_1 fields (original modelled fields)
    fields01 = [
        ('Identifier for DCI formats',                      1,                                       "Fixed 1 bit (TS 38.212 \u00a77.3.1.1.2)"),
        ('Carrier indicator',                                0,                                       "Cross-carrier scheduling not configured -> 0 bits"),
        ('UL/SUL indicator',                                 ulsulfieldvalue,                         _sul_c),
        ('Bandwidth part indicator',                         ulbwpfieldvalue,                         _ulbwp_c),
        ('Frequency domain resource assignment',             frdabitsul,                              _frul_c),
        ('Time domain resource assignment',                  tdrabitsul,                              _tdr_ul_c),
        ('Frequency hopping flag',                           ulhopping,                               _fh_c),
        ('Modulation and coding scheme',                     5,                                       "Fixed 5 bits"),
        ('New data indicator',                               1,                                       "Fixed 1 bit"),
        ('Redundancy version',                               2,                                       "Fixed 2 bits"),
        ('HARQ process number',                              4,                                       "Fixed 4 bits"),
        ('1st downlink assignment index',                    dlassignment,                            _ulai_c),
        ('CBG transmission information (CBGTI)',             maxcodeblockgroupspertransportblockvalue01, _cbgti01_c),
        ('TPC command for scheduled PUSCH',                  2,                                       "Fixed 2 bits"),
        ('SRS resource indicator',                           srsindicatorfieldvalue,                  _srsi_c),
        ('Precoding information and number of layers',       precodingnumberoflayers,                 _pre_c),
        ('Antenna port(s)',                                  antennaports01fieldvalue,                _ap01_c),
        ('SRS request',                                      srsrequestfieldvalue,                    _srsr_c),
        ('CSI request',                                      reporttriggersizevalue,                  _csi_c),
        ('PTRS-DMRS association',                            prtsdmrsfieldvalue,                      _ptrs_c),
        ('Beta offset indicator',                            betaoffsetfieldvalue,                    _beta_c),
        ('DMRS sequence initialization',                     dmrssequencefieldvalue,                  _dmrs01_c),
        ('UL-SCH indicator',                                 1,                                       "Fixed 1 bit"),
        ('PDCCH monitoring adaptation indication',           pdcch_monitoring_adapt_bits,             _pdcch_mon_c),
        ('Transform precoder indication',                    transform_prec_indicator_bits,           _transform_prec_c),
    ]
    if _FORMAT == 'full':
        print_dci_table('Format 0_1 (PUSCH - Normal)', fields01)

    # DCI 0_1 - Conditional / Optional fields (TS 38.212 7.3.1.1.2)
    # These fields are present in the spec but evaluate to 0 bits for this
    # RRC configuration.  Shown separately so the core table stays clean.
    _srs_set_src = (" [from Reconfig]" if _srs_set_from_reconfig else
                    (" [from Setup]" if srs_codebook_set_count > 0 else ""))
    if srs_resource_set_indicator_bits == 2:
        _srs_set_c = (f"txConfig=codebook, {srs_codebook_set_count} SRS resource sets with "
                      f"usage=codebook{_srs_set_src} -> 2 bits (Table 7.3.1.1.2-36)")
    else:
        _srs_set_c = (f"{srs_codebook_set_count} SRS resource set(s) with usage=codebook"
                      f"{_srs_set_src}; need \u22652 for indicator -> 0 bits")

    fields01_optional = [
        ('2nd downlink assignment index',            0,
         "Enhanced dynamic codebook with 2 HARQ-ACK sub-codebooks not configured -> 0 bits"),
        ('3rd downlink assignment index',            0,
         "HARQ-ACK codebook for multicast (fdmed-ReceptionMulticast) not configured -> 0 bits"),
        ('Second TPC command for scheduled PUSCH',   0,
         "SecondTPCFieldDCI-0-1 not configured -> 0 bits"),
        ('SRS resource set indicator',               srs_resource_set_indicator_bits,
         _srs_set_c),
        ('Second SRS resource indicator',            0,
         "SRS resource set indicator absent (< 2 codebook SRS resource sets) -> 0 bits"),
        ('Second precoding information',             0,
         "SRS resource set indicator absent -> 0 bits"),
        ('SRS offset indicator',                     0,
         "AvailableSlotOffset not configured for any aperiodic SRS resource set -> 0 bits"),
        ('Second PTRS-DMRS association',             0,
         "SRS resource set indicator absent or maxRank \u22642 -> 0 bits"),
        ('ChannelAccess-CPext-CAPC',                 0,
         "channelAccessMode-r16 not configured (licensed spectrum) -> 0 bits"),
        ('Open-loop power control parameter set',    0,
         "p0-PUSCH-SetList not configured -> 0 bits"),
        ('Priority indicator',                       0,
         "priorityIndicatorDCI-0-1 not configured -> 0 bits"),
        ('Invalid symbol pattern indicator',         0,
         "invalidSymbolPatternIndicatorDCI-0-1 not configured -> 0 bits"),
        ('Minimum scheduling offset indicator',      0,
         "minimumSchedulingOffsetK2 not configured -> 0 bits"),
        ('SCell dormancy indication',                0,
         "dormancyGroupWithinActiveTime not configured -> 0 bits"),
        ('Sidelink assignment index',                0,
         "No SL configured grant or DCI format 3_0 monitoring -> 0 bits"),
    ]
    if _FORMAT == 'full' and _SHOW_OPTIONAL:
        print_dci_table('Format 0_1 \u2013 Conditional/Optional Fields (TS 38.212 \u00a77.3.1.1.2)', fields01_optional)

    # ------------------------------------------------------------------ #
    #  DCI Size Summary (all formats) - core scope:                      #
    #    * C-RNTI USS    (active dedicated BWP)                          #
    #    * C-RNTI CSS-3  (initial common BWP via ServingCellConfigCommon)#
    #  for fallback DCI 0_0 / 1_0 (TS 38.212 SS7.3.1.1.1, 7.3.1.2.1).    #
    #  Aligned-size rule per TS 38.212 S7.3.1.0 (max(0_0, 1_0)).         #
    # ------------------------------------------------------------------ #

    init_dl_lab, init_dl_scs, _init_dl_src = parse_initial_dl_bwp_lab_scs_prefer_reconfig()
    init_ul_lab, init_ul_scs, _init_ul_src = parse_initial_ul_bwp_lab_scs_prefer_reconfig()

    init_dlnrb = init_dlstartrb = None
    if init_dl_lab is not None:
        _res = getbwprbandstartrb(init_dl_lab)
        if _res is not None:
            init_dlnrb, init_dlstartrb = _res

    init_ulnrb = init_ulstartrb = None
    if init_ul_lab is not None:
        _res = getbwprbandstartrb(init_ul_lab)
        if _res is not None:
            init_ulnrb, init_ulstartrb = _res

    sul_configured = (ulsulfieldvalue == 1)

    # USS (active dedicated BWP) - reuse already-parsed dlnrb / ulnrb
    d00_uss_nat = dci00_size(ulnrb, sul_configured, in_uss=True)
    d10_uss_nat = dci10_size(dlnrb)
    d_uss_aligned = align_fallback(d00_uss_nat, d10_uss_nat)

    # CSS Type-3 (initial common BWP from ServingCellConfigCommon)
    d00_css_nat = dci00_size(init_ulnrb, sul_configured=False, in_uss=False)
    d10_css_nat = dci10_size(init_dlnrb)
    d_css_aligned = align_fallback(d00_css_nat, d10_css_nat)

    def _src(label, n, scs):
        if n is None:
            return f"N_RB unavailable ({label})"
        return f"N_RB={n} (from {label}; SCS=kHz{scs if scs is not None else '?'})"

    _dl_uss_src = "active dedicated downlinkBWP-ToAddModList"
    _ul_uss_src = "active dedicated uplinkBWP-ToAddModList"

    fb_summary = [
        ('DCI 0_0 - C-RNTI in USS (active dedicated UL BWP)',
         d_uss_aligned,
         f"{_src(_ul_uss_src, ulnrb, subcarrierspacingulvalue)}; "
         f"natural 0_0={d00_uss_nat} / 1_0={d10_uss_nat}; aligned=max -> {d_uss_aligned}"),

        ('DCI 1_0 - C-RNTI in USS (active dedicated DL BWP)',
         d_uss_aligned,
         f"{_src(_dl_uss_src, dlnrb, subcarrierspacingdlvalue)}; "
         f"natural 1_0={d10_uss_nat} / 0_0={d00_uss_nat}; aligned=max -> {d_uss_aligned}"),

        ('DCI 0_0 - C-RNTI in CSS Type-3 (initial UL BWP common)',
         d_css_aligned,
         f"{_src(_init_ul_src, init_ulnrb, init_ul_scs)}; "
         f"natural 0_0={d00_css_nat} / 1_0={d10_css_nat}; aligned=max -> {d_css_aligned}"),

        ('DCI 1_0 - C-RNTI in CSS Type-3 (initial DL BWP common)',
         d_css_aligned,
         f"{_src(_init_dl_src, init_dlnrb, init_dl_scs)}; "
         f"natural 1_0={d10_css_nat} / 0_0={d00_css_nat}; aligned=max -> {d_css_aligned}"),

        ('DCI 0_1 (PUSCH normal)',
         totallength01,
         f"From per-field calculation in Format 0_1 table above ({totallength01} bits)"),

        ('DCI 1_1 (PDSCH normal)',
         totallength11,
         f"From per-field calculation in Format 1_1 table above ({totallength11} bits)"),
    ]
    if _FORMAT != 'quiet':
        print_dci_table('Size Summary (all formats, aligned per TS 38.212 \u00a77.3.1.0)', fb_summary)

    # ------------------------------------------------------------------ #
    #  Compact cell-parameters + DCI sizes summary  (full + summary)     #
    # ------------------------------------------------------------------ #
    _scs_dl_str = (f"{subcarrierspacingdlvalue} kHz"
                   if subcarrierspacingdlvalue else "?")
    _scs_ul_str = (f"{subcarrierspacingulvalue} kHz"
                   if subcarrierspacingulvalue else "?")
    _pci_str = str(_pci) if _pci is not None else "N/A"
    _cell_id = parse_cell_identity_prefer_reconfig()
    _log_hdr = _parse_log_header_cell_fields()
    _phys_rrc = _cell_id.get("phys_cell_id")
    if _phys_rrc is not None and _pci is not None and _phys_rrc != _pci:
        _pci_display = f"{_pci} (RRC physCellId {_phys_rrc})"
    elif _phys_rrc is not None and _pci is None:
        _pci_display = str(_phys_rrc)
    else:
        _pci_display = _pci_str
    _band_str = f"n{_cell_id['band']}" if _cell_id.get("band") is not None else "?"
    _ssb_str = (str(_cell_id["ssb_arfcn"]) if _cell_id.get("ssb_arfcn") is not None
                else "?")
    _pointa_str = (str(_cell_id["point_a_arfcn"])
                   if _cell_id.get("point_a_arfcn") is not None else "?")
    _serv_str = (str(_cell_id["serv_cell_index"])
                 if _cell_id.get("serv_cell_index") is not None else "?")
    _nrdc_str = "yes" if _nrdc_scg else "no"
    _dl_lab_str = (str(dllocationandbandwidthvalue)
                   if dllocationandbandwidthvalue else "?")
    _ul_lab_str = (str(ullocationandbandwidthvalue)
                   if ullocationandbandwidthvalue else "?")
    _dl_start_str = str(dlstartrb) if dlnrb else "?"
    _ul_start_str = str(ulstartrb) if ulnrb else "?"

    if _FORMAT != 'quiet':
        print()
        print("  " + BOLD(MAGENTA("Cell parameters")))
        _row_identity = [
            ("PCI",           _pci_display),
            ("Band",          _band_str),
            ("SSB ARFCN",     _ssb_str),
            ("Point A ARFCN", _pointa_str),
            ("servCellIndex", _serv_str),
            ("NR-DC SCG",     _nrdc_str),
        ]
        if _log_hdr.get("ncgi"):
            _row_identity.append(("NCGI (log)", _log_hdr["ncgi"]))
        if _log_hdr.get("freq"):
            _row_identity.append(("Freq (log)", _log_hdr["freq"]))
        _row_bwp = [
            ("DL N_RB",          str(dlnrb) if dlnrb else "?"),
            ("DL start RB",      _dl_start_str),
            ("DL L&B",           _dl_lab_str),
            ("UL N_RB",          str(ulnrb) if ulnrb else "?"),
            ("UL start RB",      _ul_start_str),
            ("UL L&B",           _ul_lab_str),
        ]
        _row_config = [
            ("DL SCS",           _scs_dl_str),
            ("UL SCS",           _scs_ul_str),
            ("DL BWPs",          str(numberofdownlinkbwpvalue) if numberofdownlinkbwpvalue else "?"),
            ("UL BWPs",          str(numberofuplinkbwpvalue) if numberofuplinkbwpvalue else "?"),
            ("Active DL bwp-Id", _dl_anchor_id if _dl_anchor_id else "?"),
            ("Active UL bwp-Id", _ul_anchor_id if _ul_anchor_id else "?"),
        ]
        _print_cell_param_rows([_row_identity, _row_bwp, _row_config])
        print()
        print("  " + BOLD(MAGENTA("DCI sizes (core formats)")))
        _css_aln_disp = (
            (BOLD(GREEN(str(d_css_aligned))) if USE_COLOR else str(d_css_aligned))
            if d_css_aligned is not None
            else (
                DIM("N/A (initial BWP not in capture)")
                if USE_COLOR
                else "N/A (initial BWP not in capture)"
            )
        )
        _sz_pairs = [
            ("DCI 1_1 (PDSCH)",           BOLD(GREEN(str(totallength11))) if USE_COLOR else str(totallength11)),
            ("DCI 0_1 (PUSCH)",           BOLD(GREEN(str(totallength01))) if USE_COLOR else str(totallength01)),
            ("DCI 1_0 / 0_0 USS aligned", BOLD(GREEN(str(d_uss_aligned))) if USE_COLOR else str(d_uss_aligned)),
            ("DCI 1_0 / 0_0 CSS aligned", _css_aln_disp),
        ]
        print("  " + "   ".join(
            f"{DIM(k + ':') if USE_COLOR else k + ':'} {v}"
            for k, v in _sz_pairs
        ))
        if (frdabitsdl is not None and _fdr_win_max > frdabitsdl
                and _fdr_win_note):
            print()
            print("  " + DIM("FDRA (max in cell-group window vs active BWP): ")
                  + (f"{_fdr_win_max} bits vs {frdabitsdl} bits — see DCI 1_1 table comment."
                     if not USE_COLOR else
                     f"{BOLD(str(_fdr_win_max))} bits vs {frdabitsdl} bits — see DCI 1_1 table comment."))

    # ------------------------------------------------------------------ #
    #  Write Wireshark config files  (unless --no-config)                #
    # ------------------------------------------------------------------ #
    if not _NO_CONFIG:
        _cfg01, _cfg11 = _write_wireshark_config(
            filepath, _cell_label, _OUTPUT_DIR,
            ulsulfieldvalue, ulbwpfieldvalue, frdabitsul, tdrabitsul, ulhopping,
            dlassignment, srsindicatorfieldvalue, precodingnumberoflayers,
            antennaports01fieldvalue, srsrequestfieldvalue, reporttriggersizevalue,
            maxcodeblockgroupspertransportblockvalue01, prtsdmrsfieldvalue,
            betaoffsetfieldvalue, dmrssequencefieldvalue, totallength01,
            dlbwpfieldvalue, frdabitsdl, tdrabitsdl, vrbprbfieldvalue,
            prbbundlefieldvalue, ratematchingindicatorsizefieldvalue,
            zpcsirstriggerfieldvalue, DLassignmentfieldvalue,
            pdschtoharqtimingindfieldvalue, antennaportsvaluefieldvalue,
            transmissionconfigurationfieldvalue, srsrequestfieldvalue,
            cbgtransmissioninformationfieldvalue11, codeblockflushindicatorfieldvalue,
            totallength11,
            pdcch_monitoring_adapt_bits,
        )
        if _FORMAT == 'quiet':
            # Quiet mode: one terse confirmation line then stop
            print(f"Config written: {_cfg01}  |  {_cfg11}")
        else:
            print()
            print("  " + BOLD(MAGENTA("Config files written")))
            print(f"    {DIM('DCI 0_1:') if USE_COLOR else 'DCI 0_1:'} {_cfg01}")
            print(f"    {DIM('DCI 1_1:') if USE_COLOR else 'DCI 1_1:'} {_cfg11}")


def _launch_gui():
    """FR2 DCI Helper GUI (tkinter — small frozen footprint; no Qt).

    Opens when the tool is invoked without a positional file argument (or
    with --gui).  The Run button re-invokes this app as a subprocess and
    streams merged stdout/stderr.  Wireshark copy + backups match the Qt GUI.
    Settings: ~/.fr2_dci_helper.json (wireshark_dir).

    Optional Qt UI (source only, larger): run ``python fr2_qt_gui.py`` from
    this directory (requires ``pip install PySide6``). Do not import fr2_qt_gui
    from here so PyInstaller does not bundle Qt into the default EXE.
    """
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    import fr2_tk_gui  # noqa: PLC0415

    raise SystemExit(fr2_tk_gui.main())



if _DO_GUI:
    _launch_gui()
else:
    main()
