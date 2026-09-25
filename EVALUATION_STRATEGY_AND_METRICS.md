# Enterprise PII Detection, Pseudonymization, and Document Reconstruction
## Comprehensive Evaluation Strategy, Benchmark Metrics, & Baseline Comparison Report

**Author**: Devanshi Jain  
**Assignment**: Enterprise Data - PII Redaction Tool  
**Benchmark Target**: SEBI Red Herring Prospectus (RHP) & High-Stakes Financial Documents  
**Status**: Verified & Reproducible  

---

## 1. Executive Summary & Evaluation Philosophy

In corporate legal and financial underwriting—specifically for Initial Public Offering (IPO) prospectuses filed under the Securities and Exchange Board of India (SEBI) ICDR Regulations—evaluating PII detection cannot be treated as a standard generic NLP classification task. Document redaction in capital market prospectuses carries asymmetric risk on two opposite fronts:

1. **Under-Redaction Risk (False Negatives / Data Leaks)**:
   Failing to redact personal identifiers (promoter names, residential addresses, personal phone numbers, emails, Director Identification Numbers [DIN], Permanent Account Numbers [PAN]) constitutes a direct breach of statutory data privacy mandates (such as the Digital Personal Data Protection Act / GDPR), exposing the issuer, merchant bankers, and underwriters to severe regulatory sanctions.
2. **Over-Redaction Risk (False Positives / Document Corruption)**:
   Naively redacting statutory, capital market, or procedural terms (such as *"Red Herring Prospectus"*, *"Book Running Lead Managers"*, *"Anchor Investors"*, *"Unified Payments Interface [UPI]"*, *"Companies Act, 2013"*, *"SEBI"*, *"RBI"*, or *"Board of Directors"*) destroys the legal integrity, statutory validity, and grammatical narrative of the offering circular, rendering it unreadable gibberish.

### The Class Imbalance Problem: Why Accuracy Alone Is Flawed
In an 800+ paragraph legal prospectus, true PII tokens account for **less than 1.5%** of the total document vocabulary. Consequently, a degenerate baseline model that trivially predicts "Non-PII" for every token achieves an apparent accuracy of **>98.5%** while delivering **0.0% Recall**, completely failing its privacy mandate. 

> **Core Evaluation Axiom**: Accuracy is heavily distorted by extreme negative class imbalance (98.5% negative tokens). **Strict Span Precision, Recall, Micro F1, and Macro F1** are the authoritative statistical measures of real-world privacy protection and legal compliance.

---

## 2. Mathematical Metrics & Evaluation Protocols

Every candidate entity predicted by the pipeline is subjected to exact mathematical comparison against held-out ground truth annotations. An entity prediction is defined as a tuple:
$$\text{Entity} = (s, e, l, \tau) \quad \text{where } s=\text{start offset}, e=\text{end offset}, l=\text{class label}, \tau=\text{text}$$

### 2.1 Strict Span Matching Criteria
A predicted entity is classified as a **True Positive (TP)** if and only if its character boundaries and entity classification match the ground truth annotation exactly:
$$\text{Match} \iff (s_{\text{pred}} = s_{\text{gold}}) \;\land\; (e_{\text{pred}} = e_{\text{gold}}) \;\land\; (l_{\text{pred}} = l_{\text{gold}})$$

Any boundary discrepancy (even by a single whitespace or punctuation mark) or label mismatch is penalized as **both a False Positive** (for the candidate) and a **False Negative** (for the ground truth entity).

### 2.2 Metric Formulations

- **Strict Precision ($P$)**:
  $$P = \frac{TP}{TP + FP}$$
  *Measures the proportion of detected spans that were genuine PII. Directly quantifies resistance against false alarms and corporate term scrambling.*

- **Strict Recall ($R$)**:
  $$R = \frac{TP}{TP + FN}$$
  *Measures the proportion of actual PII instances successfully detected. Directly quantifies resistance against private data leakage.*

- **Strict Micro F1**:
  $$\text{Micro F1} = \frac{2 \cdot P \cdot R}{P + R} = \frac{2 \cdot \sum TP}{2 \cdot \sum TP + \sum FP + \sum FN}$$
  *Harmonic mean of aggregate global Precision and Recall across all classes combined. Represents overall system operating safety.*

- **Strict Macro F1**:
  $$\text{Macro F1} = \frac{1}{K} \sum_{k=1}^K F1_k$$
  *Unweighted arithmetic average of F1 scores across all $K$ classes. Ensures under-represented classes (e.g. Credit Card, DOB) are weighted equally with dominant classes (e.g. Person, Organization).*

- **Relaxed Span F1**:
  *Allows boundary-tolerant matching where Jaccard token overlap $\frac{|\text{pred} \cap \text{gold}|}{|\text{pred} \cup \text{gold}|} \ge 0.5$ with identical class label. Distinguishes minor edge misalignment from a total detection miss.*

- **Token Diagnostic Accuracy**:
  $$\text{Accuracy} = \frac{\text{Tokens Correctly Classified (PII or Non-PII)}}{\text{Total Document Tokens}}$$

---

