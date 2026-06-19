import sys
import base64

try:
    barcode_bytes = env['ir.actions.report'].barcode('QR', 'TEST_QR_CODE_123', width=120, height=120)
    print(f"Barcode bytes type: {type(barcode_bytes)}")
    print(f"Barcode length: {len(barcode_bytes)}")
    res = 'data:image/png;base64,' + base64.b64encode(barcode_bytes).decode('ascii')
    print(f"QR length: {len(res)}")
    print(f"QR prefix: {res[:50]}")
except Exception as e:
    import traceback
    traceback.print_exc()
