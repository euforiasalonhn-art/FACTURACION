"""Informe SAR de selección: tarjeta, RTN y muestra determinística del resto."""
import io, hashlib
from decimal import Decimal
from xml.sax.saxutils import escape
from flask import request, jsonify, send_file, session
import accounting

def porcentaje(args):
    try:
        pct = int(str(args.get('muestra', '22')).strip())
    except (TypeError, ValueError):
        pct = 22
    return min(25, max(20, pct))

def bandera(value):
    return str(value or '').strip().lower() in ['1', 'true', 'si', 'sí', 'x', 'on']

def elegida(clave, pct):
    return int(hashlib.sha256(clave.encode()).hexdigest()[:8], 16) % 100 < pct

def collect(c, args):
    filters = dict(args)
    filters['scope'] = 'fiscal'
    pct = 100
    con_fiscal = True
    data = accounting.book(c, filters)
    salt = '|'.join([str(filters.get('start', '')), str(filters.get('end', '')), str(filters.get('branch_id', '')), str(pct)])
    elegidas = []
    universo = 0
    muestra = 0
    tarjetas = 0
    rtns = 0
    fiscales = 0
    voided = 0
    for invoice in data['invoices']:
        if invoice['status'] == 'ANULADA':
            voided += 1
            continue
        if invoice['status'] != 'EMITIDA':
            continue
        if invoice['fiscal_number']:
            motivo = 'FISCAL'
            fiscales += 1
        elif invoice['payments'].get('Tarjeta', 0) > 0:
            motivo = 'TARJETA'
            tarjetas += 1
        elif invoice['invoice_type'] == 'RTN' or (invoice['customer_rtn'] or '').strip():
            motivo = 'RTN'
            rtns += 1
        elif invoice['fiscal_number'] and con_fiscal:
            motivo = 'FISCAL'
            fiscales += 1
        else:
            universo += 1
            if not elegida(f"{salt}|{invoice['id']}", pct):
                continue
            motivo = 'MUESTRA'
            muestra += 1
        elegidas.append((invoice, motivo))
    rows = []
    total15 = 0
    total18 = 0
    unknown = 0
    for invoice, motivo in elegidas:
        a, b = (invoice['taxable_15'], invoice['taxable_18'])
        net = None if a is None or b is None else a + b
        if net is None:
            unknown += 1
        else:
            total15 += a
            total18 += b
        rows.append(dict(pago=invoice['payment_method'], tarjeta=invoice['payments'].get('Tarjeta', 0), envio=invoice['delivery_fee'], id=invoice['id'], fecha=invoice['created_at'], sucursal=invoice['branch_name'], factura=invoice['fiscal_number'] or 'INTERNO-' + str(invoice['number']), cliente=invoice['customer_name'], rtn=invoice['customer_rtn'], motivo=motivo, gravado_15=a, gravado_18=b, total_gravado_sin_impuesto=net, documento_fiscal=bool(invoice['fiscal_number'])))
    return dict(rows=rows, gravado_15=total15, gravado_18=total18, total_gravado_sin_impuesto=total15 + total18, incompletos=unknown, anuladas_excluidas=voided, incluidas_tarjeta=tarjetas, incluidas_rtn=rtns, incluidas_fiscal=fiscales, incluir_fiscal=con_fiscal, muestra_pct=pct, muestra_resto=muestra, universo_resto=universo, filters=data['filters'], generated_at=data['generated_at'])

