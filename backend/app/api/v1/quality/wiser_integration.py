"""
Wiser Integration — exporta fotos e metadados da peça aprovada para o Wiser ERP.

3 modos com fallback automático:
  1. API REST        (WISER_API_URL)          — POST foto + JSON para endpoint REST
  2. Pasta de rede   (WISER_FILE_SHARE_PATH)  — salva .json + .jpg no share de rede
  3. PDF manual      (WISER_PDF_DIR)          — gera PDF para upload manual operador

Fallback: tenta modo 1 → 2 → 3. Se todos falharem, retorna success=False.

Nomenclatura de arquivo: {OP}_{PEÇA}_{STATUS}_{TIMESTAMP}.{ext}
  Exemplo: OP1234_PC5678_APPROVED_20240419_142530.jpg

Configuração via variáveis de ambiente:
  WISER_INTEGRATION_MODE  = file_share | api | pdf  (default: file_share)
  WISER_API_URL           = URL base da API Wiser   (ex: http://wiser.local:8080)
  WISER_FILE_SHARE_PATH   = Caminho da pasta de rede (default: /tmp/wiser_export)
  WISER_PDF_DIR           = Pasta para PDFs gerados  (default: /tmp/wiser_pdf)
"""
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Modo de integração padrão
WISER_MODE = os.environ.get("WISER_INTEGRATION_MODE", "file_share")

# URL da API REST do Wiser (vazio desabilita o modo API)
WISER_API_URL = os.environ.get("WISER_API_URL", "")

# Caminho da pasta compartilhada na rede
WISER_FILE_SHARE_PATH = os.environ.get("WISER_FILE_SHARE_PATH", "/tmp/wiser_export")  # noqa: S108

# Pasta para PDFs gerados manualmente
WISER_PDF_DIR = os.environ.get("WISER_PDF_DIR", "/tmp/wiser_pdf")  # noqa: S108


