# LedgerLens – Bank Statement Processing & Classification System

LedgerLens is a Python-based bank statement processing and transaction classification application built with Streamlit. It extracts account and transaction information from text-based, scanned, and mixed PDF bank statements, classifies transactions using deterministic rules and traditional machine learning, validates financial data, and provides interactive analytics with downloadable reports.

The application is designed with a privacy-focused processing approach. It does not use external LLMs, AI APIs, or cloud OCR services. When run locally, statement processing takes place on the local machine. When deployed, processing takes place within the application hosting environment.

## Key Features

- **PDF Processing:** Extracts data from text-based, scanned, and mixed PDF statements.
- **OCR Support:** Processes scanned pages using locally installed Tesseract OCR.
- **Multiple Bank Formats:** Supports HDFC, ICICI, SBI, Axis, Kotak, PNB, Bank of Baroda, Canara, Union Bank, IndusInd, Yes Bank, IDFC FIRST, and Federal Bank, with a generic fallback parser.
- **Transaction Extraction:** Extracts transaction dates, descriptions, debit amounts, credit amounts, and running balances.
- **Hybrid Classification:** Combines deterministic rules with TF-IDF-based machine learning.
- **Manual Review:** Routes ambiguous transactions for review and allows users to correct categories.
- **Financial Validation:** Checks transaction fields, duplicate entries, running balances, and closing balance consistency.
- **Interactive Analytics:** Provides dashboards, transaction exploration, category summaries, and financial insights.
- **Data Export:** Generates formatted Excel workbooks and UTF-8 CSV files.
- **Privacy Controls:** Masks account numbers by default and provides an explicit one-time option for unmasked exports.
- **Automated Testing:** Includes test coverage for extraction, classification, validation, exports, and application workflows.

## Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python 3.11+ |
| Application Framework | Streamlit |
| Data Processing | Pandas, NumPy |
| PDF Extraction | PyMuPDF, pdfplumber, pypdf |
| OCR | Tesseract OCR, pytesseract |
| Image Processing | Pillow, OpenCV |
| Machine Learning | scikit-learn 1.6.1 |
| Text Vectorization | Word and Character TF-IDF |
| Visualization | Plotly |
| Excel Export | openpyxl |
| Model Persistence | Joblib |
| Testing | Pytest, Streamlit AppTest |

## Application Architecture

The application follows a modular processing pipeline:

1. **Input Validation:** Validates PDF signatures, file extensions, upload size, and password protection.
2. **PDF Detection:** Identifies pages containing selectable text, scanned images, or a combination of both.
3. **Text Extraction:** Uses PyMuPDF or pdfplumber for text extraction and Tesseract OCR for scanned pages.
4. **Metadata Extraction:** Identifies account information, bank details, and statement periods.
5. **Transaction Parsing:** Selects an appropriate bank-specific parser or the generic fallback parser.
6. **Rule-Based Classification:** Applies high-confidence transaction rules.
7. **Machine Learning Classification:** Uses TF-IDF features with Logistic Regression or Multinomial Naive Bayes for transactions not confidently classified by rules.
8. **Review Handling:** Routes ambiguous descriptions and low-confidence predictions to a review category instead of forcing uncertain classifications.
9. **Financial Validation:** Checks transaction consistency, duplicates, running balances, and closing balances.
10. **Results and Export:** Displays processed information through Streamlit pages and generates Excel and CSV reports.

## Processing Flow

```text
Bank Statement PDF
        |
        v
Input Validation
        |
        v
PDF Type Detection
        |
        +----------------------+
        |                      |
        v                      v
Text Extraction          OCR Processing
        |                      |
        +----------+-----------+
                   |
                   v
          Metadata Extraction
                   |
                   v
         Transaction Extraction
                   |
                   v
        Rule-Based Classification
                   |
                   v
        Machine Learning Model
                   |
                   v
          Review & Validation
                   |
                   v
          Streamlit Dashboard
                   |
                   v
          Excel / CSV Export
```

## Transaction Classification

LedgerLens uses a hybrid classification approach combining deterministic rules and traditional machine learning.

### 1. Rule-Based Classification

High-confidence transaction patterns are identified using configurable rules. Rules use transaction descriptions, keywords, and transaction direction to identify categories.

Specific patterns such as refunds, insurance, credit-card payments, housing, income receipts, and groceries take precedence over generic transfer-related wording.

### 2. Machine Learning Classification

Transactions that cannot be confidently classified using rules are evaluated using a traditional machine learning pipeline.

The classifier includes:

