from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from datetime import datetime
import re


def format_dynamic_text_to_pdf(raw_text, styles):
    """
    Convert dynamic text with markdown-like formatting to PDF elements.

    Args:
        raw_text (str): Raw text with \n for newlines, ### for titles, ** for bold, etc.
        styles (dict): ReportLab styles dictionary

    Returns:
        list: List of formatted PDF elements (Paragraphs, Spacers)
    """

    def clean_text(text):
        """Clean and normalize text"""
        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)
        # Strip leading/trailing whitespace
        return text.strip()

    def detect_list_item(line):
        """Detect if line is a list item and return cleaned text"""
        # Check for bullet points: •, -, *, numbers
        bullet_patterns = [
            r"^[•\-\*]\s+(.+)",  # • - * bullets
            r"^\d+\.\s+(.+)",  # numbered lists
            r"^[a-zA-Z]\.\s+(.+)",  # lettered lists
        ]

        for pattern in bullet_patterns:
            match = re.match(pattern, line.strip())
            if match:
                return match.group(1)
        return None

    def process_inline_formatting(text):
        """Process inline formatting like **bold**, *italic*, etc."""
        # Bold text **text**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

        # Italic text *text*
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

        # Underline text _text_
        text = re.sub(r"_(.+?)_", r"<u>\1</u>", text)

        # Code/monospace text `code`
        text = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', text)

        return text

    def get_header_level(line):
        """Determine header level based on ### markers"""
        if line.startswith("####"):
            return 4, line[4:].strip()
        elif line.startswith("###"):
            return 3, line[3:].strip()
        elif line.startswith("##"):
            return 2, line[2:].strip()
        elif line.startswith("#"):
            return 1, line[1:].strip()
        return 0, line

    # Split text into lines and process
    lines = raw_text.split("\n")
    elements = []

    for line in lines:
        line = line.strip()

        # Skip empty lines but add spacer
        if not line:
            elements.append(Spacer(1, 6))
            continue

        # Check for headers
        header_level, header_text = get_header_level(line)
        if header_level > 0:
            header_text = process_inline_formatting(clean_text(header_text))

            # Add spacing before headers (except first element)
            if elements:
                elements.append(Spacer(1, 15))

            # Choose appropriate style based on header level
            if header_level == 1:
                style = styles.get(
                    "SectionHeader", styles.get("Heading1", styles["Normal"])
                )
            elif header_level == 2:
                style = styles.get(
                    "SubSectionHeader", styles.get("Heading2", styles["Normal"])
                )
            elif header_level == 3:
                style = styles.get("Heading3", styles.get("Heading2", styles["Normal"]))
            else:  # level 4+
                style = styles.get("Heading4", styles.get("Normal"))

            elements.append(Paragraph(header_text, style))
            continue

        # Check for list items
        list_content = detect_list_item(line)
        if list_content:
            list_content = process_inline_formatting(clean_text(list_content))
            bullet_style = styles.get("BulletPoint", styles["Normal"])
            elements.append(Paragraph(f"• {list_content}", bullet_style))
            continue

        # Regular paragraph
        processed_text = process_inline_formatting(clean_text(line))
        if processed_text:  # Only add non-empty paragraphs
            body_style = styles.get("ModernBody", styles["Normal"])
            elements.append(Paragraph(processed_text, body_style))

    return elements


