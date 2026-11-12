# LedgerLens Assessment Report

**Project:** Bank Statement Processing and Classification System  
**Location:** `bank_statement_analyzer/`  
**Date:** 12 November 2026  
**Assessment type:** Implementation self-assessment against the supplied requirements

## 1. Executive Summary

LedgerLens is a complete local-first prototype for processing bank statement PDFs. It validates and reads text-based, scanned, mixed, and password-protected PDFs; extracts account and transaction data; classifies transactions using deterministic rules and classical machine learning; validates balances; presents results in a Streamlit application; and exports Excel and CSV files.

The final clean-virtual-environment verification passed all **114 automated tests** in **12.84 seconds** with no warnings. The bundled sample and the three supplied synthetic statements were processed through the real pipeline. The 60-transaction ground-truth regression produced **60/60 exact categories (100.0%)**, **2 manual-review transactions**, and **0 incorrect high-confidence predictions**. A headless Chrome session uploaded all three synthetic statements, verified all five pages for each, downloaded default-masked Excel/CSV exports, and confirmed that the explicit secure opt-in exposes the full account number only when requested and clears immediately afterwards.

The implementation is suitable as a demonstration and assignment prototype. It is **not production-ready** because live OCR could not be verified against a real Tesseract installation, no real customer bank statements were available, and the ML model was trained only on 221 synthetic rows. The 60-transaction rule result is tuned on a very small synthetic set and is not evidence of real-world accuracy.

## 2. Requirements Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| Upload and validate PDF statements | Implemented | Extension, signature, size, empty-file, corruption, and password checks |
| Text-based PDF extraction | Implemented | PyMuPDF extraction with pdfplumber fallback and table support |
| Scanned and mixed PDF support | Implemented but not fully verified | Page detection, image-page routing, OpenCV preprocessing, and pytesseract integration; Tesseract executable unavailable in the environment |
| Password-protected PDFs | Implemented and tested | Correct, missing, and incorrect password paths tested with generated encrypted PDFs |
| Account metadata extraction | Implemented | Holder name, account number, IFSC, bank name, statement period, opening and closing balances |
| Bank layout handling | Implemented with limits | Bank-name profiles for 13 banks plus a generic fallback; all use a shared layout-tolerant extraction engine |
| Transaction extraction | Implemented and tested | Line-based and ruled-table extraction, debit/credit/balance parsing, duplicate and field validation |
| Non-LLM classification | Implemented and regression-tested | Direction-aware deterministic rules plus TF-IDF Logistic Regression and Multinomial Naive Bayes; 60/60 exact category result on the supplied synthetic set |
| Review instead of forced prediction | Implemented and regression-tested | Ambiguous UPI/NEFT/IMPS descriptions and low-confidence ML results become `Other` and are marked for manual review |
| Manual category correction | Implemented | Editable transaction explorer in the Streamlit UI |
| Balance validation | Implemented and tested | Chronological running-balance checks, opening/closing consistency, descending-statement support |
| Analytics dashboard | Implemented and tested | Summary metrics and Plotly category, monthly, and transaction charts |
| Excel and CSV export | Implemented and tested | Four-sheet styled Excel workbook and UTF-8 CSV; formula injection neutralised; account numbers and embedded account-number text masked by default across every sheet, with a warned one-shot secure opt-in |
| Privacy and local-only processing | Implemented | No external AI, OCR, or financial APIs; temporary uploads removed; logs avoid transaction descriptions and account identifiers; UI and exports use consistent masking; secure export permission resets after download, navigation, or statement change |
| Automated testing | Implemented | 114 tests covering PDF handling, extraction, classification, validation, exports, privacy, pipeline, analytics, and UI |
| Documentation | Implemented | `README.md`, `.env.example`, `requirements.txt`, and this report |

## 3. Delivered Components

### Application and processing

- `app.py`: Streamlit entry point and page navigation.
- `src/pipeline.py`: end-to-end processing orchestration.
- `src/pdf_processing/`: validation, layout detection, encrypted-file handling, text/table extraction, and OCR.
- `src/extraction/`: account metadata, bank detection profiles, and transaction extraction.
- `src/classification/`: text cleanup, category rules, TF-IDF training, model persistence, and hybrid classification.
- `src/validation/`: transaction-field checks, duplicates, running balances, and closing-balance checks.
- `src/export/`: CSV and styled Excel workbooks.
- `src/ui/`: dashboard, analytics, transaction review, upload, export, charts, components, and styling.

### Data and model artifacts

