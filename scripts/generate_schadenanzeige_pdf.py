#!/usr/bin/env python3
"""Generate the standard German food poisoning claim form PDF for the persona bundle."""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_pdf():
    assets_dir = Path(__file__).resolve().parent.parent / "coworker" / "personas" / "builtin" / "gastro-worker" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = assets_dir / "schadenanzeige_lebensmittelvergiftung.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1e293b"),
        alignment=1, # Center
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        "SubTitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        alignment=1,
        spaceAfter=15
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )
    bold_cell_style = ParagraphStyle(
        "BoldCellText",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e293b")
    )

    story = []

    # Header
    story.append(Paragraph("SCHADENANZEIGE", title_style))
    story.append(Paragraph("Verdacht auf Lebensmittelvergiftung / Lebensmittelbedingte Infektion<br/>(Betriebshaftpflichtversicherung)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15))

    # Section 1: Claimant information
    story.append(Paragraph("1. Angaben zur anspruchstellenden Person (Gast)", section_style))
    data1 = [
        [Paragraph("Name, Vorname:", bold_cell_style), Paragraph("________________________________________________", cell_style)],
        [Paragraph("Straße, Hausnr.:", bold_cell_style), Paragraph("________________________________________________", cell_style)],
        [Paragraph("PLZ, Wohnort:", bold_cell_style), Paragraph("________________________________________________", cell_style)],
        [Paragraph("Telefon / E-Mail:", bold_cell_style), Paragraph("________________________________________________", cell_style)],
        [Paragraph("Krankenkasse:", bold_cell_style), Paragraph("________________________________________________", cell_style)],
    ]
    t1 = Table(data1, colWidths=[130, 390])
    t1.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # Section 2: Visit & Incident details
    story.append(Paragraph("2. Angaben zum Restaurantbesuch & Verzehr", section_style))
    data2 = [
        [Paragraph("Datum & Uhrzeit des Besuchs:", bold_cell_style), Paragraph("Datum: ____ / ____ / 202___   Uhrzeit: ca. ____:____ Uhr", cell_style)],
        [Paragraph("Rechnungs- / Belegnummer:", bold_cell_style), Paragraph("Beleg-Nr.: ___________________ (Kopie bitte beifügen)", cell_style)],
        [Paragraph("Gesamtzahl Personen am Tisch:", bold_cell_style), Paragraph("Anzahl gesamt: _____ Personen | davon erkrankt: _____ Personen", cell_style)],
        [Paragraph("Verzehrte Speisen & Getränke:<br/><i>(Möglichst genaue Auflistung)</i>", bold_cell_style), 
         Paragraph("1. ________________________________________________<br/>2. ________________________________________________<br/>3. ________________________________________________", cell_style)],
    ]
    t2 = Table(data2, colWidths=[150, 370])
    t2.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # Section 3: Medical Symptoms & Treatment
    story.append(Paragraph("3. Angaben zu Beschwerden und ärztlicher Behandlung", section_style))
    data3 = [
        [Paragraph("Erste Symptome bemerkt am:", bold_cell_style), Paragraph("Datum: ____ / ____ / 202___   Uhrzeit: ca. ____:____ Uhr", cell_style)],
        [Paragraph("Art der Beschwerden:<br/><i>(Zutreffendes bitte ankreuzen)</i>", bold_cell_style), 
         Paragraph("[  ] Übelkeit / Erbrechen &nbsp;&nbsp;&nbsp;&nbsp; [  ] Fieber / Schüttelfrost<br/>[  ] Magenkrämpfe &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; [  ] Durchfall (wässrig / blutig)<br/>[  ] Kreislaufbeschwerden &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; [  ] Sonstiges: ____________________", cell_style)],
        [Paragraph("Behandelnder Arzt / Klinik:", bold_cell_style), Paragraph("Name / Praxis: _________________________________________<br/>Anschrift: _____________________________________________", cell_style)],
        [Paragraph("Krankenhausaufenthalt:", bold_cell_style), Paragraph("[  ] Nein &nbsp;&nbsp;&nbsp;&nbsp; [  ] Ja, von ____ / ____ bis ____ / ____ / 202___", cell_style)],
        [Paragraph("Arbeitsunfähigkeit (AU):", bold_cell_style), Paragraph("[  ] Nein &nbsp;&nbsp;&nbsp;&nbsp; [  ] Ja, voraussichtlich bis ____ / ____ / 202___", cell_style)],
    ]
    t3 = Table(data3, colWidths=[150, 370])
    t3.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t3)
    story.append(Spacer(1, 15))

    # Declaration & Signatures
    story.append(Paragraph("4. Erklärung und Unterschrift", section_style))
    notice = Paragraph(
        "Ich versichere die Richtigkeit und Vollständigkeit der vorstehenden Angaben. "
        "Mir ist bekannt, dass vorsätzlich unrichtige oder unvollständige Angaben zum Verlust des Versicherungsschutzes führen können. "
        "Ich entbinde die behandelnden Ärzte gegenüber der zuständigen Betriebshaftpflichtversicherung insoweit von der Schweigepflicht, "
        "wie dies zur Feststellung des Schadensereignisses und der Ursachen erforderlich ist.",
        ParagraphStyle("LegalNotice", parent=styles["Normal"], fontSize=7.5, leading=10, textColor=colors.HexColor("#64748b"))
    )
    story.append(notice)
    story.append(Spacer(1, 15))

    sig_data = [
        [Paragraph("___________________________________<br/>Ort, Datum", cell_style),
         Paragraph("___________________________________<br/>Unterschrift des Anspruchstellers", cell_style)]
    ]
    sig_table = Table(sig_data, colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(sig_table)

    doc.build(story)
    print(f"Generated PDF successfully at: {pdf_path}")

if __name__ == "__main__":
    generate_pdf()