class ModernPDFGenerator:
    def __init__(self):
        # Modern color palette
        self.primary_color = HexColor("#2563eb")  # Blue
        self.secondary_color = HexColor("#64748b")  # Slate gray
        self.accent_color = HexColor("#10b981")  # Emerald
        self.warning_color = HexColor("#f59e0b")  # Amber
        self.danger_color = HexColor("#ef4444")  # Red
        self.background_color = HexColor("#f8fafc")  # Light gray
        self.text_color = HexColor("#1e293b")  # Dark slate

        # Create custom styles
        self.styles = self._create_styles()

    def _create_styles(self):
        """Create modern, professional styles"""
        styles = getSampleStyleSheet()

        # Custom styles
        styles.add(
            ParagraphStyle(
                name="ModernTitle",
                parent=styles["Title"],
                fontSize=28,
                textColor=self.primary_color,
                spaceAfter=30,
                alignment=TA_LEFT,
                fontName="Helvetica-Bold",
            )
        )

        styles.add(
            ParagraphStyle(
                name="ModernSubtitle",
                parent=styles["Normal"],
                fontSize=16,
                textColor=self.secondary_color,
                spaceAfter=20,
                fontName="Helvetica",
                alignment=TA_LEFT,
            )
        )

        styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=styles["Heading1"],
                fontSize=18,
                textColor=self.primary_color,
                spaceBefore=25,
                spaceAfter=15,
                fontName="Helvetica-Bold",
                borderWidth=0,
                borderColor=self.primary_color,
                borderPadding=5,
            )
        )

        styles.add(
            ParagraphStyle(
                name="SubSectionHeader",
                parent=styles["Heading2"],
                fontSize=14,
                textColor=self.text_color,
                spaceBefore=15,
                spaceAfter=10,
                fontName="Helvetica-Bold",
            )
        )

        styles.add(
            ParagraphStyle(
                name="ModernBody",
                parent=styles["Normal"],
                fontSize=11,
                textColor=self.text_color,
                spaceAfter=8,
                fontName="Helvetica",
                alignment=TA_JUSTIFY,
                leading=14,
            )
        )

        styles.add(
            ParagraphStyle(
                name="BulletPoint",
                parent=styles["Normal"],
                fontSize=11,
                textColor=self.text_color,
                spaceAfter=6,
                fontName="Helvetica",
                leftIndent=20,
                bulletIndent=10,
                leading=14,
            )
        )

        styles.add(
            ParagraphStyle(
                name="MetricValue",
                parent=styles["Normal"],
                fontSize=24,
                textColor=self.primary_color,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            )
        )

        styles.add(
            ParagraphStyle(
                name="MetricLabel",
                parent=styles["Normal"],
                fontSize=10,
                textColor=self.secondary_color,
                fontName="Helvetica",
                alignment=TA_CENTER,
                spaceAfter=15,
            )
        )

        return styles

    def _create_header_footer(self, canvas, doc):
        """Create modern header and footer"""
        canvas.saveState()

        # Header
        canvas.setFillColor(self.primary_color)
        canvas.rect(0, doc.pagesize[1] - 50, doc.pagesize[0], 50, fill=1)

        canvas.setFillColor(white)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(40, doc.pagesize[1] - 32, "Building Analytics Report")

        # Add date to header
        canvas.setFont("Helvetica", 10)
        date_str = datetime.now().strftime("%B %d, %Y")
        canvas.drawRightString(doc.pagesize[0] - 40, doc.pagesize[1] - 32, date_str)

        # Footer
        canvas.setFillColor(self.secondary_color)
        canvas.setFont("Helvetica", 9)
        canvas.drawCentredString(doc.pagesize[0] / 2, 30, f"Page {doc.page}")

        canvas.restoreState()

    def _create_metrics_table(self, data):
        """Create a modern metrics dashboard"""
        executive_summary = data.get("executive_summary", {})
        raw_stats = data.get("raw_statistics", {})

        metrics_data = [
            ["Total Traffic", str(raw_stats.get("total_traffic", 0))],
            ["Average Traffic", str(raw_stats.get("average_traffic", 0))],
            ["Max Traffic", str(raw_stats.get("max_traffic", 0))],
            [
                "Building Capacity",
                str(executive_summary.get("building_info", {}).get("capacity", "N/A")),
            ],
            ["Data Points", str(executive_summary.get("data_points_analyzed", 0))],
            [
                "Analysis Period",
                executive_summary.get("analysis_period", "N/A").title(),
            ],
        ]

        table = Table(metrics_data, colWidths=[2.5 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.background_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), self.text_color),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, self.secondary_color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        return table

    def _create_insights_section(self, insights):
        """Create formatted insights section"""
        elements = []

        for insight in insights:
            # Remove emoji and format text
            clean_insight = insight.replace("🏢", "").replace("💡", "").strip()
            elements.append(Paragraph(f"• {clean_insight}", self.styles["BulletPoint"]))

        return elements

    def _create_recommendations_section(self, recommendations):
        """Create formatted recommendations section"""
        elements = []

        for rec in recommendations:
            # Remove emoji and format text
            clean_rec = rec.replace("💰", "").replace("📊", "").strip()
            elements.append(Paragraph(f"• {clean_rec}", self.styles["BulletPoint"]))

        return elements

    def format_text_with_structure(self, raw_text):
        """
        Enhanced formatter that handles structured content with better spacing and organization.

        Args:
            raw_text (str): Raw text with formatting markers
            styles (dict): ReportLab styles dictionary

        Returns:
            list: List of formatted PDF elements
        """

        # Pre-process text to handle special cases
        def preprocess_text(text):
            # Handle numbered sections like "1. **Title**:"
            text = re.sub(
                r"^(\d+)\.\s*\*\*(.+?)\*\*:?\s*$", r"### \2", text, flags=re.MULTILINE
            )

            # Handle lettered sections like "A. **Title**:"
            text = re.sub(
                r"^([A-Z])\.\s*\*\*(.+?)\*\*:?\s*$",
                r"#### \2",
                text,
                flags=re.MULTILINE,
            )

            # Handle standalone bold text as subheaders
            text = re.sub(r"^\*\*(.+?)\*\*:\s*$", r"#### \1", text, flags=re.MULTILINE)

            return text

        # Preprocess the text
        processed_text = preprocess_text(raw_text)

        # Use the main formatter
        elements = format_dynamic_text_to_pdf(processed_text, self.styles)

        # Post-process to add better spacing around sections
        final_elements = []
        for i, element in enumerate(elements):
            # Add extra spacing before major sections
            if (
                hasattr(element, "style")
                and hasattr(element.style, "name")
                and element.style.name in ["SectionHeader", "SubSectionHeader"]
            ):
                if final_elements:  # Don't add space before first element
                    final_elements.append(Spacer(1, 10))

            final_elements.append(element)

            # Add spacing after headers
            if (
                hasattr(element, "style")
                and hasattr(element.style, "name")
                and element.style.name == "ModernBody"
            ):
                final_elements.append(Spacer(1, 5))

        return final_elements

    def generate_pdf(self, data, output_filename="building_analytics_report.pdf"):
        """Generate the complete PDF report"""
        doc = SimpleDocTemplate(
            output_filename,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=70,
            bottomMargin=50,
        )

        story = []

        # Title Section
        executive_summary = data.get("executive_summary", {})
        building_info = executive_summary.get("building_info", {})

        story.append(
            Paragraph(
                f"Analytics Report: {building_info.get('building_name', 'Building Analysis')}",
                self.styles["ModernTitle"],
            )
        )

        story.append(
            Paragraph(
                f"Building ID: {building_info.get('building_id', 'N/A')} | "
                f"Type: {building_info.get('building_type', 'N/A').title()} | "
                f"Period: {executive_summary.get('analysis_period', 'N/A').title()}",
                self.styles["ModernSubtitle"],
            )
        )

        story.append(Spacer(1, 20))

        # Executive Summary Section
        story.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))

        # Key Metrics Table
        story.append(Paragraph("Key Metrics", self.styles["SubSectionHeader"]))
        story.append(self._create_metrics_table(data))
        story.append(Spacer(1, 20))

        # Key Insights
        story.append(Paragraph("Key Insights", self.styles["SubSectionHeader"]))
        insights = data.get("key_insights", [])
        story.extend(self._create_insights_section(insights))
        story.append(Spacer(1, 15))

        # Recommendations
        story.append(Paragraph("Recommendations", self.styles["SubSectionHeader"]))
        recommendations = data.get("recommendations", [])
        story.extend(self._create_recommendations_section(recommendations))
        story.append(Spacer(1, 20))

        # Detailed Analysis Section
        story.append(Paragraph("Detailed Analysis", self.styles["SectionHeader"]))

        # Building Information
        story.append(Paragraph("Building Information", self.styles["SubSectionHeader"]))

        building_data = [
            ["Building Name", building_info.get("building_name", "N/A")],
            ["Building ID", building_info.get("building_id", "N/A")],
            ["Type", building_info.get("building_type", "N/A").title()],
            ["Capacity", str(building_info.get("capacity", "N/A"))],
            ["Total Area (sq ft)", str(building_info.get("total_area_sqft", "N/A"))],
            ["Floors", str(building_info.get("floors", "N/A"))],
            ["Operating Hours", str(building_info.get("operating_hours", "N/A"))],
        ]

        building_table = Table(building_data, colWidths=[2 * inch, 3 * inch])
        building_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), self.background_color),
                    ("TEXTCOLOR", (0, 0), (-1, -1), self.text_color),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 1, self.secondary_color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        story.append(building_table)
        story.append(Spacer(1, 20))

        # Traffic Statistics
        story.append(Paragraph("Traffic Statistics", self.styles["SubSectionHeader"]))
        raw_stats = data.get("raw_statistics", {})

        stats_data = [
            ["Metric", "Value"],
            ["Total Traffic", str(raw_stats.get("total_traffic", 0))],
            ["Average Traffic", str(raw_stats.get("average_traffic", 0))],
            ["Maximum Traffic", str(raw_stats.get("max_traffic", 0))],
            ["Data Points Collected", str(raw_stats.get("data_points", 0))],
        ]

        stats_table = Table(stats_data, colWidths=[2.5 * inch, 2 * inch])
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.primary_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("BACKGROUND", (0, 1), (0, -1), self.background_color),
                    ("TEXTCOLOR", (0, 1), (-1, -1), self.text_color),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, self.secondary_color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        story.append(stats_table)
        story.append(Spacer(1, 20))

        # AI report
        story.append(Paragraph("AI report", self.styles["SectionHeader"]))
        formated_llm_output = self.format_text_with_structure(
            data.get("detailed_report")
        )
        story.append(
            Paragraph(
                f"{formated_llm_output}",
                self.styles["BulletPoint"],
            )
        )

        # Build PDF with custom header/footer
        doc.build(
            story,
            onFirstPage=self._create_header_footer,
            onLaterPages=self._create_header_footer,
        )

        return output_filename
