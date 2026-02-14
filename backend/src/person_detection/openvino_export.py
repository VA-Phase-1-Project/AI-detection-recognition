from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

class OpenVINOExportError(RuntimeError):
    pass

def export_onnx_to_openvino(
    onnx_bytes: bytes,
    model_name: str,
    output_root: Path,
) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in model_name)
    if not safe_name:
        safe_name = "model"

    model_dir = output_root / safe_name
    model_dir.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(delete=False, suffix=".onnx") as temp:
        temp.write(onnx_bytes)
        onnx_path = Path(temp.name)

    out_xml = model_dir / f"{safe_name}.xml"
    out_bin = model_dir / f"{safe_name}.bin"

    try:
        cmd = _build_openvino_command(onnx_path, out_xml)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise OpenVINOExportError(
            "OpenVINO conversion tools not found. Install openvino-dev or add 'ovc' to PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "OpenVINO export failed").strip()
        raise OpenVINOExportError(message) from exc
    finally:
        onnx_path.unlink(missing_ok=True)

    if not out_xml.exists() or not out_bin.exists():
        raise OpenVINOExportError("OpenVINO export did not produce .xml/.bin outputs")

    return {
        "model_name": safe_name,
        "xml_path": str(out_xml),
        "bin_path": str(out_bin),
    }

def _build_openvino_command(onnx_path: Path, out_xml: Path) -> list[str]:
    ovc = shutil.which("ovc")
    if ovc:
        return [ovc, str(onnx_path), "--output_model", str(out_xml)]

    python3 = shutil.which("python3") or "python3"
    return [
        python3,
        "-m",
        "openvino.tools.ovc",
        str(onnx_path),
        "--output_model",
        str(out_xml),
    ]
