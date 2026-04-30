# Helper script to parse RRC file and extract relevant information
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

USE_COLOR = sys.stdout.isatty()

def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if USE_COLOR else s

BOLD    = lambda s: _c("1",  s)
DIM     = lambda s: _c("2",  s)
CYAN    = lambda s: _c("36", s)
GREEN   = lambda s: _c("32", s)
YELLOW  = lambda s: _c("33", s)
MAGENTA = lambda s: _c("35", s)

filepath = input(
    r"Path to RRC file (e.g C:\Users\sankdesh\Downloads\NSA_FR2_1.txt) :"
)
f = open(filepath, 'r')

# Returns a file lines as a list where lines are list items
rows = f.readlines()
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
puschTimeAllocationList = 'pusch-TimeDomainAllocationList'
pdschTimeAllocationList = 'pdsch-TimeDomainAllocationList'
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


def _find_reconfig_start_index():
    """Return (start_index, both_present).
    If the capture contains BOTH rrcSetup and rrcReconfiguration messages, the
    start_index is the line where the first rrcReconfiguration appears, so that
    downstream parsing ignores any stale values from the earlier rrcSetup block.
    Otherwise start_index is 0 (search the whole file).
    """
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
    """
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

    Per TS 38.212 §7.3.1.1.2: SRS resource set indicator is 2 bits when
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


# Calculate size of time domain allocation field DCI 0-1
def tdrabits(timedomainallocationlistvalue):
    timedomainallocationlistvalue = int(timedomainallocationlistvalue)
    if timedomainallocationlistvalue is None:
        value = math.log(16, 2)
        value = int(value)
        return value
    else:
        value = math.ceil(math.log(timedomainallocationlistvalue, 2))
        value = int(value)
        return value


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
    value = math.ceil(math.log(dldatatoulackvalue, 2))
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


# Check if value is None
def checkvalue2(value):
    if value is None:
        value = 0
        value = int(value)
        return value
    else:
        return value


def main():
    nrdc_scg_start = _find_nrdc_nrscg_start_index()
    _nrdc_scg = (nrdc_scg_start >= 0)
    _reconfig_start, _both_msgs = _find_reconfig_start_index()
    # For DL FDRA parameters: prefer Reconfiguration over Setup when both are present.
    # NR-DC SCG scope takes priority; otherwise use reconfig anchor when both messages present.
    _dl_scope = nrdc_scg_start if _nrdc_scg else (_reconfig_start if _both_msgs else 0)

    dllocationandbandwidthvalue = numericalparser1(BWPDownlink, locationAndBandwidth, 0, scan_from=_dl_scope)
    if dllocationandbandwidthvalue == 0:
        raw = input(
            "DL locationAndBandwidth not found in file (needed for frequency-domain bit-width).\n"
            "Enter value (e.g. 17875 for FR2 n258 100MHz), or press Enter to keep 0: "
        ).strip()
        if raw.isdigit():
            dllocationandbandwidthvalue = int(raw)

    _ul_scope = _reconfig_start if (_both_msgs and not _nrdc_scg) else 0
    ullocationandbandwidthvalue = numericalparser1(BWPUplink, locationAndBandwidth, 0, scan_from=_ul_scope)
    if ullocationandbandwidthvalue == 0:
        raw = input(
            "UL locationAndBandwidth not found in file.\n"
            "Enter value (or press Enter to keep 0): "
        ).strip()
        if raw.isdigit():
            ullocationandbandwidthvalue = int(raw)
    subcarrierspacingdlvalue = numericalparser1(BWPDownlink, subcarrierSpacing, 0, scan_from=_dl_scope)
    subcarrierspacingulvalue = numericalparser1(BWPUplink, subcarrierSpacing, 0, scan_from=_ul_scope)
    pdschrbgsizevalue = doubleindexparser(pdschConfig, puschConfigC, Rbgsize, scan_from=_dl_scope)
    puschrbgsizevalue = numericalparser1(puschConfig, Rbgsize, 1, scan_from=_ul_scope)
    dlresourceallocationvalue = writtenparser1(pdschConfig, dynamicSwitch, resourceAllocationType0, resourceAllocationType1, 'tyhja', None, scan_from=_dl_scope)
    ulresourceallocationvalue = writtenparser1(puschConfig, dynamicSwitch, resourceAllocationType0, resourceAllocationType1, 'tyhja', None, scan_from=_ul_scope)
    pdschtimedomainallocationlistvalue = doublenumericalparser(
        pdschConfig, pdschTimeAllocationList1, pdschTimeAllocationList, None,
        scan_from=_dl_scope)
    if _nrdc_scg:
        puschtimedomainallocationlistvalue = doublenumericalparser(
            puschConfig, puschTimeAllocationList1, puschTimeAllocationList,
            None, scan_from=nrdc_scg_start)
    elif _both_msgs:
        puschtimedomainallocationlistvalue = doublenumericalparser(
            puschConfig, puschTimeAllocationList1, puschTimeAllocationList,
            None, scan_from=_reconfig_start)
    else:
        puschtimedomainallocationlistvalue = doublenumericalparser(
            puschConfig, puschTimeAllocationList1, puschTimeAllocationList, None)
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
    pdschharqackcodebookvalue = writtenparser1(physicalcellgroupconfig, semistatic, dynamic, 'tyhja', 'tyhja', dynamic)
    prbbundlingvalue = writtenparser1(prbbundlingtype, dynamic, static, 'tyhja', 'tyhja', None)
    ratematchpatterngroup1value = writtenparser2(ratematch1, None)
    ratematchpatterngroup2value = writtenparser2(ratematch2, None)
    zpcsirstriggervalue = numericalparser2(zpcsiresresourcesetstoaddmodlist, 0)
    servingcellvalue = writtenparser2(scelltoaddmodlist, 1)
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

    # ------------------------------------------------------------------ #
    #  Standard reference banner                                          #
    # ------------------------------------------------------------------ #
    SPEC_REF  = "3GPP TS 38.212 \u00a77.3.1"
    INPUT_SRC = "Input: RRC text file (.txt)"
    banner_inner = f"  {SPEC_REF}    {INPUT_SRC}  "
    banner_w = max(len(banner_inner), 74)
    banner_inner = banner_inner.ljust(banner_w)
    print()
    print(CYAN("\u2554" + "\u2550" * banner_w + "\u2557"))
    print(CYAN("\u2551") + BOLD(CYAN(banner_inner)) + CYAN("\u2551"))
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

        for idx, (name, bits, comment) in enumerate(fields, start=1):
            b_str = "?" if bits is None else str(bits)
            is_zero = (bits == 0)
            comment_lines = _wrap(comment, cmt_w)

            num_cell   = f"{idx}"
            bits_color = (DIM if is_zero else (YELLOW if bits is None else GREEN))
            name_color = (DIM if is_zero else BOLD)

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

    # Bandwidth part indicator
    _dlbwp_c = (f"downlinkBWP-ToAddModList: {numberofdownlinkbwpvalue} BWP(s) "
                f"-> ceil(log2({numberofdownlinkbwpvalue}+1)) = {dlbwpfieldvalue} bit(s)")
    _ulbwp_c = (f"uplinkBWP-ToAddModList: {numberofuplinkbwpvalue} BWP(s) "
                f"-> ceil(log2({numberofuplinkbwpvalue}+1)) = {ulbwpfieldvalue} bit(s)")

    # Frequency domain resource assignment
    _frdl_src = " [from mrdc-SecondaryCellGroup nr-SCG]" if _nrdc_scg else ""
    if dlresourceallocationvalue == resourceAllocationType0:
        _frdl_c = (f"RA type0 (RBG){_frdl_src}: nrb={dlnrb}, nominalRBG={dlnominalrbg} "
                   f"-> ceil({dlnrb}/{dlnominalrbg}) = {frdabitsdl} bits")
    elif dlresourceallocationvalue == resourceAllocationType1:
        _frdl_c = (f"RA type1 (RIV){_frdl_src}: nrb={dlnrb} "
                   f"-> ceil(log2({dlnrb}x{dlnrb+1}/2)) = {frdabitsdl} bits")
    elif dlresourceallocationvalue == dynamicSwitch:
        _frdl_c = f"RA dynamic{_frdl_src}: max(type0,type1)+1 = {frdabitsdl} bits"
    else:
        _frdl_c = f"resourceAllocation not found in pdsch-Config{_frdl_src} -> None"

    if frequencyhoppingoffsetlistsvalue in (2, 4):
        _frul_c = (f"Freq hopping ({frequencyhoppingoffsetlistsvalue} offsets): "
                   f"ulnrf1-{frequencyhoppingoffsetlistsvalue} = {frdabitsul} bits")
    elif ulresourceallocationvalue == resourceAllocationType1:
        _frul_c = (f"RA type1 (RIV): nrb={ulnrb} "
                   f"-> ceil(log2({ulnrb}x{ulnrb+1}/2)) = {frdabitsul} bits")
    elif ulresourceallocationvalue == resourceAllocationType0:
        _frul_c = (f"RA type0 (RBG): nrb={ulnrb}, nominalRBG={ulnominalrbg} "
                   f"-> ceil({ulnrb}/{ulnominalrbg}) = {frdabitsul} bits")
    elif ulresourceallocationvalue == dynamicSwitch:
        _frul_c = f"RA dynamic: max(type0,type1)+1 = {frdabitsul} bits"
    else:
        _frul_c = "resourceAllocation not found in pusch-Config -> None"

    # Time domain resource assignment
    _tdr_dl_c = (f"pdsch-TimeDomainAllocationList: {pdschtimedomainallocationlistvalue} entries "
                 f"-> ceil(log2({pdschtimedomainallocationlistvalue})) = {tdrabitsdl} bits")
    _tdr_ul_src = " [from mrdc-SecondaryCellGroup nr-SCG]" if _nrdc_scg else ""
    _tdr_ul_c = (f"pusch-TimeDomainAllocationList{_tdr_ul_src}: "
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
    _harq_src = ("parsed from physicalCellGroupConfig"
                 if any('physicalCellGroupConfig' in r for r in rows)
                 else "physicalCellGroupConfig absent (delta reconfig) -> defaulted to dynamic")
    if DLassignmentfieldvalue == 4:
        _dlai_c = f"pdschHARQ-ACK-Codebook=dynamic + SCells configured -> 4 bits [{_harq_src}]"
    elif DLassignmentfieldvalue == 2:
        _dlai_c = f"pdschHARQ-ACK-Codebook=dynamic, single serving cell -> 2 bits [{_harq_src}]"
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

    _ptrs_src = " [from rrcReconfiguration]" if _ptrs_from_reconfig else ""
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
        _beta_src = " [from mrdc-SecondaryCellGroup nr-SCG]"
    elif _betaoffsets_from_reconfig:
        _beta_src = " [from rrcReconfiguration]"
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
    totallength11 = fixedlength11 + modifiablelength11

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
    ]
    print_dci_table('Format 1_1 (PDSCH - Normal)', fields11)

    # ── DCI 1_1 – Conditional / Optional fields (TS 38.212 §7.3.1.2.2) ──────
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
        ('PDCCH monitoring adaptation indication',   0,
         "pdcch-SkippingDurationList / searchSpaceGroupIdList-r17 not configured -> 0 bits"),
        ('PUCCH Cell indicator',                     0,
         "pucch-sSCellDyn not configured -> 0 bits"),
    ]
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
    totallength01 = fixedlength01 + modifiablelength01

    # ── Core DCI 0_1 fields (original modelled fields) ──────────────────────
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
    ]
    print_dci_table('Format 0_1 (PUSCH - Normal)', fields01)

    # ── DCI 0_1 – Conditional / Optional fields (TS 38.212 \u00a77.3.1.1.2) ────
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
        ('PDCCH monitoring adaptation indication',   0,
         "pdcch-SkippingDurationList / searchSpaceGroupIdList-r17 not configured -> 0 bits"),
    ]
    print_dci_table('Format 0_1 \u2013 Conditional/Optional Fields (TS 38.212 \u00a77.3.1.1.2)', fields01_optional)

main()
