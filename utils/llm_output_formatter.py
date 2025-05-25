from datetime import date
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import black, blue
from io import BytesIO


# Setting today's date for each report
today = date.today()


def clean_text_remove_think_tags(text):
    """
    Remove <think> tags and their contents from text, then clean formatting.

    Args:
        text (str): Raw text with <think> tags

    Returns:
        str: Cleaned text without <think> content
    """
    # Remove <think> tags and everything between them
    cleaned_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # Clean up extra whitespace and formatting issues
    cleaned_text = re.sub(r"\s+", " ", cleaned_text.strip())

    # Fix common formatting issues
    cleaned_text = clean_formatting_issues(cleaned_text)

    return cleaned_text


def clean_formatting_issues(text):
    """Clean up various formatting issues in the text."""

    # Remove random characters that appear to be formatting artifacts
    text = re.sub(r"^[X\-d;y�Hl]+\s*-\s*", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[X\-d;y�Hl]+\s*", "", text, flags=re.MULTILINE)

    # Clean up bullet points
    text = re.sub(r"\s*-\s*\*\*([^*]+)\*\*:\s*", r"\n\n**\1:**\n", text)
    text = re.sub(r"\s*-\s*([^-\n]+)", r"\n- \1", text)

    # Fix section headers
    text = re.sub(r"\*\*(\d+\.\s*[^*]+)\*\*", r"\n\n**\1**\n", text)

    # Clean up excessive spacing
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)

    # Fix punctuation spacing
    text = re.sub(r"\.([A-Z])", r". \1", text)

    return text.strip()


def format_for_pdf(text):
    """
    Format cleaned text for PDF generation.

    Args:
        text (str): Cleaned text

    Returns:
        list: List of formatted paragraphs for PDF
    """
    # Get styles
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=blue,
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=12,
        textColor=black,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        leftIndent=0,
    )

    bullet_style = ParagraphStyle(
        "CustomBullet",
        parent=styles["Normal"],
        fontSize=11,
        spaceAfter=6,
        leftIndent=20,
        bulletIndent=10,
    )

    # Split text into sections
    sections = text.split("\n\n")
    story = []

    first_section = True
    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Check if it's a title (first section)
        if first_section and (
            "**Comprehensive Report:" in section
            or "**Foot Traffic Analytics Report" in section
        ):
            # Extract title text
            title_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", section)
            title_text = re.sub(r"---.*", "", title_text).strip()
            story.append(Paragraph(title_text, title_style))
            story.append(Spacer(1, 20))
            first_section = False
            continue

        # Check if it's a section header
        if section.startswith("**") and section.endswith("**"):
            header_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", section)
            story.append(Paragraph(header_text, heading_style))
            continue

        # Handle section headers with content
        if "**" in section and section.count("**") >= 2:
            lines = section.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("**") and line.count("**") >= 2:
                    header_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
                    story.append(Paragraph(header_text, heading_style))
                elif line.startswith("-"):
                    bullet_text = line[1:].strip()
                    bullet_text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", bullet_text)
                    story.append(Paragraph(f"• {bullet_text}", bullet_style))
                else:
                    # Regular paragraph
                    para_text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", line)
                    story.append(Paragraph(para_text, body_style))
        else:
            # Regular paragraph
            para_text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", section)
            story.append(Paragraph(para_text, body_style))

    return story


def create_pdf_from_text(text, filename=f"./utils/reports/{today}_report.pdf"):
    """
    Create a PDF from the cleaned and formatted text.

    Args:
        text (str): Input text with <think> tags
        filename (str): Output PDF filename

    Returns:
        str: Path to created PDF file
    """
    # Clean the text
    cleaned_text = clean_text_remove_think_tags(text)

    # Create PDF document
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )

    # Format content for PDF
    story = format_for_pdf(cleaned_text)

    # Build PDF
    doc.build(story)

    return filename


def get_cleaned_text_only(text):
    """
    Just return the cleaned text without PDF generation.

    Args:
        text (str): Input text with <think> tags

    Returns:
        str: Cleaned and formatted text
    """
    cleaned = clean_text_remove_think_tags(text)

    # Additional formatting for readability
    lines = cleaned.split("\n")
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append("")
            continue

        # Handle section dividers
        if line == "---":
            formatted_lines.append("\n" + "=" * 60 + "\n")
            continue

        # Handle headers
        if line.startswith("**") and line.endswith("**"):
            formatted_lines.append("\n" + line + "\n")
            continue

        # Handle bullet points
        if line.startswith("-"):
            formatted_lines.append("  " + line)
            continue

        formatted_lines.append(line)

    return "\n".join(formatted_lines)


"""
# Example usage
    # Get cleaned text only
    cleaned = get_cleaned_text_only(sample_text_with_think)
    print("Cleaned text:")
    print(cleaned)
    
    # Create PDF (uncomment to use)
    # pdf_file = create_pdf_from_text(sample_text_with_think)
    # print(f"PDF created: {pdf_file}")"""