## 3. Benchmark Datasets & Testing Methodology

The redaction engine was evaluated on two distinct, frozen test suites designed to probe both structured format validation and multi-paragraph contextual narrative flow:

1. **Synthetic Enterprise Benchmark (`evaluation/data/synthetic_benchmark.jsonl`)**:
   - 15 multi-class test scenarios covering all 9 required PII types: Full Names, Email Addresses, Phone Numbers, Company Names, Physical Addresses, Social Security Numbers (US SSN, Indian PAN, DIN, CIN, GSTIN), Credit Card Numbers, Dates of Birth, and IP Addresses.
   - Crucially incorporates adversarial **hard negatives**:
     - *Order & Ticket Numbers*: `Ticket #492819`, `Order No. 99482910`
     - *Financial Values & Currencies*: `₹4,500.00 million`
     - *Statutory Corporate Filings*: `CIN: U29299PN1989PLC054652`, `Companies Act, 2013`
     - *Regulatory Authorities*: `SEBI`, `Reserve Bank of India`, `Board of Directors`
2. **Real-World Held-Out Prospectus Annotations (`evaluation/data/gold_prospectus.jsonl`)**:
   - Extracted directly from the primary benchmark document (`Red Herring Prospectus.docx`). Covers 8 dense, multi-page excerpts:
     - Registered and corporate offices with complex Indian industrial layout (`MIDC`, `Taluka Khed`, `Chakan`, `Parel`, `Pune`, `Mumbai`)
     - Promoter shareholding tables with multiple family members and promoter-group corporate entities
     - Senior Management and Key Managerial Personnel (KMP) statutory disclosures
     - Regulatory disclaimers explicitly citing SEBI ICDR Regulations and Companies Act provisions

---

## 4. Quantitative Performance Results

### Table 1: Synthetic Enterprise Benchmark Results (All 9 PII Classes)

| Entity Class | Ground Truth Count | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Precision | Recall | Strict F1 | Relaxed F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ADDRESS** | 3 | 3 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **CREDIT_CARD** | 1 | 1 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **DATE_OF_BIRTH** | 1 | 1 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **EMAIL** | 4 | 4 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **IP_ADDRESS** | 3 | 3 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **ORGANIZATION** | 2 | 2 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **PERSON** | 9 | 9 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **PHONE** | 3 | 3 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **SSN_TAX_ID** | 2 | 2 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** | 100.0% |
| **GLOBAL TOTAL** | **28** | **28** | **0** | **0** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |

- **Strict Micro Precision**: **100.00%**
- **Strict Micro Recall**: **100.00%**
- **Strict Micro F1**: **100.00%**
- **Strict Macro F1**: **100.00%**
- **Diagnostic Token Accuracy**: **100.00%**

---

### Table 2: Held-Out Prospectus Gold Annotations (Real RHP Excerpts)

| Metric | Score | Performance Summary |
| :--- | :---: | :--- |
| **Strict Precision** | **94.44%** | 18 detected spans; 17 true positives, 1 safe boundary expansion. |
| **Strict Recall** | **100.00%** | **17 out of 17** true prospectus entities captured without omission. |
| **Strict Micro F1** | **97.14%** | Optimal balance between thorough PII detection and zero leakage. |
| **Strict Macro F1** | **95.00%** | Consistent performance across Person, Organization, Phone, and Address. |
| **Diagnostic Accuracy**| **99.34%** | Calculated across >1,200 real document words and punctuation tokens. |

---

## 5. Head-to-Head Comparison with Industry Baselines

We evaluated leading open-source enterprise PII systems against our hybrid solution on the **exact same frozen benchmark** (`evaluation/data/synthetic_benchmark.jsonl`):

| Architecture / System | Strict Precision | Strict Recall | Strict Micro F1 | Strict Macro F1 | Accuracy | TP | FP | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Microsoft Presidio (`en_core_web_lg`)** | 48.8% | 71.4% | **58.0%** | 53.8% | 87.9% | 20 | 21 | 8 |
| **Standalone GLiNER Transformer** | 38.1% | 28.6% | **32.6%** | 21.4% | 86.2% | 8 | 13 | 20 |
| **Our Hybrid Production Pipeline** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **28** | **0** | **0** |

### In-Depth Failure Mode & Tradeoff Analysis:

1. **Microsoft Presidio Failure Modes (Strict F1: 58.0% | 21 False Positives)**:
   - *Semantic Confusion*: Presidio's underlying spaCy large model lacks domain awareness for financial filings. It incorrectly flagged the Indian PAN `AABPH1234Q` and invoice amounts as date/phone entities.
   - *IP Address Misclassification*: Presidio misclassified raw IP addresses as international phone numbers, producing overlapping contradictory spans.
   - *False Alarms on Statutory Acts*: Presidio flagged `Companies Act, 2013` and `Board of Directors` as Organizations, corrupting the legal prose of the document.
2. **Standalone GLiNER Failure Modes (Strict F1: 32.6% | 20 False Negatives)**:
   - *Zero Algorithmic Grounding*: Pure neural span extractors have no capacity to execute Luhn checksums on credit cards, validate IPv4 subnet ranges, or verify telephone STD area codes, resulting in complete recall collapse on technical PII.
   - *Document Header False Positives*: Without proximity scoring, GLiNER flagged document section headers like `RED HERRING PROSPECTUS` as organizational entities, causing severe document scrambling.
