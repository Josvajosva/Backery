from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def barcode(self, barcode_type, value, **kwargs):
        """Override core barcode generation to bypass broken reportlab backend for QR codes."""
        if barcode_type == 'QR':
            try:
                import qrcode
                import base64
                from io import BytesIO
                
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=4,
                    border=0,
                )
                qr.add_data(value)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                
                return buffer.getvalue()
            except Exception as e:
                _logger.error(f"Fallback qrcode generation failed: {e}")
                
        return super().barcode(barcode_type, value, **kwargs)
