"""
Generatore PDF per il Verbale di Incongruenze POS-PSC
e per i Report di Verifica PSC/POS.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from datetime import datetime
import os

# ── Colori ──────────────────────────────────────────────────────────────────
NAVY    = colors.HexColor('#1A3A5C')
GOLD    = colors.HexColor('#C88B2A')
GREY    = colors.HexColor('#5A6B7D')
RED     = colors.HexColor('#C0392B')
ORANGE  = colors.HexColor('#E67E22')
GREEN   = colors.HexColor('#27AE60')
BGRED   = colors.HexColor('#FDEDEC')
BGORANGE= colors.HexColor('#FEF9E7')
BGGREEN = colors.HexColor('#EAFAF1')
WHITE   = colors.white

SEV_COLOR = {
    "CRITICO":    (RED,    BGRED,    "🔴"),
    "IMPORTANTE": (ORANGE, BGORANGE, "🟡"),
    "CONSIGLIO":  (GREEN,  BGGREEN,  "🟢"),
}

def _build_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle('T', parent=styles['Normal'],
            fontSize=16, fontName='Helvetica-Bold',
            textColor=WHITE, alignment=TA_CENTER, spaceAfter=4),
        "subtitle": ParagraphStyle('Sub', parent=styles['Normal'],
            fontSize=9, textColor=GREY, alignment=TA_CENTER,
            italic=True, spaceAfter=12),
        "h1": ParagraphStyle('H1', parent=styles['Normal'],
            fontSize=12, fontName='Helvetica-Bold',
            textColor=NAVY, spaceBefore=14, spaceAfter=4),
        "h2": ParagraphStyle('H2', parent=styles['Normal'],
            fontSize=10, fontName='Helvetica-Bold',
            textColor=NAVY, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle('B', parent=styles['Normal'],
            fontSize=9, leading=13, spaceAfter=4),
        "body_j": ParagraphStyle('BJ', parent=styles['Normal'],
            fontSize=9, leading=13, alignment=TA_JUSTIFY, spaceAfter=4),
        "small": ParagraphStyle('S', parent=styles['Normal'],
            fontSize=7.5, textColor=GREY, italic=True),
        "label": ParagraphStyle('L', parent=styles['Normal'],
            fontSize=8.5, fontName='Helvetica-Bold', textColor=GREY),
        "code": ParagraphStyle('C', parent=styles['Normal'],
            fontSize=8, fontName='Courier', textColor=NAVY,
            backColor=colors.HexColor('#F5F5F5'), leftIndent=8),
        "warn": ParagraphStyle('W', parent=styles['Normal'],
            fontSize=8, textColor=RED, italic=True, spaceAfter=4),
    }


def _header_table(doc_canvas, doc_template):
    pass


def genera_verbale_incongruenze(
    incongruenze: list,
    pos_filename: str,
    psc_filename: str,
    nome_cantiere: str,
    output_dir: str,
) -> str:
    """Genera il Verbale di Incongruenze POS-PSC in formato PDF."""

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = nome_cantiere.replace(" ", "_")[:25]
    path = os.path.join(output_dir, f"Verbale_Incongruenze_{safe_name}_{ts}.pdf")

    doc = SimpleDocTemplate(path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm)

    S = _build_styles()
    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    header = Table([[
        Paragraph("VERBALE DI INCONGRUENZE POS-PSC", S["title"])
    ]], colWidths=[17*cm])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(header)
    story.append(Paragraph(
        f"ai sensi dell'Art. 100-101 — D.Lgs. 81/2008 — Allegato XV",
        S["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD))
    story.append(Spacer(1, 0.4*cm))

    # ── Riquadro dati ────────────────────────────────────────────────────────
    data_info = [
        ["Cantiere:", nome_cantiere, "Data verifica:", datetime.now().strftime("%d/%m/%Y %H:%M")],
        ["PSC di riferimento:", psc_filename, "POS analizzato:", pos_filename],
    ]
    t_info = Table(data_info, colWidths=[3*cm, 6.5*cm, 3.5*cm, 4*cm])
    t_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F9FA')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 0.4*cm))

    # ── Conteggio per severità ───────────────────────────────────────────────
    critici    = [i for i in incongruenze if i.get("severita") == "CRITICO"]
    importanti = [i for i in incongruenze if i.get("severita") == "IMPORTANTE"]
    consigli   = [i for i in incongruenze if i.get("severita") == "CONSIGLIO"]
    validate   = [i for i in incongruenze if i.get("validata")]
    non_valid  = [i for i in incongruenze if not i.get("validata")]

    riepilogo = [
        ["🔴 Incongruenze CRITICHE", str(len(critici)), RED],
        ["🟡 Incongruenze IMPORTANTI", str(len(importanti)), ORANGE],
        ["🟢 Consigli", str(len(consigli)), GREEN],
        ["✅ Validate dall'utente", str(len(validate)), NAVY],
        ["⏳ Da validare", str(len(non_valid)), GREY],
    ]
    t_riepilogo = Table(
        [[Paragraph(r[0], S["body"]), Paragraph(f"<b>{r[1]}</b>", S["body"])]
         for r in riepilogo],
        colWidths=[13*cm, 4*cm])
    t_riepilogo.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [WHITE, colors.HexColor('#F8F9FA')]),
    ]))

    story.append(Paragraph("RIEPILOGO INCONGRUENZE", S["h1"]))
    story.append(t_riepilogo)
    story.append(Spacer(1, 0.5*cm))

    # ── Incongruenze dettagliate ─────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("DETTAGLIO INCONGRUENZE", S["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    story.append(Spacer(1, 0.3*cm))

    for idx, inc in enumerate(incongruenze, 1):
        sev = inc.get("severita", "CONSIGLIO")
        col_testo, col_bg, emoji = SEV_COLOR.get(sev, (GREY, WHITE, "⚪"))
        validata = inc.get("validata", False)

        badge_sev = Table([[Paragraph(f"{emoji} {sev}", ParagraphStyle(
            'badge', parent=_build_styles()["body"],
            fontSize=8, fontName='Helvetica-Bold', textColor=WHITE
        ))]], colWidths=[3*cm])
        badge_sev.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), col_testo),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))

        stato_label = "✅ VALIDATA" if validata else "⏳ DA VALIDARE"
        stato_color = GREEN if validata else GREY

        items = [
            [Paragraph(f"<b>#{idx} — {inc.get('id','?')} — {inc.get('elemento','')}</b>",
                       S["h2"]), badge_sev],
        ]
        t_header_inc = Table(items, colWidths=[12.5*cm, 4.5*cm])
        t_header_inc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), col_bg),
            ('PADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.3, col_testo),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))

        body_rows = [
            ["Descrizione:", inc.get("descrizione", "—")],
            ["Nel PSC:", inc.get("valore_psc", "—")],
            ["Nel POS:", inc.get("valore_pos", "—")],
            ["Sezione POS da modificare:", inc.get("sezione_pos_da_modificare", "—")],
            ["Modifica richiesta:", inc.get("modifica_richiesta", "—")],
        ]
        if inc.get("nota_utente"):
            body_rows.append(["Nota del professionista:", inc["nota_utente"]])

        t_body = Table([
            [Paragraph(f"<b>{r[0]}</b>", S["label"]),
             Paragraph(str(r[1]), S["body_j"])]
            for r in body_rows
        ], colWidths=[4*cm, 13*cm])
        t_body.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
            ('PADDING', (0,0), (-1,-1), 5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [WHITE, colors.HexColor('#FAFAFA')]),
        ]))

        stato_row = Table([[
            Paragraph(f"Stato: <b><font color='{'#27AE60' if validata else '#8A9BB0'}'>{stato_label}</font></b>",
                      S["body"])
        ]], colWidths=[17*cm])
        stato_row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F0F0F0')),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))

        story.append(KeepTogether([
            t_header_inc,
            t_body,
            stato_row,
            Spacer(1, 0.4*cm)
        ]))

    # ── Dichiarazione finale ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("DICHIARAZIONE E FIRME", S["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Il presente Verbale documenta le incongruenze rilevate tra il Piano Operativo di Sicurezza "
        f"({pos_filename}) e il Piano di Sicurezza e Coordinamento ({psc_filename}) "
        f"per il cantiere '{nome_cantiere}'. "
        "Le modifiche validate dal professionista devono essere recepite nel POS e trasmesse "
        "al CSE prima dell'inizio delle lavorazioni ai sensi dell'art. 101 D.Lgs. 81/2008.",
        S["body_j"]))
    story.append(Spacer(1, 1*cm))

    firme = [
        ["Il CSE / Coordinatore:", "", "Il Datore di Lavoro (impresa):"],
        ["Nome: ______________________", "", "Nome: ______________________"],
        ["Firma: _____________________", "", "Firma: _____________________"],
        [f"Data: {datetime.now().strftime('%d/%m/%Y')}", "", "Data: _____________________"],
    ]
    t_firme = Table(firme, colWidths=[6.5*cm, 4*cm, 6.5*cm])
    t_firme.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_firme)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "⚠ Documento generato automaticamente da SafetyDocs come supporto al professionista. "
        "Deve essere verificato e firmato dal CSE e dal Datore di Lavoro prima dell'utilizzo.",
        S["warn"]))

    doc.build(story)
    return path


def genera_report_verifica(
    risultato: dict,
    tipo_documento: str,
    output_dir: str,
) -> str:
    """Genera il Report di Verifica PSC o POS in formato PDF."""

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_file = risultato.get("nome_file", "documento").replace(".", "_")[:30]
    path = os.path.join(output_dir, f"Report_Verifica_{tipo_documento}_{nome_file}_{ts}.pdf")

    doc = SimpleDocTemplate(path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm)

    S = _build_styles()
    story = []
    nc = risultato.get("non_conformita", [])
    pc = risultato.get("punti_conformi", [])
    rie = risultato.get("riepilogo", {})
    punteggio = risultato.get("punteggio_conformita", 0)
    giudizio = risultato.get("giudizio_sintetico", "—")

    # ── Header ──────────────────────────────────────────────────────────────
    header = Table([[
        Paragraph(f"REPORT DI VERIFICA {tipo_documento.upper()}", S["title"])
    ]], colWidths=[17*cm])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('PADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(header)
    story.append(Paragraph(
        "Verifica conformità ai sensi del D.Lgs. 81/2008 — Allegato XV — Aggiornato Marzo 2026",
        S["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD))
    story.append(Spacer(1, 0.4*cm))

    # ── Info documento ───────────────────────────────────────────────────────
    t_info = Table([
        ["File analizzato:", risultato.get("nome_file", "—"),
         "Data:", risultato.get("data_verifica", "—")],
        ["Impresa:", risultato.get("impresa", "—"),
         "Tipo doc.:", tipo_documento],
    ], colWidths=[3.5*cm, 6*cm, 2.5*cm, 5*cm])
    t_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F9FA')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 0.4*cm))

    # ── Giudizio sintetico ───────────────────────────────────────────────────
    giu_color = {"CONFORME": GREEN, "NON CONFORME": RED,
                 "CONFORME CON RISERVE": ORANGE}.get(giudizio, GREY)
    bar_color = GREEN if punteggio >= 80 else (ORANGE if punteggio >= 60 else RED)

    t_giudizio = Table([[
        Paragraph(f"<b>GIUDIZIO: {giudizio}</b>",
                  ParagraphStyle('G', parent=S["body"], fontSize=13,
                                 textColor=WHITE, fontName='Helvetica-Bold')),
        Paragraph(f"<b>CONFORMITÀ: {punteggio}%</b>",
                  ParagraphStyle('P', parent=S["body"], fontSize=13,
                                 textColor=WHITE, fontName='Helvetica-Bold',
                                 alignment=TA_RIGHT)),
    ]], colWidths=[9*cm, 8*cm])
    t_giudizio.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), giu_color),
        ('BACKGROUND', (1,0), (1,0), bar_color),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_giudizio)
    story.append(Spacer(1, 0.3*cm))

    # ── Riepilogo numerico ───────────────────────────────────────────────────
    t_riepilogo = Table([
        [
            Paragraph(f"🔴 CRITICI\n<b>{rie.get('critici',0)}</b>",
                      ParagraphStyle('rc', parent=S["body"], alignment=TA_CENTER, textColor=RED)),
            Paragraph(f"🟡 IMPORTANTI\n<b>{rie.get('importanti',0)}</b>",
                      ParagraphStyle('ro', parent=S["body"], alignment=TA_CENTER, textColor=ORANGE)),
            Paragraph(f"🟢 CONSIGLI\n<b>{rie.get('consigli',0)}</b>",
                      ParagraphStyle('rg', parent=S["body"], alignment=TA_CENTER, textColor=GREEN)),
            Paragraph(f"✅ CONFORMI\n<b>{rie.get('conformi',0)}</b>",
                      ParagraphStyle('rn', parent=S["body"], alignment=TA_CENTER, textColor=NAVY)),
        ]
    ], colWidths=[4.25*cm]*4)
    t_riepilogo.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,0), BGRED),
        ('BACKGROUND', (1,0), (1,0), BGORANGE),
        ('BACKGROUND', (2,0), (2,0), BGGREEN),
        ('BACKGROUND', (3,0), (3,0), colors.HexColor('#EAF4FB')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_riepilogo)
    story.append(Spacer(1, 0.5*cm))

    # ── Non conformità ───────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("NON CONFORMITÀ RILEVATE", S["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    story.append(Spacer(1, 0.3*cm))

    for sev_filter in ["CRITICO", "IMPORTANTE", "CONSIGLIO"]:
        filtrati = [n for n in nc if n.get("severita") == sev_filter]
        if not filtrati:
            continue

        col_testo, col_bg, emoji = SEV_COLOR[sev_filter]
        story.append(Paragraph(f"{emoji} {sev_filter} ({len(filtrati)})", S["h2"]))

        for item in filtrati:
            rows = [
                ["Sezione:", item.get("sezione", "—")],
                ["Norma violata:", item.get("norma_violata", "—")],
                ["Sanzione:", item.get("sanzione_applicabile") or "—"],
                ["Testo trovato:", item.get("testo_trovato", "ASSENTE")],
                ["Testo corretto:", item.get("testo_corretto", "—")],
            ]
            t_item = Table([
                [Paragraph(f"<b>{item.get('id','?')}</b> — " +
                           item.get("descrizione", ""), S["body"]),
                 Paragraph(f"<b>{emoji} {sev_filter}</b>",
                           ParagraphStyle('sv', parent=S["body"],
                                          textColor=col_testo, alignment=TA_RIGHT))],
                *[[Paragraph(f"<b>{r[0]}</b>", S["label"]),
                   Paragraph(str(r[1]), S["body_j"])] for r in rows]
            ], colWidths=[14*cm, 3*cm])
            t_item.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), col_bg),
                ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDDDDD')),
                ('SPAN', (0,1), (-1,1)) if False else ('PADDING', (0,0), (-1,-1), 5),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(t_item)
            story.append(Spacer(1, 0.25*cm))

    # ── Punti conformi ───────────────────────────────────────────────────────
    if pc:
        story.append(PageBreak())
        story.append(Paragraph("REQUISITI CONFORMI", S["h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=GREEN))
        story.append(Spacer(1, 0.2*cm))
        for item in pc:
            story.append(Paragraph(
                f"✅ <b>{item.get('id','?')}</b> — {item.get('sezione','')}: {item.get('descrizione','')}",
                S["body"]))

    # ── Note aggiuntive ──────────────────────────────────────────────────────
    if risultato.get("note_aggiuntive"):
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("NOTE DELL'ISPETTORE AI", S["h1"]))
        story.append(Paragraph(risultato["note_aggiuntive"], S["body_j"]))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        f"Report generato il {datetime.now().strftime('%d/%m/%Y %H:%M')} da SafetyDocs — "
        "Verifica automatica. Deve essere revisionata da un professionista abilitato prima dell'utilizzo.",
        S["warn"]))

    doc.build(story)
    return path