3. **Why Our Hybrid Production Pipeline Outperforms (+42.0% F1 vs Presidio, +67.4% vs GLiNER)**:
   - By enforcing strict algorithmic validators for structured formats, using GLiNER only for named entities, filtering statutory terms via proximity scoring, and resolving overlaps via deterministic Non-Maximum Suppression (NMS), our system simultaneously achieves **100.0% Precision (0 false positives)** and **100.0% Recall (0 leaks)**.

---

## 6. Component-by-Component Ablation Study

To mathematically quantify the marginal utility of each architectural module, we executed an ablation experiment across 6 incremental configurations on the identical frozen benchmark:

| # | Configuration | Strict Precision | Strict Recall | Strict Micro F1 | Strict Macro F1 | Accuracy |
| :- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | **Regex Detectors Only** | 100.0% | 46.4% | 63.4% | 55.6% | 93.8% |
| 2 | **GLiNER Neural Only** | 92.3% | 42.9% | 58.5% | 33.3% | 92.9% |
| 3 | **Regex + GLiNER Combined** | 100.0% | 89.3% | 94.3% | 88.9% | 98.8% |
| 4 | **Regex + GLiNER + Context Proximity Scorer** | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 5 | **Regex + GLiNER + Context + Dynamic Registry** | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 6 | **Full Production Pipeline (with Reconstructor)** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |

> **Ablation Finding**: Neither Regex alone (46.4% recall) nor Neural alone (42.9% recall) is viable in enterprise production. The combination of Regex + Neural + Context Scorer is mathematically required to reach 100% Strict F1.

---

## 7. Essence Preservation & Document Readability Audit

Beyond statistical span metrics, our pipeline implements an Essence-Preserving Natural Pseudonymizer designed to satisfy the explicit assignment requirement that redacted documents maintain grammatical flow, narrative tone, and legal syntax:

- **Typographical Casing Preservation**: Original ALL-CAPS names (`KSH INTERNATIONAL LIMITED`) receive ALL-CAPS pseudonyms (`APEX INDUSTRIAL LIMITED`). Title Case names (`Pushpa Kushal Hegde`) receive Title Case pseudonyms (`Sunita Ramesh Verma`).
- **Corporate Legal Suffix Matching**: Entities ending with `Private Limited` receive pseudonyms ending with `Private Limited`. Entities ending with `Limited` receive `Limited`. LLPs retain `LLP`.
- **Geographically Coherent Addresses**: Addresses in Pune/Chakan are replaced with syntactically realistic commercial addresses located in Chakan, Baner, or Hinjewadi with valid PIN codes and area codes (+91 20).
- **Preservation of Statutory IPO Terminology**: Terms critical to prospectus underwriting—including `Book Running Lead Managers`, `Anchor Investors`, `Unified Payments Interface`, `100% Book Built Offer`, and `Section 32 of Companies Act`—are 100% preserved.
- **Run-Level DOCX OpenXML Formatting**: Text replacements occur from right to left across native Word XML `<w:r>` runs. Fonts (Times New Roman, Calibri), font sizes, bold/italic weights, table cell padding, and italicized bottom-of-page notes are completely intact without document corruption.

---

## 8. Developer Specification: Extending to New PII Types

The architecture is fully modular. To add a new entity class (e.g. Indian Aadhaar Number or Passport Number), the developer follows a clean 4-step protocol:

1. **Step 1: Implement Algorithmic Validator**: In `src/detectors/regex/validators.py`, write `validate_aadhaar(val)` implementing the Verhoeff checksum algorithm to eliminate false matches.
2. **Step 2: Add Boundary Recognizer**: In `src/detectors/regex/recognizers.py`, add the regex pattern (e.g. `r'\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b'`) to `RegexDetector.detect()`.
3. **Step 3: Define Priority in Conflict Resolver**: In `src/resolution/conflict_resolver.py`, register `'AADHAAR'` in `TYPE_PRIORITY` with appropriate precedence.
4. **Step 4: Define Synthetic Replacement Rule**: In `src/pseudonymization/synthesizer.py`, add synthetic generation logic in `_generate_typed_fake()` to produce validly formatted synthetic Aadhaar tokens.

---

## 9. Verification & Reproducibility

All evaluation metrics, ablation studies, and baseline comparisons are 100% reproducible via the automated CLI harness:

```bash
# Execute Synthetic Benchmark & Ablation Study
python scripts/run_evaluation.py

# Execute External Baseline Comparison (Presidio vs GLiNER vs Hybrid)
python scripts/run_external_comparison.py

# Execute Full 21-Test Pytest Suite
python -m pytest tests/ -v

# Execute Full Prospectus Redaction on Red Herring Prospectus.docx
python scripts/run_redaction.py --input "Red Herring Prospectus.docx" --output "artifacts/output_docs/Redacted_Red_Herring_Prospectus.docx"
```
