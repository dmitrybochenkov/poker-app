import io
import re

from PIL import Image, ImageOps

try:
  import pytesseract
except Exception:  # pragma: no cover
  pytesseract = None

try:
  import pypdfium2 as pdfium
except Exception:  # pragma: no cover
  pdfium = None


def extract_amount_rub(text: str) -> int | None:
  if not text:
    return None
  normalized = text.replace(",", ".").replace(" ", "")
  candidates: list[int] = []
  for raw in re.findall(r"(\d{1,6}(?:[.]\d{1,2})?)", normalized):
    try:
      value = float(raw)
    except ValueError:
      continue
    if value <= 0:
      continue
    rub = int(round(value))
    if 1 <= rub <= 500_000:
      candidates.append(rub)
  if not candidates:
    return None
  return max(candidates)


def phone_tail_matches(text: str, tel_number: str | None) -> bool | None:
  if not tel_number:
    return None
  digits = "".join(ch for ch in tel_number if ch.isdigit())
  if len(digits) < 4:
    return None
  tail = digits[-4:]
  text_digits = re.sub(r"\D", "", text or "")
  return tail in text_digits


def extract_phone_tail4(text: str, tel_number: str | None) -> str | None:
  if not tel_number:
    return None
  digits = "".join(ch for ch in tel_number if ch.isdigit())
  if len(digits) < 4:
    return None
  tail = digits[-4:]
  text_digits = re.sub(r"\D", "", text or "")
  return tail if tail in text_digits else None


def extract_operation_id(text: str) -> str | None:
  if not text:
    return None
  normalized = " ".join((text or "").replace("\n", " ").split())
  patterns = [
    r"(?:операц(?:ия|ии|ией)?|operation|op|id)\s*[:№#]?\s*([A-Za-z0-9\-]{6,40})",
    r"(?:чек|квитанц(?:ия|ии)?)\s*[:№#]?\s*([A-Za-z0-9\-]{6,40})",
  ]
  for pattern in patterns:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if match:
      return match.group(1).strip().lower()
  return None


def ocr_text_from_image_bytes(image_bytes: bytes) -> str:
  if not image_bytes or pytesseract is None:
    return ""
  try:
    # PDF path: render first page locally to bitmap before OCR.
    if image_bytes[:4] == b"%PDF" and pdfium is not None:
      pdf = pdfium.PdfDocument(io.BytesIO(image_bytes))
      if len(pdf) <= 0:
        return ""
      page = pdf[0]
      pil_image = page.render(scale=2.2).to_pil()
      image = pil_image
    else:
      image = Image.open(io.BytesIO(image_bytes))
  except Exception:
    return ""
  # Light preprocessing for payment screenshots.
  image = ImageOps.exif_transpose(image).convert("L")
  image = ImageOps.autocontrast(image)
  image = image.resize((int(image.width * 1.5), int(image.height * 1.5)))
  try:
    return pytesseract.image_to_string(image, lang="rus+eng", config="--psm 6")
  except Exception:
    return ""
