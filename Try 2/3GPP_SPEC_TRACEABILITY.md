# 3GPP specification traceability — FR2 DCI helper

This document maps **3GPP technical specification references cited in** [`FR2_dci_helper.py`](FR2_dci_helper.py) **to functions and `main()` behaviour**, so reviewers can explain what is *normatively grounded* versus *tool policy* or *presentation*.

A **Word** export of this page is kept alongside it as [`3GPP_SPEC_TRACEABILITY.docx`](3GPP_SPEC_TRACEABILITY.docx) (regenerate with `python Try 2/build_spec_traceability_docx.py` after editing the Markdown; requires **`python-docx`**).

**Companion docs:** high-level architecture and parsing flow — [`TOOL_ARCHITECTURE.md`](TOOL_ARCHITECTURE.md); agent-oriented function buckets — [`.cursor/skills/fr2-dci-helper-code-map/SKILL.md`](../.cursor/skills/fr2-dci-helper-code-map/SKILL.md).

---

## 1. Purpose and scope

| Item | Detail |
|------|--------|
| **What the tool consumes** | Plain-text RRC / log captures (`rows` of strings), not ASN.1 PER binaries. |
| **What the tool produces** | Bit-width estimates for **DCI 0_1**, **DCI 1_1**, and **aligned DCI 0_0 / 1_0** (USS/CSS-3 style); optional **Wireshark CSV** field-width files (`_write_wireshark_config`). |
| **How to read the tables below** | Each row ties a **citation as it appears in source** to **code**. Clause numbers can shift slightly between 3GPP releases; where the code pins a release (e.g. **38.331 V17**), that is stated. |
| **Not claimed** | Byte-exact encoder behaviour, ASN.1 value encodings, or compliance with every optional Rel-x feature unless explicitly referenced in code. |

---

## 2. Normative document roles (summary)

| 3GPP TS | Role in this tool |
|---------|-------------------|
| **TS 38.212** | DCI formats: field inventories, fixed widths, conditional/optional fields, alignment (`§7.3.1.0`), and many **Table 7.3.1.x** lookups for bit widths. |
| **TS 38.214** | PDSCH/PUSCH scheduling: **frequency-domain** (RBG / RIV / `dynamicSwitch`) and **time-domain** allocation list sizing (`ceil(log2(N))` when lists are configured; default tables when absent — see `tdrabits` docstring). R16 **TDA** override IEs under cited subclauses. |
| **TS 38.331** | RRC **configuration source**: BWP lists, `ServingCellConfigCommon`, `physicalCellGroupConfig`, PUSCH/PDSCH configs, etc. Structural resolution of **active dedicated BWP** (`§6.3.2` in code comment). |
| **TS 38.213** | Cited in `main()` comments together with 38.331 as **scheduling / cell-group** context (not every procedure step is implemented). |
| **TS 38.211** | Physical layer / DM-RS: cited in `_parse_physical_cell_id` for PCI-related note (`§7.4.1.1.1`). |

---

## 3. End-to-end flow (conceptual)

```mermaid
flowchart LR
  rrc[RRC_text_lines]
  scope[Scope_and_parsers_TS38_331_shaped]
  pure[Bit_width_functions_TS38_212_214]
  out[CLI_tables_and_Wireshark_CSV]

  rrc --> scope
  scope --> pure
  pure --> out
```

- **Scope / parsers:** NR-DC SCG detection, dedicated BWP list resolution, `numericalparser*` / `writtenparser*` / `doubleindexparser` / list counters — turn text into typed values (38.331-shaped IE names in patterns).
- **Pure width functions:** Map those values to integers using 38.212 / 38.214 rules cited in docstrings or `main()` comments.
- **Wireshark CSV:** Column layout matches a **dissector/tool convention**; not a 3GPP deliverable (see §8).

---

## 4. Traceability by specification

### 4.1 TS 38.212 — Physical layer multiplexing and channel coding (DCI)