class WiserIntegration:
    """Exporta dados da peça aprovada para o Wiser ERP."""

    def export_piece(self, piece: dict, photo_path: str) -> dict:
        """Exporta peça para Wiser usando o modo configurado com fallback.

        Tenta: API → pasta de rede → PDF. Para na primeira que tem sucesso.

        Args:
            piece: Dict com dados da peça (piece_number, work_order, product_type,
                   status, total_rework_count, total_rework_time_seconds).
            photo_path: Caminho local da foto de qualidade a exportar.

        Returns:
            Dict com:
              - success (bool): se a exportação foi bem-sucedida
              - method (str): "api", "file_share" ou "pdf"
              - path (str): caminho/URL de destino
              - error (str): descrição do erro se success=False
        """
        # Tenta API primeiro (apenas se URL configurada)
        if WISER_API_URL:
            result = self._export_api(piece, photo_path)
            if result["success"]:
                return result
            logger.warning("wiser_api_failed, trying file_share: %s", result.get("error"))

        # Fallback: pasta compartilhada de rede
        result = self._export_file_share(piece, photo_path)
        if result["success"]:
            return result
        logger.warning("wiser_file_share_failed, trying pdf: %s", result.get("error"))

        # Último recurso: PDF gerado localmente
        return self._export_pdf(piece, photo_path)

    def _get_filename_base(self, piece: dict) -> str:
        """Gera nome de arquivo padronizado sem extensão.

        Formato: {OP}_{PEÇA}_{STATUS}_{TIMESTAMP}
        Barras "/" são substituídas por "-" para compatibilidade de filesystem.

        Args:
            piece: Dict com os dados da peça.

        Returns:
            String base do nome de arquivo (sem extensão).
        """
        op = (piece.get("work_order") or "SEMOP").replace("/", "-")
        num = (piece.get("piece_number") or "SEMNUM").replace("/", "-")
        status = (piece.get("status") or "approved").upper()
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"{op}_{num}_{status}_{ts}"

    def _export_api(self, piece: dict, photo_path: str) -> dict:
        """Envia peça via API REST para o Wiser.

        Args:
            piece: Dict com dados da peça.
            photo_path: Caminho local da foto.

        Returns:
            Dict com success, method, path, error.
        """
        try:
            import requests
            metadata = {
                "piece_number": piece.get("piece_number"),
                "work_order": piece.get("work_order"),
                "product_type": piece.get("product_type"),
                "status": piece.get("status"),
                "approved_at": datetime.now(UTC).isoformat(),
                "total_rework_count": piece.get("total_rework_count", 0),
                "total_rework_time_seconds": piece.get("total_rework_time_seconds", 0),
            }
            files = {}
            photo_fh = None
            if photo_path and os.path.exists(photo_path):
                photo_fh = open(photo_path, "rb")  # noqa: SIM115
                files["photo"] = photo_fh

            resp = requests.post(
                f"{WISER_API_URL}/quality/pieces",
                data={"metadata": json.dumps(metadata)},
                files=files,
                timeout=10,
            )
            if photo_fh:
                photo_fh.close()

            resp.raise_for_status()
            return {"success": True, "method": "api", "path": WISER_API_URL, "error": ""}
        except Exception as exc:
            return {"success": False, "method": "api", "path": "", "error": str(exc)}

    def _export_file_share(self, piece: dict, photo_path: str) -> dict:
        """Salva metadados JSON e foto na pasta compartilhada de rede.

        Args:
            piece: Dict com dados da peça.
            photo_path: Caminho local da foto.

        Returns:
            Dict com success, method, path, error.
        """
        try:
            base = self._get_filename_base(piece)
            share_dir = Path(WISER_FILE_SHARE_PATH)
            share_dir.mkdir(parents=True, exist_ok=True)

            # Salva JSON de metadados
            meta_path = share_dir / f"{base}.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "piece_number": piece.get("piece_number"),
                        "work_order": piece.get("work_order"),
                        "product_type": piece.get("product_type"),
                        "status": piece.get("status"),
                        "approved_at": datetime.now(UTC).isoformat(),
                        "total_rework_count": piece.get("total_rework_count", 0),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )

            # Copia foto para a pasta de rede
            if photo_path and os.path.exists(photo_path):
                import shutil
                dest = share_dir / f"{base}.jpg"
                shutil.copy2(photo_path, dest)

            return {
                "success": True,
                "method": "file_share",
                "path": str(meta_path),
                "error": "",
            }
        except Exception as exc:
            return {
                "success": False,
                "method": "file_share",
                "path": "",
                "error": str(exc),
            }

    def _export_pdf(self, piece: dict, photo_path: str) -> dict:
        """Gera PDF de laudo de qualidade para upload manual pelo operador.

        Requer reportlab. Se não disponível, retorna success=False.

        Args:
            piece: Dict com dados da peça.
            photo_path: Caminho local da foto (opcional — incluída no PDF se existir).

        Returns:
            Dict com success, method, path, error.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Image as RLImage
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            base = self._get_filename_base(piece)
            pdf_dir = Path(WISER_PDF_DIR)
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_dir / f"{base}.pdf"

            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(
                    f"Laudo de Qualidade — Peça {piece.get('piece_number')}",
                    styles["Title"],
                ),
                Spacer(1, 12),
                Paragraph(f"Ordem de Produção: {piece.get('work_order', 'N/A')}", styles["Normal"]),
                Paragraph(f"Produto: {piece.get('product_type', 'N/A')}", styles["Normal"]),
                Paragraph("Status: APROVADA", styles["Normal"]),
                Paragraph(f"Retrabalhos: {piece.get('total_rework_count', 0)}", styles["Normal"]),
                Paragraph(
                    f"Emitido em: {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')}",
                    styles["Normal"],
                ),
            ]

            # Inclui foto no PDF se disponível
            if photo_path and os.path.exists(photo_path):
                story.append(Spacer(1, 12))
                story.append(RLImage(photo_path, width=400, height=300))

            doc.build(story)
            return {"success": True, "method": "pdf", "path": str(pdf_path), "error": ""}
        except Exception as exc:
            return {"success": False, "method": "pdf", "path": "", "error": str(exc)}


# Instância singleton — criada na primeira chamada a get_wiser_integration()
_wiser: WiserIntegration | None = None


def get_wiser_integration() -> WiserIntegration:
    """Retorna instância singleton do WiserIntegration.

    Returns:
        WiserIntegration: instância compartilhada do serviço.
    """
    global _wiser
    if _wiser is None:
        _wiser = WiserIntegration()
    return _wiser
