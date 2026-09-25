# Enterprise PII Redaction & Document Reconstruction Engine

An enterprise-grade, privacy-preserving PII redaction and essence-preserving pseudonymization tool built for complex legal, corporate, and financial documents (such as IPO **Red Herring Prospectuses**).

---

## 1. Approach Overview

Rather than relying on a single fallible mechanism (such as pure regex, zero-shot NER, or non-deterministic LLMs), this system employs a **Hybrid Multi-Engine Pipeline**:

1. **Algorithmic Regex Engine**: Detects structured identifiers paired strictly with mathematical checksum validators:
   - Credit Cards (`Luhn` algorithm validation)
   - Phone Numbers (E.164 + Indian STD dialing plans)
   - Emails (RFC 5322 syntax validation)
   - IP Addresses (IPv4 / IPv6 validation)
   - Tax IDs & National IDs (Indian PAN checksum, US SSN format, DIN, CIN, GSTIN)
2. **Contextual Address Detector**: Identifies multi-line registered and physical office addresses using PIN-code anchoring, backward street-cue scanning, and Indian geographic lexicons.
3. **Neural Span Extractor (GLiNER)**: Uses bidirectional transformer span extraction (`urchade/gliner_multi_pii-v1`) with windowed sentence segmentation and honorific normalization for open-vocabulary detection of `PERSON`, `ORGANIZATION`, and `ADDRESS`.
4. **Context Proximity & Non-PII Filter**: Analyzes surrounding text windows to disambiguate true `DATE_OF_BIRTH` from statutory filing dates (`"dated"`, `"FY 2025"`, `"issue date"`), and suppresses false positives on capital market terms (`"SEBI"`, `"RBI"`, `"BSE"`, `"Companies Act"`, `"Anchor Investors"`, `"UPI"`).
5. **Dynamic Document Entity Registry**: Ephemeral in-memory symbol table that catalogs high-confidence promoter/director seeds and propagates aliases across all 800+ paragraphs.
6. **Essence-Preserving Pseudonymization**: Replaces PII with realistic synthetic alternatives while strictly preserving typographical casing (ALL-CAPS stays ALL-CAPS), corporate legal forms (`Private Limited` $\rightarrow$ `Private Limited`, `LLP` $\rightarrow$ `LLP`), and narrative flow.
7. **DOCX Run-Level Reconstructor**: Re-injects synthetic spans directly into python-docx XML runs from right to left, preserving fonts, styles, tables, and italicized bottom-of-page legal notes.

---

## 2. Tradeoffs & False Positive / Negative Handling

- **Order / Ticket Numbers vs. PII**: Internal tracking IDs (`Order #`, `Ticket #`, invoice amounts like `₹4,500.00 million`) are treated as non-PII operational business data. Pre-regex negative lookbehinds ensure financial figures are not misflagged as phone numbers or tax IDs.
- **Regulatory & Statutory False Positives**: Off-the-shelf NER aggressively flags `"Red Herring Prospectus"`, `"Book Running Lead Managers"`, and statutory bodies (`"SEBI"`, `"RBI"`, `"MCA"`) as organizations. Our system incorporates strict regulatory suppression dictionaries and syntactic filters to prevent document corruption.
- **Precision vs. Recall in DOB**: Strict proximity scoring ensures only dates anchored by birth cues (`"date of birth"`, `"aged"`, `"born on"`) are redacted, eliminating false positives on legal filing and board meeting dates.

---

## 3. Evaluation Summary

Evaluated using **Strict Span Matching** (requiring exact start, exact end, and matching entity class):

| Metric | Synthetic Enterprise Benchmark (9 Classes) | Real-World Prospectus Gold Annotations | Microsoft Presidio Baseline | Standalone GLiNER Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **Strict Precision** | **100.0%** | **94.4%** | 48.8% | 38.1% |
| **Strict Recall** | **100.0%** | **100.0%** (17/17) | 71.4% | 28.6% |
| **Strict Micro F1** | **100.0%** | **97.1%** | 58.0% | 32.6% |
| **Diagnostic Accuracy**| **100.0%** | **99.3%** | 87.9% | 86.2% |

---

## 4. How to Extend to a New PII Type

Adding a new PII class (e.g., **Aadhaar Number** or **Passport Number**) requires 4 modular steps:
1. **Validator**: In `src/detectors/regex/validators.py`, implement format validation (e.g., Verhoeff checksum algorithm for Aadhaar).
2. **Recognizer**: In `src/detectors/regex/recognizers.py`, add the compiled regex pattern to `RegexDetector.detect()`.
3. **Priority**: In `src/resolution/conflict_resolver.py`, assign its precedence rank in `TYPE_PRIORITY`.
4. **Synthesizer**: In `src/pseudonymization/synthesizer.py`, define its synthetic replacement rule in `_generate_typed_fake()`.

---

## 5. Quickstart & Usage

### Installation
```bash
pip install -r requirements.txt
```

### Run Redaction on DOCX
```bash
python scripts/run_redaction.py --input "Red Herring Prospectus.docx" --output "artifacts/output_docs/Redacted_Red_Herring_Prospectus.docx"
```

### Run Web Application
```bash
streamlit run app.py
```

### Run Tests & Verification
```bash
python -m pytest tests/ -v
```