| Citation (as in code) | Function(s) / location | How it is used |
|------------------------|---------------------------|----------------|
| **§7.3.1.0** | `align_fallback`, DCI size summary `print_dci_table` in `main()` | Aligned USS size for 0_0 vs 1_0: `max(d00, d10)` per code comment. |
| **§7.3.1.1.1** | `dci00_size` | Natural (pre-alignment) size of DCI format **0_0**. |
| **§7.3.1.2.1** | `dci10_size`; comment in `parse_pdsch_tda_r16_count` re fallback TDA | Natural size of DCI format **1_0**; cross-reference when R16 PDSCH TDA affects fallback behaviour. |
| **§7.3.1.1.2** | DCI 0_1 core field rows in `main()` (e.g. identifier MCS, …); `print_dci_table` optional block; Rel-18 transform precoder scan in `main()` | Format **0_1** field widths and user-visible comments; optional-field table header. |
| **§7.3.1.2.2** | DCI 1_1 core field rows in `main()`; `print_dci_table` optional block | Format **1_1** field widths and comments. |
| **Table 7.3.1.1.2-5** | `sizeofprecodingandnumberoflayers`; precoding / `_ap01_c` comments in `main()` (incl. “7.3.1.1.2 scenario 1”) | Precoding information and number of layers (DCI 0_1): table lookup and branches. |
| **§7.3.1.1.2** + **Tables 7.3.1.1.2-25 / -26** | `prtsdmrsfield`; PTRS-DMRS comment strings in `main()` | PTRS–DMRS association width (DCI 0_1). |
| **§7.3.1.1.2** (scenario text) | `_srs_c` style comments in `main()` | SRS request / related 0_1 commentary. |
| **§7.3.1.1.2** (docstring) | `count_codebook_srs_resource_sets_prefer_reconfig` | Documents when SRS resource set indicator is 2 bits (codebook SRS sets); feeds `srs_resource_set_indicator_bits` in `main()`. |
| **Table 7.3.1.1.2-28** | `parse_betaoffsets_prefer_reconfig` (docstring), `betaoffsetfield`, beta-offset comment strings | Beta offset indicator: 0 vs 2 bits from `betaOffsets` semi-static vs dynamic. |
| **Table 7.3.1.1.2-36** | Optional DCI 0_1 table row comment in `main()` (`_srs_set_c`) | SRS resource set indicator when ≥2 codebook SRS sets. |
| **Table 7.3.1.2.2-1** | `antennaportsfield`; antenna-port comment strings for DCI 1_1 | DL DMRS antenna port(s) field width vs `dmrs-Type` / `maxLength`. |
| **§7.3.1.1.2** / **§7.3.1.2.2** (Rel-16/17) | `main()`: `_pdcch_mon_adapt` regex scan | PDCCH monitoring adaptation indicator (0 or 1 bit) from SearchSpace / PDCCH-Config IE names. |
| **§7.3.1.1.2** (Rel-18) | `main()`: `_transform_prec_indicator` scan; `_tpi_c` string | Transform precoder indication for DCI 0_1 when `dynamicTransformPrecoderFieldPresenceDCI-0-1-r18` enabled. |
| **§7.3.1** (banner) | `SPEC_REF` string in `main()` | CLI banner: “TS 38.212 §7.3.1 + TS 38.331 V17 ServingCellConfigCommon”. |
| **38.212** (padding / monitored DCI) | `collect_max_fdr_bits_dci11_window` → `note` string only | **Advisory text** when max FDRA in window exceeds active BWP; not used to change core field math unless user compares totals manually. |

**Additional DCI 0_1 / 1_1 width helpers** (same format sections in 38.212; explicit clause only in comments where noted):  
`ulsulsize`, `bwpindsize`, `firstdlassignment`, `antennaports01`, `nsrsrequest`, `srsindicatorfield`, `dmrssequencefield`, `vrbprbfield`, `prbbundlefield`, `zpcsirstriggerfield`, `DLassignment`, `pdschtoharqtimingind`, `transmissionconfigurationfield`, `cbgtransmissioninformationfield11`, `ratematchingindicatorsizefield`, `codeblockflushindicatorfield`, `checkvalue` / `checkvalue2`, and the **modifiable length** sums in `main()`.

The [`FR2_dci_helper.py`](FR2_dci_helper.py) file header comments also cite **SS7.3.1.1.1** / **7.3.1.2.1** / **7.3.1.0** (alternate section notation for the same **§7.3.1.x** clauses) for **CSS Type-3** and aligned **DCI 0_0 / 1_0** sizing.

---

### 4.2 TS 38.214 — Physical layer procedures for data

| Citation (as in code) | Function(s) / location | How it is used |
|------------------------|---------------------------|----------------|
| **Table 5.1.2.2.1-1** | `parse_pdsch_ra_and_rbg_in_first_block` (docstring) | Maps `rbg-Size` **config1** / **config2** to nominal RBG divisor for DL type-0 FDRA. |
| **§5.1.2.1.1** | `parse_pdsch_tda_r16_count`; `main()` PDSCH TDA comment | R16 PDSCH time-domain IE: when configured, entry count can override legacy list counting for **DCI 1_1** TDA bits. |
| **§6.1.2.1.1** | `parse_pusch_tda_r16_dci01_count`; `main()` PUSCH TDA comment | R16 PUSCH time-domain IE for **DCI 0_1** TDA list. |
| **§5.1.2.1.1 / §6.1.2.1.1** | `main()` comment near PUSCH TDA display | Cross-links R16 override IEs for both directions. |
| **Table 6.1.2.1.1-1A** | PUSCH TDA comment string in `main()` (`_tdr_ul_c`) | Referenced in user-facing comment when R16 default table applies. |
| **38.214 / 38.212** (joint docstring) | `tdrabits` | When configured list present: `ceil(log2(N))`; when absent: **4 bits** default table (16 entries) per docstring. |

**Coupled to 38.214 without a repeated clause tag:**  
`getbwprbandstartrb`, `getnominalresourceblockgroup`, `calculatefrdabitsdl`, `calculatefrdabitsul`, `numberulhopping` — implement **resource assignment** widths used by DCI fields defined in 38.212.

---

