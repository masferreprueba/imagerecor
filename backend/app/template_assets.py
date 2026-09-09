import json
import re
import unicodedata
from io import BytesIO
from pathlib import Path

from PIL import Image


MAX_TEMPLATE_BYTES = 15 * 1024 * 1024


def clean_template_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")
    clean = re.sub(r"_+", "_", clean)
    if not clean:
        raise ValueError("Escribe un nombre válido para la plantilla.")
    return clean[:120]


def save_job_template(data: bytes, name: str, root: Path) -> dict[str, str]:
    if not data:
        raise ValueError("Selecciona una plantilla PNG.")
    if len(data) > MAX_TEMPLATE_BYTES:
        raise ValueError("La plantilla supera el límite de 15 MB.")
    clean_name = clean_template_name(name)
    try:
        with Image.open(BytesIO(data)) as opened:
            if (opened.format or "").upper() != "PNG":
                raise ValueError("La plantilla debe estar en formato PNG.")
            opened.load()
            template = opened.convert("RGBA")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("La plantilla PNG no se pudo leer.") from exc
    if template.size != (500, 500):
        template.close()
        raise ValueError("La plantilla debe medir exactamente 500 × 500 px.")
    alpha = template.getchannel("A")
    minimum, _ = alpha.getextrema()
    alpha.close()
    if minimum == 255:
        template.close()
        raise ValueError("La plantilla necesita un área transparente para colocar el producto.")
    path = root / "template.png"
    template.save(path, "PNG", optimize=True)
    template.close()
    metadata = {"name": name.strip(), "base_name": clean_name}
    (root / "template.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    return metadata


def load_template_metadata(root: Path) -> dict[str, str]:
    path = root / "template.json"
    if not path.is_file():
        raise ValueError("No se encontró la plantilla seleccionada.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"name": str(payload["name"]), "base_name": clean_template_name(str(payload["base_name"]))}
