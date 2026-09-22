#!/usr/bin/env python3
"""
generate_pdf_guide.py
---------------------
Generates a professionally styled PDF guide with:
  - Clean spacing and page budgeting (no orphan lines or awkward table splits).
  - Complete omission/masking of sensitive credentials.
  - Prompts with explicit brand names (Hexoskin, Masimo, Somno-Art) visible on the shirts and devices.
"""

import sys
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

BASE_DIR = Path("C:/CPAP_Video_Server")
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)
PDF_PATH = DOCS_DIR / "CPAP_Wearables_Video_Ideas_and_Google_Veo_Prompts.pdf"


class CleanNumberedCanvas(canvas.Canvas):
    """Running header and footer canvas with accurate page numbering."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 748, "CPAP & Wearables Video Coaching Guide — Novel Problems & Google Veo Prompts")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 44, 558, 44)
        self.drawString(54, 32, "DISP Laboratory Lyon / Linde HomeCare France — CPAP Teletherapy Platform")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)

        self.restoreState()


def build_pdf():
    # 54pt (0.75 in) margins on letter (612 x 792 pt) -> Printable width = 504 pt
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0369a1"),
        spaceBefore=0,
        spaceAfter=2,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#0f172a")
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155")
    )

    card_text_style = ParagraphStyle(
        'CardText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=2
    )

    prompt_code_style = ParagraphStyle(
        'PromptCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#0f172a")
    )

    exec_callout_style = ParagraphStyle(
        'ExecCallout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b")
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, EXECUTIVE SUMMARY & DEVICE PROBLEM RESEARCH TABLE
    # =========================================================================
    story.append(Paragraph("CPAP & Wearables Video Coaching Guide", title_style))
    story.append(Paragraph("<b>Novel Patient Problem Definitions & Google Veo 3.1 Prompts</b> | Generated: " + datetime.now().strftime("%B %d, %Y"), subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceBefore=0, spaceAfter=8))

    exec_box = [
        [Paragraph(
            "<b>Document Scope & Purpose:</b> This guide analyzes patient troubleshooting manuals for three clinical wearables "
            "(<b>Hexoskin Smart Garment</b>, <b>Masimo MightySat Rx</b>, and <b>Somno-Art Armband</b>) to establish <b>10 new, "
            "non-duplicate video coaching topics</b>. It provides structured 10-second pacing breakdowns, bilingual (EN/FR) "
            "voiceovers, and production-ready <b>Google Veo prompt specifications</b> designed for 1080p Full HD clinical animations "
            "with clear brand-name labeling on shirts and devices. <i>(All credentials excluded).</i>",
            exec_callout_style
        )]
    ]
    t_exec = Table(exec_box, colWidths=[504])
    t_exec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#86efac")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_exec)
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. Device Guidance & Root-Cause Problem Identification", h1_style))
    story.append(Paragraph(
        "By reviewing the official user guides, the following mechanical, optical, and signal contact issues were identified during CPAP co-usage:",
        body_style
    ))

    dev_analysis = [
        [Paragraph("<b>Target Wearable</b>", table_header_style), Paragraph("<b>Key Troubleshooting Findings from User Guidance</b>", table_header_style)],
        [
            Paragraph("<b>Hexoskin Smart Garment</b><br/><i>(hexoskin.com/pages/start)</i>", table_cell_style),
            Paragraph(
                "• <b>Dry Textile Electrodes:</b> Dry textile electrodes cause weak ECG signals before sweat breaks.<br/>"
                "• <b>RIP Sensor Slack:</b> Movement wrinkles the dual bands, causing false hypopnea events.<br/>"
                "• <b>Connector Seating:</b> Failure to push connector firmly until the middle orange LED lights up solid.<br/>"
                "• <b>Garment Wash Care:</b> Unplugging device before washing; avoiding softeners that coat silver fibers.",
                table_cell_style
            )
        ],
        [
            Paragraph("<b>Masimo MightySat Rx</b><br/><i>(masimo.com/products/wearables/mightysatrx/)</i>", table_cell_style),
            Paragraph(
                "• <b>Low Perfusion Index (PI < 0.5%):</b> Cold fingers restrict capillary blood flow and cause dropouts.<br/>"
                "• <b>Nail Polish / Depth:</b> Dark nail polish and partial finger insertion block dual-wavelength LEDs.<br/>"
                "• <b>Signal I.Q. & Glare:</b> Direct bedside lamp glare drops Signal I.Q. confidence bars.",
                table_cell_style
            )
        ],
        [
            Paragraph("<b>Somno-Art Armband</b><br/><i>(somno-art.com)</i>", table_cell_style),
            Paragraph(
                "• <b>Forearm Fit & Optical Gap:</b> Band worn too loose lifts PPG sensor off skin; too tight constricts flow.<br/>"
                "• <b>1-Min Calibration Stillness:</b> Arm motion during 60s white-LED baseline causes orange LED failure.<br/>"
                "• <b>Pod Disinfection:</b> Removing electronic pod before washing textile sleeve; wiping optical window.",
                table_cell_style
            )
        ],
        [
            Paragraph("<b>CPAP Co-Usage Synergy</b><br/><i>(Integrated Co-Monitoring)</i>", table_cell_style),
            Paragraph(
                "• <b>Tubing Tension & Sensor Snagging:</b> CPAP air hose pulls on armbands when tossing and turning.<br/>"
                "• <b>Exhaust Air Noise:</b> Mask vent flow blowing onto chest sensors causes micro-vibration artifacts.",
                table_cell_style
            )
        ]
    ]
    t_dev = Table(dev_analysis, colWidths=[140, 364])
    t_dev.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t_dev)

    # Force clean page break to keep Section 2 (Summary Table) completely unified on Page 2
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: 10 NOVEL VIDEO CONCEPTS MAPPING TABLE
    # =========================================================================
    story.append(Paragraph("2. Master Summary: 10 Novel Video Coaching Concepts (Videos 28–37)", h1_style))
    story.append(Paragraph(
        "These 10 coaching modules directly target wearable troubleshooting and have <b>zero duplication</b> with existing library clips 1–27:",
        body_style
    ))
    story.append(Spacer(1, 4))

    summary_table_data = [
        [
            Paragraph("<b>#</b>", table_header_style),
            Paragraph("<b>Video Title & Domain</b>", table_header_style),
            Paragraph("<b>Clinical / Device Trigger</b>", table_header_style),
            Paragraph("<b>Actionable Solution</b>", table_header_style)
        ],
        [
            Paragraph("<b>28</b>", table_cell_style),
            Paragraph("Hexoskin: Electrode Moistening", table_cell_style),
            Paragraph("Noisy ECG / Weak Cardiac Baseline", table_cell_style),
            Paragraph("Apply drop of water/gel to 3 gray pads", table_cell_style)
        ],
        [
            Paragraph("<b>29</b>", table_cell_style),
            Paragraph("Hexoskin: Dual Elastic Straps", table_cell_style),
            Paragraph("Garment Wrinkling / RIP Sensor Shift", table_cell_style),
            Paragraph("Fasten chest & abdominal straps snugly", table_cell_style)
        ],
        [
            Paragraph("<b>30</b>", table_cell_style),
            Paragraph("Hexoskin: Recorder Docking Check", table_cell_style),
            Paragraph("Session Recording Not Initiated", table_cell_style),
            Paragraph("Push connector firmly until orange LED solid", table_cell_style)
        ],
        [
            Paragraph("<b>31</b>", table_cell_style),
            Paragraph("MightySat: Low Perfusion Warming", table_cell_style),
            Paragraph("Low Perfusion Index (PI < 0.5%)", table_cell_style),
            Paragraph("Rub hands together to warm fingers", table_cell_style)
        ],
        [
            Paragraph("<b>32</b>", table_cell_style),
            Paragraph("MightySat: Finger Insertion Depth", table_cell_style),
            Paragraph("Optical Blockage / Nail Obstruction", table_cell_style),
            Paragraph("Slide clean bare finger to internal stop", table_cell_style)
        ],
        [
            Paragraph("<b>33</b>", table_cell_style),
            Paragraph("MightySat: Signal I.Q. Shielding", table_cell_style),
            Paragraph("Low SIQ Bar / Direct Light Glare", table_cell_style),
            Paragraph("Rest hand flat, shield from lamp glare", table_cell_style)
        ],
        [
            Paragraph("<b>34</b>", table_cell_style),
            Paragraph("SomnoArt: Forearm PPG Seal", table_cell_style),
            Paragraph("Poor Optical PPG Skin Contact", table_cell_style),
            Paragraph("Position mid-forearm (1-finger clearance)", table_cell_style)
        ],
        [
            Paragraph("<b>35</b>", table_cell_style),
            Paragraph("SomnoArt: 1-Min Stillness Check", table_cell_style),
            Paragraph("Calibration Failure (Orange LEDs)", table_cell_style),
            Paragraph("Hold arm still 60s until solid green", table_cell_style)
        ],
        [
            Paragraph("<b>36</b>", table_cell_style),
            Paragraph("SomnoArt: Pod Care & Washing", table_cell_style),
            Paragraph("Lens Fogging / Pod Submersion", table_cell_style),
            Paragraph("Remove pod before wash, wipe lens", table_cell_style)
        ],
        [
            Paragraph("<b>37</b>", table_cell_style),
            Paragraph("Co-Usage: CPAP Hose Clearance", table_cell_style),
            Paragraph("Hose Pulling on Arm Wearables", table_cell_style),
            Paragraph("Route hose overhead behind pillow", table_cell_style)
        ]
    ]

    t_sum = Table(summary_table_data, colWidths=[24, 150, 160, 170])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#dbeafe")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#bfdbfe")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t_sum)
    story.append(Spacer(1, 10))

    prompt_rule_box = [
        [Paragraph(
            "<b>Google Veo 3.1 Prompting Formula (with Explicit Brand Labeling):</b><br/>"
            "• <b>Hexoskin:</b> <i>'wearing a black shirt with Hexoskin text on it'</i> / <i>'Hexoskin recording device'</i><br/>"
            "• <b>Masimo MightySat:</b> <i>'MightySat fingertip pulse oximeter with Masimo text on it'</i><br/>"
            "• <b>Somno-Art:</b> <i>'Somno-Art forearm armband with Somno-Art text on it'</i> / <i>'Somno-Art pod'</i><br/>"
            "• <b>Pacing & Audio:</b> <code>0-3s Alert -> 3-7s Hands-on Adjustment -> 7-10s Compliance | Calm female voiceover</code>",
            card_text_style
        )]
    ]
    t_prule = Table(prompt_rule_box, colWidths=[504])
    t_prule.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BORDER', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_prule)

    story.append(PageBreak())

    # =========================================================================
    # PAGES 3–7: 10 DETAILED VIDEO CARDS (EXACTLY 2 CARDS PER PAGE)
    # =========================================================================
    videos_data = [
        {
            "id": 28,
            "title": "Hexoskin — Cardiac Electrode Moistening & Prep",
            "file": "28_Hexoskin_Electrode_moistening_prep.mp4",
            "pacing": "<b>0:00-0:03:</b> Patient holds shirt; app alerts noisy ECG baseline.<br/><b>0:03-0:07:</b> Gently applies drop of moisture onto the 3 gray textile heart electrodes.<br/><b>0:07-0:10:</b> Puts shirt on; ECG waveform stabilizes into a clean rhythm.",
            "en_vo": "If cardiac signals are weak, apply a small drop of water or moisturizing cream to the three gray electrodes inside your shirt for optimal contact.",
            "fr_vo": "Si le signal cardiaque est faible, appliquez une goutte d'eau ou de crème hydratante sur les trois électrodes grises à l'intérieur du vêtement.",
            "veo_prompt": (
                "A stylized 3D animated character holding a black smart shirt with Hexoskin text on it in a warm bedroom setting. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character is preparing for sleep and holds the black shirt with Hexoskin text. The character gently applies a single drop of water onto the three gray textile heart electrodes inside the shirt to improve contact. The character smoothly puts the shirt on.\n"
                "Setting: Soft bedroom lighting, clean modern interior.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'If cardiac signals are weak, apply a small drop of water or moisturizing cream to the three gray electrodes inside your shirt for optimal contact.'"
            )
        },
        {
            "id": 29,
            "title": "Hexoskin — Dual Elastic Strap Adjustment",
            "file": "29_Hexoskin_Elastic_strap_adjustment.mp4",
            "pacing": "<b>0:00-0:03:</b> Patient turns in bed; loose fabric creates erratic breathing curves.<br/><b>0:03-0:07:</b> Sits up and fastens upper chest & lower abdominal elastic straps snugly.<br/><b>0:07-0:10:</b> Lying down; smooth synchronized thoracic & abdominal breathing waves appear.",
            "en_vo": "Fasten the chest and abdominal elastic straps snugly over your shirt to prevent sensor shifting and ensure accurate breathing tracking.",
            "fr_vo": "Ajustez les sangles élastiques sur la poitrine et l'abdomen pour maintenir les capteurs bien en place et fiabiliser les données respiratoires.",
            "veo_prompt": (
                "A stylized 3D animated character wearing a black shirt with Hexoskin text on it in a warm bedroom setting. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character sits on the edge of the bed and fastens the upper chest elastic strap and lower abdominal strap over the shirt. The character pulls the straps evenly to smooth out all wrinkles and ensure the breathing sensors rest firmly against the ribs. The character breathes in and out comfortably.\n"
                "Setting: Soft bedroom lighting, clean modern interior.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Fasten the chest and abdominal elastic straps snugly over your shirt to prevent sensor shifting and ensure accurate breathing tracking.'"
            )
        },
        {
            "id": 30,
            "title": "Hexoskin — Device Docking & Orange LED Check",
            "file": "30_Hexoskin_Recorder_docking_led_check.mp4",
            "pacing": "<b>0:00-0:03:</b> Device placed loosely in side pocket; recording not initiated.<br/><b>0:03-0:07:</b> Firmly snaps connector into socket; middle orange LED lights up solid.<br/><b>0:07-0:10:</b> Tucks recorder neatly into side pocket with cable loop secure.",
            "en_vo": "Firmly plug the recording device into the garment connector until the middle orange light turns solid, confirming your session is recording.",
            "fr_vo": "Enclenchez fermement le boîtier sur le connecteur du vêtement jusqu'à ce que le voyant orange reste allumé en continu.",
            "veo_prompt": (
                "A stylized 3D animated character wearing a black shirt with Hexoskin text on it in a warm bedroom setting. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character takes the Hexoskin recording device and firmly snaps the shirt connector into the device socket until it clicks. The middle orange LED light illuminates solid and steady, confirming recording is active. The character neatly tucks the device into the side pocket.\n"
                "Setting: Bedside table in a cozy modern bedroom, soft warm lighting.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Firmly plug the recording device into the garment connector until the middle orange light turns solid, confirming your session is recording.'"
            )
        },
        {
            "id": 31,
            "title": "MightySat Rx — Low Perfusion (PI) Hand Warming",
            "file": "31_MightySat_Low_perfusion_hand_warming.mp4",
            "pacing": "<b>0:00-0:03:</b> Oximeter shows low blood flow (PI 0.2%) with weak signal bar.<br/><b>0:03-0:07:</b> Patient removes sensor and rubs palms together vigorously to warm fingers.<br/><b>0:07-0:10:</b> Re-inserts middle finger; display shows robust PI 2.8% and steady 98% SpO2.",
            "en_vo": "If your Perfusion Index is low, warm your hands by rubbing them together for a moment to improve blood flow before placing the sensor.",
            "fr_vo": "Si l'indice de perfusion est faible, réchauffez vos mains en les frottant pour stimuler la circulation avant de placer le capteur.",
            "veo_prompt": (
                "A stylized 3D animated character sitting in a warm bedroom setting holding a MightySat pulse oximeter with Masimo text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character looks at the MightySat fingertip pulse oximeter showing low blood flow. The character removes the sensor and vigorously rubs both palms together for a few seconds to warm their hands. The character places the device back on the middle finger; the screen now displays a strong pulse bar and healthy 98% oxygen reading.\n"
                "Setting: Soft warm bedside lamp, cozy modern bedroom.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'If your Perfusion Index is low, warm your hands by rubbing them together for a moment to improve blood flow before placing the sensor.'"
            )
        },
        {
            "id": 32,
            "title": "MightySat Rx — Finger Insertion Depth & Nail Prep",
            "file": "32_MightySat_Finger_depth_nail_prep.mp4",
            "pacing": "<b>0:00-0:03:</b> Sensor partially inserted shows fluctuating pulse wave.<br/><b>0:03-0:07:</b> Slides clean bare finger fully inside until touching internal stop.<br/><b>0:07-0:10:</b> Smooth arterial plethysmograph waveform appears with immediate lock.",
            "en_vo": "Insert your finger completely until it touches the internal stop on a clean, unpolished nail for precise oxygen readings.",
            "fr_vo": "Insérez votre doigt jusqu'au fond de l'appareil sur un ongle propre et sans vernis pour une mesure précise de l'oxygène.",
            "veo_prompt": (
                "Close-up shot of a stylized 3D animated character's hands using a MightySat pulse oximeter with Masimo text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character slides their bare, clean index finger all the way into the MightySat fingertip sensor until it touches the internal stop. The optical sensor aligns directly over the center of the finger pad. The display shows a smooth, continuous arterial pulse wave.\n"
                "Setting: Bedside table with warm soft lighting.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Insert your finger completely until it touches the internal stop on a clean, unpolished nail for precise oxygen readings.'"
            )
        },
        {
            "id": 33,
            "title": "MightySat Rx — Signal I.Q. & Ambient Light Shielding",
            "file": "33_MightySat_Signal_iq_light_shielding.mp4",
            "pacing": "<b>0:00-0:03:</b> Direct bright bedside lamp glare causes Signal I.Q. bar to drop.<br/><b>0:03-0:07:</b> Dims direct lamp and rests forearm flat & completely still on mattress.<br/><b>0:07-0:10:</b> Signal I.Q. vertical confidence bar reaches full 100% height.",
            "en_vo": "Rest your hand flat and stay still for a few seconds away from direct bright light until the Signal I.Q. bar peaks.",
            "fr_vo": "Posez votre main à plat, restez immobile et évitez la lumière directe jusqu'à ce que la barre de signal atteigne son niveau maximal.",
            "veo_prompt": (
                "A stylized 3D animated character resting in bed wearing a MightySat fingertip pulse oximeter with Masimo text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character's hand is resting under a bright bedside lamp causing signal interference. The character dims the direct lamp and rests their hand flat and completely still on the mattress. The vertical Signal I.Q. confidence bar on the Masimo oximeter rises to maximum height.\n"
                "Setting: Peaceful, dimmed bedroom environment.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Rest your hand flat and stay still for a few seconds away from direct bright light until the Signal I.Q. bar peaks.'"
            )
        },
        {
            "id": 34,
            "title": "Somno-Art — Forearm Placement & Optical PPG Seal",
            "file": "34_SomnoArt_Forearm_positioning_ppg_seal.mp4",
            "pacing": "<b>0:00-0:03:</b> Loose armband on wrist slips; app indicates poor optical contact.<br/><b>0:03-0:07:</b> Moves band to mid-forearm, adjusting Velcro snugly (1-finger test).<br/><b>0:07-0:10:</b> PPG optical sensor sits securely flush against skin with green light.",
            "en_vo": "Position the armband on your mid-forearm with a snug, comfortable fit so the optical sensor rests firmly against clean skin.",
            "fr_vo": "Placez le brassard au milieu de l'avant-bras avec un ajustement souple pour que le capteur optique adhère bien à la peau.",
            "veo_prompt": (
                "A stylized 3D animated character in a bedroom setting putting on an armband with Somno-Art text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character slides the Somno-Art armband onto their mid-forearm, halfway between the elbow and wrist. The character adjusts the soft Velcro strap so the optical sensor sits flat and flush against clean skin. The character slides one finger under the band to confirm it is snug and comfortable.\n"
                "Setting: Soft bedroom lighting, clean modern interior.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Position the armband on your mid-forearm with a snug, comfortable fit so the optical sensor rests firmly against clean skin.'"
            )
        },
        {
            "id": 35,
            "title": "Somno-Art — 1-Minute Calibration Stillness Check",
            "file": "35_SomnoArt_Calibration_stillness_led_check.mp4",
            "pacing": "<b>0:00-0:03:</b> Power button pressed (2s); white LEDs flash in calibration mode.<br/><b>0:03-0:07:</b> Patient rests forearm completely still on pillow for 60 seconds.<br/><b>0:07-0:10:</b> All LEDs illuminate solid green for 4 seconds, confirming calibration.",
            "en_vo": "After turning on your Somno-Art, keep your arm completely still for one minute until the lights turn solid green.",
            "fr_vo": "Après avoir allumé votre Somno-Art, gardez le bras totalement immobile pendant une minute jusqu'à ce que les voyants deviennent verts.",
            "veo_prompt": (
                "A stylized 3D animated character sitting relaxed in bed wearing an armband with Somno-Art text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character presses the power button on the Somno-Art pod. The white LED lights begin flashing to start calibration. The character rests their arm completely still on the pillow without moving. After a moment, all LEDs light up in a solid green glow for 4 seconds, confirming calibration is complete.\n"
                "Setting: Cozy, quiet bedroom setting with soft warm night lighting.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'After turning on your Somno-Art, keep your arm completely still for one minute until the lights turn solid green.'"
            )
        },
        {
            "id": 36,
            "title": "Somno-Art — Pod Removal & Textile Sleeve Care",
            "file": "36_SomnoArt_Pod_care_sleeve_washing.mp4",
            "pacing": "<b>0:00-0:03:</b> Patient slides electronic pod out of fabric armband sleeve.<br/><b>0:03-0:07:</b> Places fabric sleeve in wash bag; gently wipes optical glass window with cloth.<br/><b>0:07-0:10:</b> Clean pod and fresh sleeve assembled ready for bedtime recording.",
            "en_vo": "Always remove the electronic pod before washing the textile sleeve, and clean the optical sensor with a gentle wipe.",
            "fr_vo": "Retirez toujours le boîtier électronique avant de laver le brassard textile et nettoyez le capteur optique avec une lingette douce.",
            "veo_prompt": (
                "Close-up shot of a stylized 3D animated character's hands handling a fabric sleeve and a small pod with Somno-Art text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character gently slides the small electronic recording pod out of the Somno-Art fabric armband sleeve. The character places the fabric sleeve into a gentle laundry bag, and takes a soft disinfectant wipe to gently clean the glass optical sensor on the electronic pod.\n"
                "Setting: Clean modern nightstand table with bright soft lighting.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Always remove the electronic pod before washing the textile sleeve, and clean the optical sensor with a gentle wipe.'"
            )
        },
        {
            "id": 37,
            "title": "Co-Usage — CPAP Tubing & Armband Clearance",
            "file": "37_CoUsage_CPAP_tubing_sensor_clearance.mp4",
            "pacing": "<b>0:00-0:03:</b> CPAP hose pulls on wearable armband during bedtime turning.<br/><b>0:03-0:07:</b> Re-routes air hose overhead behind pillow, giving full arm clearance.<br/><b>0:07-0:10:</b> Turns comfortably on side with no pulling on mask or sensors.",
            "en_vo": "Route your CPAP tubing overhead or behind your pillow so it moves freely without pulling on your wearable monitoring sensors.",
            "fr_vo": "Acheminez le tuyau PPC au-dessus de l'oreiller pour éviter qu'il ne tire sur vos capteurs et votre brassard de suivi.",
            "veo_prompt": (
                "A stylized 3D animated character wearing a fitted CPAP mask and a black shirt with Hexoskin text on it, along with a forearm band with Somno-Art text on it. Friendly non-photorealistic 3D medical animation style.\n"
                "Action: The character turns from their back to their side in bed. The character routes the flexible CPAP air tube overhead behind the pillow so it does not pull or catch on their wearable forearm monitor. The character sleeps peacefully with full freedom of movement for both arms.\n"
                "Setting: Comfortable bed with plush pillows and soft warm night lighting.\n"
                "Audio and Voiceover: Calm female off-screen voiceover: 'Route your CPAP tubing overhead or behind your pillow so it moves freely without pulling on your wearable monitoring sensors.'"
            )
        }
    ]

    for idx, item in enumerate(videos_data):
        card_content = []
        card_content.append(Paragraph(f"<b>Video {item['id']}: {item['title']}</b>", h2_style))
        card_content.append(Paragraph(f"<b>Target Filename:</b> <code>{item['file']}</code>", card_text_style))
        card_content.append(Paragraph(f"<b>Pacing Breakdown (10.0s):</b> {item['pacing']}", card_text_style))
        card_content.append(Paragraph(f"<b>Voiceover (EN):</b> \"{item['en_vo']}\"", card_text_style))
        card_content.append(Paragraph(f"<b>Voiceover (FR):</b> \"{item['fr_vo']}\"", card_text_style))
        
        prompt_lines = item['veo_prompt'].replace(chr(10), '<br/>')
        prompt_table_data = [[
            Paragraph(f"<b>Google Veo 3.1 Prompt:</b><br/>{prompt_lines}", prompt_code_style)
        ]]
        t_prompt = Table(prompt_table_data, colWidths=[496])
        t_prompt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
            ('BORDER', (0,0), (-1,-1), 0.5, colors.HexColor("#94a3b8")),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        card_content.append(t_prompt)

        # Wrap in a card table
        card_wrapper_data = [[card_content]]
        t_card = Table(card_wrapper_data, colWidths=[504])
        t_card.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.white),
            ('BORDER', (0,0), (-1,-1), 0.75, colors.HexColor("#cbd5e1")),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))

        story.append(t_card)
        story.append(Spacer(1, 8))

        # Add page break after every 2 cards (except the last one)
        if idx % 2 == 1 and idx < len(videos_data) - 1:
            story.append(PageBreak())

    # Build PDF with clean running canvas
    doc.build(story, canvasmaker=CleanNumberedCanvas)
    print(f"Clean PDF generated at: {PDF_PATH}")


if __name__ == "__main__":
    build_pdf()