- `data/sample/sample_bank_statement.pdf`: two-page synthetic HDFC-style statement with 18 transactions.
- `data/training/transactions_training.csv`: 221 synthetic training rows labelled `synthetic_demo`.
- `models/transaction_classifier.joblib`: persisted classifier retrained against the expanded category taxonomy.
- `tests/fixtures/ledgerlens_synthetic/`: three supplied synthetic statements plus the unchanged 60-row ground-truth CSV.

### Supporting files

- `tests/`: deterministic test fixtures and 114 tests.
- `requirements.txt`, `.env.example`, `.gitignore`, and `pytest.ini`.
- `README.md`: setup, architecture, usage, limitations, and privacy notes.

## 4. Classification Assessment

### Approach

The system applies direction-aware deterministic rules first. Only unresolved descriptions are passed to the ML classifier. Specific categories take precedence over generic payment-rail wording, and classic false-positive patterns are explicitly separated:

- Refunds override Amazon/Shopping wording.
- Insurance premiums override Investment wording.
- Credit-card bill payments override Transfer wording.
- Salary, interest credits, cash deposits, and client receipts override Transfer/Other.
- Grocery and quick-commerce merchants override generic Food & Dining.
- Explicit transfer wording remains Transfer, but a bare UPI/NEFT/IMPS reference does not.
- Ambiguous UPI/NEFT/IMPS descriptions without a recognised category are sent to `Other` and marked for review with confidence 0.0 instead of being forced into Transfer.

The ML pipeline combines word-level and character-level TF-IDF with Logistic Regression and Multinomial Naive Bayes. The better macro-F1 candidate is persisted. Training checks for duplicates and conflicting labels before splitting.

### Categories

The taxonomy now matches the supplied ground-truth names: Food & Dining, Groceries, Transport, Shopping, Entertainment, Bills & Utilities, Healthcare, Education, Housing, Income, Investment, Transfer, Cash Withdrawal, Insurance, Refund, Credit Card Payment, Banking Charges, Travel, and `Other`.

### Measured synthetic regression metrics

| Metric | Value |
| --- | --- |
| Synthetic statements | 3 |
| Ground-truth transactions | 60 |
| Exact category accuracy | **60/60 = 100.0%** |
| Rule-based classifications | 58 |
| Manual-review classifications | 2 (`UPI TO UNKNOWN MERCHANT X91`, `UPI PAYMENT REF 771829`) |
| Incorrect high-confidence predictions (confidence >= 0.80) | **0** |
| `01_standard_statement.pdf` | 20/20 correct, 0 review |
| `02_mixed_transactions.pdf` | 15/15 correct, 0 review |
| `03_extended_statement.pdf` | 25/25 correct, 2 review |

The two review rows were already labelled `Other` in the ground truth, so routing them to `Other` with review is both correct and conservative. These 60 descriptions guided rule development and are not a held-out generalisation set. The result demonstrates compatibility with this synthetic corpus, not production accuracy.

### ML holdout metrics

| Metric | Value |
| --- | --- |
| Training rows | 221 total; 165 train / 55 holdout |
| Data source | Synthetic demonstration data |
| Accuracy | 0.6182 |
| Macro precision | 0.5301 |
| Macro recall | 0.5526 |
| Macro F1 | 0.5071 |
| Selected model | Logistic Regression |

The holdout score is lower than the earlier 15-category model because the taxonomy was expanded to match the ground truth and several new classes have very few synthetic examples. It is reported honestly and is not used to claim production accuracy.

## 5. Bundled Sample and Synthetic Fixture Results

The bundled sample was processed through the full pipeline after the final rule and validation changes:

- PDF type: text-based, 2 pages, not encrypted.
- Bank detected: HDFC Bank.
- Transactions extracted: 18.
- Opening balance: 125,000.00.
- Closing balance: 117,287.00.
- Validation: 0 errors, 0 warnings, with a consistent running balance across 18 checked transaction pairs.
- Classification: all 18 transactions accepted by high-confidence rules; 0 routed to review.

The three supplied synthetic statements were verified programmatically and through the running Streamlit UI:

- `01_standard_statement.pdf`: 20 transactions, 0 validation errors, 0 review; all dates, descriptions, references, debits, credits, balances, and categories matched the unchanged ground truth.
- `02_mixed_transactions.pdf`: 15 transactions, 0 validation errors, 0 review; all extracted fields and categories matched.
- `03_extended_statement.pdf`: 25 transactions, 0 validation errors, 2 review; all extracted fields matched, and the two ambiguous descriptions were labelled `Other` and routed to review.

