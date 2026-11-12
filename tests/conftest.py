"""Shared deterministic PDF fixtures for the test suite."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATEMENT_HEADER = (
    "HDFC BANK LIMITED",
    "Statement of Account",
    "Account Holder Name : AARAV SHARMA",
    "Account Number : 50100123456789",
    "IFSC Code : HDFC0001234",
    "Branch : MG Road Bengaluru",
    "Statement Period : 01/04/2024 to 30/04/2024",
    "Opening Balance : 125,000.00",
    "",
    "Date        Narration                                  Ref          Withdrawal   Deposit      Balance",
)

STATEMENT_ROWS = (
    "01/04/2024  SALARY CREDIT APRIL ACME CORP             NEFT123      0.00         85,000.00    210,000.00",
    "02/04/2024  UPI/ZOMATO/ORDER 445566                    UPI445566                 1,250.00     208,750.00",
    "03/04/2024  ATM WITHDRAWAL MG ROAD                     ATM7788      5,000.00                  203,750.00",
    "04/04/2024  NETFLIX SUBSCRIPTION                       NACH9988     649.00                    203,101.00",
    "05/04/2024  UBER RIDE AIRPORT                          UPI123       480.00                    202,621.00",
    "07/04/2024  AMAZON MARKETPLACE ORDER                   UPI00981     3,499.00                  199,122.00",
    "08/04/2024  ELECTRICITY BILL PAYMENT                   BILL445      2,340.00                  196,782.00",
    "10/04/2024  HOUSE RENT PAYMENT LANDLORD                IMPS776      35,000.00                 161,782.00",
    "12/04/2024  MUTUAL FUND SIP AUTO DEBIT                 MF0098       10,000.00                 151,782.00",
    "15/04/2024  APOLLO PHARMACY MEDICINES                  POS4455      780.00                    151,002.00",
    "18/04/2024  NEFT RECEIVED FROM SELF                    NEFT552                   5,000.00     156,002.00",
    "20/04/2024  CREDIT CARD PAYMENT                        CC8899       12,000.00                 144,002.00",
    "22/04/2024  SCHOOL ANNUAL FEE                           NEFT667      18,000.00                 126,002.00",
    "24/04/2024  INDIGO AIRLINES TICKET                      AIR112       8,500.00                  117,502.00",
    "25/04/2024  BANK CHARGES QUARTERLY                      CHG001       250.00                    117,252.00",
    "28/04/2024  SWIGGY INSTAMART ORDER                      UPI7788      650.00                    116,602.00",
    "29/04/2024  OLA CABS CITY RIDE                          UPI3344      315.00                    116,287.00",
    "30/04/2024  INTEREST CREDIT SAVINGS                     INT009                    1,000.00     117,287.00",
)


def _write_text_pdf(
    path: Path,
    pages: list[list[str]],
    *,
    password: str | None = None,
) -> Path:
    document = fitz.open()
    for lines in pages:
        page = document.new_page(width=595, height=842)
        y = 48
        for line in lines:
            page.insert_text((38, y), line, fontname="cour", fontsize=8)
            y += 12
    if password:
        document.save(
            path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw=password,
        )
    else:
        document.save(path, garbage=3, deflate=True)
    document.close()
    return path


def _write_scanned_pdf(path: Path, pages: int = 1) -> Path:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=595, height=842)
        image = Image.new("RGB", (900, 1200), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 60, 840, 1140), outline="black", width=3)
        draw.text((100, 100), f"SCANNED STATEMENT PAGE {index + 1}", fill="black")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        page.insert_image(page.rect, stream=buffer.getvalue())
    document.save(path, garbage=3, deflate=True)
    document.close()
    return path


@pytest.fixture
def statement_lines() -> list[str]:
    return list(STATEMENT_HEADER) + list(STATEMENT_ROWS) + [
        "Closing Balance : 117,287.00"
    ]


@pytest.fixture
def text_statement_path(tmp_path: Path, statement_lines: list[str]) -> Path:
    return _write_text_pdf(tmp_path / "text_statement.pdf", [statement_lines])


@pytest.fixture
def password_statement_path(tmp_path: Path, statement_lines: list[str]) -> Path:
    return _write_text_pdf(
        tmp_path / "password_statement.pdf",
        [statement_lines],
        password="secret",
    )


@pytest.fixture
def scanned_pdf_path(tmp_path: Path) -> Path:
    return _write_scanned_pdf(tmp_path / "scanned_statement.pdf")


@pytest.fixture
def mixed_pdf_path(tmp_path: Path, statement_lines: list[str]) -> Path:
    document = fitz.open()
    text_page = document.new_page(width=595, height=842)
    y = 48
    for line in statement_lines:
        text_page.insert_text((38, y), line, fontname="cour", fontsize=8)
        y += 12

    image_page = document.new_page(width=595, height=842)
    image = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 840, 1140), outline="black", width=3)
    draw.text((100, 100), "SCANNED PAGE", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_page.insert_image(image_page.rect, stream=buffer.getvalue())

    path = tmp_path / "mixed_statement.pdf"
    document.save(path, garbage=3, deflate=True)
    document.close()
    return path


@pytest.fixture
def empty_pdf_path(tmp_path: Path) -> Path:
    document = fitz.open()
    document.new_page()
    path = tmp_path / "empty_statement.pdf"
    document.save(path)
    document.close()
    return path


@pytest.fixture
def corrupt_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.7\nthis is not a valid PDF document\n")
    return path


@pytest.fixture
def non_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "notes.txt"
    path.write_text("not a PDF", encoding="utf-8")
    return path


@pytest.fixture
def blank_file_path(tmp_path: Path) -> Path:
    path = tmp_path / "blank.pdf"
    path.write_bytes(b"")
    return path


@pytest.fixture
def bundled_sample_path() -> Path:
    path = PROJECT_ROOT / "data" / "sample" / "sample_bank_statement.pdf"
    assert path.exists(), "The bundled synthetic sample statement is missing."
    return path