def excel(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    w = Workbook()
    summary = w.active
    summary.title = 'INFORMES SAR'
    summary.append(['Concepto', 'Valor'])
    for name, key in [('Venta gravada 15% sin ISV', 'gravado_15'), ('Venta gravada 18% sin ISV', 'gravado_18'), ('TOTAL VENTA GRAVADA SIN IMPUESTO', 'total_gravado_sin_impuesto')]:
        summary.append([name, Decimal(data[key]) / 100])
        summary.cell(summary.max_row, 2).number_format = '#,##0.00'
    summary.append(['Criterio de inclusión', 'Todas las facturas fiscales emitidas para los filtros seleccionados'])
    summary.append(['Porcentaje de muestra', '%d%%' % data['muestra_pct']])
    summary.append(['Universo del resto elegible para muestreo', data['universo_resto']])
    summary.append(['Ventas incluidas por muestreo', data['muestra_resto']])
    summary.append(['Facturas incluidas por tarjeta', data['incluidas_tarjeta']])
    summary.append(['Facturas incluidas por RTN', data['incluidas_rtn']])
    summary.append(['Facturas incluidas por ser fiscales', data['incluidas_fiscal']])
    summary.append(['Facturas emitidas en el informe', len(data['rows'])])
    summary.append(['Anuladas excluidas', data['anuladas_excluidas']])
    summary.append(['Desgloses incompletos excluidos de las sumas', data['incompletos']])
    summary.append(['Desde', data['filters'].get('start', '')])
    summary.append(['Hasta', data['filters'].get('end', '')])
    sheet = w.create_sheet('Detalle sin impuesto')
    sheet.append(['Fecha', 'Sucursal', 'Factura', 'Cliente', 'RTN', 'MOTIVO', 'Base gravada 15% sin ISV L', 'Base gravada 18% sin ISV L', 'TOTAL GRAVADO SIN IMPUESTO L', 'Forma de pago', 'Cobrado con tarjeta L', 'Envío separado L'])
    for r in data['rows']:
        sheet.append([r['fecha'], r['sucursal'], r['factura'], r['cliente'], r['rtn'], r['motivo']] + [None if r[k] is None else Decimal(r[k]) / 100 for k in ['gravado_15', 'gravado_18', 'total_gravado_sin_impuesto']] + [r['pago'], Decimal(r['tarjeta']) / 100, Decimal(r['envio']) / 100])
        for cell in list(sheet[sheet.max_row][6:9]) + list(sheet[sheet.max_row][10:12]):
            cell.number_format = '#,##0.00'
    for sh in w:
        sh.freeze_panes = 'A2'
        sh.auto_filter.ref = sh.dimensions
        for row in sh:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
        for cell in sh[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='18252A')
        for col in sh.columns:
            sh.column_dimensions[col[0].column_letter].width = 28 if sh == sheet else 48
    out = io.BytesIO()
    w.save(out)
    out.seek(0)
    return out

def pdf(data):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=26, bottomMargin=26)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('sar-small', fontSize=8, leading=10)
    fmt = lambda n: 'NO DISPONIBLE' if n is None else f'L {Decimal(n) / 100:,.2f}'
    story = [Paragraph('INFORMES SAR — SELECCIÓN DE BASES GRAVADAS', styles['Heading2']), Paragraph(escape(accounting.filter_text(data['filters'])), small), Spacer(1, 12)]
    for title, key in [('Base gravada 15% sin ISV', 'gravado_15'), ('Base gravada 18% sin ISV', 'gravado_18'), ('TOTAL VENTA GRAVADA SIN IMPUESTO', 'total_gravado_sin_impuesto')]:
        story.append(Paragraph(title + ': ' + fmt(data[key]), styles['Normal']))
    story += [Spacer(1, 8), Paragraph(f"Facturas: {len(data['rows'])}. Anuladas excluidas: {data['anuladas_excluidas']}. Desgloses incompletos excluidos de sumas: {data['incompletos']}.", small), Paragraph('Incluye todas las facturas fiscales emitidas para los filtros seleccionados. Las bases corresponden a los importes netos después del descuento, sin ISV ni envío.', small), Spacer(1, 12)]
    grid = [['Fecha', 'Sucursal', 'Factura', 'Cliente / RTN', 'MOTIVO', 'Gravado 15%\nsin ISV', 'Gravado 18%\nsin ISV', 'TOTAL GRAVADO\nSIN IMPUESTO']]
    for r in data['rows']:
        grid.append([r['fecha'], r['sucursal'], r['factura'], r['cliente'] + ' / ' + r['rtn'] + ' / ' + r['pago'], r['motivo'], fmt(r['gravado_15']), fmt(r['gravado_18']), fmt(r['total_gravado_sin_impuesto'])])
    grid = [[Paragraph(escape(str(v)).replace('\n', '<br/>'), small) for v in row] for row in grid]
    table = Table(grid, colWidths=[70, 86, 120, 150, 74, 80, 80, 86], repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8edef')), ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.lightgrey), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.append(table)
    doc.build(story)
    out.seek(0)
    return out

def register(app, connect):

    @app.get('/api/accounting/sar')
    def sar_report():
        with connect() as c:
            c.execute('BEGIN')
            return jsonify(collect(c, request.args))

    @app.get('/api/accounting/sar/export/<kind>')
    def sar_export(kind):
        if kind not in ['pdf', 'xlsx']:
            raise ValueError('Formato no permitido')
        with connect() as c:
            c.execute('BEGIN')
            data = collect(c, request.args)
        content = pdf(data) if kind == 'pdf' else excel(data)
        with connect() as c:
            accounting.audit(c, 'EXPORTACION_INFORME_SAR', kind, dict(filters=data['filters'], rows=len(data['rows']), muestra=data['muestra_pct'], muestra_resto=data['muestra_resto'], universo=data['universo_resto'], incluir_fiscal=data['incluir_fiscal']))
        return send_file(content, as_attachment=True, download_name='INFORMES-SAR-SELECCION-SIN-IMPUESTO.' + kind, mimetype='application/pdf' if kind == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