- Word-level and character-level TF-IDF features.
- Logistic Regression with balanced class weights.
- Multinomial Naive Bayes.
- Stratified holdout evaluation using macro-F1 and accuracy.
- Duplicate and conflicting-label checks before dataset splitting.

The better-performing candidate model, based on holdout macro-F1, is saved as a Joblib artifact.

### 3. Ambiguous Transaction Handling

Generic UPI, NEFT, and IMPS descriptions without a recognised category are not automatically classified as transfers. Ambiguous transactions and low-confidence predictions are routed for manual review.

Users can also correct transaction categories through the transaction explorer.

### Model Evaluation and Limitations

The bundled training dataset contains 221 synthetic demonstration transactions.

Current holdout evaluation:

| Metric | Result |
|---|---:|
| Accuracy | Approximately 61.82% |
| Macro-F1 | 0.5071 |

These results are based on synthetic demonstration data and should not be interpreted as real-world bank transaction classification accuracy.

A separate deterministic regression fixture contains three synthetic statements with 60 ground-truth transactions. The current rule-based regression result is:

- 60 out of 60 exact category matches.
- 2 ambiguous transactions routed for review.
- 0 incorrect high-confidence predictions.

These transactions were used to tune and verify the classification rules. Therefore, this result is a regression test outcome, not an independent generalisation benchmark.

Production use would require a larger, consented, anonymised, and representative dataset, followed by ongoing evaluation.

**Model Compatibility:** The bundled model was trained using scikit-learn 1.6.1. The project pins this version in `requirements.txt` to maintain compatibility. If the dependency is upgraded, the model should be retrained using the new version.

## Project Structure

```text
bank_statement_analyzer/
|
|-- app.py
|-- README.md
|-- ASSESSMENT_REPORT.md
|
|-- config/
|   |-- category_rules.py
|   `-- settings.py
|
|-- data/
|   |-- sample/
|   |   `-- sample_bank_statement.pdf
|   `-- training/
|       `-- transactions_training.csv
|
|-- models/
|   `-- transaction_classifier.joblib
|
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
|
|-- tests/
|
|-- logs/
|   `-- .gitkeep
|
|-- .env.example
|-- .gitignore
|-- packages.txt
|-- pytest.ini
`-- requirements.txt
```

## Installation and Setup

### Prerequisites

- Windows 10 or Windows 11 (64-bit).
- Python 3.11–3.13.
- PowerShell.
- Tesseract OCR 5.x (optional; required only for scanned PDF processing).

### 1. Clone the Repository

```powershell
git clone https://github.com/jatinsinhsolanki0102-eng/LedgerLens-bank-statement-analyzer.git

cd LedgerLens-bank-statement-analyzer
```

### 2. Create a Virtual Environment

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If the Python launcher is unavailable, use:

```powershell
python -m venv .venv
```

If PowerShell blocks environment activation, run the following command in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3. Install Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Verify the installed scikit-learn version:

```powershell
python -c "import sklearn; print(sklearn.__version__)"
```

The expected version is `1.6.1`.

### 4. Run the Application

```powershell
streamlit run app.py
```

Open the local URL displayed in the terminal.

Upload the sample statement from:

```text
data/sample/sample_bank_statement.pdf
```

Then select **Process Statement** to start processing.

## OCR Configuration

Text-based PDFs can be processed without installing Tesseract.

For scanned statements, install Tesseract OCR 5.x and verify the installation:

```powershell
Get-Command tesseract
tesseract --version
```

If Tesseract is installed but not available through the system PATH, create the local environment configuration file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set the executable path according to the local installation:

```text
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

The `pytesseract` Python package and the Tesseract executable are separate dependencies. If the executable is unavailable, the application reports a clear OCR error.

## Model Training

The pre-trained model is included in:

```text
models/transaction_classifier.joblib
```

If the model artifact is unavailable, the application attempts to train a model using the bundled training dataset.

To retrain the classifier explicitly:

```powershell
python -m src.classification.ml_classifier --dataset data\training\transactions_training.csv --model models\transaction_classifier.joblib
```

Use the pinned scikit-learn version when loading or retraining the bundled model.

## Deployment

The application can be deployed using Streamlit Community Cloud.

### Deployment Steps

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) using your GitHub account.
2. Select **Create App**.
3. Choose the public GitHub repository.
4. Configure the deployment:
   - Repository: `jatinsinhsolanki0102-eng/LedgerLens-bank-statement-analyzer`
   - Branch: `main`
   - Main file: `app.py`
5. Select a compatible Python runtime, preferably Python 3.13 or 3.12.
6. Deploy the application.

The repository includes `packages.txt` for required Linux system packages, including OCR-related dependencies.

