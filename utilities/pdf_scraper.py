from PyPDF2 import PdfReader

def get_pdf_text(pdf_docs):
    text = "### Datasheet ### \n"
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def get_pdf_info(pdf_files):
    pdf_text = ""
    for pdf_file in pdf_files:
        with open(pdf_file, 'rb') as file:
            # Per   form processing on each PDF file
            pdf_text += get_pdf_text([file])

    return pdf_text 