move = None
for m in env['account.move'].search([('move_type', '=', 'out_invoice')], order='id desc', limit=1000):
    so_ids = m._get_intercompany_po_ids()
    if so_ids:
        move = m
        break

if move:
    print(f"Found intercompany move: {move.id}")
    so_ids = move._get_intercompany_po_ids()
    print(f"so_ids: {so_ids}")
    qr_value = f"{so_ids}|{move.id}"
    print(f"qr_value: {qr_value}")
    try:
        qr_data_uri = move.get_intercompany_so_qr_code()
        print(f"QR length: {len(qr_data_uri)}")
        print(f"QR prefix: {qr_data_uri[:50]}")
    except Exception as e:
        import traceback
        traceback.print_exc()
else:
    print("No intercompany move found")