For every synthetic statement, the browser flow loaded Dashboard, Upload Statement, Transactions, Analytics, and Export without a Streamlit exception. Default Excel downloads contained four sheets, the expected transaction row count, masked account numbers in every sheet, and no full account number anywhere in the workbook. Default CSV downloads contained the expected row count, no full account number, and a UTF-8 BOM. On `01_standard_statement.pdf`, the secure opt-in download contained the full account number only after explicit confirmation; the normal download remained masked even while the opt-in was enabled, and the secure permission cleared immediately after the secure download.

The classification behavior is conservative for ambiguous payment rails: uncertain UPI/NEFT/IMPS results are surfaced for user review rather than presented as confident predictions.

## 6. Verification Results

| Check | Command | Result |
| --- | --- | --- |
| Clean dependency install | Fresh venv plus `python -m pip install -r requirements.txt` | Completed successfully on Python 3.13.9 |
| Dependency consistency | `python -m pip check` in the clean venv | No broken requirements found |
| Full automated suite | `python -m pytest -q` in the clean venv | 114 passed in 12.84s, no warnings |
| 60-transaction regression | `pytest tests/test_synthetic_regression.py -q` | 60/60 exact, 2 review, 0 incorrect high-confidence; all dates, descriptions, references, amounts, balances, and categories matched |
| Compilation | `python -m compileall -q app.py config src tests` | Passed, no output |
| Static import/name check | `python -m pyflakes app.py config src tests` | Passed, no output |
| Model compatibility | scikit-learn 1.6.1 plus scipy 1.15.3 pins; Joblib load | Loaded without version warnings |
| Sample pipeline | Programmatic end-to-end run | 18 transactions, 0 validation errors, 0 warnings |
| Sample exports | Programmatic Excel and CSV validation | 4-sheet workbook, 18 rows, valid CSV with BOM, account masked by default |
| Streamlit AppTest | Included in pytest | Passed as part of the 114 tests |
| Browser upload and export | Headless Chrome against the running Streamlit app | All five pages loaded for all three synthetic statements; default exports masked in every sheet; secure opt-in exposed the full account number and reset after download |

The final test pass includes password-protected PDFs, scanned-page detection with a fake OCR processor, mixed statements, corrupt files, empty files, extraction edge cases, balance failures, formula-injection exports, export masking, ambiguous-payment review, the 60-transaction synthetic regression, and UI helper behavior. Actual Tesseract OCR was not run because the Tesseract executable is not installed on this machine.

## 7. Security and Privacy Assessment

### Strengths

- Processing is local; no external AI, OCR, or financial service is called.
- Uploaded files are handled in temporary storage and removed after processing.
- Logs contain status and error metadata rather than transaction descriptions or full account numbers.
- Account numbers are masked in the UI and in Excel/CSV exports by default, using the same `AccountExtractor.mask_account_number()` helper.
- Excel exports apply frame-level masking to every sheet, not only the Account Summary; CSV output uses the same default mask.
- Full account numbers appear in exports only after an explicit, warned opt-in checkbox.
- Account-number occurrences in exported free text are redacted by default.
- The secure permission is one-shot: normal exports remain masked even while it is enabled, and the permission clears after any download, page navigation, or statement change.
- Spreadsheet cells beginning with formula characters are neutralised to reduce CSV/Excel injection risk.
- Upload size, file type, and PDF signature are validated before parsing.
- Encrypted PDFs are decrypted into memory using pypdf before PyMuPDF processing, avoiding a repeated wrong-password failure observed in the installed PyMuPDF AES path.

### Remaining security considerations

- This is a single-user local application with no authentication, authorization, or multi-user isolation.
- Exported files contain sensitive financial information and must be protected by the user.
- The model artifact is loaded from the local filesystem; only trusted model files should be deployed.
- Direct dependency versions are pinned, but transitive dependencies are still resolved by pip and should be locked and audited for a production deployment.
- PDF parsing remains exposed to malformed or adversarial files; production use should include sandboxing and resource limits.

## 8. Limitations and Gaps

