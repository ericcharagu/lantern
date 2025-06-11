import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib import colors
from datetime import datetime, date
import os

class ModernPDFGenerator:
    def __init__(self):
        # Modern color palette
        self.primary_color = HexColor('#2563eb')  # Blue
        self.secondary_color = HexColor('#64748b')  # Slate gray
        self.accent_color = HexColor('#10b981')  # Emerald
        self.warning_color = HexColor('#f59e0b')  # Amber
        self.danger_color = HexColor('#ef4444')  # Red
        self.background_color = HexColor('#f8fafc')  # Light gray
        self.text_color = HexColor('#1e293b')  # Dark slate
        
        # Create custom styles
        self.styles = self._create_styles()
    
    def _create_styles(self):
        """Create modern, professional styles"""
        styles = getSampleStyleSheet()
        
        # Custom styles
        styles.add(ParagraphStyle(
            name='ModernTitle',
            parent=styles['Title'],
            fontSize=28,
            textColor=self.primary_color,
            spaceAfter=30,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))
        
        styles.add(ParagraphStyle(
            name='ModernSubtitle',
            parent=styles['Normal'],
            fontSize=16,
            textColor=self.secondary_color,
            spaceAfter=20,
            fontName='Helvetica',
            alignment=TA_LEFT
        ))
        
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=self.primary_color,
            spaceBefore=25,
            spaceAfter=15,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderColor=self.primary_color,
            borderPadding=5
        ))
        
        styles.add(ParagraphStyle(
            name='SubSectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=self.text_color,
            spaceBefore=15,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        ))
        
        styles.add(ParagraphStyle(
            name='ModernBody',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.text_color,
            spaceAfter=8,
            fontName='Helvetica',
            alignment=TA_JUSTIFY,
            leading=14
        ))
        
        styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.text_color,
            spaceAfter=6,
            fontName='Helvetica',
            leftIndent=20,
            bulletIndent=10,
            leading=14
        ))
        
        styles.add(ParagraphStyle(
            name='MetricValue',
            parent=styles['Normal'],
            fontSize=24,
            textColor=self.primary_color,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=styles['Normal'],
            fontSize=10,
            textColor=self.secondary_color,
            fontName='Helvetica',
            alignment=TA_CENTER,
            spaceAfter=15
        ))
        
        return styles
    
    def _create_header_footer(self, canvas, doc):
        """Create modern header and footer"""
        canvas.saveState()
        
        # Header
        canvas.setFillColor(self.primary_color)
        canvas.rect(0, doc.pagesize[1] - 50, doc.pagesize[0], 50, fill=1)
        
        canvas.setFillColor(white)
        canvas.setFont('Helvetica-Bold', 16)
        canvas.drawString(40, doc.pagesize[1] - 32, "Building Analytics Report")
        
        # Add date to header
        canvas.setFont('Helvetica', 10)
        date_str = datetime.now().strftime("%B %d, %Y")
        canvas.drawRightString(doc.pagesize[0] - 40, doc.pagesize[1] - 32, date_str)
        
        # Footer
        canvas.setFillColor(self.secondary_color)
        canvas.setFont('Helvetica', 9)
        canvas.drawCentredString(doc.pagesize[0]/2, 30, f"Page {doc.page}")
        
        canvas.restoreState()
    
    def _create_metrics_table(self, data):
        """Create a modern metrics dashboard"""
        executive_summary = data.get('executive_summary', {})
        raw_stats = data.get('raw_statistics', {})
        
        metrics_data = [
            ['Total Traffic', str(raw_stats.get('total_traffic', 0))],
            ['Average Traffic', str(raw_stats.get('average_traffic', 0))],
            ['Max Traffic', str(raw_stats.get('max_traffic', 0))],
            ['Building Capacity', str(executive_summary.get('building_info', {}).get('capacity', 'N/A'))],
            ['Data Points', str(executive_summary.get('data_points_analyzed', 0))],
            ['Analysis Period', executive_summary.get('analysis_period', 'N/A').title()]
        ]
        
        table = Table(metrics_data, colWidths=[2.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.background_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.text_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, self.secondary_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        return table
    
    def _create_insights_section(self, insights):
        """Create formatted insights section"""
        elements = []
        
        for insight in insights:
            # Remove emoji and format text
            clean_insight = insight.replace('🏢', '').replace('💡', '').strip()
            elements.append(Paragraph(f"• {clean_insight}", self.styles['BulletPoint']))
        
        return elements
    
    def _create_recommendations_section(self, recommendations):
        """Create formatted recommendations section"""
        elements = []
        
        for rec in recommendations:
            # Remove emoji and format text
            clean_rec = rec.replace('💰', '').replace('📊', '').strip()
            elements.append(Paragraph(f"• {clean_rec}", self.styles['BulletPoint']))
        
        return elements
    
    def generate_pdf(self, data, output_filename="building_analytics_report.pdf"):
        """Generate the complete PDF report"""
        doc = SimpleDocTemplate(
            output_filename,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=70,
            bottomMargin=50
        )
        
        story = []
        
        # Title Section
        executive_summary = data.get('executive_summary', {})
        building_info = executive_summary.get('building_info', {})
        
        story.append(Paragraph(
            f"Analytics Report: {building_info.get('building_name', 'Building Analysis')}", 
            self.styles['ModernTitle']
        ))
        
        story.append(Paragraph(
            f"Building ID: {building_info.get('building_id', 'N/A')} | "
            f"Type: {building_info.get('building_type', 'N/A').title()} | "
            f"Period: {executive_summary.get('analysis_period', 'N/A').title()}", 
            self.styles['ModernSubtitle']
        ))
        
        story.append(Spacer(1, 20))
        
        # Executive Summary Section
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        # Key Metrics Table
        story.append(Paragraph("Key Metrics", self.styles['SubSectionHeader']))
        story.append(self._create_metrics_table(data))
        story.append(Spacer(1, 20))
        
        # Key Insights
        story.append(Paragraph("Key Insights", self.styles['SubSectionHeader']))
        insights = data.get('key_insights', [])
        story.extend(self._create_insights_section(insights))
        story.append(Spacer(1, 15))
        
        # Recommendations
        story.append(Paragraph("Recommendations", self.styles['SubSectionHeader']))
        recommendations = data.get('recommendations', [])
        story.extend(self._create_recommendations_section(recommendations))
        story.append(Spacer(1, 20))
        
        # Detailed Analysis Section
        story.append(Paragraph("Detailed Analysis", self.styles['SectionHeader']))
        
        # Building Information
        story.append(Paragraph("Building Information", self.styles['SubSectionHeader']))
        
        building_data = [
            ['Building Name', building_info.get('building_name', 'N/A')],
            ['Building ID', building_info.get('building_id', 'N/A')],
            ['Type', building_info.get('building_type', 'N/A').title()],
            ['Capacity', str(building_info.get('capacity', 'N/A'))],
            ['Total Area (sq ft)', str(building_info.get('total_area_sqft', 'N/A'))],
            ['Floors', str(building_info.get('floors', 'N/A'))],
            ['Operating Hours', str(building_info.get('operating_hours', 'N/A'))]
        ]
        
        building_table = Table(building_data, colWidths=[2*inch, 3*inch])
        building_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.background_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.text_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, self.secondary_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(building_table)
        story.append(Spacer(1, 20))
        
        # Traffic Statistics
        story.append(Paragraph("Traffic Statistics", self.styles['SubSectionHeader']))
        raw_stats = data.get('raw_statistics', {})
        
        stats_data = [
            ['Metric', 'Value'],
            ['Total Traffic', str(raw_stats.get('total_traffic', 0))],
            ['Average Traffic', str(raw_stats.get('average_traffic', 0))],
            ['Maximum Traffic', str(raw_stats.get('max_traffic', 0))],
            ['Data Points Collected', str(raw_stats.get('data_points', 0))]
        ]
        
        stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('BACKGROUND', (0, 1), (0, -1), self.background_color),
            ('TEXTCOLOR', (0, 1), (-1, -1), self.text_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, self.secondary_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 20))
        
        # AI report
        story.append(Paragraph("AI report", self.styles['SectionHeader']))
        story.append(Paragraph(f"• {data.get('detailed_report')}", self.styles['BulletPoint']))
        
        # Build PDF with custom header/footer
        doc.build(story, onFirstPage=self._create_header_footer, onLaterPages=self._create_header_footer)
        
        return output_filename


    