### 4.3 TS 38.331 — RRC protocol

| Citation (as in code) | Function(s) / location | How it is used |
|------------------------|---------------------------|----------------|
| **§6.3.2** | `_resolve_active_dedicated_bwp_block_start`; `main()` anchor comment | Structural rule: active dedicated DL/UL BWP list entry vs `firstActive*DownlinkBWP-Id` / `UplinkBWP-Id`. |
| **V17 ServingCellConfigCommon** (file header + `SPEC_REF`) | `parse_initial_dl_bwp_lab_scs_prefer_reconfig`, `parse_initial_ul_bwp_lab_scs_prefer_reconfig`, `_parse_initial_bwp_lab_scs` | Initial BWP **locationAndBandwidth** and SCS for **DCI 0_0 / 1_0** CSS Type-3 style fallback sizing. |
| **(generic 38.331)** | `parse_*_prefer_reconfig` helpers, `writtenparser1` / `numericalparser1` patterns | Prefer `rrcReconfiguration` over setup when parsing scalars (PCI-adjacent helpers, DMRS type, max rank, beta offsets, PTRS, SRS sets, etc.). |

**NR-DC / cell-group (behaviour described in [`TOOL_ARCHITECTURE.md`](TOOL_ARCHITECTURE.md)):**  
`_find_nrdc_nrscg_start_index`, `_dai_lo` / `_dai_hi`, `writtenparser1(..., scan_from=_dai_lo)` for `pdsch-HARQ-ACK-Codebook` — **windowing** on text, motivated by MN vs SCG structure (see architecture doc, not a single 38.331 clause in code).

---

### 4.4 TS 38.213 — Physical layer procedures for control

| Citation (as in code) | Function(s) / location | How it is used |
|------------------------|---------------------------|----------------|
| **§12** (comment only) | `main()` comment with 38.331 §6.3.2 | **Context** for scheduling / cell-group anchors; no standalone 38.213 formula functions in this file. |

---

### 4.5 TS 38.211 — Physical channels and modulation

| Citation (as in code) | Function(s) / location | How it is used |
|------------------------|---------------------------|----------------|
| **§7.4.1.1.1** | `_parse_physical_cell_id` (comment) | Explains N_ID vs PCI when log header PCI differs from RRC `physCellId` (DM-RS / scrambling context). |

---

## 5. Wireshark output (non-normative)

| Artifact | Spec? | Notes |
|----------|-------|--------|
| `_write_wireshark_config` | **No** | CSV column ordering matches **tool / dissector** expectations; see code comments (e.g. Rel-18 transform precoder omitted from CSV because dissector lacks the field). |
| GUI copy to `%APPDATA%\Wireshark` | **No** | OS-level convenience; backups under `fr2_dci_helper_backups/` per [`TOOL_ARCHITECTURE.md`](TOOL_ARCHITECTURE.md). |

---

## 6. Tool policy vs single-clause trace (read carefully)

| Topic | Behaviour | Traceability |
|-------|-----------|--------------|
| **DAI (DCI 1_1)** | If `pdsch-HARQ-ACK-Codebook` is **dynamic** and an **`sCellToAddModList`** header exists in the **cell-group window** (SCG: from `nr-SCG` to EOF; MN: start of file to first `nr-SCG`), `DLassignment` returns **4** bits; else **2** bits with dynamic. | **`DLassignment`** implements a **simple rule** aligned with multicell dynamic codebook usage; see [`TOOL_ARCHITECTURE.md`](TOOL_ARCHITECTURE.md) §5. For a formal multi-step proof, consult **38.212** (DCI field) and **38.213** (HARQ-ACK codebook procedures) in your target release. |
| **Max FDRA window** | `collect_max_fdr_bits_dci11_window` may append a **note** when max FDRA in window exceeds active BWP FDRA. | **Advisory**; core table still uses active BWP `frdabitsdl` unless product rules change. |

---

## 7. Maintenance

When you add or change a **normative citation** in [`FR2_dci_helper.py`](FR2_dci_helper.py) (`Per TS …`, `Table 7…`, banner text):

1. Add or update the matching row in **§4** of this file.  
2. Regenerate **`3GPP_SPEC_TRACEABILITY.docx`** with `python Try 2/build_spec_traceability_docx.py` (install `python-docx` if needed).  
3. Update [`.cursor/skills/fr2-dci-helper-code-map/SKILL.md`](../.cursor/skills/fr2-dci-helper-code-map/SKILL.md) if a new **representative function** should appear in a bucket.  
4. Update [`TOOL_ARCHITECTURE.md`](TOOL_ARCHITECTURE.md) if behaviour or windows change.

---

## 8. Document history

| Date | Change |
|------|--------|
| Initial | Created `3GPP_SPEC_TRACEABILITY.md` from citations in `FR2_dci_helper.py` (grep inventory) plus policy notes from `TOOL_ARCHITECTURE.md`. |
| Follow-up | Added `3GPP_SPEC_TRACEABILITY.docx` (Word) generated from this file via `build_spec_traceability_docx.py` (`python-docx`). |