1. **Live OCR was not verified end-to-end.** `pytesseract` 0.3.13 is installed by the requirements file, but the Tesseract executable is not installed or on `PATH`. The OCR code path, image preprocessing, and unavailable-OCR error are tested with controlled fakes and error paths; no claim is made that real scanned-document OCR was executed.
2. **No real bank statements were tested.** The bundled statement is synthetic. Bank-name profiles and the shared extraction engine have not been validated against real HDFC, ICICI, SBI, Axis, Kotak, PNB, Bank of Baroda, Canara, Union Bank, IndusInd, Yes Bank, IDFC FIRST, or Federal Bank PDFs.
3. **Classification metrics remain demonstration-only.** The 221-row ML dataset is small, and the 60-transaction evaluation set is synthetic and was used for rule tuning. The 100% exact result should not be read as production accuracy or evidence of generalisation to real bank narrations.
4. **No external assessment rubric was available.** Coverage was mapped to the requirements stated in the supplied task prompt.
5. **No performance benchmark exists.** Small statements work, but large multi-hundred-page statements and high-resolution OCR workloads were not benchmarked.
6. **Bank-specific extraction is not separately proven.** The bank profiles identify layouts, but extraction is primarily a shared heuristic engine rather than independently validated parsers for each bank.
7. **Password support should be regression-tested.** The pypdf decryption path works for generated AES-256 PDFs, but additional encryption modes and real bank PDFs should be added to the fixture suite.

## 9. Recommended Next Steps

1. Install Tesseract OCR 5.x and verify scanned and mixed statements end-to-end, including skewed and low-resolution scans.
2. Obtain consented, anonymised real statements from each supported bank and add regression fixtures for layout detection and transaction extraction.
3. Expand the training dataset with real, anonymised narrations and measure per-category precision, recall, and confusion matrices.
4. Add CI that runs pytest, compile checks, static analysis, and a dependency audit on every change.
5. Add resource limits and process isolation for PDF parsing if the application is ever exposed to untrusted uploads.
6. Add explicit user confirmation and retention guidance for exported financial files.
7. Generate and review a transitive dependency lock file before any production deployment.

## 10. Overall Assessment

| Area | Assessment |
| --- | --- |
| Functional completeness | Strong for a prototype: all core processing, classification, validation, UI, and export flows are present |
| Code organization | Good: clear separation of processing, extraction, classification, validation, export, and UI |
| Test coverage | Good for deterministic synthetic scenarios: 114 passing tests including the 60-transaction field/category regression plus browser verification of all five pages, all three statements, exports, and masking |
| Real-world robustness | Limited: no real statements and no live OCR verification |
| ML credibility | Limited: synthetic training data, expanded taxonomy, and modest holdout metrics |
| Security/privacy design | Good local-first baseline, but not a hardened multi-user service |
| Production readiness | Not production-ready; appropriate for demonstration and further validation |

## 11. Reproduction Commands

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m compileall -q app.py config src tests
streamlit run app.py
```

Use `data/sample/sample_bank_statement.pdf` for the bundled demonstration. For scanned statements, install Tesseract OCR and configure `TESSERACT_CMD` in `.env` if it is not on `PATH`.

## 12. Final ZIP Layout

The final submission archive is `LedgerLens_Assessment.zip`. Its root contains one folder, `bank_statement_analyzer/`, with the application source, tests, documentation, pinned requirements, sample data, model artifact, and placeholder log folder. Caches and generated output files are excluded.

```text
LedgerLens_Assessment.zip
`-- bank_statement_analyzer/
    |-- app.py
    |-- README.md
    |-- ASSESSMENT_REPORT.md
    |-- requirements.txt
    |-- config/
    |-- src/
    |-- tests/
    |-- data/
    |-- models/
    |-- logs/
    |-- .env.example
    |-- .gitignore
    `-- pytest.ini
