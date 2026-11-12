# LedgerLens

A local-first bank statement processing and classification system. LedgerLens accepts text-based or scanned PDF statements, extracts account and transaction data, classifies transactions with deterministic rules and classical machine learning, validates balance consistency, and presents the results in a Streamlit analytics application.

The application does **not** use an LLM, external AI API, or cloud OCR service. Files are processed on the local machine and temporary upload files are deleted after each run.

## Highlights

- Text PDF extraction with PyMuPDF and a pdfplumber fallback.
- Scanned and mixed PDF support through locally installed Tesseract OCR.
- Password-protected PDF handling.
- Layout-tolerant line and table transaction extraction.
- Bank detection for HDFC, ICICI, SBI, Axis, Kotak, PNB, Bank of Baroda, Canara, Union Bank, IndusInd, Yes Bank, IDFC FIRST, and Federal Bank, plus a generic fallback.
- Hybrid classification: high-confidence rules, TF-IDF machine learning, then a review bucket instead of forced guesses.
- Manual category correction in the transaction explorer.
- Running-balance and transaction-field validation.
- Dashboard, analytics, transaction review, and export pages.
- Styled Excel workbook and UTF-8 CSV downloads.
- Local model training and model metadata with honest evaluation warnings.
- Pytest coverage for PDF handling, extraction, classification, validation, exports, and the end-to-end pipeline.

## Technology

- Python 3.11+ (tested with Python 3.13)
- Streamlit
- pandas and NumPy
- PyMuPDF, pdfplumber, and pypdf
- Pillow and OpenCV
- pytesseract and Tesseract OCR
- scikit-learn 1.6.1, joblib, TF-IDF
- Plotly and openpyxl
- Pytest

## Windows Quick Start

Prerequisites:

- Windows 10 or Windows 11 (64-bit).
- Python 3.11-3.13 installed and available as `python` (tested with Python 3.13.9).
- PowerShell.
- Tesseract OCR is optional and only needed for scanned PDFs.

Open PowerShell in the `bank_statement_analyzer` folder and run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

If `py` is unavailable, use `python -m venv .venv` instead. If PowerShell blocks activation, allow it for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Confirm the pinned model-compatible scikit-learn version:

```powershell
python -c "import sklearn; print(sklearn.__version__)"
```

This must print `1.6.1`, which is the version used to train the bundled model.

Start the application:

```powershell
streamlit run app.py
```

Open the local URL shown in the terminal, upload `data/sample/sample_bank_statement.pdf`, and choose **Process statement**.

The trained model artifact is included at `models/transaction_classifier.joblib`. If it is missing, the application attempts to train it automatically from the bundled dataset. To retrain explicitly using the pinned dependency version:

```powershell
python -m src.classification.ml_classifier --dataset data\training\transactions_training.csv --model models\transaction_classifier.joblib
```

### Tesseract OCR Setup on Windows

Text-based PDFs work without OCR. For scanned statements, install Tesseract OCR 5.x for Windows and check that it is available:

```powershell
Get-Command tesseract
tesseract --version
```

If `tesseract.exe` is installed but not on `PATH`, create the local environment file and set the explicit executable path:

```powershell
Copy-Item .env.example .env
notepad .env
```

Use the actual installation path, for example:

```text
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

The `pytesseract` Python package is installed by `requirements.txt`; the Tesseract executable is a separate system installation. If Tesseract is unavailable, LedgerLens reports a clear OCR error instead of silently producing an empty result.

## Testing

```powershell
python -m pytest -q
python -m compileall -q app.py config src tests
```

The suite contains 114 tests. It includes Streamlit `AppTest` smoke tests for the application pages. Tests use generated PDFs and do not require real customer statements. OCR integration is tested with a controlled fake OCR processor so the suite remains deterministic on machines without Tesseract. A live OCR check requires the Tesseract executable described above.

## Project Structure

```text
bank_statement_analyzer/
|-- app.py
|-- ASSESSMENT_REPORT.md
|-- config/
|   |-- category_rules.py
|   `-- settings.py
|-- data/
|   |-- sample/sample_bank_statement.pdf
|   `-- training/transactions_training.csv
|-- models/transaction_classifier.joblib
|-- src/
|   |-- classification/
|   |-- export/
|   |-- extraction/
|   |-- pdf_processing/
|   |-- ui/
|   |-- utils/
|   |-- validation/
|   |-- models.py
|   `-- pipeline.py
|-- tests/
|-- logs/.gitkeep
|-- .env.example
|-- .gitignore
|-- pytest.ini
|-- requirements.txt
`-- README.md
```

## Processing Flow

1. Validate the PDF signature, extension, size, and password.
2. Detect whether pages have a text layer, images, or both.
3. Extract text directly or OCR image pages.
4. Extract account metadata and statement period.
5. Select a bank layout parser and extract transaction rows from line text or ruled tables.
6. Apply deterministic rules first.
7. Classify remaining descriptions with TF-IDF Logistic Regression or Multinomial Naive Bayes.
8. Route ambiguous UPI/NEFT/IMPS descriptions and low-confidence predictions to `Other` and mark them for review.
9. Validate fields, duplicates, running balances, and closing balance.
10. Display results and generate Excel/CSV exports.

## Classification Model

The classifier uses combined word and character TF-IDF features with two candidate models:

- Logistic Regression with balanced class weights.
- Multinomial Naive Bayes.

The better macro-F1 model on a stratified holdout split is saved. Training enforces duplicate and conflicting-label checks before splitting to reduce leakage.

The bundled Joblib artifact was trained with **scikit-learn 1.6.1**, and `requirements.txt` pins that exact version. Do not install a different scikit-learn version for the submitted model. If the dependency is upgraded intentionally, retrain and regenerate the model with the new version before using it.

The bundled dataset has 221 synthetic demonstration rows. The current holdout result is approximately 61.82% accuracy and 0.5071 macro-F1. The lower holdout score reflects the expanded ground-truth-aligned category set and remains a demonstration metric only; it must not be presented as real-world bank-transaction accuracy. Production use would require a larger, consented, anonymised, bank-specific dataset and ongoing evaluation.

Classification rules are direction-aware and use explicit precedence: refunds, insurance, credit-card payments, housing, client/income receipts, groceries, and other specific patterns override generic transfer wording. Generic UPI/NEFT/IMPS descriptions without a recognised category are not forced into `Transfer`; they are routed to `Other` for manual review.

A deterministic regression fixture at `tests/fixtures/ledgerlens_synthetic/` contains three synthetic statements and 60 ground-truth transactions. The current exact category result is 60/60, with 2 ambiguous transactions routed to review and 0 incorrect high-confidence predictions. These 60 descriptions were used to tune and verify the rules, so this is not a held-out generalisation metric.

## Output

Excel workbooks contain four sheets:

- `Transactions`
- `Account Summary`
- `Category Summary`
- `Validation Report`

CSV exports contain transaction fields, category, classification method, confidence, review state, source page, and raw extracted text.

Spreadsheet text fields are neutralised against formula injection. Account numbers are masked in the UI and in Excel/CSV exports by default. Excel masking is applied to every sheet, including transaction free text, and CSV uses the same default mask. The Export page provides an explicit, warned, one-shot opt-in to include the full account number in downloaded files. Normal downloads remain masked even while the opt-in is enabled, and the permission clears after any download, page navigation, or statement change.

## Supported Inputs and Limitations

- PDF statements only.
- OCR quality depends on scan resolution, skew, language, and Tesseract installation.
- Extraction is deliberately layout-tolerant but cannot guarantee every bank-specific template. The bundled sample is synthetic; real bank formats should be validated before use.
- Password-protected PDFs are supported when the correct password is supplied.
- The app assumes INR by default and parses Indian-style number formatting.
- Very large statements are processed locally and may take longer on machines without OCR acceleration.
- Dates are interpreted day-first when ambiguous, which suits common Indian bank statement formats.
- Classification rules are configurable in `config/category_rules.py`; merchant keywords are not hidden inside the classifier implementation.

## Privacy and Security

- No external AI, OCR, or financial API is called.
- Temporary PDF files are deleted after processing.
- Logs contain status and error metadata, not transaction descriptions or account identifiers.
- Uploaded files are never persisted by the application.
- Exported files contain sensitive financial information and should be stored and shared only through approved channels.

## Configuration

Runtime options can be supplied in `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BANK_STATEMENT_MAX_UPLOAD_MB` | `15` | Maximum upload size |
| `BANK_STATEMENT_MIN_TEXT_CHARS` | `40` | Text threshold before OCR |
| `BANK_STATEMENT_OCR_DPI` | `300` | OCR render resolution |
| `TESSERACT_CMD` | empty | Explicit Tesseract executable path |
| `BANK_STATEMENT_RULE_THRESHOLD` | `0.80` | Minimum rule confidence |
| `BANK_STATEMENT_ML_THRESHOLD` | `0.55` | Minimum ML confidence |
| `BANK_STATEMENT_BALANCE_TOLERANCE` | `0.01` | Balance comparison tolerance |