No external API keys or secrets are required for the default configuration.

**Deployment Considerations:**

- Free Streamlit Community Cloud applications may sleep after periods of inactivity.
- Uploaded statements are processed within the hosted application environment.
- Export files are generated in memory and downloaded directly.
- Users should avoid uploading real financial statements to public demonstration deployments unless the hosting and data-handling arrangements are approved for that information.

## Testing

The project includes an automated test suite covering:

- PDF validation and password handling.
- Text and OCR extraction workflows.
- Bank-specific and generic transaction parsing.
- Rule-based and machine learning classification.
- Transaction validation and running-balance consistency.
- Excel and CSV export functionality.
- Application pages and end-to-end processing workflows.

Run the test suite:

```powershell
python -m pytest -q
```

Run compilation checks:

```powershell
python -m compileall -q app.py config src tests
```

The current test suite contains **114 tests**.

OCR integration tests use a controlled OCR processor to ensure deterministic test execution. Live OCR functionality requires a working Tesseract installation and should be validated separately with suitable scanned statements.

## Export Functionality

LedgerLens generates Excel workbooks containing four sheets:

1. `Transactions`
2. `Account Summary`
3. `Category Summary`
4. `Validation Report`

CSV exports include transaction fields, category, classification method, confidence, review status, source page, and extracted text.

### Data Protection in Exports

- Account numbers are masked by default in the application interface and downloaded files.
- Masking is applied across all Excel sheets, including transaction free-text fields.
- CSV exports follow the same default masking behaviour.
- Users can explicitly enable a warned, one-time option to include the full account number in an Excel export.
- The permission is cleared after a download, page navigation, or statement change.
- Spreadsheet text fields are neutralised to reduce formula-injection risks.

## Configuration

Runtime settings can be configured through a `.env` file.

| Variable | Default | Description |
|---|---:|---|
| `BANK_STATEMENT_MAX_UPLOAD_MB` | `15` | Maximum PDF upload size |
| `BANK_STATEMENT_MIN_TEXT_CHARS` | `40` | Minimum text threshold before OCR |
| `BANK_STATEMENT_OCR_DPI` | `300` | OCR rendering resolution |
| `TESSERACT_CMD` | Empty | Explicit Tesseract executable path |
| `BANK_STATEMENT_RULE_THRESHOLD` | `0.80` | Minimum rule confidence |
| `BANK_STATEMENT_ML_THRESHOLD` | `0.55` | Minimum ML confidence |
| `BANK_STATEMENT_BALANCE_TOLERANCE` | `0.01` | Allowed balance comparison tolerance |

## Supported Inputs and Limitations

- Supports PDF bank statements only.
- Supports text-based, scanned, and mixed PDF documents.
- OCR accuracy depends on scan quality, resolution, skew, and language configuration.
- Extraction is designed to handle multiple layouts but cannot guarantee compatibility with every bank-specific statement template.
- Real bank statement formats should be validated before production use.
- Password-protected PDFs are supported when the correct password is provided.
- INR is the default currency, with Indian-style number formatting.
- Ambiguous dates are interpreted using day-first formatting.
- Large documents may require additional processing time, particularly on systems without OCR acceleration.
- Classification performance depends on the quality and diversity of the training data.

## Privacy and Security

LedgerLens follows a privacy-conscious processing design:

- No external LLM, AI API, or cloud OCR service is used.
- Local execution processes uploaded statements on the user's machine.
- Temporary PDF files are deleted after processing.
- Application logs store processing status and error metadata rather than transaction descriptions or account identifiers.
- Uploaded files are not intentionally persisted by the application.
- Exported files may contain sensitive financial information and should be stored and shared only through approved channels.

When using a hosted deployment, uploaded files are processed by the hosting environment. Users should consider the deployment provider's policies and avoid submitting confidential financial information to an unapproved public instance.

## Future Improvements

Potential areas for further development include:

- Improving OCR accuracy across different scan qualities and statement languages.
- Expanding support for additional banks and statement layouts.
- Improving classification performance with larger and more diverse anonymised datasets.
- Adding more advanced transaction insights and anomaly detection.
- Introducing additional validation and reconciliation capabilities.
- Improving processing performance for large statements.

## Project Links

- **GitHub Repository:** https://github.com/jatinsinhsolanki0102-eng/LedgerLens-bank-statement-analyzer
- **Live Application:** https://ledgerlens-bank-statement-analyzer-kgundglxggkzne7zmecthe.streamlit.app/

---

**LedgerLens – Turning Bank Statements into Structured Financial Insights.**