```

## 13. Post-Testing Bug Fixes

Real-world testing of `01_standard_statement.pdf` exposed two UI regressions. Both were fixed without changing PDF extraction, classification, sample data, or expected transaction values.

### Analytics monthly Net regression

- **Symptom:** Analytics raised `KeyError: 'Net'` while rendering the monthly net cash-flow chart.
- **Root cause:** `_build_monthly_data()` aggregated only `Income` and `Expenses`, while `monthly_net_line()` expected a `Net` column.
- **Fix:** Monthly aggregation now computes `Net = Income - Expenses` before returning the frame. Empty and fully undated inputs continue to return Month, Income, Expenses, and Net columns. The monthly summary table now uses the same aggregated frame instead of recalculating Net separately.
- **Regression coverage:** one-month statements, multi-month statements, empty transactions, fully undated transactions, positive and negative net cash flow, chart values, and chart colours. The Analytics page is also exercised through Streamlit AppTest with multi-month data.

### Account details raw HTML regression

- **Symptom:** Upload Statement displayed account-detail markup as text, beginning with `<div class="ll-account-item">`.
- **Root cause:** Account cards were generated with indented multi-line HTML that could be interpreted as Markdown code rather than rendered markup.
- **Fix:** Added `build_account_strip_html()`, which emits compact HTML with no leading indentation, and the existing renderer now passes that string to Streamlit. Account numbers remain masked through `AccountExtractor.mask_account_number()`.
- **Regression coverage:** verifies five account cards, holder, bank, IFSC, statement period, absence of the full account number, presence of the masked value, and absence of indentation in the markup. Browser verification confirmed five rendered `.ll-account-item` cards, no raw `<div class="ll-account-item">` text, and no exposed full account number.

### Regression verification

- Full clean-venv suite after all fixes: **114 passed in 12.84s**.
- Browser verification: Dashboard, Upload Statement, Transactions, Analytics, and Export all loaded without Streamlit exceptions.
- Browser account check: five rendered cards, masked account number, no raw HTML text.
- Remaining limitation: live Tesseract OCR remains unverified because the Tesseract executable is not installed.

## 14. Classification and Export Privacy Improvements

### Category taxonomy and rules

- Aligned the application taxonomy with the supplied ground-truth labels without changing the ground-truth CSV.
- Added direction-aware rules for income credits, interest credits, cash deposits, client receipts, refunds, insurance premiums, credit-card payments, groceries, subscriptions, education, housing, and explicit transfers.
- Added precedence so specific categories win over generic wording: Refund over Shopping, Insurance over Investment, Credit Card Payment over Transfer, Income over Transfer for client receipts, Housing over Transfer for rent, and Groceries over Food for quick-commerce merchants.
- Removed automatic Transfer classification for bare UPI/NEFT/IMPS descriptions.
- Ambiguous UPI/NEFT/IMPS descriptions that match no category are now `Other` with confidence 0.0 and `needs_review=True`.
- Retrained the Joblib classifier with the expanded 19-category labels and 221 synthetic training rows.

### 60-transaction regression

- Added `tests/fixtures/ledgerlens_synthetic/` with the three supplied PDFs and the unchanged 60-row ground-truth CSV.
- Added `tests/test_synthetic_regression.py`, which runs the real pipeline over all three PDFs and compares exact categories.
- Result: **60/60 exact (100.0%)**, **2 review**, **0 incorrect high-confidence predictions**.
- Before the changes, the same evaluation produced **18/60 exact**, **11 review**, and **31 incorrect high-confidence predictions** when compared against the ground-truth labels.

### Export masking

- Found a privacy leak in workbooks generated by an earlier build: the full account number appeared in `Account Summary!B3`, and the secure opt-in could persist across exports and pages.
- Excel Account Summary and CSV output are masked by default using the same helper as the UI.
- Added `mask_frame_account_numbers()` and applied it to every exported workbook sheet, so account-number occurrences in transaction and raw-text fields are redacted by default.
- Full account-number occurrences in exported description/raw-text fields are redacted by default.
- Replaced the persistent opt-in with a warned one-shot `Enable sensitive full-account-number export` flow. Normal downloads always use masked data, even while the opt-in is enabled.
- Full-number downloads are generated only for explicit secure actions and use separate filenames.
- The secure permission clears after any download, page navigation, or statement change.
- Regression tests scan all workbook sheets and CSV text for the full account number, verify masked defaults for all three statements, verify secure workbooks contain the full number only when requested, and verify the UI permission resets on navigation.
- Verified in a browser that default Excel/CSV downloads contain only the masked value, that the normal Excel download stays masked while the opt-in is enabled, that the secure Excel download contains the full number, and that the opt-in resets immediately after the secure download.

### Verification

- Full clean-venv suite: **114 passed in 12.84s**.
- Browser: Dashboard, Upload Statement, Transactions, Analytics, and Export loaded without exceptions for all three synthetic statements.
- Browser: 5 rendered account cards, masked account number, no raw HTML.
- Browser: default exports for all three statements contained no full account number in any workbook sheet or CSV line.
- Remaining limitation: live Tesseract OCR remains unverified because the Tesseract executable is not installed.

## 15. Conclusion

LedgerLens satisfies the functional shape of the requested bank statement processing system and has a clean, tested implementation for text-based PDFs and generated encrypted files. The strongest evidence is the 114-test clean-venv pass, the 60/60 synthetic regression with full field checks, the browser verification of all five pages for all three statements, and the all-sheet default-masked Excel/CSV checks. The main unresolved validation work is live Tesseract OCR execution and testing against real, anonymised bank statements; until those are completed, the system should be described as a working prototype rather than a production-ready financial tool.
